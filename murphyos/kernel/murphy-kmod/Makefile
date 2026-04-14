# SPDX-License-Identifier: GPL-2.0-only OR BSD-2-Clause
#
# Makefile — Murphy kernel module (murphy_kmod)
#
# Build against the running kernel:
#   make
#
# Build against a specific kernel source tree:
#   make KDIR=/path/to/kernel/source
#
# Install:
#   sudo make install
#
# Clean:
#   make clean

MODULE_NAME := murphy_kmod

ifneq ($(KERNELRELEASE),)
# ---- Called from the kernel build system ----
obj-m                  := $(MODULE_NAME).o
$(MODULE_NAME)-objs    := murphy_kmod.o murphy_netfilter.o
ccflags-y              += -I$(src)

else
# ---- Called directly from the command line ----
KDIR   ?= /lib/modules/$(shell uname -r)/build
PWD    := $(shell pwd)

.PHONY: all modules install clean help

all: modules

modules:
	$(MAKE) -C $(KDIR) M=$(PWD) modules

install:
	$(MAKE) -C $(KDIR) M=$(PWD) modules_install
	depmod -a

clean:
	$(MAKE) -C $(KDIR) M=$(PWD) clean

help:
	@echo "Murphy kernel module build targets:"
	@echo "  make            - Build the module"
	@echo "  make install    - Install the module"
	@echo "  make clean      - Remove build artifacts"
	@echo "  make KDIR=/path - Build against a specific kernel tree"

endif
