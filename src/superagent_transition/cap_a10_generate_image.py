"""Cap A.10 — generate_image.

Architecture:
  - Call DeepInfra's FLUX-1-schnell endpoint (fast + cheap, ~$0.00003/img)
  - DeepInfra returns base64 data URI in JSON response
  - Decode to PNG bytes, write to temp file
  - Hand off to A.7 upload_file to land on /static/uploads/ + return public URL
  - Single round-trip: prompt in → public https://murphy.systems URL out

Why DeepInfra:
  - Murphy already has DEEPINFRA_API_KEY (no new secret)
  - llm_provider already routes text-gen through it (consistency)
  - $0.00003/image is ~33k images per $1 — effectively free at our scale
  - 1 inference step on FLUX schnell takes ~50ms

Future enhancement (logged): When this box gets a GPU, swap the API
call for image_generation_engine._StableDiffusionBackend.generate().
The public surface stays identical.

Hard caps:
  - prompt length 4000 chars
  - dimensions 256-1536 per side, default 1024x1024
  - 1-4 inference steps (FLUX schnell sweet spot)
"""
from __future__ import annotations
import base64
import json
import os
import tempfile
import time
import urllib.request
from typing import Any, Dict, Optional

DEFAULT_MODEL = "black-forest-labs/FLUX-1-schnell"
DEEPINFRA_BASE = "https://api.deepinfra.com/v1/inference"
MAX_PROMPT_LEN = 4000
MIN_DIM = 256
MAX_DIM = 1536
DEFAULT_DIM = 1024
MAX_STEPS = 4
DEFAULT_STEPS = 1


def _api_key() -> str:
    k = os.environ.get("DEEPINFRA_API_KEY", "")
    if not k:
        try:
            with open("/etc/murphy-production/secrets.env") as f:
                for line in f:
                    if line.startswith("DEEPINFRA_API_KEY="):
                        k = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    if not k:
        raise RuntimeError("DEEPINFRA_API_KEY not set")
    return k


def generate_image(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    width: int = DEFAULT_DIM,
    height: int = DEFAULT_DIM,
    num_inference_steps: int = DEFAULT_STEPS,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "ok": False, "prompt": prompt, "url": None,
        "model": model, "width": width, "height": height,
        "steps": num_inference_steps, "cost_usd": 0.0,
        "wall_ms": 0, "error": None,
    }
    try:
        if not prompt or not prompt.strip():
            out["error"] = "empty prompt"; return out
        if len(prompt) > MAX_PROMPT_LEN:
            out["error"] = f"prompt too long: {len(prompt)} > {MAX_PROMPT_LEN}"
            return out
        # Clamp dimensions
        w = max(MIN_DIM, min(MAX_DIM, int(width)))
        h = max(MIN_DIM, min(MAX_DIM, int(height)))
        # Round to multiple of 8 (most diffusion models require this)
        w = (w // 8) * 8
        h = (h // 8) * 8
        steps = max(1, min(MAX_STEPS, int(num_inference_steps)))

        out["width"], out["height"], out["steps"] = w, h, steps

        # POST to DeepInfra
        body = json.dumps({
            "prompt": prompt,
            "width": w,
            "height": h,
            "num_inference_steps": steps,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{DEEPINFRA_BASE}/{model}",
            data=body,
            headers={
                "Authorization": f"Bearer {_api_key()}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
        wall_ms = int((time.time() - t0) * 1000)
        out["wall_ms"] = wall_ms

        data = json.loads(raw)
        status = (data.get("inference_status") or {}).get("status")
        if status != "succeeded":
            out["error"] = f"deepinfra status: {status} / {data.get('inference_status')}"
            return out
        out["cost_usd"] = float((data.get("inference_status") or {}).get("cost", 0))

        images = data.get("images") or []
        if not images:
            out["error"] = "no images in response"; return out
        data_uri = images[0]
        # Strip "data:image/png;base64," prefix if present
        if "," in data_uri:
            data_uri = data_uri.split(",", 1)[1]
        try:
            img_bytes = base64.b64decode(data_uri)
        except Exception as e:
            out["error"] = f"base64 decode failed: {e}"; return out

        # Sniff actual format. DeepInfra labels as PNG but often returns JPEG.
        ext = ".png"
        if img_bytes[:3] == b"\xff\xd8\xff":
            ext = ".jpg"
        elif img_bytes[:8] == b"\x89PNG\r\n\x1a\n":
            ext = ".png"
        elif img_bytes[:4] == b"RIFF" and img_bytes[8:12] == b"WEBP":
            ext = ".webp"

        # Write to temp file then hand to A.7
        with tempfile.NamedTemporaryFile(
            prefix="cap_a10_", suffix=ext, dir="/tmp", delete=False,
        ) as f:
            f.write(img_bytes)
            tmp_path = f.name

        # Compose with A.7 to get public URL
        from .cap_a7_upload_file import upload_file as _upload
        up = _upload(tmp_path)
        os.unlink(tmp_path)
        if not up["ok"]:
            out["error"] = f"upload failed: {up['error']}"; return out

        out["url"] = up["file_url"]
        out["sha256"] = up["sha256"]
        out["size_bytes"] = up["size_bytes"]
        out["ok"] = True
        return out
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            body = ""
        out["error"] = f"HTTP {e.code}: {body}"; return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def execute_generate_image(**kwargs) -> Dict[str, Any]:
    return generate_image(
        prompt=kwargs.get("prompt", ""),
        model=kwargs.get("model", DEFAULT_MODEL),
        width=int(kwargs.get("width", DEFAULT_DIM)),
        height=int(kwargs.get("height", DEFAULT_DIM)),
        num_inference_steps=int(kwargs.get("num_inference_steps", DEFAULT_STEPS)),
    )
