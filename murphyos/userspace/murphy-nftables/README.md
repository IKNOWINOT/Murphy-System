# Murphy nftables Network Security

> © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1

Firewall rules for MurphyOS using **nftables** (`table inet murphy_security`).

## Chains

| Chain | Hook | Purpose |
|-------|------|---------|
| `murphy_output` | output / mangle | Mark Murphy traffic, rate-limit LLM API calls |
| `murphy_swarm_isolation` | forward / 0 | Isolate swarm agents — default drop, allow only confident agents |
| `murphy_input` | input / 0 | Protect Murphy ports — localhost-only for API, allow Matrix federation |

## Installation

```bash
sudo cp murphy.nft /etc/murphy/murphy.nft
sudo cp murphy-nftables.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now murphy-nftables
```
