# SPDX-License-Identifier: LicenseRef-BSL-1.1
#
# Makefile — MurphyOS PQC kernel module (HMAC-SHA3-256 event authentication)
#
# © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
#
# Usage:
#   make                 — build against running kernel
#   make KDIR=/path/to   — build against a specific kernel source tree
#   make clean           — remove build artifacts

obj-m := murphy_pqc_kmod.o

KDIR  ?= /lib/modules/$(shell uname -r)/build
PWD   := $(shell pwd)

all:
	$(MAKE) -C $(KDIR) M=$(PWD) modules

clean:
	$(MAKE) -C $(KDIR) M=$(PWD) clean

install:
	$(MAKE) -C $(KDIR) M=$(PWD) modules_install
	depmod -a

.PHONY: all clean install
