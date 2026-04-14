# Murphy DNS Resolver

Resolves `*.murphy.local` domains to the local Murphy API and swarm agent namespaces.

## Install

```bash
sudo cp murphy_resolved.py /usr/lib/murphy/murphy-resolved
sudo cp murphy-resolved.service /etc/systemd/system/
sudo cp murphy-resolved.conf /etc/systemd/resolved.conf.d/
sudo systemctl daemon-reload
sudo systemctl enable --now murphy-resolved
sudo systemctl restart systemd-resolved
```

## Domains

| Pattern | Resolves To |
|---------|-------------|
| `api.murphy.local` | `127.0.0.1` |
| `*.murphy.local` | `127.0.0.1` |
| `<name>.swarm.murphy.local` | Agent namespace IP |
| `pqc-ca.murphy.local` | PQC CA endpoint |
