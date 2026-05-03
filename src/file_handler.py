"""
Murphy File Handler — PATCH-161
Upload, read, and inspect files of all kinds including ZIP archives.
"""
import zipfile, tarfile, io, os, base64, mimetypes, json, hashlib
from pathlib import Path
from typing import Optional

_UPLOAD_DIR = Path("/var/lib/murphy-production/uploads")
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_SIZE_MB = 50
ALLOWED_EXTS = {
    # Documents
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".md", ".rst", ".csv", ".json", ".xml", ".yaml", ".yml",
    # Code
    ".py", ".js", ".ts", ".html", ".css", ".sh", ".sql",
    # Archives
    ".zip", ".tar", ".gz", ".tar.gz", ".tgz", ".bz2",
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
    # Data
    ".parquet", ".feather", ".db", ".sqlite",
    # Other
    ".log", ".env.example", ".toml", ".ini", ".cfg",
}


def save_upload(filename: str, data: bytes, uploader: str = "system") -> dict:
    """Save an uploaded file to the uploads directory."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        return {"success": False, "error": f"File type {ext!r} not allowed"}
    size_mb = len(data) / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        return {"success": False, "error": f"File too large ({size_mb:.1f}MB > {MAX_SIZE_MB}MB)"}
    # Hash for dedup
    sha = hashlib.sha256(data).hexdigest()[:12]
    safe_name = f"{sha}_{Path(filename).stem[:40]}{ext}"
    dest = _UPLOAD_DIR / safe_name
    dest.write_bytes(data)
    return {
        "success": True,
        "filename": safe_name,
        "original_name": filename,
        "path": str(dest),
        "size_bytes": len(data),
        "sha256": sha,
        "mime": mimetypes.guess_type(filename)[0] or "application/octet-stream",
    }


def list_uploads(limit: int = 50) -> list:
    files = sorted(_UPLOAD_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    return [
        {
            "name": f.name,
            "size_bytes": f.stat().st_size,
            "modified": f.stat().st_mtime,
            "mime": mimetypes.guess_type(f.name)[0],
        }
        for f in files if f.is_file()
    ]


def read_zip(path_or_bytes, max_files: int = 100, max_file_size_kb: int = 500) -> dict:
    """Inspect a ZIP archive — list contents and read text files."""
    try:
        if isinstance(path_or_bytes, (str, Path)):
            zf = zipfile.ZipFile(path_or_bytes, "r")
        else:
            zf = zipfile.ZipFile(io.BytesIO(path_or_bytes), "r")
        
        with zf:
            infos = zf.infolist()
            manifest = [
                {
                    "name": i.filename,
                    "size": i.file_size,
                    "compressed": i.compress_size,
                    "is_dir": i.is_dir(),
                }
                for i in infos[:max_files]
            ]
            # Read small text files
            text_files = {}
            text_exts = {".py", ".js", ".ts", ".html", ".css", ".md", ".txt",
                         ".json", ".yaml", ".yml", ".csv", ".sql", ".sh", ".toml", ".env"}
            for info in infos:
                if info.is_dir():
                    continue
                ext = Path(info.filename).suffix.lower()
                if ext in text_exts and info.file_size < max_file_size_kb * 1024:
                    try:
                        content = zf.read(info.filename).decode("utf-8", errors="replace")
                        text_files[info.filename] = content[:5000]  # cap at 5KB per file
                    except Exception:
                        pass
                if len(text_files) >= 20:
                    break
            return {
                "success": True,
                "total_files": len(infos),
                "shown": len(manifest),
                "manifest": manifest,
                "text_files": text_files,
                "truncated": len(infos) > max_files,
            }
    except zipfile.BadZipFile:
        return {"success": False, "error": "Not a valid ZIP file"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def read_tar(path_or_bytes, max_files: int = 100) -> dict:
    """Inspect a tar/tar.gz archive."""
    try:
        if isinstance(path_or_bytes, (str, Path)):
            tf = tarfile.open(path_or_bytes)
        else:
            tf = tarfile.open(fileobj=io.BytesIO(path_or_bytes))
        with tf:
            members = tf.getmembers()
            manifest = [
                {"name": m.name, "size": m.size, "is_dir": m.isdir()}
                for m in members[:max_files]
            ]
            return {
                "success": True,
                "total_files": len(members),
                "shown": len(manifest),
                "manifest": manifest,
                "truncated": len(members) > max_files,
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


def inspect_file(path: str) -> dict:
    """Read and describe any uploaded file."""
    p = Path(path)
    if not p.exists():
        return {"success": False, "error": "File not found"}
    ext = p.suffix.lower()
    data = p.read_bytes()
    result = {
        "success": True,
        "name": p.name,
        "size_bytes": len(data),
        "mime": mimetypes.guess_type(p.name)[0],
        "sha256": hashlib.sha256(data).hexdigest()[:16],
    }
    if ext == ".zip":
        result["archive"] = read_zip(data)
    elif ext in (".tar", ".gz", ".tgz", ".bz2"):
        result["archive"] = read_tar(data)
    elif ext in (".json",):
        try:
            result["parsed"] = json.loads(data.decode())
        except Exception:
            result["raw_text"] = data.decode("utf-8", errors="replace")[:5000]
    elif ext in (".py", ".js", ".ts", ".html", ".css", ".md", ".txt",
                  ".csv", ".sql", ".sh", ".yaml", ".yml", ".toml"):
        result["text"] = data.decode("utf-8", errors="replace")[:10000]
    else:
        result["b64_preview"] = base64.b64encode(data[:1024]).decode()
    return result
