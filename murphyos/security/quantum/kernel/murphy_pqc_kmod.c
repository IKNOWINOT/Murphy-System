// SPDX-License-Identifier: LicenseRef-BSL-1.1
/*
 * murphy_pqc_kmod.c — Post-Quantum event authentication kernel module
 *
 * © 2020 Inoni Limited Liability Company
 * Creator: Corey Post
 * License: Business Source License 1.1 (BSL 1.1)
 *
 * This module protects /dev/murphy-event with HMAC-SHA3-256 message
 * authentication.  Every event written through the character device is
 * expected to carry a 32-byte HMAC tag as its final bytes.  Events with
 * a missing or invalid tag are rejected with -EACCES.
 *
 * A companion userspace daemon (murphy-pqc-keymanager) pushes a new
 * per-session key via the MURPHY_IOC_SET_PQC_KEY ioctl.
 *
 * sysfs entries
 *   /sys/murphy/pqc/algorithm   — active HMAC algorithm name
 *   /sys/murphy/pqc/key_epoch   — current key-rotation epoch
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
#include <linux/kobject.h>
#include <linux/sysfs.h>
#include <linux/string.h>
#include <linux/crypto.h>
#include <crypto/hash.h>

#include "murphy_pqc_kmod.h"

/* ------------------------------------------------------------------ */
/* Module metadata                                                    */
/* ------------------------------------------------------------------ */

#define DEVICE_NAME     "murphy-event"
#define CLASS_NAME      "murphy"
#define PQC_ALGO_NAME   "hmac(sha3-256)"

MODULE_LICENSE("Dual MIT/GPL");
MODULE_AUTHOR("Corey Post — Inoni LLC");
MODULE_DESCRIPTION("MurphyOS PQC event authentication (HMAC-SHA3-256)");
MODULE_VERSION("1.0.0");

/* ------------------------------------------------------------------ */
/* Internal state                                                     */
/* ------------------------------------------------------------------ */

static int              major_number;
static struct class    *murphy_class;
static struct device   *murphy_device;
static struct cdev      murphy_cdev;

static DEFINE_MUTEX(pqc_lock);
static u8               session_key[MURPHY_PQC_KEY_SIZE];
static u32              key_epoch;
static bool             key_loaded;

/* Kernel crypto HMAC handle — allocated once at init. */
static struct crypto_shash *hmac_tfm;

/* sysfs kobject under /sys/murphy/pqc/ */
static struct kobject *murphy_kobj;
static struct kobject *pqc_kobj;

/* ------------------------------------------------------------------ */
/* HMAC helpers                                                       */
/* ------------------------------------------------------------------ */

/**
 * murphy_compute_hmac() — Compute HMAC-SHA3-256 over a buffer.
 * @data:    Input data.
 * @datalen: Length of @data in bytes.
 * @out:     Caller-provided buffer of at least MURPHY_PQC_TAG_SIZE bytes.
 *
 * Returns 0 on success, negative errno on failure.
 */
static int murphy_compute_hmac(const u8 *data, size_t datalen, u8 *out)
{
	struct shash_desc *desc;
	int ret;

	desc = kzalloc(sizeof(*desc) + crypto_shash_descsize(hmac_tfm),
		       GFP_KERNEL);
	if (!desc)
		return -ENOMEM;

	desc->tfm = hmac_tfm;

	mutex_lock(&pqc_lock);
	ret = crypto_shash_setkey(hmac_tfm, session_key,
				  MURPHY_PQC_KEY_SIZE);
	mutex_unlock(&pqc_lock);

	if (ret)
		goto out_free;

	ret = crypto_shash_digest(desc, data, datalen, out);

out_free:
	kfree(desc);
	return ret;
}

/**
 * murphy_verify_hmac() — Verify an HMAC tag in constant time.
 */
static int murphy_verify_hmac(const u8 *data, size_t datalen,
			      const u8 *expected_tag)
{
	u8 computed[MURPHY_PQC_TAG_SIZE];
	int ret;

	ret = murphy_compute_hmac(data, datalen, computed);
	if (ret)
		return ret;

	if (crypto_memneq(computed, expected_tag, MURPHY_PQC_TAG_SIZE))
		return -EACCES;

	return 0;
}

/* ------------------------------------------------------------------ */
/* Character device file operations                                   */
/* ------------------------------------------------------------------ */

static int murphy_open(struct inode *inode, struct file *filp)
{
	return 0;
}

static int murphy_release(struct inode *inode, struct file *filp)
{
	return 0;
}

/**
 * murphy_write() — Accept an event + trailing HMAC tag.
 *
 * The last MURPHY_PQC_TAG_SIZE bytes of the write buffer are the HMAC.
 * If the key has not been loaded yet, or the tag is invalid, the write
 * is rejected.
 */
static ssize_t murphy_write(struct file *filp, const char __user *buf,
			    size_t count, loff_t *off)
{
	u8 *kbuf;
	size_t payload_len;
	int ret;

	if (count <= MURPHY_PQC_TAG_SIZE || count > MURPHY_PQC_MAX_EVENT)
		return -EINVAL;

	mutex_lock(&pqc_lock);
	if (!key_loaded) {
		mutex_unlock(&pqc_lock);
		pr_warn("murphy-event: write rejected — no PQC key loaded\n");
		return -EACCES;
	}
	mutex_unlock(&pqc_lock);

	kbuf = kvmalloc(count, GFP_KERNEL);
	if (!kbuf)
		return -ENOMEM;

	if (copy_from_user(kbuf, buf, count)) {
		ret = -EFAULT;
		goto out_free;
	}

	payload_len = count - MURPHY_PQC_TAG_SIZE;

	ret = murphy_verify_hmac(kbuf, payload_len,
				 kbuf + payload_len);
	if (ret) {
		pr_warn("murphy-event: HMAC verification failed (epoch %u)\n",
			key_epoch);
		ret = -EACCES;
		goto out_free;
	}

	/* Event authenticated — real delivery would happen here. */
	pr_debug("murphy-event: accepted %zu-byte event (epoch %u)\n",
		 payload_len, key_epoch);
	ret = (ssize_t)count;

out_free:
	kvfree(kbuf);
	return ret;
}

/**
 * murphy_ioctl() — Handle PQC key management ioctls.
 */
static long murphy_ioctl(struct file *filp, unsigned int cmd,
			 unsigned long arg)
{
	struct murphy_pqc_key uk;

	switch (cmd) {
	case MURPHY_IOC_SET_PQC_KEY:
		if (copy_from_user(&uk, (void __user *)arg, sizeof(uk)))
			return -EFAULT;

		mutex_lock(&pqc_lock);
		memcpy(session_key, uk.key, MURPHY_PQC_KEY_SIZE);
		key_epoch = uk.epoch;
		key_loaded = true;
		mutex_unlock(&pqc_lock);

		pr_info("murphy-event: PQC key loaded (epoch %u)\n",
			uk.epoch);
		return 0;

	case MURPHY_IOC_GET_PQC_EPOCH:
		mutex_lock(&pqc_lock);
		if (copy_to_user((void __user *)arg, &key_epoch,
				 sizeof(key_epoch))) {
			mutex_unlock(&pqc_lock);
			return -EFAULT;
		}
		mutex_unlock(&pqc_lock);
		return 0;

	default:
		return -ENOTTY;
	}
}

static const struct file_operations murphy_fops = {
	.owner          = THIS_MODULE,
	.open           = murphy_open,
	.release        = murphy_release,
	.write          = murphy_write,
	.unlocked_ioctl = murphy_ioctl,
};

/* ------------------------------------------------------------------ */
/* sysfs: /sys/murphy/pqc/algorithm  and  key_epoch                   */
/* ------------------------------------------------------------------ */

static ssize_t algorithm_show(struct kobject *kobj,
			      struct kobj_attribute *attr, char *buf)
{
	return sysfs_emit(buf, "%s\n", PQC_ALGO_NAME);
}

static ssize_t key_epoch_show(struct kobject *kobj,
			      struct kobj_attribute *attr, char *buf)
{
	u32 e;

	mutex_lock(&pqc_lock);
	e = key_epoch;
	mutex_unlock(&pqc_lock);

	return sysfs_emit(buf, "%u\n", e);
}

static struct kobj_attribute algorithm_attr =
	__ATTR_RO(algorithm);

static struct kobj_attribute key_epoch_attr =
	__ATTR_RO(key_epoch);

static struct attribute *pqc_attrs[] = {
	&algorithm_attr.attr,
	&key_epoch_attr.attr,
	NULL,
};

static const struct attribute_group pqc_attr_group = {
	.attrs = pqc_attrs,
};

/* ------------------------------------------------------------------ */
/* Module init / exit                                                  */
/* ------------------------------------------------------------------ */

static int __init murphy_pqc_init(void)
{
	dev_t dev;
	int ret;

	/* Allocate HMAC transform. */
	hmac_tfm = crypto_alloc_shash(PQC_ALGO_NAME, 0, 0);
	if (IS_ERR(hmac_tfm)) {
		pr_err("murphy-pqc: failed to allocate %s (%ld)\n",
		       PQC_ALGO_NAME, PTR_ERR(hmac_tfm));
		return PTR_ERR(hmac_tfm);
	}

	/* Register character device. */
	ret = alloc_chrdev_region(&dev, 0, 1, DEVICE_NAME);
	if (ret < 0)
		goto err_crypto;
	major_number = MAJOR(dev);

	cdev_init(&murphy_cdev, &murphy_fops);
	ret = cdev_add(&murphy_cdev, dev, 1);
	if (ret < 0)
		goto err_region;

	murphy_class = class_create(CLASS_NAME);
	if (IS_ERR(murphy_class)) {
		ret = PTR_ERR(murphy_class);
		goto err_cdev;
	}

	murphy_device = device_create(murphy_class, NULL, dev, NULL,
				      DEVICE_NAME);
	if (IS_ERR(murphy_device)) {
		ret = PTR_ERR(murphy_device);
		goto err_class;
	}

	/* sysfs: /sys/murphy/pqc/ */
	murphy_kobj = kobject_create_and_add("murphy", NULL);
	if (!murphy_kobj) {
		ret = -ENOMEM;
		goto err_device;
	}

	pqc_kobj = kobject_create_and_add("pqc", murphy_kobj);
	if (!pqc_kobj) {
		ret = -ENOMEM;
		goto err_mkobj;
	}

	ret = sysfs_create_group(pqc_kobj, &pqc_attr_group);
	if (ret)
		goto err_pqc_kobj;

	pr_info("murphy-pqc: module loaded — %s, epoch %u\n",
		PQC_ALGO_NAME, key_epoch);
	return 0;

err_pqc_kobj:
	kobject_put(pqc_kobj);
err_mkobj:
	kobject_put(murphy_kobj);
err_device:
	device_destroy(murphy_class, dev);
err_class:
	class_destroy(murphy_class);
err_cdev:
	cdev_del(&murphy_cdev);
err_region:
	unregister_chrdev_region(dev, 1);
err_crypto:
	crypto_free_shash(hmac_tfm);
	return ret;
}

static void __exit murphy_pqc_exit(void)
{
	dev_t dev = MKDEV(major_number, 0);

	sysfs_remove_group(pqc_kobj, &pqc_attr_group);
	kobject_put(pqc_kobj);
	kobject_put(murphy_kobj);
	device_destroy(murphy_class, dev);
	class_destroy(murphy_class);
	cdev_del(&murphy_cdev);
	unregister_chrdev_region(dev, 1);
	crypto_free_shash(hmac_tfm);

	pr_info("murphy-pqc: module unloaded\n");
}

module_init(murphy_pqc_init);
module_exit(murphy_pqc_exit);
