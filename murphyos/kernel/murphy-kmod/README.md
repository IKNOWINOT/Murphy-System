# Murphy Kernel Module (`murphy_kmod`)

Linux kernel module for MurphyOS providing hardware-level integration with
the Murphy event bus, live confidence scoring, governance gates, and
network-aware packet classification.

**Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post**
Kernel module: `Dual BSD/GPL` · Project license: BSL 1.1

---

## What It Provides

| Interface | Path | Description |
|-----------|------|-------------|
| Event bus | `/dev/murphy-event` | Write JSON events from userspace; Murphy daemon reads via ring buffer |
| Confidence | `/dev/murphy-confidence` | Read-only; returns MFGC score as text (e.g. `0.8700`) |
| Gates | `/sys/murphy/gates/{EXECUTIVE,OPERATIONS,QA,HITL,COMPLIANCE,BUDGET}` | Read gate status: `open`, `blocked`, or `pending` |
| Netfilter | NF_INET_LOCAL_OUT hook | Marks outbound packets to Murphy-managed ports for QoS/routing |
| ioctl | via `/dev/murphy-event` | Update confidence, gate states, and managed ports from userspace |

## Prerequisites

```bash
# Debian / Ubuntu
sudo apt-get install build-essential linux-headers-$(uname -r)

# Fedora / RHEL
sudo dnf install kernel-devel kernel-headers gcc make
```

## Build

```bash
cd murphyos/kernel/murphy-kmod
make
```

To build against a different kernel:

```bash
make KDIR=/path/to/kernel/source
```

## Install (manual)

```bash
sudo make install
sudo modprobe murphy_kmod
```

## Install (DKMS)

```bash
sudo cp -r . /usr/src/murphy_kmod-1.0.0
sudo dkms add murphy_kmod/1.0.0
sudo dkms build murphy_kmod/1.0.0
sudo dkms install murphy_kmod/1.0.0
```

The module will auto-rebuild on kernel updates.

## Module Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `event_buf_size` | `65536` | Ring-buffer size in bytes (must be power of 2) |
| `default_confidence` | `5000` | Initial MFGC score × 10 000 (0.5000) |
| `murphy_default_ports` | `""` | Comma-separated managed ports (e.g. `443,8080`) |

Example:

```bash
sudo modprobe murphy_kmod event_buf_size=131072 default_confidence=8500 \
    murphy_default_ports="443,8080,6379"
```

## Usage Examples

### Write an event

```bash
echo '{"type":"deploy","module":"llm-router"}' > /dev/murphy-event
```

### Read confidence score

```bash
cat /dev/murphy-confidence
# 0.8500
```

### Check gate status

```bash
cat /sys/murphy/gates/EXECUTIVE
# open
```

### ioctl from C

```c
#include "murphy_kmod.h"

int fd = open("/dev/murphy-event", O_RDWR);

/* Update confidence to 0.92 */
struct murphy_confidence_info ci = { .score = 9200 };
ioctl(fd, MURPHY_IOC_SET_CONFIDENCE, &ci);

/* Block the QA gate */
struct murphy_gate_info gi = {
    .gate_id = MURPHY_GATE_QA,
    .state   = MURPHY_GATE_BLOCKED,
};
ioctl(fd, MURPHY_IOC_SET_GATE, &gi);
```

## Netfilter Marks

Outbound packets to managed ports receive `skb->mark = 0x4D555201`
(priority).  All other packets receive `0x4D555202` (normal).  Use
iptables or nftables to act on these marks:

```bash
# Prioritize Murphy traffic with tc
iptables -t mangle -A OUTPUT -m mark --mark 0x4D555201 -j CLASSIFY --set-class 1:10
```

## Unload

```bash
sudo rmmod murphy_kmod
```

## Clean

```bash
make clean
```
