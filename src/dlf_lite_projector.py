"""R439 — DLF-Lite projector + export endpoint.

Adds a one-way exporter that takes any DLF-R package and emits a Shogun-
compatible .dlf-lite container. Pure projector — no changes to dlf_r.pack(),
unpack(), validate(), store(), or load(). DLF-R remains the internal native
format; DLF-Lite is only the wire format for outside-system handoffs.

Container layout (matches the v0.1 SPEC.md from the Shogun package):

    magic              8 bytes        "DLFLITE1"
    header_len         uint32 BE
    payload_len        uint64 BE
    header_json        UTF-8 JSON of metadata
    payload_bytes      JSON body (compressed or plain)
    checksum           sha256 hex of payload_bytes, UTF-8, 64 bytes

Weave-type normalization:
    SUPPORTS         -> SUPPORT
    CONTRADICTS      -> CONTRADICTION
    DEPENDS_ON       -> DEPENDENCY
    SEQUENCE         -> SEQUENCE
    ASSOCIATION      -> ASSOCIATION
    REFERENCE        -> REFERENCE
    FALLBACK_SUCCEEDS -> ASSOCIATION  (Murphy-native, no DLF-Lite equivalent)
    ROUTED_TO         -> ASSOCIATION  (Murphy-native)
    ESCALATED_TO      -> ASSOCIATION  (Murphy-native)

Rosetta block: per DLF-Lite spec §9.4 ("Do NOT overload the format"), the
constitutional snapshot is NOT embedded in the body. Instead, we put a single
opaque attestation reference into provenance.metadata so Murphy receivers can
recover it from our own store, while outside systems can safely ignore it.

Sentinel: _R439_DLF_LITE_EXPORT_WIRED
"""
from __future__ import annotations

import gzip
import hashlib
import json
import struct
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

DLF_LITE_MAGIC = b"DLFLITE1"
DLF_LITE_VERSION = "0.1"

# DLF-R weave type -> DLF-Lite v0.1 weave type
WEAVE_TYPE_MAP = {
    "SUPPORTS": "SUPPORT",
    "CONTRADICTS": "CONTRADICTION",
    "DEPENDS_ON": "DEPENDENCY",
    "SEQUENCE": "SEQUENCE",
    "ASSOCIATION": "ASSOCIATION",
    "REFERENCE": "REFERENCE",
    # Murphy-native types collapse to ASSOCIATION with original type preserved in metadata
    "FALLBACK_SUCCEEDS": "ASSOCIATION",
    "ROUTED_TO": "ASSOCIATION",
    "ESCALATED_TO": "ASSOCIATION",
}


def project_to_lite_payload(dlfr_body: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a DLF-R body dict into a DLF-Lite v0.1 payload dict.

    Args:
        dlfr_body: The decoded body of a DLF-R blob (output of unpack()).

    Returns:
        A DLF-Lite-shaped dict ready to be serialized into the container.
    """
    semantic = dlfr_body.get("semantic_layers", {})
    threads_in = semantic.get("threads", []) or []
    nodes_in = semantic.get("nodes", []) or []
    weaves_in = semantic.get("weaves", []) or []
    fabric_in = dlfr_body.get("fabric", {}) or {}
    has_rosetta = bool(dlfr_body.get("rosetta_block"))

    # Threads pass through unchanged — same field names already
    threads_out = []
    for t in threads_in:
        threads_out.append({
            "id": t.get("id"),
            "payload": t.get("payload", ""),
            "created_at_utc": t.get("created_at_utc") or dlfr_body.get("created_at_utc"),
            "metadata": t.get("metadata", {}) or {},
            "symbol_signature": t.get("symbol_signature", ""),
        })

    # Nodes pass through unchanged
    nodes_out = []
    for n in nodes_in:
        nodes_out.append({
            "id": n.get("id"),
            "label": n.get("label", n.get("id", "")),
            "thread_refs": list(n.get("thread_refs", []) or []),
            "metadata": n.get("metadata", {}) or {},
        })

    # Weaves: normalize type, preserve original in metadata for round-trip
    weaves_out = []
    for w in weaves_in:
        original_type = w.get("type", "ASSOCIATION")
        lite_type = WEAVE_TYPE_MAP.get(original_type, "ASSOCIATION")
        meta = dict(w.get("metadata", {}) or {})
        if lite_type != original_type:
            meta["_dlfr_native_type"] = original_type
        weaves_out.append({
            "id": w.get("id"),
            "source": w.get("source"),
            "target": w.get("target"),
            "type": lite_type,
            "confidence": float(w.get("confidence", 1.0)),
            "metadata": meta,
        })

    # Fabric: emit DLF-Lite-shaped summary
    fabric_out = {
        "summary": (f"{len(threads_out)} thread(s), {len(nodes_out)} node(s), "
                    f"{len(weaves_out)} weave(s)"),
        "domains": fabric_in.get("domains", []) or [],
        "keywords": fabric_in.get("keywords", []) or [],
        "metadata": {
            "weave_type_histogram_dlfr": fabric_in.get("weave_type_histogram", {}),
            "exported_from": "DLF-R",
            "exported_from_format_version": dlfr_body.get("format_version", "0.1"),
        },
    }

    # Provenance: per §9.4 keep Rosetta OUT of body. Reference it by hash only.
    provenance_out = {
        "created_by": dlfr_body.get("creator", "murphy-dlf-r"),
        "created_at_utc": dlfr_body.get("created_at_utc"),
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "exported_by": "murphy.dlf_lite_projector",
        "native_loom_runtime_required": False,
        "source_system": "murphy.systems",
        "has_rosetta_attestation": has_rosetta,
        "lineage": [
            {
                "event": "dlf_r_package_created",
                "system": dlfr_body.get("creator", "murphy"),
                "ts": dlfr_body.get("created_at_utc"),
                "package_id": dlfr_body.get("package_id"),
            },
            {
                "event": "exported_to_dlf_lite",
                "system": "murphy.dlf_lite_projector",
                "ts": datetime.now(timezone.utc).isoformat(),
            },
        ],
    }
    if has_rosetta:
        rosetta_json = json.dumps(dlfr_body["rosetta_block"], sort_keys=True,
                                  default=str).encode("utf-8")
        provenance_out["rosetta_attestation_sha256"] = hashlib.sha256(
            rosetta_json).hexdigest()

    # Audit log — empty array at export time; receivers may append on import
    audit_out = list(dlfr_body.get("audit", []) or [])
    audit_out.append({
        "event": "exported_to_dlf_lite",
        "at": datetime.now(timezone.utc).isoformat(),
        "from_format": "DLF-R",
        "from_format_version": dlfr_body.get("format_version", "0.1"),
    })

    return {
        "format": "DLF-LITE",
        "version": DLF_LITE_VERSION,
        "manifest": {
            "package_id": dlfr_body.get("package_id"),
            "title": dlfr_body.get("metadata", {}).get("label",
                     dlfr_body.get("metadata", {}).get("title", "DLF-R Export")),
            "created_at_utc": dlfr_body.get("created_at_utc"),
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "producer": "murphy.dlf_lite_projector",
            "source_system": "murphy.systems",
        },
        "threads": threads_out,
        "nodes": nodes_out,
        "weaves": weaves_out,
        "fabric": fabric_out,
        "provenance": provenance_out,
        "audit": audit_out,
    }


def _json_canonical(obj: Any) -> bytes:
    """Stable canonical JSON (sorted keys, compact, UTF-8) for hashing/byte-eq."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def encode_lite_container(payload: Dict[str, Any], *, compress: bool = True) -> bytes:
    """Serialize a DLF-Lite payload into the .dlf-lite binary container.

    Layout matches the Shogun v0.1 SPEC exactly:
        magic(8) | header_len(u32 BE) | payload_len(u64 BE) | header_json |
        payload_bytes | sha256_hex(64)
    """
    payload_json = _json_canonical(payload)
    if compress:
        payload_bytes = gzip.compress(payload_json)
        encoding = "gzip"
    else:
        payload_bytes = payload_json
        encoding = "plain"

    header = {
        "format": "DLF-LITE",
        "version": DLF_LITE_VERSION,
        "encoding": encoding,
        "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "exporter": "murphy.dlf_lite_projector",
    }
    header_bytes = _json_canonical(header)

    out = bytearray()
    out += DLF_LITE_MAGIC                                  # 8 bytes
    out += struct.pack(">I", len(header_bytes))            # 4 bytes u32 BE
    out += struct.pack(">Q", len(payload_bytes))           # 8 bytes u64 BE
    out += header_bytes
    out += payload_bytes
    out += header["payload_sha256"].encode("utf-8")        # 64 bytes
    return bytes(out)


def decode_lite_container(blob: bytes) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Parse a .dlf-lite container. Returns (header, payload).

    Verifies magic and checksum. Decompresses if needed.
    """
    if not blob.startswith(DLF_LITE_MAGIC):
        raise ValueError("not a DLF-Lite container (magic mismatch)")
    p = 8
    (header_len,) = struct.unpack(">I", blob[p:p+4]); p += 4
    (payload_len,) = struct.unpack(">Q", blob[p:p+8]); p += 8
    header = json.loads(blob[p:p+header_len].decode("utf-8")); p += header_len
    payload_bytes = blob[p:p+payload_len]; p += payload_len
    stored_checksum = blob[p:p+64].decode("utf-8")
    actual_checksum = hashlib.sha256(payload_bytes).hexdigest()
    if stored_checksum != actual_checksum:
        raise ValueError(f"checksum mismatch: stored={stored_checksum} actual={actual_checksum}")
    if header.get("encoding") == "gzip":
        payload_bytes = gzip.decompress(payload_bytes)
    payload = json.loads(payload_bytes.decode("utf-8"))
    return header, payload


def export_dlf_r_package(package_id: str) -> bytes:
    """High-level: load a DLF-R package by ID, project it, return .dlf-lite bytes.

    Args:
        package_id: The DLF-R package ID stored in dlfr_packages.

    Returns:
        Bytes ready to write as a .dlf-lite file or stream over HTTP.

    Raises:
        ValueError if package_id not found or DLF-R blob is malformed.
    """
    from src import dlf_r
    dlfr_body = dlf_r.load(package_id)
    if not dlfr_body:
        raise ValueError(f"package_id not found: {package_id}")
    lite_payload = project_to_lite_payload(dlfr_body)
    return encode_lite_container(lite_payload, compress=True)
