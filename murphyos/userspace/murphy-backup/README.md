# MurphyOS Snapshot Backup & Disaster Recovery

> SPDX-License-Identifier: LicenseRef-BSL-1.1
> © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1

OS-level snapshot-based backup for Murphy System state, keys, configuration,
and databases.  Corresponds to the application-level `backup_disaster_recovery.py`
but operates at the filesystem / block-device layer.

## Strategy Comparison

| Strategy | Speed | Dedup | Encryption | Incremental | Requirements |
|----------|-------|-------|------------|-------------|--------------|
| **btrfs** | ★★★★★ Instant (COW) | Implicit | No (use dm-crypt) | Implicit | btrfs filesystem |
| **LVM** | ★★★★ Fast (block) | No | No (use LUKS) | No | LVM thin pool |
| **restic** | ★★★ Good | Yes | Yes (AES-256) | Yes | `restic` binary |
| **tar** | ★★ Slow (full copy) | No | No (wrap with gpg) | No | coreutils |

Strategy is auto-detected in priority order: btrfs → LVM → restic → tar.
Override with `strategy:` in `backup.yaml`.

## Backup Targets

| Path | Contents |
|------|----------|
| `/var/lib/murphy/` | Runtime state, persistent memory, agent data |
| `/murphy/keys/` | PQC key material (encrypted at rest) |
| `/etc/murphy/` | Configuration files |
| Murphy database | PostgreSQL (`pg_dump`) or SQLite (file copy) — auto-detected |

## Quick Start

```bash
# Install systemd units
sudo cp murphy-backup.service /etc/systemd/system/
sudo cp murphy-backup.timer   /etc/systemd/system/
sudo cp backup.yaml           /etc/murphy/backup.yaml
sudo systemctl daemon-reload
sudo systemctl enable --now murphy-backup.timer

# Manual backup
sudo systemctl start murphy-backup.service

# Or use CLI directly
python3 murphy_backup.py create --label manual
```

## CLI Usage

```bash
# Create a backup (auto-detect strategy)
python3 murphy_backup.py create --label nightly

# Create with explicit strategy
python3 murphy_backup.py create --label snapshot --strategy btrfs

# List all backups
python3 murphy_backup.py list

# Verify backup integrity (SHA3-256)
python3 murphy_backup.py verify <backup_id>

# Restore from backup
python3 murphy_backup.py restore <backup_id>

# Apply retention policy
python3 murphy_backup.py prune --keep-daily 7 --keep-weekly 4 --keep-monthly 6

# Export for off-site storage
python3 murphy_backup.py export <backup_id> /mnt/offsite/
```

## Python API

```python
from murphy_backup import MurphyBackup

bkp = MurphyBackup(config_path="/etc/murphy/backup.yaml")

# Create
backup_id = bkp.create_backup(label="nightly", strategy="auto")

# List
for info in bkp.list_backups():
    print(info.backup_id, info.timestamp, info.size_bytes)

# Verify
bkp.verify_backup(backup_id)

# Prune
pruned = bkp.prune_backups(keep_daily=7, keep_weekly=4, keep_monthly=6)

# Export
bkp.export_backup(backup_id, "/mnt/offsite/")

# Restore (stops murphy-system.service, restores, starts service)
bkp.restore_backup(backup_id)
```

## Restore Procedures

### Full System Restore

1. **Stop Murphy System** (automatic via pre-hooks):
   ```bash
   sudo systemctl stop murphy-system.service
   ```

2. **List available backups**:
   ```bash
   python3 murphy_backup.py list
   ```

3. **Verify the target backup**:
   ```bash
   python3 murphy_backup.py verify <backup_id>
   ```

4. **Restore**:
   ```bash
   python3 murphy_backup.py restore <backup_id>
   ```

5. **Verify services** (automatic via post-hooks):
   ```bash
   sudo systemctl status murphy-system.service
   ```

### Database-Only Restore

For PostgreSQL:
```bash
gunzip -c /var/lib/murphy/backups/<backup_id>/murphy_db.sql.gz | psql <dsn>
```

For SQLite:
```bash
cp /var/lib/murphy/backups/<backup_id>/murphy.db /var/lib/murphy/murphy.db
```

### Disaster Recovery from Off-Site Export

```bash
# Copy the exported archive to the new host
scp /mnt/offsite/<backup_id>.tar.gz newhost:/var/lib/murphy/backups/

# Extract
cd /var/lib/murphy/backups
mkdir <backup_id> && tar xzf <backup_id>.tar.gz -C <backup_id>

# Restore
python3 murphy_backup.py restore <backup_id>
```

## Configuration

Edit `backup.yaml` (default: `/etc/murphy/backup.yaml`):

| Key | Description | Default |
|-----|-------------|---------|
| `enabled` | Master switch | `true` |
| `strategy` | Backup strategy | `auto` |
| `backup_dir` | Where backups are stored | `/var/lib/murphy/backups` |
| `retention.keep_daily` | Daily backups to keep | `7` |
| `retention.keep_weekly` | Weekly backups to keep | `4` |
| `retention.keep_monthly` | Monthly backups to keep | `6` |
| `targets` | Filesystem paths to back up | See above |
| `pre_hooks` | Commands to run before backup/restore | `systemctl stop murphy-system.service` |
| `post_hooks` | Commands to run after backup/restore | `systemctl start murphy-system.service` |
| `encryption.enabled` | Encrypt backups | `true` |
| `encryption.key_source` | Key derivation source | `pqc` |

## Error Codes

| Code | Description |
|------|-------------|
| `MURPHY-BACKUP-ERR-001` | Configuration file load / parse failure |
| `MURPHY-BACKUP-ERR-002` | Backup directory creation failed |
| `MURPHY-BACKUP-ERR-003` | No viable backup strategy detected |
| `MURPHY-BACKUP-ERR-004` | btrfs snapshot command failed |
| `MURPHY-BACKUP-ERR-005` | LVM snapshot creation failed |
| `MURPHY-BACKUP-ERR-006` | restic backup command failed |
| `MURPHY-BACKUP-ERR-007` | tar archive creation failed |
| `MURPHY-BACKUP-ERR-008` | Manifest write / serialise error |
| `MURPHY-BACKUP-ERR-009` | Restore operation failed |
| `MURPHY-BACKUP-ERR-010` | Integrity verification mismatch |
| `MURPHY-BACKUP-ERR-011` | Retention pruning error |
| `MURPHY-BACKUP-ERR-012` | Export / off-site copy error |
| `MURPHY-BACKUP-ERR-013` | Database dump failure (pg_dump / SQLite copy) |
| `MURPHY-BACKUP-ERR-014` | Pre/post hook execution error |
| `MURPHY-BACKUP-ERR-015` | Requested backup_id not found |

## systemd Units

### `murphy-backup.service`

`Type=oneshot` unit for manual or timer-triggered backups.  Runs with the
following hardening:

- `ProtectHome=yes` — no access to `/home`
- `ProtectSystem=strict` — read-only root filesystem
- `ReadWritePaths=/var/lib/murphy/backups` — only the backup directory
- `ReadOnlyPaths=/var/lib/murphy /murphy/keys /etc/murphy` — backup targets
- `NoNewPrivileges=yes` — no privilege escalation
- `MemoryMax=1G` — bounded memory
- `TimeoutStartSec=3600` — allow up to 1 hour for large backups

### `murphy-backup.timer`

Fires daily at 03:00 UTC with up to 15 minutes of jitter
(`RandomizedDelaySec=900`).  `Persistent=true` ensures missed runs
execute on next boot.

## Requirements

- Linux (systemd-based distribution)
- Python ≥ 3.10
- PyYAML (included in Murphy runtime)
- Optional: `btrfs-progs`, `lvm2`, `restic`, `postgresql-client`
