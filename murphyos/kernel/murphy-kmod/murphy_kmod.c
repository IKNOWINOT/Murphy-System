// SPDX-License-Identifier: GPL-2.0-only OR BSD-2-Clause
/*
 * murphy_kmod.c — Main kernel module for MurphyOS
 *
 * Provides:
 *   /dev/murphy-event       — character device for event-bus writes
 *   /dev/murphy-confidence  — read-only device for live MFGC score
 *   /sys/murphy/gates/      — sysfs entries for 6 governance gates
 *   netfilter hooks         — Murphy-aware packet classification
 *   ioctl interface         — daemon ↔ kernel control plane
 *
 * Copyright © 2020 Inoni Limited Liability Company
 * Creator: Corey Post
 *
 * Dual-licensed: GPL-2.0-only OR BSD-2-Clause (kernel compatibility).
 * The broader Murphy System project is released under BSL 1.1; see the
 * repository root LICENSE for details.
 */

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/fs.h>
#include <linux/cdev.h>
#include <linux/device.h>
#include <linux/uaccess.h>
#include <linux/slab.h>
#include <linux/mutex.h>
#include <linux/spinlock.h>
#include <linux/kobject.h>
#include <linux/sysfs.h>
#include <linux/atomic.h>
#include <linux/circ_buf.h>
#include <linux/wait.h>
#include <linux/poll.h>

#include "murphy_kmod.h"

/* ================================================================== */
/*  Module parameters                                                 */
/* ================================================================== */
static int event_buf_size = MURPHY_EVENT_BUF_SIZE;
module_param(event_buf_size, int, 0444);
MODULE_PARM_DESC(event_buf_size,
	"Size of the event ring buffer in bytes (default 65536)");

static int default_confidence = 5000;  /* 0.5000 */
module_param(default_confidence, int, 0644);
MODULE_PARM_DESC(default_confidence,
	"Initial MFGC confidence score × 10000 (default 5000 = 0.50)");

/* ================================================================== */
/*  Global shared state                                               */
/* ================================================================== */
atomic_t murphy_confidence_score;
EXPORT_SYMBOL_GPL(murphy_confidence_score);

enum murphy_gate_state murphy_gates[MURPHY_NUM_GATES];
EXPORT_SYMBOL_GPL(murphy_gates);
DEFINE_MUTEX(murphy_gate_lock);
EXPORT_SYMBOL_GPL(murphy_gate_lock);

struct murphy_managed_ports murphy_managed_ports;
EXPORT_SYMBOL_GPL(murphy_managed_ports);
DEFINE_SPINLOCK(murphy_port_lock);
EXPORT_SYMBOL_GPL(murphy_port_lock);

/* ================================================================== */
/*  Event ring buffer                                                 */
/* ================================================================== */
static char              *event_buf;
static int                event_head;   /* producer (write from user)  */
static int                event_tail;   /* consumer (read by daemon)   */
static DEFINE_SPINLOCK(event_lock);
static DECLARE_WAIT_QUEUE_HEAD(event_waitq);

/* ================================================================== */
/*  Character devices                                                 */
/* ================================================================== */
static dev_t             murphy_devt;       /* base dev_t              */
static struct cdev       event_cdev;
static struct cdev       confidence_cdev;
static struct class     *murphy_class;
static struct device    *event_device;
static struct device    *confidence_device;

#define MURPHY_NUM_DEVS  2
#define DEV_EVENT_IDX    0
#define DEV_CONF_IDX     1

/* ------------------------------------------------------------------ */
/*  /dev/murphy-event — write: push event; read: consume ring         */
/* ------------------------------------------------------------------ */
static int event_open(struct inode *inode, struct file *filp)
{
	return 0;
}

static ssize_t event_write(struct file *filp, const char __user *ubuf,
			   size_t count, loff_t *ppos)
{
	unsigned long flags;
	size_t space, i;
	char tmp[MURPHY_EVENT_MAX_WRITE];

	if (count == 0)
		return 0;
	if (count > MURPHY_EVENT_MAX_WRITE)
		count = MURPHY_EVENT_MAX_WRITE;

	if (copy_from_user(tmp, ubuf, count))
		return -EFAULT;

	spin_lock_irqsave(&event_lock, flags);
	space = CIRC_SPACE(event_head, event_tail, event_buf_size);
	if (count > space)
		count = space;

	for (i = 0; i < count; i++) {
		event_buf[event_head] = tmp[i];
		event_head = (event_head + 1) & (event_buf_size - 1);
	}
	spin_unlock_irqrestore(&event_lock, flags);

	wake_up_interruptible(&event_waitq);
	return count;
}

static ssize_t event_read(struct file *filp, char __user *ubuf,
			  size_t count, loff_t *ppos)
{
	unsigned long flags;
	size_t avail, i;
	char tmp[MURPHY_EVENT_MAX_WRITE];

	if (count > MURPHY_EVENT_MAX_WRITE)
		count = MURPHY_EVENT_MAX_WRITE;

	spin_lock_irqsave(&event_lock, flags);
	avail = CIRC_CNT(event_head, event_tail, event_buf_size);
	if (avail == 0) {
		spin_unlock_irqrestore(&event_lock, flags);
		if (filp->f_flags & O_NONBLOCK)
			return -EAGAIN;
		if (wait_event_interruptible(event_waitq,
		    CIRC_CNT(event_head, event_tail, event_buf_size) > 0))
			return -ERESTARTSYS;
		spin_lock_irqsave(&event_lock, flags);
		avail = CIRC_CNT(event_head, event_tail, event_buf_size);
	}

	if (count > avail)
		count = avail;

	for (i = 0; i < count; i++) {
		tmp[i] = event_buf[event_tail];
		event_tail = (event_tail + 1) & (event_buf_size - 1);
	}
	spin_unlock_irqrestore(&event_lock, flags);

	if (copy_to_user(ubuf, tmp, count))
		return -EFAULT;
	return count;
}

static __poll_t event_poll(struct file *filp, struct poll_table_struct *wait)
{
	__poll_t mask = 0;

	poll_wait(filp, &event_waitq, wait);

	if (CIRC_CNT(event_head, event_tail, event_buf_size) > 0)
		mask |= EPOLLIN | EPOLLRDNORM;
	if (CIRC_SPACE(event_head, event_tail, event_buf_size) > 0)
		mask |= EPOLLOUT | EPOLLWRNORM;

	return mask;
}

/* ioctl on the event device controls confidence, gates, and ports */
static long event_ioctl(struct file *filp, unsigned int cmd, unsigned long arg)
{
	struct murphy_confidence_info ci;
	struct murphy_gate_info gi;
	struct murphy_managed_ports mp;
	unsigned long flags;

	switch (cmd) {
	case MURPHY_IOC_SET_CONFIDENCE:
		if (copy_from_user(&ci, (void __user *)arg, sizeof(ci)))
			return -EFAULT;
		if (ci.score > MURPHY_CONFIDENCE_SCALE)
			return -EINVAL;
		atomic_set(&murphy_confidence_score, ci.score);
		return 0;

	case MURPHY_IOC_GET_CONFIDENCE:
		ci.score = atomic_read(&murphy_confidence_score);
		if (copy_to_user((void __user *)arg, &ci, sizeof(ci)))
			return -EFAULT;
		return 0;

	case MURPHY_IOC_SET_GATE:
		if (copy_from_user(&gi, (void __user *)arg, sizeof(gi)))
			return -EFAULT;
		if (gi.gate_id >= MURPHY_NUM_GATES)
			return -EINVAL;
		if (gi.state > MURPHY_GATE_PENDING)
			return -EINVAL;
		mutex_lock(&murphy_gate_lock);
		murphy_gates[gi.gate_id] = gi.state;
		mutex_unlock(&murphy_gate_lock);
		return 0;

	case MURPHY_IOC_GET_GATE:
		if (copy_from_user(&gi, (void __user *)arg, sizeof(gi)))
			return -EFAULT;
		if (gi.gate_id >= MURPHY_NUM_GATES)
			return -EINVAL;
		mutex_lock(&murphy_gate_lock);
		gi.state = murphy_gates[gi.gate_id];
		mutex_unlock(&murphy_gate_lock);
		if (copy_to_user((void __user *)arg, &gi, sizeof(gi)))
			return -EFAULT;
		return 0;

	case MURPHY_IOC_SET_PORTS:
		if (copy_from_user(&mp, (void __user *)arg, sizeof(mp)))
			return -EFAULT;
		if (mp.count > MURPHY_MAX_MANAGED_PORTS)
			return -EINVAL;
		spin_lock_irqsave(&murphy_port_lock, flags);
		memcpy(&murphy_managed_ports, &mp, sizeof(mp));
		spin_unlock_irqrestore(&murphy_port_lock, flags);
		return 0;

	case MURPHY_IOC_GET_PORTS:
		spin_lock_irqsave(&murphy_port_lock, flags);
		memcpy(&mp, &murphy_managed_ports, sizeof(mp));
		spin_unlock_irqrestore(&murphy_port_lock, flags);
		if (copy_to_user((void __user *)arg, &mp, sizeof(mp)))
			return -EFAULT;
		return 0;

	default:
		return -ENOTTY;
	}
}

static const struct file_operations event_fops = {
	.owner          = THIS_MODULE,
	.open           = event_open,
	.read           = event_read,
	.write          = event_write,
	.poll           = event_poll,
	.unlocked_ioctl = event_ioctl,
};

/* ------------------------------------------------------------------ */
/*  /dev/murphy-confidence — read-only confidence score               */
/* ------------------------------------------------------------------ */
static int confidence_open(struct inode *inode, struct file *filp)
{
	if ((filp->f_flags & O_ACCMODE) != O_RDONLY)
		return -EACCES;
	return 0;
}

static ssize_t confidence_read(struct file *filp, char __user *ubuf,
			       size_t count, loff_t *ppos)
{
	int score;
	char tmp[16];
	int len;

	score = atomic_read(&murphy_confidence_score);
	len = scnprintf(tmp, sizeof(tmp), "%d.%04d\n",
			score / MURPHY_CONFIDENCE_SCALE,
			score % MURPHY_CONFIDENCE_SCALE);

	return simple_read_from_buffer(ubuf, count, ppos, tmp, len);
}

static const struct file_operations confidence_fops = {
	.owner = THIS_MODULE,
	.open  = confidence_open,
	.read  = confidence_read,
};

/* ================================================================== */
/*  sysfs — /sys/murphy/gates/{EXECUTIVE,OPERATIONS,…}               */
/* ================================================================== */
static struct kobject *murphy_kobj;
static struct kobject *gates_kobj;

static const char * const gate_names[MURPHY_NUM_GATES] = {
	[MURPHY_GATE_EXECUTIVE]  = "EXECUTIVE",
	[MURPHY_GATE_OPERATIONS] = "OPERATIONS",
	[MURPHY_GATE_QA]         = "QA",
	[MURPHY_GATE_HITL]       = "HITL",
	[MURPHY_GATE_COMPLIANCE] = "COMPLIANCE",
	[MURPHY_GATE_BUDGET]     = "BUDGET",
};

static const char * const state_names[] = {
	[MURPHY_GATE_OPEN]    = "open",
	[MURPHY_GATE_BLOCKED] = "blocked",
	[MURPHY_GATE_PENDING] = "pending",
};

struct murphy_gate_attr {
	struct attribute attr;
	int gate_id;
};

#define GATE_ATTR(_name, _id)						\
	static struct murphy_gate_attr gate_attr_##_name = {		\
		.attr = { .name = #_name, .mode = 0444 },		\
		.gate_id = _id,						\
	}

GATE_ATTR(EXECUTIVE,  MURPHY_GATE_EXECUTIVE);
GATE_ATTR(OPERATIONS, MURPHY_GATE_OPERATIONS);
GATE_ATTR(QA,         MURPHY_GATE_QA);
GATE_ATTR(HITL,       MURPHY_GATE_HITL);
GATE_ATTR(COMPLIANCE, MURPHY_GATE_COMPLIANCE);
GATE_ATTR(BUDGET,     MURPHY_GATE_BUDGET);

static struct attribute *gate_attrs[] = {
	&gate_attr_EXECUTIVE.attr,
	&gate_attr_OPERATIONS.attr,
	&gate_attr_QA.attr,
	&gate_attr_HITL.attr,
	&gate_attr_COMPLIANCE.attr,
	&gate_attr_BUDGET.attr,
	NULL,
};

static ssize_t gate_show(struct kobject *kobj, struct attribute *attr,
			 char *buf)
{
	struct murphy_gate_attr *ga =
		container_of(attr, struct murphy_gate_attr, attr);
	enum murphy_gate_state st;

	mutex_lock(&murphy_gate_lock);
	st = murphy_gates[ga->gate_id];
	mutex_unlock(&murphy_gate_lock);

	return scnprintf(buf, PAGE_SIZE, "%s\n", state_names[st]);
}

static const struct sysfs_ops gate_sysfs_ops = {
	.show = gate_show,
};

static void gate_release(struct kobject *kobj)
{
	/* statically allocated — nothing to free */
}

static const struct kobj_type gate_ktype = {
	.sysfs_ops     = &gate_sysfs_ops,
	.release       = gate_release,
	.default_attrs = gate_attrs,
};

/* ================================================================== */
/*  Module init / exit                                                */
/* ================================================================== */
static int __init murphy_kmod_init(void)
{
	int ret;

	pr_info("murphy: loading v%s\n", MURPHY_KMOD_VERSION);

	/* ---- confidence & gates init -------------------------------- */
	atomic_set(&murphy_confidence_score, default_confidence);
	memset(murphy_gates, MURPHY_GATE_OPEN, sizeof(murphy_gates));
	memset(&murphy_managed_ports, 0, sizeof(murphy_managed_ports));

	/* ---- event ring buffer -------------------------------------- */
	if (!is_power_of_2(event_buf_size)) {
		pr_err("murphy: event_buf_size must be a power of 2\n");
		return -EINVAL;
	}
	event_buf = kzalloc(event_buf_size, GFP_KERNEL);
	if (!event_buf)
		return -ENOMEM;
	event_head = 0;
	event_tail = 0;

	/* ---- character devices -------------------------------------- */
	ret = alloc_chrdev_region(&murphy_devt, 0, MURPHY_NUM_DEVS,
				  "murphy");
	if (ret)
		goto err_free_buf;

	murphy_class = class_create(MURPHY_CLASS_NAME);
	if (IS_ERR(murphy_class)) {
		ret = PTR_ERR(murphy_class);
		goto err_unreg_chrdev;
	}

	/* event device */
	cdev_init(&event_cdev, &event_fops);
	event_cdev.owner = THIS_MODULE;
	ret = cdev_add(&event_cdev, MKDEV(MAJOR(murphy_devt), DEV_EVENT_IDX),
		       1);
	if (ret)
		goto err_class;

	event_device = device_create(murphy_class, NULL,
				     MKDEV(MAJOR(murphy_devt), DEV_EVENT_IDX),
				     NULL, MURPHY_EVENT_DEV_NAME);
	if (IS_ERR(event_device)) {
		ret = PTR_ERR(event_device);
		goto err_event_cdev;
	}

	/* confidence device */
	cdev_init(&confidence_cdev, &confidence_fops);
	confidence_cdev.owner = THIS_MODULE;
	ret = cdev_add(&confidence_cdev,
		       MKDEV(MAJOR(murphy_devt), DEV_CONF_IDX), 1);
	if (ret)
		goto err_event_dev;

	confidence_device = device_create(murphy_class, NULL,
					  MKDEV(MAJOR(murphy_devt),
						DEV_CONF_IDX),
					  NULL, MURPHY_CONFIDENCE_DEV_NAME);
	if (IS_ERR(confidence_device)) {
		ret = PTR_ERR(confidence_device);
		goto err_conf_cdev;
	}

	/* ---- sysfs (/sys/murphy/gates/) ----------------------------- */
	murphy_kobj = kobject_create_and_add("murphy", kernel_kobj->parent);
	if (!murphy_kobj) {
		ret = -ENOMEM;
		goto err_conf_dev;
	}

	gates_kobj = kzalloc(sizeof(*gates_kobj), GFP_KERNEL);
	if (!gates_kobj) {
		ret = -ENOMEM;
		goto err_murphy_kobj;
	}
	ret = kobject_init_and_add(gates_kobj, &gate_ktype, murphy_kobj,
				   "gates");
	if (ret)
		goto err_gates_kobj;

	/* ---- netfilter ---------------------------------------------- */
	ret = murphy_nf_init();
	if (ret)
		goto err_gates_kobj;

	pr_info("murphy: module loaded — event ring %d bytes, confidence %d.%04d\n",
		event_buf_size,
		default_confidence / MURPHY_CONFIDENCE_SCALE,
		default_confidence % MURPHY_CONFIDENCE_SCALE);
	return 0;

err_gates_kobj:
	kobject_put(gates_kobj);
err_murphy_kobj:
	kobject_put(murphy_kobj);
err_conf_dev:
	device_destroy(murphy_class,
		       MKDEV(MAJOR(murphy_devt), DEV_CONF_IDX));
err_conf_cdev:
	cdev_del(&confidence_cdev);
err_event_dev:
	device_destroy(murphy_class,
		       MKDEV(MAJOR(murphy_devt), DEV_EVENT_IDX));
err_event_cdev:
	cdev_del(&event_cdev);
err_class:
	class_destroy(murphy_class);
err_unreg_chrdev:
	unregister_chrdev_region(murphy_devt, MURPHY_NUM_DEVS);
err_free_buf:
	kfree(event_buf);
	return ret;
}

static void __exit murphy_kmod_exit(void)
{
	murphy_nf_exit();

	kobject_put(gates_kobj);
	kobject_put(murphy_kobj);

	device_destroy(murphy_class,
		       MKDEV(MAJOR(murphy_devt), DEV_CONF_IDX));
	cdev_del(&confidence_cdev);

	device_destroy(murphy_class,
		       MKDEV(MAJOR(murphy_devt), DEV_EVENT_IDX));
	cdev_del(&event_cdev);

	class_destroy(murphy_class);
	unregister_chrdev_region(murphy_devt, MURPHY_NUM_DEVS);

	kfree(event_buf);

	pr_info("murphy: module unloaded\n");
}

module_init(murphy_kmod_init);
module_exit(murphy_kmod_exit);

MODULE_LICENSE("Dual BSD/GPL");
MODULE_AUTHOR("Corey Post <corey@inoni.llc>");
MODULE_DESCRIPTION("MurphyOS kernel module — event bus, confidence device, governance gates, netfilter hooks");
MODULE_VERSION(MURPHY_KMOD_VERSION);
