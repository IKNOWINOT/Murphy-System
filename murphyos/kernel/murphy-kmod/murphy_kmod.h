/* SPDX-License-Identifier: GPL-2.0-only OR BSD-2-Clause */
/*
 * murphy_kmod.h — Shared header for the Murphy kernel module
 *
 * Character devices, sysfs gates, ioctl definitions, and shared structures
 * for the MurphyOS kernel integration layer.
 *
 * Copyright © 2020 Inoni Limited Liability Company
 * Creator: Corey Post
 *
 * This kernel module is dual-licensed under GPL-2.0-only and BSD-2-Clause
 * for Linux kernel compatibility.  The broader Murphy System project is
 * released under BSL 1.1 — see the repository root LICENSE for details.
 */

#ifndef _MURPHY_KMOD_H
#define _MURPHY_KMOD_H

#include <linux/ioctl.h>
#include <linux/types.h>

/* ------------------------------------------------------------------ */
/*  Version                                                           */
/* ------------------------------------------------------------------ */
#define MURPHY_KMOD_VERSION        "1.0.0"
#define MURPHY_KMOD_VERSION_MAJOR  1
#define MURPHY_KMOD_VERSION_MINOR  0
#define MURPHY_KMOD_VERSION_PATCH  0

/* ------------------------------------------------------------------ */
/*  Device names                                                      */
/* ------------------------------------------------------------------ */
#define MURPHY_EVENT_DEV_NAME      "murphy-event"
#define MURPHY_CONFIDENCE_DEV_NAME "murphy-confidence"
#define MURPHY_CLASS_NAME          "murphy"

/* ------------------------------------------------------------------ */
/*  Ring-buffer sizing                                                */
/* ------------------------------------------------------------------ */
#define MURPHY_EVENT_BUF_SIZE      (64 * 1024)   /* 64 KiB ring       */
#define MURPHY_EVENT_MAX_WRITE     4096           /* max single write  */

/* ------------------------------------------------------------------ */
/*  Governance gates                                                  */
/* ------------------------------------------------------------------ */
#define MURPHY_NUM_GATES           6

enum murphy_gate_id {
	MURPHY_GATE_EXECUTIVE  = 0,
	MURPHY_GATE_OPERATIONS = 1,
	MURPHY_GATE_QA         = 2,
	MURPHY_GATE_HITL       = 3,
	MURPHY_GATE_COMPLIANCE = 4,
	MURPHY_GATE_BUDGET     = 5,
};

enum murphy_gate_state {
	MURPHY_GATE_OPEN    = 0,
	MURPHY_GATE_BLOCKED = 1,
	MURPHY_GATE_PENDING = 2,
};

struct murphy_gate_info {
	__u32 gate_id;                 /* enum murphy_gate_id              */
	__u32 state;                   /* enum murphy_gate_state           */
};

/* ------------------------------------------------------------------ */
/*  Confidence score (MFGC — G/D/H formula)                          */
/* ------------------------------------------------------------------ */
/*  Confidence is stored as an integer in [0, 10000] representing     */
/*  the range 0.0000 – 1.0000 (four-decimal fixed-point).            */
/* ------------------------------------------------------------------ */
#define MURPHY_CONFIDENCE_SCALE    10000

struct murphy_confidence_info {
	__u32 score;                   /* 0 … MURPHY_CONFIDENCE_SCALE     */
};

/* ------------------------------------------------------------------ */
/*  Netfilter — managed port/mark definitions                        */
/* ------------------------------------------------------------------ */
#define MURPHY_MAX_MANAGED_PORTS   32
#define MURPHY_NF_MARK_BASE        0x4D555200  /* "MUR\0" prefix      */
#define MURPHY_NF_MARK_PRIORITY    (MURPHY_NF_MARK_BASE | 0x01)
#define MURPHY_NF_MARK_NORMAL      (MURPHY_NF_MARK_BASE | 0x02)

struct murphy_managed_port {
	__u16 port;
	__u16 flags;                   /* reserved — set to 0             */
};

struct murphy_managed_ports {
	__u32 count;                   /* number of entries (≤ max)       */
	struct murphy_managed_port ports[MURPHY_MAX_MANAGED_PORTS];
};

/* ------------------------------------------------------------------ */
/*  ioctl interface                                                   */
/* ------------------------------------------------------------------ */
#define MURPHY_IOC_MAGIC           'M'

/* Set / get the live confidence score */
#define MURPHY_IOC_SET_CONFIDENCE  _IOW(MURPHY_IOC_MAGIC, 1, \
					struct murphy_confidence_info)
#define MURPHY_IOC_GET_CONFIDENCE  _IOR(MURPHY_IOC_MAGIC, 2, \
					struct murphy_confidence_info)

/* Set / get a single governance gate */
#define MURPHY_IOC_SET_GATE        _IOW(MURPHY_IOC_MAGIC, 3, \
					struct murphy_gate_info)
#define MURPHY_IOC_GET_GATE        _IOR(MURPHY_IOC_MAGIC, 4, \
					struct murphy_gate_info)

/* Configure managed ports for the netfilter hook */
#define MURPHY_IOC_SET_PORTS       _IOW(MURPHY_IOC_MAGIC, 5, \
					struct murphy_managed_ports)
#define MURPHY_IOC_GET_PORTS       _IOR(MURPHY_IOC_MAGIC, 6, \
					struct murphy_managed_ports)

/* ------------------------------------------------------------------ */
/*  Declarations shared between compilation units                     */
/* ------------------------------------------------------------------ */
#ifdef __KERNEL__

#include <linux/mutex.h>
#include <linux/spinlock.h>
#include <linux/kobject.h>

/* Global confidence score — updated via ioctl, read via chardev */
extern atomic_t murphy_confidence_score;

/* Gate states — protected by murphy_gate_lock */
extern enum murphy_gate_state murphy_gates[MURPHY_NUM_GATES];
extern struct mutex murphy_gate_lock;

/* Managed ports — protected by murphy_port_lock */
extern struct murphy_managed_ports murphy_managed_ports;
extern spinlock_t murphy_port_lock;

/* Netfilter registration helpers (murphy_netfilter.c) */
int  murphy_nf_init(void);
void murphy_nf_exit(void);

#endif /* __KERNEL__ */

#endif /* _MURPHY_KMOD_H */
