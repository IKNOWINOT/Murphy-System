// SPDX-License-Identifier: GPL-2.0-only OR BSD-2-Clause
/*
 * murphy_netfilter.c — Netfilter hooks for Murphy-aware packet classification
 *
 * Hooks NF_INET_LOCAL_OUT to classify outbound packets.  Destinations
 * that match Murphy-managed ports (swarm agents, LLM providers, etc.)
 * receive a priority mark; everything else gets a normal mark.  Marks
 * are applied via skb->mark so that iptables/nftables rules can match
 * on them (e.g. for QoS, routing, or logging).
 *
 * Which ports are "managed" is configurable at runtime through the
 * MURPHY_IOC_SET_PORTS ioctl on /dev/murphy-event or through the
 * murphy_default_ports module parameter.
 *
 * Copyright © 2020 Inoni Limited Liability Company
 * Creator: Corey Post
 *
 * Dual-licensed: GPL-2.0-only OR BSD-2-Clause (kernel compatibility).
 */

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/netfilter.h>
#include <linux/netfilter_ipv4.h>
#include <linux/ip.h>
#include <linux/tcp.h>
#include <linux/udp.h>
#include <linux/skbuff.h>
#include <linux/spinlock.h>

#include "murphy_kmod.h"

/* ================================================================== */
/*  Module parameter — comma-separated default managed ports          */
/* ================================================================== */
static char *murphy_default_ports = "";
module_param(murphy_default_ports, charp, 0444);
MODULE_PARM_DESC(murphy_default_ports,
	"Comma-separated list of TCP/UDP ports to mark as Murphy-managed "
	"(e.g. \"443,8080,6379\")");

/* ================================================================== */
/*  Helpers                                                           */
/* ================================================================== */

/*
 * Check whether @port is in the current managed-ports list.
 * Called from softirq context — uses spin_lock.
 */
static bool murphy_port_is_managed(__be16 port_be)
{
	unsigned long flags;
	__u16 port = ntohs(port_be);
	__u32 i;
	bool found = false;

	spin_lock_irqsave(&murphy_port_lock, flags);
	for (i = 0; i < murphy_managed_ports.count; i++) {
		if (murphy_managed_ports.ports[i].port == port) {
			found = true;
			break;
		}
	}
	spin_unlock_irqrestore(&murphy_port_lock, flags);

	return found;
}

/*
 * Extract the destination port from a TCP or UDP header.  Returns 0
 * for non-TCP/UDP protocols.
 */
static __be16 murphy_get_dst_port(const struct sk_buff *skb,
				  const struct iphdr *iph)
{
	unsigned int hdr_off = iph->ihl * 4;

	if (iph->protocol == IPPROTO_TCP) {
		const struct tcphdr *th;
		struct tcphdr _th;

		th = skb_header_pointer(skb, hdr_off, sizeof(_th), &_th);
		if (th)
			return th->dest;
	} else if (iph->protocol == IPPROTO_UDP) {
		const struct udphdr *uh;
		struct udphdr _uh;

		uh = skb_header_pointer(skb, hdr_off, sizeof(_uh), &_uh);
		if (uh)
			return uh->dest;
	}

	return 0;
}

/* ================================================================== */
/*  NF_INET_LOCAL_OUT hook                                            */
/* ================================================================== */
static unsigned int murphy_nf_local_out(void *priv,
					struct sk_buff *skb,
					const struct nf_hook_state *state)
{
	const struct iphdr *iph;
	__be16 dport;

	if (!skb)
		return NF_ACCEPT;

	iph = ip_hdr(skb);
	if (!iph)
		return NF_ACCEPT;

	dport = murphy_get_dst_port(skb, iph);
	if (dport == 0)
		return NF_ACCEPT;

	if (murphy_port_is_managed(dport))
		skb->mark = MURPHY_NF_MARK_PRIORITY;
	else
		skb->mark = MURPHY_NF_MARK_NORMAL;

	return NF_ACCEPT;
}

/* ================================================================== */
/*  Hook registration                                                 */
/* ================================================================== */
static const struct nf_hook_ops murphy_nf_ops = {
	.hook     = murphy_nf_local_out,
	.pf       = NFPROTO_IPV4,
	.hooknum  = NF_INET_LOCAL_OUT,
	.priority = NF_IP_PRI_MANGLE + 1,   /* just after mangle table */
};

/* ------------------------------------------------------------------ */
/*  Parse the module parameter to seed the managed-ports table        */
/* ------------------------------------------------------------------ */
static void murphy_parse_default_ports(void)
{
	char *buf, *tok;
	unsigned long port;
	unsigned long flags;

	if (!murphy_default_ports || murphy_default_ports[0] == '\0')
		return;

	buf = kstrdup(murphy_default_ports, GFP_KERNEL);
	if (!buf)
		return;

	spin_lock_irqsave(&murphy_port_lock, flags);
	murphy_managed_ports.count = 0;

	while ((tok = strsep(&buf, ",")) != NULL) {
		if (kstrtoul(tok, 10, &port) == 0 && port <= 65535 &&
		    murphy_managed_ports.count < MURPHY_MAX_MANAGED_PORTS) {
			murphy_managed_ports.ports[murphy_managed_ports.count].port =
				(__u16)port;
			murphy_managed_ports.ports[murphy_managed_ports.count].flags = 0;
			murphy_managed_ports.count++;
		}
	}
	spin_unlock_irqrestore(&murphy_port_lock, flags);

	kfree(buf);
}

/* ================================================================== */
/*  Public init / exit                                                */
/* ================================================================== */
int murphy_nf_init(void)
{
	int ret;

	murphy_parse_default_ports();

	ret = nf_register_net_hook(&init_net, &murphy_nf_ops);
	if (ret) {
		pr_err("murphy: failed to register netfilter hook (%d)\n", ret);
		return ret;
	}

	pr_info("murphy: netfilter hook registered (managed ports: %u)\n",
		murphy_managed_ports.count);
	return 0;
}

void murphy_nf_exit(void)
{
	nf_unregister_net_hook(&init_net, &murphy_nf_ops);
	pr_info("murphy: netfilter hook unregistered\n");
}
