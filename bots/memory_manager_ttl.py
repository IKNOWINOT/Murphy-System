import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

STM_DIR = Path("memory/stm")
LTM_DIR = Path("memory/ltm")


def archive_to_ltm(entry: dict) -> None:
    project = entry.get("context", {}).get("project", "default")
    ltm_path = LTM_DIR / project
    ltm_path.mkdir(parents=True, exist_ok=True)
    archive_file = ltm_path / "memory_chunks.json"
    if archive_file.exists():
        with open(archive_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = []
    data.append(entry)
    with open(archive_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def check_expired_stm() -> None:
    now = datetime.now(timezone.utc)
    for file in STM_DIR.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        ts = datetime.fromisoformat(data["timestamp"])
        exp = ts + timedelta(seconds=data.get("ttl_seconds", 0))
        if now > exp:
            archive_to_ltm(data)
            file.unlink()


def deduplicate_ltm(archive_file: Path) -> None:
    if not archive_file.exists():
        return
    with open(archive_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    seen = set()
    deduped = []
    for entry in data:
        key = (entry.get("task_id"), entry.get("content", "")[:50])
        if key not in seen:
            seen.add(key)
            deduped.append(entry)
    with open(archive_file, "w", encoding="utf-8") as f:
        json.dump(deduped, f, indent=2)
