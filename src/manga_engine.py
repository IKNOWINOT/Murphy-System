"""
manga_engine.py — Murphy Manga Generator
=========================================
PATCH-065: Full manga generation with consistent characters.

Flow:
  1. User provides story prompt + character descriptions
  2. LLM generates panel-by-panel script (JSON)
  3. Character reference images generated via FLUX.1-schnell
  4. Each panel rendered using FLUX.1-kontext-pro (image conditioning = consistent chars)
  5. Returns structured manga data for frontend renderer

Copyright © 2020 Inoni LLC · Creator: Corey Post · BSL 1.1
"""

import os
import json
import time
import asyncio
import aiohttp
import logging
from typing import Optional

logger = logging.getLogger(__name__)

TOGETHER_API_KEY = os.environ.get("TOGETHER_API_KEY", "")
TOGETHER_BASE = "https://api.together.xyz/v1"

FLUX_FAST  = "black-forest-labs/FLUX.1-schnell"       # fast, for character sheets
FLUX_KONTEXT = "black-forest-labs/FLUX.1-kontext-pro"  # consistent, for panels

MANGA_STYLE_PREFIX = (
    "manga panel, black and white ink illustration, hand-drawn japanese comic art, "
    "high contrast, cross-hatching shadows, expressive faces, dynamic composition, "
    "professional manga artist quality, "
)

PANEL_SCRIPT_SYSTEM = """You are a manga story scripter. Given a story prompt and character list, 
produce a manga script as JSON. Output ONLY valid JSON, no markdown.

Format:
{
  "title": "Story title",
  "genre": "action/romance/mystery/etc",
  "pages": [
    {
      "page_number": 1,
      "panels": [
        {
          "panel_id": "p1_pan1",
          "layout": "full" | "half" | "third" | "quarter",
          "scene": "Brief scene description for image generation (max 60 words)",
          "characters": ["CharName1", "CharName2"],
          "dialogue": [
            {"character": "CharName1", "text": "Dialogue text", "type": "speech" | "thought" | "narration"}
          ],
          "sound_effects": ["BOOM", "CRASH"],
          "mood": "tense/calm/excited/sad/dramatic"
        }
      ]
    }
  ]
}

Rules:
- Generate exactly 3 pages with 3-5 panels each (10-15 panels total)
- Make dialogue short and punchy (manga style)
- Sound effects are in ALL CAPS
- scene descriptions must mention the character by name and their visual appearance
- Keep consistent character traits across all panels
"""


async def _together_image(session, prompt: str, image_url: Optional[str] = None,
                           width=512, height=512, steps=None) -> Optional[str]:
    """Generate image via Together.ai. Returns URL or None."""
    headers = {"Authorization": f"Bearer {TOGETHER_API_KEY}", "Content-Type": "application/json"}
    
    if image_url:
        # Kontext: character-conditioned generation
        model = FLUX_KONTEXT
        payload = {
            "model": model,
            "prompt": prompt,
            "image_url": image_url,
            "width": width,
            "height": height,
            "steps": steps or 20,
            "n": 1,
            "response_format": "url",
        }
    else:
        # Schnell: fresh generation (character sheets)
        model = FLUX_FAST
        payload = {
            "model": model,
            "prompt": prompt,
            "width": width,
            "height": height,
            "steps": steps or 4,
            "n": 1,
            "response_format": "url",
        }
    
    try:
        async with session.post(
            f"{TOGETHER_BASE}/images/generations",
            headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=120)
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.warning(f"Image gen failed {resp.status}: {text[:200]}")
                return None
            data = await resp.json()
            items = data.get("data", [])
            if items:
                return items[0].get("url")
    except Exception as e:
        logger.error(f"Image gen error: {e}")
    return None


async def _generate_character_sheets(session, characters: list[dict]) -> dict:
    """Generate reference image for each character. Returns {name: url}."""
    tasks = {}
    for char in characters:
        name = char["name"]
        desc = char["description"]
        prompt = (
            MANGA_STYLE_PREFIX +
            f"character reference sheet, full body portrait of {name}: {desc}, "
            "neutral pose, clean white background, character design sheet, "
            "manga character design, detailed face and outfit"
        )
        tasks[name] = _together_image(session, prompt, width=512, height=768, steps=4)
    
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    char_urls = {}
    for name, result in zip(tasks.keys(), results):
        if isinstance(result, str):
            char_urls[name] = result
            logger.info(f"Character sheet generated: {name} -> {result[:60]}")
        else:
            logger.warning(f"Character sheet failed for {name}: {result}")
            char_urls[name] = None
    return char_urls


async def _generate_panel_image(session, panel: dict, char_urls: dict) -> Optional[str]:
    """Generate a single panel image with character consistency."""
    scene = panel.get("scene", "")
    panel_chars = panel.get("characters", [])
    mood = panel.get("mood", "dramatic")
    
    # Build prompt with character descriptions
    prompt = MANGA_STYLE_PREFIX + f"{mood} mood, {scene}"
    
    # Add mood modifiers
    mood_map = {
        "tense": "high contrast, dramatic shadows, intense expressions",
        "excited": "dynamic lines, speed lines, energetic composition",
        "sad": "soft lighting, downcast expressions, rain or tears",
        "calm": "balanced composition, soft lines, peaceful atmosphere",
        "dramatic": "extreme angles, bold shadows, cinematic composition",
    }
    prompt += f", {mood_map.get(mood, 'dramatic composition')}"
    
    # Find best character reference image to use
    ref_url = None
    for char_name in panel_chars:
        if char_name in char_urls and char_urls[char_name]:
            ref_url = char_urls[char_name]
            break
    
    if ref_url:
        # Use kontext for character consistency
        return await _together_image(session, prompt, image_url=ref_url, 
                                      width=512, height=512, steps=20)
    else:
        # Fallback: plain generation
        return await _together_image(session, prompt, width=512, height=512, steps=4)


async def generate_panel_script(story_prompt: str, characters: list[dict]) -> dict:
    """Use LLM to generate panel-by-panel script."""
    from src.llm_provider import chat_completion
    
    char_desc = "\n".join(
        f"- {c['name']}: {c['description']}" for c in characters
    )
    
    user_msg = f"""Story: {story_prompt}

Characters:
{char_desc}

Generate a 3-page manga script in JSON format."""
    
    response = await asyncio.to_thread(
        chat_completion,
        messages=[
            {"role": "system", "content": PANEL_SCRIPT_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=2048,
        temperature=0.8,
    )
    
    content = response.get("content", "")
    # Strip markdown fences if present
    import re
    content = re.sub(r"^```(?:json)?\s*", "", content.strip(), flags=re.IGNORECASE)
    content = re.sub(r"\s*```$", "", content.strip())
    
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Script parse error: {e}\nContent: {content[:300]}")
        raise ValueError(f"Script generation failed: {e}")


async def generate_manga(story_prompt: str, characters: list[dict]) -> dict:
    """
    Full manga generation pipeline.
    
    Args:
        story_prompt: The story idea (e.g. "A young ninja discovers he can control time")
        characters: List of {name, description} dicts
    
    Returns:
        {
            "title": str,
            "genre": str,
            "characters": {name: {"description": str, "ref_url": str}},
            "pages": [...with panel data + image_url for each panel...]
        }
    """
    logger.info(f"Starting manga generation: {story_prompt[:60]}")
    
    # Step 1: Generate panel script via LLM
    logger.info("Generating panel script...")
    script = await generate_panel_script(story_prompt, characters)
    
    connector = aiohttp.TCPConnector(limit=4)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Step 2: Generate character reference sheets
        logger.info("Generating character sheets...")
        char_urls = await _generate_character_sheets(session, characters)
        
        # Step 3: Generate panel images (with concurrency limit to avoid rate limiting)
        logger.info("Generating panel images...")
        all_panels = []
        for page in script.get("pages", []):
            for panel in page.get("panels", []):
                all_panels.append((page["page_number"], panel))
        
        # Process in batches of 3 to avoid rate limits
        panel_images = {}
        batch_size = 3
        for i in range(0, len(all_panels), batch_size):
            batch = all_panels[i:i+batch_size]
            tasks = [
                _generate_panel_image(session, panel, char_urls)
                for _, panel in batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for (_, panel), result in zip(batch, results):
                pid = panel.get("panel_id", f"panel_{i}")
                panel_images[pid] = result if isinstance(result, str) else None
            # Small delay between batches
            if i + batch_size < len(all_panels):
                await asyncio.sleep(1)
    
    # Step 4: Assemble final result
    for page in script.get("pages", []):
        for panel in page.get("panels", []):
            pid = panel.get("panel_id", "")
            panel["image_url"] = panel_images.get(pid)
    
    # Build character info with ref images
    char_info = {}
    for char in characters:
        name = char["name"]
        char_info[name] = {
            "description": char["description"],
            "ref_url": char_urls.get(name),
        }
    
    script["characters"] = char_info
    script["story_prompt"] = story_prompt
    logger.info(f"Manga generation complete: {script.get('title', '?')}")
    return script
