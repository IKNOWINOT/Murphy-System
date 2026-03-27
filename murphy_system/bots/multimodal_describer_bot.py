"""Utilities for describing multimodal inputs in verbose natural language."""
from __future__ import annotations

from typing import Any, List

import numpy as np


def describe_input(data: Any, type: str) -> List[str]:
    """Route raw multimodal data to the appropriate describer.

    Parameters
    ----------
    data:
        The raw input payload.  Expected shapes depend on ``type``.
    type:
        One of ``"image"``, ``"audio"``, ``"video"`` or ``"text"``.

    Returns
    -------
    list[str]
        A list of verbose natural-language descriptions.
    """

    if type == "image":
        return describe_image_pixels(data)
    if type == "audio":
        return describe_audio_frames(data)
    if type == "video":
        return describe_video_frames(data)
    if type == "text":
        return [f"Text snippet: {data}"]
    raise ValueError(f"Unsupported multimodal type: {type}")


def describe_image_pixels(image_data: np.ndarray, threshold: int = 256) -> List[str]:
    """Describe the RGB value of each pixel in an image.

    The description is truncated once ``threshold`` entries have been produced
    to avoid unbounded output for large images.
    """

    height, width, _ = image_data.shape
    descriptions: List[str] = []
    for y in range(height):
        for x in range(width):
            r, g, b = image_data[y, x]
            descriptions.append(
                f"Pixel at x {x} y {y} has red {int(r)}, green {int(g)}, blue {int(b)}"
            )
            if len(descriptions) >= threshold:
                descriptions.append(f"[...truncated after {threshold} pixels]")
                return descriptions
    return descriptions


def describe_audio_frames(
    audio_data: np.ndarray, *, sample_rate: int = 44100, step: int = 1000
) -> List[str]:
    """Quantise waveform samples into natural-language descriptions."""

    descriptions: List[str] = []
    for i in range(0, len(audio_data), step):
        sample = audio_data[i]
        time_ms = int((i / sample_rate) * 1000)
        descriptions.append(f"At {time_ms} ms the audio sample amplitude is {int(sample)}")
    return descriptions


def describe_video_frames(
    video_frames: List[np.ndarray], *, frame_rate: int = 30
) -> List[str]:
    """Describe a sequence of video frames.

    Each frame is tokenised using :func:`describe_image_pixels` with a small
    threshold to keep output concise.
    """

    descriptions: List[str] = []
    for i, frame in enumerate(video_frames):
        time_sec = i / frame_rate
        pixel_desc = "; ".join(describe_image_pixels(frame, threshold=10))
        descriptions.append(f"Frame at time {round(time_sec, 2)} seconds: {pixel_desc}")
    return descriptions
