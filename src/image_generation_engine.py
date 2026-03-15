"""
Image Generation Engine — Murphy System

Provides open-source, free image generation using Stable Diffusion
(via HuggingFace ``diffusers``) with automatic fallback to a lightweight
Pillow-based procedural generator when GPU/heavy dependencies are absent.

Supported backends (in priority order):
  1. **Stable Diffusion XL** (diffusers) — highest quality, requires GPU + torch
  2. **Stable Diffusion 1.5** (diffusers) — good quality, lower VRAM
  3. **Pillow procedural** — always available, generates placeholder/branded images

All backends are 100% open-source and free. No API keys required.

Design Label: IMG-001
Thread-safe: Yes (``threading.Lock`` on shared state)
Persistence: Saves generated images to ``.murphy_persistence/images/``

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import enum
import hashlib
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ImageBackend(enum.Enum):
    """Available image generation backends."""
    STABLE_DIFFUSION_XL = "stable_diffusion_xl"
    STABLE_DIFFUSION_15 = "stable_diffusion_1_5"
    PILLOW_PROCEDURAL = "pillow_procedural"


class ImageStyle(enum.Enum):
    """Pre-defined style presets."""
    PHOTOREALISTIC = "photorealistic"
    DIGITAL_ART = "digital_art"
    LOGO = "logo"
    ICON = "icon"
    ILLUSTRATION = "illustration"
    WATERCOLOR = "watercolor"
    PIXEL_ART = "pixel_art"
    SKETCH = "sketch"
    MINIMALIST = "minimalist"
    THREE_D_RENDER = "3d_render"


class ImageFormat(enum.Enum):
    """Output image formats."""
    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp"


class GenerationStatus(enum.Enum):
    """Status of an image generation request."""
    QUEUED = "queued"
    GENERATING = "generating"
    COMPLETE = "complete"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ImageRequest:
    """Describes a single image generation request."""
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    prompt: str = ""
    negative_prompt: str = ""
    width: int = 1024
    height: int = 1024
    style: ImageStyle = ImageStyle.DIGITAL_ART
    output_format: ImageFormat = ImageFormat.PNG
    num_inference_steps: int = 30
    guidance_scale: float = 7.5
    seed: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "width": self.width,
            "height": self.height,
            "style": self.style.value,
            "output_format": self.output_format.value,
            "num_inference_steps": self.num_inference_steps,
            "guidance_scale": self.guidance_scale,
            "seed": self.seed,
            "metadata": self.metadata,
        }


@dataclass
class ImageResult:
    """Result of an image generation request."""
    request_id: str = ""
    status: GenerationStatus = GenerationStatus.QUEUED
    backend_used: ImageBackend = ImageBackend.PILLOW_PROCEDURAL
    file_path: Optional[str] = None
    width: int = 0
    height: int = 0
    generation_time_seconds: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status.value,
            "backend_used": self.backend_used.value,
            "file_path": self.file_path,
            "width": self.width,
            "height": self.height,
            "generation_time_seconds": self.generation_time_seconds,
            "error": self.error,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Style presets — negative prompts and guidance per style
# ---------------------------------------------------------------------------

_STYLE_PRESETS: Dict[ImageStyle, Dict[str, Any]] = {
    ImageStyle.PHOTOREALISTIC: {
        "prompt_suffix": ", photorealistic, 8k, detailed, professional photography",
        "negative": "cartoon, illustration, painting, drawing, anime",
        "guidance": 7.5,
    },
    ImageStyle.DIGITAL_ART: {
        "prompt_suffix": ", digital art, vibrant colors, detailed",
        "negative": "blurry, low quality, distorted",
        "guidance": 7.5,
    },
    ImageStyle.LOGO: {
        "prompt_suffix": ", logo design, clean lines, professional, vector style, centered, white background",
        "negative": "photorealistic, blurry, complex background, text",
        "guidance": 9.0,
    },
    ImageStyle.ICON: {
        "prompt_suffix": ", app icon, clean, flat design, centered",
        "negative": "blurry, complex, text, photorealistic",
        "guidance": 9.0,
    },
    ImageStyle.ILLUSTRATION: {
        "prompt_suffix": ", illustration, artistic, detailed line work",
        "negative": "photorealistic, blurry",
        "guidance": 7.0,
    },
    ImageStyle.WATERCOLOR: {
        "prompt_suffix": ", watercolor painting, soft edges, artistic",
        "negative": "digital, sharp, photorealistic",
        "guidance": 6.5,
    },
    ImageStyle.PIXEL_ART: {
        "prompt_suffix": ", pixel art, retro, 16-bit style",
        "negative": "photorealistic, smooth, high resolution",
        "guidance": 8.0,
    },
    ImageStyle.SKETCH: {
        "prompt_suffix": ", pencil sketch, hand drawn, detailed linework",
        "negative": "color, photorealistic, digital",
        "guidance": 7.0,
    },
    ImageStyle.MINIMALIST: {
        "prompt_suffix": ", minimalist design, clean, simple, modern",
        "negative": "complex, detailed, cluttered, busy",
        "guidance": 8.5,
    },
    ImageStyle.THREE_D_RENDER: {
        "prompt_suffix": ", 3D render, octane render, studio lighting",
        "negative": "flat, 2D, blurry, low quality",
        "guidance": 7.5,
    },
}


# ---------------------------------------------------------------------------
# Backend implementations
# ---------------------------------------------------------------------------

class _PillowBackend:
    """Always-available fallback that generates branded placeholder images."""

    @staticmethod
    def available() -> bool:
        try:
            from PIL import Image, ImageDraw, ImageFont  # noqa: F401
            return True
        except ImportError:
            return False

    @staticmethod
    def generate(request: ImageRequest, output_path: str) -> ImageResult:
        start = time.time()
        try:
            from PIL import Image, ImageDraw

            img = Image.new("RGB", (request.width, request.height), color=(30, 30, 40))
            draw = ImageDraw.Draw(img)

            # Draw a gradient background
            for y in range(request.height):
                r = int(30 + (y / request.height) * 40)
                g = int(30 + (y / request.height) * 20)
                b = int(40 + (y / request.height) * 60)
                draw.line([(0, y), (request.width, y)], fill=(r, g, b))

            # Draw centered text with the prompt
            prompt_text = request.prompt[:60] + ("..." if len(request.prompt) > 60 else "")
            # Use default font (always available)
            text_bbox = draw.textbbox((0, 0), prompt_text)
            tw = text_bbox[2] - text_bbox[0]
            th = text_bbox[3] - text_bbox[1]
            tx = (request.width - tw) // 2
            ty = (request.height - th) // 2
            draw.text((tx, ty), prompt_text, fill=(200, 200, 220))

            # Draw style badge
            badge = f"[{request.style.value}]"
            draw.text((10, 10), badge, fill=(100, 180, 255))

            # Draw Murphy branding
            branding = "Murphy System — Image Generation"
            brand_bbox = draw.textbbox((0, 0), branding)
            bw = brand_bbox[2] - brand_bbox[0]
            draw.text(
                (request.width - bw - 10, request.height - 20),
                branding,
                fill=(80, 80, 100),
            )

            fmt = request.output_format.value.upper()
            if fmt == "JPEG":
                img = img.convert("RGB")
            img.save(output_path, format=fmt if fmt != "JPEG" else "JPEG")

            return ImageResult(
                request_id=request.request_id,
                status=GenerationStatus.COMPLETE,
                backend_used=ImageBackend.PILLOW_PROCEDURAL,
                file_path=output_path,
                width=request.width,
                height=request.height,
                generation_time_seconds=time.time() - start,
                metadata={"mode": "procedural_placeholder"},
            )
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return ImageResult(
                request_id=request.request_id,
                status=GenerationStatus.FAILED,
                backend_used=ImageBackend.PILLOW_PROCEDURAL,
                error=str(exc),
                generation_time_seconds=time.time() - start,
            )


class _StableDiffusionBackend:
    """Stable Diffusion backend using HuggingFace diffusers (open-source, free)."""

    _pipe = None
    _model_id: Optional[str] = None
    _lock = threading.Lock()

    @classmethod
    def available(cls, model_variant: str = "xl") -> bool:
        try:
            import diffusers  # noqa: F401
            import torch  # noqa: F401
            return True
        except ImportError:
            return False

    @classmethod
    def _load_pipeline(cls, model_variant: str = "xl"):
        with cls._lock:
            target_model = (
                "stabilityai/stable-diffusion-xl-base-1.0"
                if model_variant == "xl"
                else "stable-diffusion-v1-5/stable-diffusion-v1-5"
            )
            if cls._pipe is not None and cls._model_id == target_model:
                return cls._pipe

            import torch
            from diffusers import StableDiffusionPipeline, StableDiffusionXLPipeline

            device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.float16 if device == "cuda" else torch.float32

            if model_variant == "xl":
                pipe = StableDiffusionXLPipeline.from_pretrained(
                    target_model, torch_dtype=dtype
                )
            else:
                pipe = StableDiffusionPipeline.from_pretrained(
                    target_model, torch_dtype=dtype
                )

            pipe = pipe.to(device)

            # Enable memory optimizations when available
            if device == "cuda":
                try:
                    pipe.enable_xformers_memory_efficient_attention()
                except Exception as exc:
                    logger.debug("Suppressed exception: %s", exc)
                    pass

            cls._pipe = pipe
            cls._model_id = target_model
            return pipe

    @classmethod
    def generate(cls, request: ImageRequest, output_path: str, model_variant: str = "xl") -> ImageResult:
        start = time.time()
        try:
            pipe = cls._load_pipeline(model_variant)

            preset = _STYLE_PRESETS.get(request.style, {})
            full_prompt = request.prompt + preset.get("prompt_suffix", "")
            neg_prompt = request.negative_prompt or preset.get("negative", "")
            guidance = preset.get("guidance", request.guidance_scale)

            import torch
            generator = None
            if request.seed is not None:
                generator = torch.Generator(device=pipe.device).manual_seed(request.seed)

            image = pipe(
                prompt=full_prompt,
                negative_prompt=neg_prompt,
                width=request.width,
                height=request.height,
                num_inference_steps=request.num_inference_steps,
                guidance_scale=guidance,
                generator=generator,
            ).images[0]

            fmt = request.output_format.value.upper()
            image.save(output_path, format=fmt if fmt != "JPEG" else "JPEG")

            backend = (
                ImageBackend.STABLE_DIFFUSION_XL
                if model_variant == "xl"
                else ImageBackend.STABLE_DIFFUSION_15
            )

            return ImageResult(
                request_id=request.request_id,
                status=GenerationStatus.COMPLETE,
                backend_used=backend,
                file_path=output_path,
                width=request.width,
                height=request.height,
                generation_time_seconds=time.time() - start,
                metadata={
                    "model": cls._model_id,
                    "prompt": full_prompt,
                    "seed": request.seed,
                },
            )
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return ImageResult(
                request_id=request.request_id,
                status=GenerationStatus.FAILED,
                backend_used=ImageBackend.STABLE_DIFFUSION_XL,
                error=str(exc),
                generation_time_seconds=time.time() - start,
            )


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class ImageGenerationEngine:
    """
    Open-source image generation engine for Murphy System.

    Automatically selects the highest-quality available backend:
    1. Stable Diffusion XL (if torch + diffusers + GPU available)
    2. Stable Diffusion 1.5 (if torch + diffusers available, lower VRAM)
    3. Pillow procedural (always available — generates branded placeholders)

    All backends are 100% open-source and free. No API keys required.

    Usage::

        engine = ImageGenerationEngine()
        result = engine.generate(ImageRequest(
            prompt="A futuristic AI control room",
            style=ImageStyle.DIGITAL_ART,
        ))
        logger.info(result.file_path)
    """

    # Maximum dimensions to prevent memory exhaustion
    MAX_DIMENSION = 2048
    MAX_HISTORY = 500

    def __init__(self, output_dir: Optional[str] = None):
        self._lock = threading.Lock()
        self._output_dir = Path(output_dir or ".murphy_persistence/images")
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._history: List[Dict[str, Any]] = []
        self._generation_count = 0
        self._error_count = 0

        # Detect available backends
        self._backends = self._detect_backends()
        self._active_backend = self._select_best_backend()

        logger.info(
            "ImageGenerationEngine initialized (backend=%s, available=%s)",
            self._active_backend.value,
            [b.value for b in self._backends],
        )

    # -- backend detection --------------------------------------------------

    def _detect_backends(self) -> List[ImageBackend]:
        available = []
        if _StableDiffusionBackend.available("xl"):
            available.append(ImageBackend.STABLE_DIFFUSION_XL)
            available.append(ImageBackend.STABLE_DIFFUSION_15)
        if _PillowBackend.available():
            available.append(ImageBackend.PILLOW_PROCEDURAL)
        return available

    def _select_best_backend(self) -> ImageBackend:
        for preferred in [
            ImageBackend.STABLE_DIFFUSION_XL,
            ImageBackend.STABLE_DIFFUSION_15,
            ImageBackend.PILLOW_PROCEDURAL,
        ]:
            if preferred in self._backends:
                return preferred
        return ImageBackend.PILLOW_PROCEDURAL

    # -- public interface ---------------------------------------------------

    def generate(self, request: ImageRequest) -> ImageResult:
        """Generate an image from a text prompt."""
        # Clamp dimensions
        request.width = min(max(request.width, 64), self.MAX_DIMENSION)
        request.height = min(max(request.height, 64), self.MAX_DIMENSION)

        ext = request.output_format.value
        filename = f"{request.request_id}.{ext}"
        output_path = str(self._output_dir / filename)

        result = self._dispatch(request, output_path)

        with self._lock:
            self._generation_count += 1
            if result.status == GenerationStatus.FAILED:
                self._error_count += 1
            if len(self._history) >= self.MAX_HISTORY:
                self._history.pop(0)
            capped_append(self._history, result.to_dict())

        return result

    def generate_batch(self, requests: List[ImageRequest]) -> List[ImageResult]:
        """Generate multiple images."""
        return [self.generate(req) for req in requests]

    def get_available_backends(self) -> List[str]:
        """Return list of available backend names."""
        return [b.value for b in self._backends]

    def get_active_backend(self) -> str:
        """Return the currently active backend."""
        return self._active_backend.value

    def get_available_styles(self) -> List[str]:
        """Return list of supported style presets."""
        return [s.value for s in ImageStyle]

    def get_statistics(self) -> Dict[str, Any]:
        """Return generation statistics."""
        with self._lock:
            return {
                "total_generated": self._generation_count,
                "error_count": self._error_count,
                "active_backend": self._active_backend.value,
                "available_backends": [b.value for b in self._backends],
                "output_directory": str(self._output_dir),
                "history_size": len(self._history),
            }

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent generation history."""
        with self._lock:
            return list(self._history[-limit:])

    # -- internal -----------------------------------------------------------

    def _dispatch(self, request: ImageRequest, output_path: str) -> ImageResult:
        backend = self._active_backend

        if backend == ImageBackend.STABLE_DIFFUSION_XL:
            result = _StableDiffusionBackend.generate(request, output_path, "xl")
            if result.status == GenerationStatus.FAILED:
                # Fallback to SD 1.5
                result = _StableDiffusionBackend.generate(request, output_path, "1.5")
            if result.status == GenerationStatus.FAILED:
                # Final fallback to Pillow
                result = _PillowBackend.generate(request, output_path)
        elif backend == ImageBackend.STABLE_DIFFUSION_15:
            result = _StableDiffusionBackend.generate(request, output_path, "1.5")
            if result.status == GenerationStatus.FAILED:
                result = _PillowBackend.generate(request, output_path)
        else:
            result = _PillowBackend.generate(request, output_path)

        return result
