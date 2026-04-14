/* SPDX-License-Identifier: LicenseRef-BSL-1.1
 *
 * murphy_pqc_kmod.h — Post-Quantum Cryptography ioctl definitions for MurphyOS
 *
 * © 2020 Inoni Limited Liability Company
 * Creator: Corey Post
 * License: Business Source License 1.1 (BSL 1.1)
 *
 * Defines ioctl commands and structures used by the murphy-event PQC
 * kernel module and its companion userspace key-management daemon.
 */

#ifndef _MURPHY_PQC_KMOD_H
#define _MURPHY_PQC_KMOD_H

#include <linux/types.h>
#include <linux/ioctl.h>

/* ------------------------------------------------------------------ */
/* Constants                                                          */
/* ------------------------------------------------------------------ */

/** SHA3-256 session key size in bytes. */
#define MURPHY_PQC_KEY_SIZE   32

/** HMAC-SHA3-256 authentication tag size in bytes. */
#define MURPHY_PQC_TAG_SIZE   32

/** Maximum event payload before the HMAC tag (64 KiB). */
#define MURPHY_PQC_MAX_EVENT  (64 * 1024)

/* ------------------------------------------------------------------ */
/* Structures                                                         */
/* ------------------------------------------------------------------ */

/**
 * struct murphy_pqc_key - Per-session HMAC key pushed from userspace.
 * @key:   Raw key material (MURPHY_PQC_KEY_SIZE bytes).
 * @epoch: Monotonically-increasing key-rotation epoch counter.
 */
struct murphy_pqc_key {
	__u8  key[MURPHY_PQC_KEY_SIZE];
	__u32 epoch;
};

/* ------------------------------------------------------------------ */
/* ioctl interface on /dev/murphy-event                               */
/* ------------------------------------------------------------------ */

/** Magic number for the Murphy PQC ioctl family. */
#define MURPHY_PQC_IOC_MAGIC  'M'

/**
 * MURPHY_IOC_SET_PQC_KEY - Load a new HMAC session key.
 *
 * The userspace key-management daemon calls this after every key
 * rotation.  The kernel module copies the key into its internal state
 * and increments the visible epoch counter.
 *
 * Arg: pointer to struct murphy_pqc_key.
 */
#define MURPHY_IOC_SET_PQC_KEY   _IOW(MURPHY_PQC_IOC_MAGIC, 1, \
                                      struct murphy_pqc_key)

/**
 * MURPHY_IOC_GET_PQC_EPOCH - Retrieve the current key epoch.
 *
 * Arg: pointer to __u32 (filled with the current epoch value).
 */
#define MURPHY_IOC_GET_PQC_EPOCH _IOR(MURPHY_PQC_IOC_MAGIC, 2, __u32)

#endif /* _MURPHY_PQC_KMOD_H */
