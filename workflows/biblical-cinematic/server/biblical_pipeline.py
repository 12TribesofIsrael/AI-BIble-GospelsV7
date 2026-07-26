"""
Biblical Cinematic v9 — Direct Python Pipeline (no n8n)

Replaces the n8n webhook with direct API calls:
  Claude AI → scene image prompts
  FLUX → images
  Kling → video clips
  JSON2Video → final MP4 with ElevenLabs narration + subtitles

Mount in app.py:
    from biblical_pipeline import biblical_router
    app.include_router(biblical_router, prefix="/v9")
"""

import json
import os
import re
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from rate_limit import limiter, EXPENSIVE_LIMIT, MEDIUM_LIMIT
from usage import log_event
from style_packs import (
    DEFAULT_STYLE, ETHNICITY_RULES, apply_subtitle_style, resolve_style, style_list,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
FAL_KEY = os.getenv("FAL_KEY")
JSON2VIDEO_API_KEY = os.getenv("JSON2VIDEO_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

FLUX_URL = "https://fal.run/fal-ai/flux-pro/v1.1"
JSON2VIDEO_URL = "https://api.json2video.com/v2/movies"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

KLING_MODELS = {
    "v1.6": {"url": "https://fal.run/fal-ai/kling-video/v1.6/standard/image-to-video", "duration": "10"},
    "v2.1": {"url": "https://fal.run/fal-ai/kling-video/v2.1/standard/image-to-video", "duration": "10"},
    "v3.0": {"url": "https://fal.run/fal-ai/kling-video/v3/standard/image-to-video", "duration": "15"},
    "v3.0-pro": {"url": "https://fal.run/fal-ai/kling-video/v3/pro/image-to-video", "duration": "15"},
    "o3": {"url": "https://fal.run/fal-ai/kling-video/o3/standard/image-to-video", "duration": "15"},
    "o3-pro": {"url": "https://fal.run/fal-ai/kling-video/o3/pro/image-to-video", "duration": "15"},
}

# fal's FLUX uses `portrait_16_9` as its label for a 9:16 (tall) canvas — not a typo.
ASPECT_RATIOS = {
    "16:9": {"flux": "landscape_16_9", "kling": "16:9", "j2v": "full-hd",
             "sub_font_size": 80, "sub_max_words": 4},
    "1:1":  {"flux": "square_hd",      "kling": "1:1",  "j2v": "instagram-feed",
             "sub_font_size": 70, "sub_max_words": 3},
    "9:16": {"flux": "portrait_16_9",  "kling": "9:16", "j2v": "instagram-story",
             "sub_font_size": 64, "sub_max_words": 3},
}

VOICE_ID = "NgBYGKDDq2Z8Hnhatgma"
VOICE_SPEED = 0.9

# Voice catalog exposed to the UI via GET /v9/api/voices.
# Order matters — first entry shown first in the picker. Keep in sync with
# workflows/custom-script/router.py and the README voice table.
# Test-rendered against JSON2Video on 2026-07-25. JSON2Video only accepts voice
# ids on its own supported list — an unsupported id fails the render AFTER all the
# FLUX + Kling money is spent, so unsupported entries are marked, not silently kept.
VOICES = [
    {"id": "NgBYGKDDq2Z8Hnhatgma", "name": "Pro Narrator (default)"},
    {"id": "onwK4e9ZLuTAKqWW03F9", "name": "Daniel Steady Broadcaster"},
    {"id": "6OzrBCQf8cjERkYgzSg8", "name": "Young Jamal"},
    {"id": "T4sLxEj9xEGMREO21ACw", "name": "Tommy Israel (unsupported by JSON2Video)"},
    {"id": "C8OtYB0OTgD7K0YWkg7y", "name": "William J"},
    {"id": "nJvj5shg2xu1GKGxqfkE", "name": "Hakeem"},
    {"id": "CVRACyqNcQefTlxMj9b", "name": "Lamar Lincoln (unsupported by JSON2Video)"},
    {"id": "h2sm0NbeIZXHBzJOMYcQ", "name": "Natasha Smooth Narrator (untested)"},
    {"id": "OOk3INdXVLRmSaQoAX9D", "name": "Alicia Calm Storyteller (unsupported by JSON2Video)"},
    {"id": "6aDn1KB0hjpdcocrUkmq", "name": "Tiffany Warm Conversational (untested)"},
]
def resolve_voice(voice_id):
    """Return the supplied voice id (catalog or user-entered) or the default
    if blank. We trust the caller — UI lets users paste in any ElevenLabs id,
    so we cannot whitelist against VOICES."""
    if isinstance(voice_id, str):
        cleaned = voice_id.strip()
        if cleaned:
            return cleaned
    return VOICE_ID

# Auto-split threshold: if total narration exceeds this many words, split into multiple renders
# Based on render history, 865 words (325s) succeeded at 662s render time; 1467 words always times out
MAX_WORDS_PER_RENDER = 900

# Target words per scene to match Kling clip duration (avoids looping)
# At ~135 effective WPM: 10s clip = ~22 words, 15s clip = ~34 words
WORDS_PER_SCENE = {"v1.6": 22, "v2.1": 22, "v3.0": 34, "v3.0-pro": 34, "o3": 34, "o3-pro": 34}

# Persistent state + history files — survive container restarts and redeploys on Modal (uses /data volume).
# Without /data, these lived inside the code mount and got wiped on every deploy.
STATE_DIR = Path("/data") if Path("/data").exists() else Path(__file__).parent
STATE_FILE = STATE_DIR / "pipeline_state.json"
HISTORY_FILE = STATE_DIR / "render_history.json"
# Disk-backed stop flag — shared across Modal web containers via /data volume.
# Fixes the case where /api/stop lands on a different container than the worker.
STOP_FILE = STATE_DIR / "biblical_stop.flag"
_LEGACY_HISTORY = Path(__file__).parent / "render_history.json"
if not HISTORY_FILE.exists() and _LEGACY_HISTORY.exists():
    # One-time migration: seed the persistent history from the committed file on first run.
    try:
        HISTORY_FILE.write_text(_LEGACY_HISTORY.read_text(encoding="utf-8"), encoding="utf-8")
    except Exception as e:
        print(f"[history] Failed to seed from legacy file: {e}")

# ---------------------------------------------------------------------------
# Shared pipeline state
# ---------------------------------------------------------------------------
pipeline_state = {
    "phase": "idle",
    "scenes": None,
    "current_scene": 0,
    "total_scenes": 0,
    "message": "",
    "video_url": None,
    "video_urls": [],
    "error": None,
    "processed": [],
    "book": "",
    "chapter": "",
    "model": "v1.6",
    "aspect_ratio": "16:9",
    "voice_id": VOICE_ID,
    # Style pack id — "cinematic" (default) | "epic" (High Cinematic, adults) | "kids" (animation).
    # Read by generate_image / generate_video / build_json2video_payload, same as aspect_ratio.
    "style": DEFAULT_STYLE,
    # When an admin kicks off a render for a specific waitlist invitee, this holds
    # the render id linked to their row (so save_to_history reuses it and the admin
    # dashboard can match the live render back to the user). None for ad-hoc /app renders.
    "render_id": None,
    # Pending fal.ai queue request persisted across container restarts — prevents
    # duplicate-charge ghosts when a long-running Kling clip is interrupted mid-poll.
    # {"kind": "flux"|"kling", "queue_url": str, "status_url": str, "response_url": str, "request_id": str}
    "pending_fal": None,
}

lock = threading.Lock()
stop_requested = threading.Event()


def is_stop_requested() -> bool:
    # Call via the class so the textual form doesn't match a future
    # replace-all of "stop_requested.is_set()" (which is what broke this originally).
    return threading.Event.is_set(stop_requested) or STOP_FILE.exists()


def request_stop() -> None:
    threading.Event.set(stop_requested)
    try:
        STOP_FILE.write_text("1")
    except Exception as e:
        print(f"[stop] Failed to write flag: {e}")


def clear_stop() -> None:
    threading.Event.clear(stop_requested)
    try:
        STOP_FILE.unlink(missing_ok=True)
    except Exception as e:
        print(f"[stop] Failed to clear flag: {e}")


def save_state():
    """Persist pipeline state to disk so it survives container restarts."""
    try:
        data = json.dumps(pipeline_state, default=str)
        # Write + fsync to ensure data hits the volume before container can die
        fd = os.open(str(STATE_FILE), os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
        os.write(fd, data.encode())
        os.fsync(fd)
        os.close(fd)
    except Exception as e:
        print(f"[state] Failed to save: {e}")


def load_state():
    """Restore pipeline state from disk on startup."""
    global pipeline_state
    if STATE_FILE.exists():
        try:
            saved = json.loads(STATE_FILE.read_text())
            # If it was mid-render, mark as error so user can retry
            if saved.get("phase") in ("generating_media", "rendering", "generating_scenes"):
                saved["phase"] = "error"
                saved["error"] = "Container restarted mid-render. Use Retry to resume from where it left off."
                saved["message"] = f"Interrupted — {len(saved.get('processed', []))} scenes completed. Use Retry to resume."
            pipeline_state.update(saved)
            print(f"[state] Restored: {saved.get('phase')}, {len(saved.get('processed', []))} scenes processed")
        except Exception as e:
            print(f"[state] Failed to load: {e}")


# Restore state on module load
load_state()
# Clear any stale stop flag left behind by a crashed/killed container.
clear_stop()

# ---------------------------------------------------------------------------
# Claude prompt — image prompts only (narration is word-for-word scripture)
# ---------------------------------------------------------------------------
def image_prompt_system(pack) -> str:
    """Build the Claude system prompt for a given style pack.

    The `cinematic` pack reproduces the engine's original prompt verbatim — it is
    the regression baseline. `epic` and `kids` swap the visual language while the
    ethnicity rules and the no-text rule stay fixed for every pack.
    """
    extra = f"\n{pack['extra_guidelines']}" if pack["extra_guidelines"] else ""
    narration_note = f"\n\n{pack['narration_note']}" if pack["narration_note"] else ""
    return f"""You are a {pack['director_role']} for AI Bible Gospels — a channel revealing the hidden identity of the 12 Tribes of Israel through Scripture, history, and prophecy.

BRAND STYLE:
{pack['brand_style']}

{ETHNICITY_RULES}{pack['ethnicity_extra']}

YOUR TASK:
You will receive scripture text that has been split into narration chunks. The narration is FINAL — do NOT modify it.

For each narration chunk, generate ONLY visual descriptions:
1. **imagePrompt**: Extremely detailed visual description for AI image generation. Include character ethnicity per rules above, clothing details, setting, camera angle, atmosphere. ALWAYS end with "{pack['image_suffix']}". {pack['forbidden_line']} NEVER include text, words, letters, or titles in the image prompt — AI misspells them.
2. **motion**: {pack['motion_note']}
3. **lighting**: {pack['lighting_note']}

GUIDELINES:
- Vary camera angles: close-up → wide shot → medium → aerial → over-shoulder
- Vary lighting: {pack['lighting_examples']}
- Each scene should be visually distinct from the one before it{extra}
- NEVER put text, words, letters, or titles in image prompts
- ANIMATION SAFETY: these stills get animated afterwards, and small ambiguous shapes
  get reinvented into modern objects when they move. Do NOT describe large scatters of
  tiny distant figures, animals, or objects strung along a road, path, or ridge line.
  Keep distant elements few, large enough to read, and clearly identifiable; put
  crowds and flocks in the mid-ground as a readable mass rather than as a line of
  small dots receding into the distance{narration_note}

INTRO & OUTRO SCENES:
In addition to the scripture scenes, you MUST generate:
- **FIRST scene (Intro)**: A cinematic 20-40 word opening narration that sets the stage for the scripture passage. If a book and chapter are provided, reference them (e.g. "In the book of Genesis, chapter one, the Most High speaks all of creation into existence..."). Include imagePrompt, motion, lighting for a dramatic establishing shot. Mark it with "type": "intro".
- **LAST scene (Outro)**: A 20-40 word closing narration that wraps up the passage with a call to action for the AI Bible Gospels channel (e.g. "Subscribe to AI Bible Gospels for more revelations of Scripture, history, and prophecy. Like, share, and stay blessed."). Include imagePrompt, motion, lighting for a cinematic closing shot. Mark it with "type": "outro".
- All middle scenes (the scripture narration) should have "type": "scripture".

Return ONLY valid JSON in this exact format:
{{
  "scenes": [
    {{
      "type": "intro",
      "narration": "your intro narration here...",
      "imagePrompt": "...",
      "motion": "...",
      "lighting": "..."
    }},
    {{
      "type": "scripture",
      "imagePrompt": "...",
      "motion": "...",
      "lighting": "..."
    }},
    {{
      "type": "outro",
      "narration": "your outro narration here...",
      "imagePrompt": "...",
      "motion": "...",
      "lighting": "..."
    }}
  ]
}}"""


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class BiblicalGenerateInput(BaseModel):
    text: str
    model: str = "v1.6"
    aspect_ratio: str = "16:9"
    scene_count: int = 20  # legacy — ignored, scene count now auto-calculated from Kling clip duration
    book: str = ""
    chapter: str = ""
    voice_id: str = VOICE_ID
    style: str = DEFAULT_STYLE


class BiblicalScenesInput(BaseModel):
    scenes: list
    model: str = "v1.6"
    aspect_ratio: str = "16:9"
    voice_id: str = VOICE_ID
    style: str = DEFAULT_STYLE


class BiblicalFixSceneInput(BaseModel):
    scene_index: int
    scene: dict
    model: str = "v1.6"
    aspect_ratio: str = "16:9"
    voice_id: str = VOICE_ID
    style: str = DEFAULT_STYLE


class BiblicalFixScenesInput(BaseModel):
    fixes: list  # [{scene_index: int, scene: dict}, ...]
    model: str = "v1.6"
    aspect_ratio: str = "16:9"
    voice_id: str = VOICE_ID
    style: str = DEFAULT_STYLE


# ---------------------------------------------------------------------------
# Text splitting
# ---------------------------------------------------------------------------
_SECTION_METADATA_PATTERNS = [
    re.compile(r'^\s*={3,}\s*SECTION\s+\d+\s*={3,}\s*$', re.IGNORECASE),
    re.compile(r'^\s*Words:\s*\d+.*\|.*Est\.?\s*Video:.*\|.*Scenes?:\s*\d+\s*$', re.IGNORECASE),
    re.compile(r'^\s*Ready for Biblical Video Generator\s*$', re.IGNORECASE),
]


def _strip_section_metadata(text: str) -> str:
    """Remove UI-injected section headers / stats / status lines so they
    can't leak into scripture narration.

    Defensive: catches metadata regardless of which client path injected it.
    Patterns matched (one per line):
      - === SECTION N ===
      - Words: N | Est. Video: N min | Scenes: N
      - Ready for Biblical Video Generator
    """
    if not text:
        return text
    out = []
    for line in text.splitlines():
        if any(p.match(line) for p in _SECTION_METADATA_PATTERNS):
            continue
        out.append(line)
    return "\n".join(out)


def split_scripture_into_scenes(text, target_words_per_scene=30):
    """Split cleaned scripture into narration chunks at sentence boundaries.

    target_words_per_scene: aim for this many words per chunk to match Kling clip duration.
    """
    text = _strip_section_metadata(text).strip()
    words = text.split()
    total_words = len(words)

    sentences = re.split(r'(?<=[.!?;:])\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks = []
    current = []
    current_wc = 0

    for sentence in sentences:
        sw = len(sentence.split())
        current.append(sentence)
        current_wc += sw

        if current_wc >= target_words_per_scene:
            chunks.append(" ".join(current))
            current = []
            current_wc = 0

    if current:
        # Merge remainder into last chunk if it's very short (< 10 words)
        if chunks and current_wc < 10:
            chunks[-1] += " " + " ".join(current)
        else:
            chunks.append(" ".join(current))

    return chunks


# ---------------------------------------------------------------------------
# Claude — generate image prompts from narration chunks
# ---------------------------------------------------------------------------
# How many scripture scenes to request per Claude call. One giant call for a full
# chapter (75+ scenes) overflows max_tokens (truncated → invalid JSON → 500) AND
# runs past the Cloudflare proxy's ~100s limit (524 HTML page). Batching keeps each
# call's output well under the token cap and each call short. 12 scenes ≈ <2K output
# tokens, comfortably inside the 8000 cap.
PROMPT_BATCH_SIZE = 12


def _request_prompt_batch(chunks, include_intro, include_outro, book="", chapter="", style=DEFAULT_STYLE):
    """One Claude call for a slice of scripture scenes (+ intro on the first batch,
    + outro on the last). Returns the parsed scenes with word-for-word narration
    already merged onto the scripture scenes in THIS batch (localizes any miscount
    so a wrong count in one batch can't shift narration alignment in the next)."""
    numbered = "\n".join(
        f"Scene {i+1} narration: \"{chunk}\"" for i, chunk in enumerate(chunks)
    )
    context_line = ""
    if book:
        context_line = f"\n\nBOOK: {book}"
        if chapter:
            context_line += f", CHAPTER: {chapter}"

    parts = []
    breakdown = []
    if include_intro:
        parts.append("an INTRO scene")
        breakdown.append("1 intro")
    parts.append(f"imagePrompt/motion/lighting for each of these {len(chunks)} scripture scenes")
    breakdown.append(f"{len(chunks)} scripture")
    if include_outro:
        parts.append("an OUTRO scene")
        breakdown.append("1 outro")
    total = len(chunks) + (1 if include_intro else 0) + (1 if include_outro else 0)
    intro_note = "" if include_intro else "\nDo NOT generate an intro scene in this batch."
    outro_note = "" if include_outro else "\nDo NOT generate an outro scene in this batch."

    user_msg = (
        f"{image_prompt_system(resolve_style(style))}\n\n---{context_line}\n\n"
        f"Generate {', then '.join(parts)}.{intro_note}{outro_note}\n\n"
        f"Total scenes in your response: {total} ({' + '.join(breakdown)})\n\n{numbered}"
    )

    resp = requests.post(
        ANTHROPIC_URL,
        headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
        json={"model": "claude-sonnet-4-6", "max_tokens": 8000,
              "thinking": {"type": "disabled"}, "output_config": {"effort": "low"},
              "messages": [{"role": "user", "content": user_msg}]},
        timeout=300,
    )
    resp.raise_for_status()
    content = resp.json()["content"][0]["text"]
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    scenes = json.loads(content.strip())["scenes"]

    # Word-for-word narration for scripture scenes in this batch; intro/outro keep
    # Claude's own narration.
    idx = 0
    for scene in scenes:
        if scene.get("type", "scripture") == "scripture":
            scene["narration"] = chunks[idx] if idx < len(chunks) else ""
            idx += 1
    return scenes


def generate_image_prompts(narration_chunks, book="", chapter="", style=DEFAULT_STYLE):
    """Send narration chunks to Claude in bounded batches, get back
    imagePrompt/motion/lighting per scene plus a leading intro and trailing outro."""
    n = len(narration_chunks)
    if n == 0:
        return []
    all_scenes = []
    for start in range(0, n, PROMPT_BATCH_SIZE):
        batch = narration_chunks[start:start + PROMPT_BATCH_SIZE]
        include_intro = (start == 0)
        include_outro = (start + PROMPT_BATCH_SIZE >= n)
        all_scenes.extend(
            _request_prompt_batch(batch, include_intro, include_outro, book, chapter, style)
        )
    return all_scenes


# ---------------------------------------------------------------------------
# Media generation
# ---------------------------------------------------------------------------
def fal_headers():
    return {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}


# Legacy alias — the live negative prompt now comes from the active style pack.
# A kids render must NOT negative-prompt "cartoon"; that is the whole point of the pack.
NEGATIVE_PROMPT = resolve_style(DEFAULT_STYLE)["negative_prompt"]


def active_pack():
    """The style pack for the render currently in flight."""
    return resolve_style(pipeline_state.get("style", DEFAULT_STYLE))


def fal_queue_submit(sync_url, payload, kind, poll_seconds=10, max_wait_seconds=1800):
    """Submit to fal.ai's async queue endpoint and poll until completion.

    Avoids the duplicate-charge trap of the sync endpoint: long-running models like
    Kling O3 Pro can exceed any Python client timeout; fal.ai still completes and
    bills the request, so the retry path pays twice. The queue endpoint returns
    immediately, and each poll is a short GET that never times out under load.

    Persists the in-flight request to pipeline_state.pending_fal so a container
    restart mid-poll can resume the same request on next run instead of paying
    fal.ai twice for the same clip.
    """
    queue_url = sync_url.replace("https://fal.run/", "https://queue.fal.run/", 1)

    pending = pipeline_state.get("pending_fal") or {}
    if pending.get("kind") == kind and pending.get("queue_url") == queue_url:
        status_url = pending["status_url"]
        response_url = pending["response_url"]
        print(f"[fal] Resuming pending {kind} request {pending.get('request_id')}")
    else:
        submit = requests.post(queue_url, headers=fal_headers(), json=payload, timeout=60)
        submit.raise_for_status()
        job = submit.json()
        status_url = job.get("status_url")
        response_url = job.get("response_url")
        if not status_url or not response_url:
            raise RuntimeError(f"fal.ai queue missing status/response url: {job}")
        with lock:
            pipeline_state["pending_fal"] = {
                "kind": kind, "queue_url": queue_url,
                "status_url": status_url, "response_url": response_url,
                "request_id": job.get("request_id"),
            }
            save_state()

    deadline = time.time() + max_wait_seconds
    while time.time() < deadline:
        if is_stop_requested():
            raise RuntimeError("Stopped by user")
        time.sleep(poll_seconds)
        err = None
        for _ in range(3):
            try:
                s = requests.get(status_url, headers=fal_headers(), timeout=30)
                s.raise_for_status()
                err = None
                break
            except Exception as e:
                err = e
                time.sleep(2)
        if err:
            continue
        status = s.json().get("status")
        if status == "COMPLETED":
            r = requests.get(response_url, headers=fal_headers(), timeout=60)
            r.raise_for_status()
            with lock:
                pipeline_state["pending_fal"] = None
                save_state()
            return r.json()
        if status in ("FAILED", "ERROR", "CANCELLED"):
            with lock:
                pipeline_state["pending_fal"] = None
                save_state()
            raise RuntimeError(f"fal.ai queue status={status}: {s.json()}")
    # Timeout — keep pending_fal set so a retry can resume polling the same request.
    raise RuntimeError(f"fal.ai queue timed out after {max_wait_seconds}s (request_id={pending.get('request_id') or status_url})")


def generate_image(scene):
    prompt = scene["imagePrompt"]
    if scene.get("lighting"):
        prompt += f", {scene['lighting']}"
    ratio = ASPECT_RATIOS.get(pipeline_state.get("aspect_ratio", "16:9"), ASPECT_RATIOS["16:9"])
    pack = active_pack()
    # Belt-and-braces: if Claude ignored the style instruction, the suffix still lands
    # on the image prompt so FLUX renders in the right medium.
    if pack["image_suffix"].split(",")[0].strip().lower() not in prompt.lower():
        prompt += f", {pack['image_suffix']}"
    data = fal_queue_submit(FLUX_URL, {
        "prompt": prompt, "negative_prompt": pack["negative_prompt"],
        "image_size": ratio["flux"], "num_inference_steps": 28, "num_images": 1,
    }, kind="flux", poll_seconds=5, max_wait_seconds=300)
    return data["images"][0]["url"]


def generate_video(image_url, scene, model="v1.6"):
    kling = KLING_MODELS.get(model, KLING_MODELS["v1.6"])
    ratio = ASPECT_RATIOS.get(pipeline_state.get("aspect_ratio", "16:9"), ASPECT_RATIOS["16:9"])
    pack = active_pack()
    data = fal_queue_submit(kling["url"], {
        "image_url": image_url, "prompt": scene.get("motion", "Slow cinematic camera movement"),
        "duration": kling["duration"], "cfg_scale": pack["cfg_scale"],
        "negative_prompt": pack["kling_negative"],
        "aspect_ratio": ratio["kling"],
    }, kind="kling", poll_seconds=10, max_wait_seconds=1800)
    return data.get("video", {}).get("url") or data["data"]["video"]["url"]


def build_json2video_payload(scenes_data, voice_id=None, aspect_ratio="16:9", style=None):
    voice = resolve_voice(voice_id)
    ratio = ASPECT_RATIOS.get(aspect_ratio, ASPECT_RATIOS["16:9"])
    subtitle_settings = {
        "style": "classic", "font-family": "Oswald Bold", "font-size": ratio["sub_font_size"],
        "position": "bottom-center", "line-color": "#CCCCCC", "word-color": "#FFFF00",
        "outline-color": "#000000", "outline-width": 8, "shadow-color": "#000000",
        "shadow-offset": 6, "max-words-per-line": ratio["sub_max_words"],
    }
    pack = resolve_style(style) if style is not None else active_pack()
    subtitle_settings = apply_subtitle_style(subtitle_settings, pack)
    scenes = []
    for i, s in enumerate(scenes_data, 1):
        elements = [
            {"id": f"scene{i}_bg", "type": "video", "src": s["video_url"], "resize": "cover", "loop": -1, "duration": -2},
        ]
        if s.get("narration", "").strip():
            elements.append({"id": f"scene{i}_voice", "type": "voice", "text": s["narration"], "voice": voice, "model": "elevenlabs", "speed": VOICE_SPEED})
        scenes.append({"id": f"scene{i}", "comment": f"Scene {i}", "duration": "auto", "elements": elements})
    # Movie-level subtitle element — JSON2Video requires this at root, not per-scene
    movie_subtitles = {"id": "movie_subtitles", "type": "subtitles", "language": "en", "model": "default", "settings": subtitle_settings}
    return {"resolution": ratio["j2v"], "quality": "high", "elements": [movie_subtitles], "scenes": scenes}


def submit_and_poll_json2video(payload):
    resp = requests.post(JSON2VIDEO_URL, headers={"x-api-key": JSON2VIDEO_API_KEY, "Content-Type": "application/json"}, json=payload, timeout=30)
    resp.raise_for_status()
    project_id = resp.json().get("project") or resp.json().get("id")
    while True:
        time.sleep(10)
        resp = requests.get(JSON2VIDEO_URL, headers={"x-api-key": JSON2VIDEO_API_KEY}, params={"project": project_id}, timeout=30)
        resp.raise_for_status()
        movie = resp.json().get("movie", resp.json())
        status = movie.get("status", "unknown")
        with lock:
            pipeline_state["message"] = f"JSON2Video: {status}"
        if status == "done":
            return movie["url"]
        elif status in ("error", "timeout"):
            raise RuntimeError(f"Render {status}: {movie.get('message')}")


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------
def save_to_history(status="done"):
    """Append the current render to render_history.json."""
    try:
        history = json.loads(HISTORY_FILE.read_text()) if HISTORY_FILE.exists() else []
        entry = {
            # Reuse the admin-assigned render id (linked to a waitlist row) when present,
            # so the history entry, the waitlist.render_id, and the dashboard all agree.
            "id": pipeline_state.get("render_id") or datetime.now().strftime("%Y%m%d_%H%M%S"),
            "created_at": datetime.now().isoformat(),
            "book": pipeline_state.get("book", ""),
            "chapter": pipeline_state.get("chapter", ""),
            "model": pipeline_state.get("model", "v1.6"),
            "status": status,
            "scene_count": len(pipeline_state.get("scenes") or []),
            "scenes": pipeline_state.get("scenes") or [],
            "video_url": pipeline_state.get("video_url", ""),
            "video_urls": pipeline_state.get("video_urls", []),
        }
        history.append(entry)
        HISTORY_FILE.write_text(json.dumps(history, indent=2))
    except Exception as e:
        print(f"[history] Failed to save: {e}")


def get_latest_completed_render():
    """Return the most recent completed render with a usable video URL, or None.

    Used by the admin 'Send video-ready' flow to auto-pull the video URL when the
    Supabase `renders` table has nothing (it's never written by this pipeline).
    Prefers the live `video_url` if the current render just finished, then falls
    back to the newest done entry in render_history.json. History is append-only,
    so the last matching entry is the freshest.
    """
    # Freshest source: the render that just finished in this container.
    if pipeline_state.get("phase") == "done":
        live_url = (pipeline_state.get("video_url") or "").strip()
        if live_url:
            return {
                "video_url": live_url,
                "book": pipeline_state.get("book", ""),
                "chapter": pipeline_state.get("chapter", ""),
                "status": "done",
                "source": "pipeline_state",
            }
    try:
        history = json.loads(HISTORY_FILE.read_text()) if HISTORY_FILE.exists() else []
    except Exception as e:
        print(f"[history] Failed to read for latest render: {e}")
        return None
    for entry in reversed(history):
        if entry.get("status") == "done" and (entry.get("video_url") or "").strip():
            return {**entry, "source": "render_history"}
    return None


def get_render_status(render_id):
    """Return a coarse status string for a render id, or None if unknown.

    Used by the admin dashboard to show each invitee's real render state:
      - 'rendering' while it's the live in-flight render
      - 'done' / 'error' / 'stopped' from render_history once it has finished
    Checks the live pipeline first (history is only written on completion).
    """
    if not render_id:
        return None
    rid = str(render_id)
    if str(pipeline_state.get("render_id") or "") == rid:
        phase = pipeline_state.get("phase")
        if phase in ("generating_scenes", "generating_media", "rendering"):
            return "rendering"
        if phase in ("done", "error", "stopped"):
            return phase
    try:
        history = json.loads(HISTORY_FILE.read_text()) if HISTORY_FILE.exists() else []
    except Exception:
        return None
    for entry in reversed(history):
        if str(entry.get("id")) == rid:
            return entry.get("status") or "done"
    return None


def _run_chapter(text, book, chapter, model, voice_id, style=DEFAULT_STYLE):
    """Background worker: scripture text -> Claude scenes -> full media pipeline.
    Mirrors the /api/generate body so the admin 'Render chapter' button reuses
    the exact same proven path. Errors land in pipeline_state for the status bar."""
    try:
        words_target = WORDS_PER_SCENE.get(model, 30)
        narration_chunks = split_scripture_into_scenes(text, words_target)
        scenes = generate_image_prompts(narration_chunks, book, chapter)
        with lock:
            pipeline_state.update(scenes=scenes,
                                  message=f"Generated {len(scenes)} scenes — starting media pipeline...")
            save_state()
        run_pipeline(scenes, model, voice_id=voice_id)
    except Exception as e:
        with lock:
            pipeline_state.update(phase="error", error=str(e), message=f"Error: {e}")
            save_state()
        traceback.print_exc()


def start_render_for_chapter(text, book="", chapter="", model="v1.6", voice_id=None, render_id=None,
                             style=DEFAULT_STYLE):
    """Kick off a full render (scenes + media) for one chapter in a background
    thread, callable in-process (the admin 'Render chapter' button).

    Returns (ok: bool, info: dict | error_str). Refuses with a clear message when
    a render is already running — the pipeline is single-tenant (one at a time).
    """
    if not ANTHROPIC_API_KEY:
        return False, "ANTHROPIC_API_KEY not set"
    if not FAL_KEY or not JSON2VIDEO_API_KEY:
        return False, "Render keys missing (FAL_KEY / JSON2VIDEO_API_KEY)"
    if model not in KLING_MODELS:
        return False, f"Unknown model '{model}'. Choose from: {', '.join(KLING_MODELS.keys())}"
    if not (text or "").strip():
        return False, "No scripture text to render."
    if pipeline_state["phase"] in ("generating_scenes", "generating_media", "rendering"):
        busy = f"{pipeline_state.get('book','')} {pipeline_state.get('chapter','')}".strip()
        return False, f"A render is already running ({busy or 'in progress'}). Wait for it to finish."

    vid = resolve_voice(voice_id)
    with lock:
        pipeline_state.update(phase="generating_scenes",
                              message="Splitting scripture and generating scenes with Claude AI...",
                              scenes=None, error=None, video_url=None, video_urls=[], processed=[],
                              book=book, chapter=chapter, model=model, aspect_ratio="16:9",
                              voice_id=vid, render_id=render_id, style=resolve_style(style)["id"])
        save_state()
    thread = threading.Thread(target=_run_chapter,
                              args=(text, book, chapter, model, vid, resolve_style(style)["id"]),
                              daemon=True)
    thread.start()
    return True, {"render_id": render_id, "book": book, "chapter": chapter}


# ---------------------------------------------------------------------------
# Background runners
# ---------------------------------------------------------------------------
def run_pipeline(scenes, model="v1.6", resume_from=0, existing_processed=None, voice_id=None):
    global pipeline_state
    voice_id = resolve_voice(voice_id)
    try:
        clear_stop()
        total = len(scenes)
        processed = list(existing_processed) if existing_processed else []
        is_fresh_run = resume_from == 0 and not processed
        with lock:
            updates = dict(phase="generating_media", current_scene=resume_from, total_scenes=total,
                           message=f"Generating media for {total} scenes...", processed=list(processed), error=None, video_url=None)
            if is_fresh_run:
                updates["pending_fal"] = None
            pipeline_state.update(updates)
            save_state()
        for i, scene in enumerate(scenes, 1):
            if i <= resume_from:
                continue
            if is_stop_requested():
                with lock:
                    pipeline_state.update(phase="stopped", message="Stopped by user", processed=list(processed))
                    save_state()
                return
            with lock:
                pipeline_state["current_scene"] = i
                pipeline_state["message"] = f"Scene {i}/{total} — Generating FLUX image..."
            image_url = generate_image(scene)
            if is_stop_requested():
                with lock:
                    pipeline_state.update(phase="stopped", message="Stopped by user", processed=list(processed))
                    save_state()
                return
            with lock:
                pipeline_state["message"] = f"Scene {i}/{total} — Generating Kling {model} video..."
            video_url = generate_video(image_url, scene, model)
            processed.append({"narration": scene["narration"], "video_url": video_url})
            with lock:
                pipeline_state["processed"] = list(processed)
                pipeline_state["message"] = f"Scene {i}/{total} complete"
                save_state()
        # Check if we need to split into multiple renders
        total_words = sum(len(p["narration"].split()) for p in processed if p.get("narration"))
        if total_words > MAX_WORDS_PER_RENDER:
            # Split into 2 parts at the midpoint
            mid = len(processed) // 2
            parts = [processed[:mid], processed[mid:]]
            part_urls = []
            for part_num, part in enumerate(parts, 1):
                with lock:
                    pipeline_state["phase"] = "rendering"
                    pipeline_state["message"] = f"Rendering Part {part_num} of {len(parts)} ({len(part)} scenes)..."
                payload = build_json2video_payload(part, voice_id, pipeline_state.get("aspect_ratio", "16:9"))
                mp4_url = submit_and_poll_json2video(payload)
                part_urls.append(mp4_url)
            with lock:
                pipeline_state.update(phase="done", video_url=part_urls[0], video_urls=part_urls,
                                      message=f"Video complete! Split into {len(part_urls)} parts.")
        else:
            with lock:
                pipeline_state["phase"] = "rendering"
                pipeline_state["message"] = "Submitting to JSON2Video for final render..."
            payload = build_json2video_payload(processed, voice_id, pipeline_state.get("aspect_ratio", "16:9"))
            mp4_url = submit_and_poll_json2video(payload)
            with lock:
                pipeline_state.update(phase="done", video_url=mp4_url, video_urls=[mp4_url], message="Video complete!")
        save_to_history("done")
        save_state()
    except Exception as e:
        with lock:
            pipeline_state.update(phase="error", error=str(e), message=f"Error: {e}")
            save_state()
        traceback.print_exc()


def run_fix_scene(scene_index, scene, processed, model="v1.6", voice_id=None):
    global pipeline_state
    voice_id = resolve_voice(voice_id)
    try:
        total = len(processed)
        idx = scene_index + 1
        with lock:
            pipeline_state.update(phase="generating_media", current_scene=idx, total_scenes=total,
                                  message=f"Fixing Scene {idx}/{total} — Generating FLUX image...", error=None, video_url=None)
        image_url = generate_image(scene)
        with lock:
            pipeline_state["message"] = f"Fixing Scene {idx}/{total} — Generating Kling {model} video..."
        video_url = generate_video(image_url, scene, model)
        processed[scene_index] = {"narration": scene["narration"], "video_url": video_url}
        with lock:
            # Update the master scenes list so fix panel stays in sync
            if pipeline_state.get("scenes") and scene_index < len(pipeline_state["scenes"]):
                pipeline_state["scenes"][scene_index].update(scene)
            pipeline_state.update(phase="rendering", processed=list(processed), message="Re-submitting all scenes to JSON2Video...")
        payload = build_json2video_payload(processed, voice_id, pipeline_state.get("aspect_ratio", "16:9"))
        mp4_url = submit_and_poll_json2video(payload)
        with lock:
            pipeline_state.update(phase="done", video_url=mp4_url, video_urls=[mp4_url], message="Fixed video complete!")
        save_to_history("done")
        save_state()
    except Exception as e:
        with lock:
            pipeline_state.update(phase="error", error=str(e), message=f"Error: {e}")
            save_state()
        traceback.print_exc()


def run_fix_scenes(fixes, processed, model="v1.6", voice_id=None):
    """Batch-fix multiple scenes: regenerate FLUX + Kling for each, then ONE JSON2Video render."""
    global pipeline_state
    voice_id = resolve_voice(voice_id)
    try:
        clear_stop()
        total_fixes = len(fixes)
        total = len(processed)
        with lock:
            pipeline_state.update(phase="generating_media", current_scene=0, total_scenes=total,
                                  message=f"Batch fixing {total_fixes} scenes...", error=None, video_url=None)
        for fix_num, fix in enumerate(fixes, 1):
            if is_stop_requested():
                with lock:
                    pipeline_state.update(phase="stopped", message="Stopped by user", processed=list(processed))
                return
            idx = fix["scene_index"]
            scene = fix["scene"]
            with lock:
                pipeline_state["current_scene"] = idx + 1
                pipeline_state["message"] = f"Fixing scene {fix_num} of {total_fixes} selected — Generating FLUX image..."
            image_url = generate_image(scene)
            if is_stop_requested():
                with lock:
                    pipeline_state.update(phase="stopped", message="Stopped by user", processed=list(processed))
                return
            with lock:
                pipeline_state["message"] = f"Fixing scene {fix_num} of {total_fixes} selected — Generating Kling {model} video..."
            video_url = generate_video(image_url, scene, model)
            processed[idx] = {"narration": scene["narration"], "video_url": video_url}
            with lock:
                # Update the master scenes list so fix panel stays in sync
                if pipeline_state.get("scenes") and idx < len(pipeline_state["scenes"]):
                    pipeline_state["scenes"][idx].update(scene)
                pipeline_state["processed"] = list(processed)
                pipeline_state["message"] = f"Fixed scene {fix_num} of {total_fixes} selected"
        with lock:
            pipeline_state.update(phase="rendering", processed=list(processed), message="Re-submitting all scenes to JSON2Video...")
        payload = build_json2video_payload(processed, voice_id, pipeline_state.get("aspect_ratio", "16:9"))
        mp4_url = submit_and_poll_json2video(payload)
        with lock:
            pipeline_state.update(phase="done", video_url=mp4_url, video_urls=[mp4_url], message="Batch fix complete!")
        save_to_history("done")
        save_state()
    except Exception as e:
        with lock:
            pipeline_state.update(phase="error", error=str(e), message=f"Error: {e}")
            save_state()
        traceback.print_exc()


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
biblical_router = APIRouter()


def _run_scene_generation(text, words_target, book, chapter, style=DEFAULT_STYLE):
    """Background worker: split scripture + batch Claude calls → scenes. Runs off the
    request thread so a long full-chapter generation (many batches, >100s) doesn't
    block the HTTP response and trip the Cloudflare proxy's ~100s timeout. The browser
    polls /api/status for the result."""
    try:
        narration_chunks = split_scripture_into_scenes(text, words_target)
        scenes = generate_image_prompts(narration_chunks, book, chapter, style)
        with lock:
            pipeline_state.update(phase="idle", scenes=scenes, message=f"Generated {len(scenes)} scenes")
            save_state()
    except Exception as e:
        with lock:
            pipeline_state.update(phase="error", error=str(e), message="Scene generation failed")
            save_state()


@biblical_router.post("/api/generate-scenes")
@limiter.limit(MEDIUM_LIMIT)
async def api_generate_scenes(request: Request, body: BiblicalGenerateInput):
    """Step 1: Split scripture + Claude AI → scenes for user review. No media generation.
    Runs in the background and returns immediately; the browser polls /api/status."""
    if not ANTHROPIC_API_KEY:
        raise HTTPException(400, "ANTHROPIC_API_KEY not set")
    if pipeline_state["phase"] in ("generating_scenes", "generating_media", "rendering"):
        raise HTTPException(409, "Pipeline already running")

    with lock:
        pipeline_state.update(phase="generating_scenes", message="Splitting scripture and generating scene visuals with Claude AI...",
                              scenes=None, error=None, video_url=None, video_urls=[], processed=[],
                              book=body.book, chapter=body.chapter, model=body.model, aspect_ratio=body.aspect_ratio,
                              style=resolve_style(body.style)["id"])
        save_state()

    words_target = WORDS_PER_SCENE.get(body.model, 30)
    log_event(request, "biblical_generate_scenes", model=body.model, words=len(body.text.split()),
              style=resolve_style(body.style)["id"])
    thread = threading.Thread(
        target=_run_scene_generation,
        args=(body.text, words_target, body.book, body.chapter, resolve_style(body.style)["id"]),
        daemon=True,
    )
    thread.start()
    return {"status": "started"}


@biblical_router.post("/api/generate-video")
@limiter.limit(EXPENSIVE_LIMIT)
async def api_generate_video(request: Request, body: BiblicalScenesInput):
    """Step 2: Take (possibly edited) scenes → kick off FLUX + Kling + JSON2Video pipeline."""
    if not FAL_KEY:
        raise HTTPException(400, "FAL_KEY not set")
    if not JSON2VIDEO_API_KEY:
        raise HTTPException(400, "JSON2VIDEO_API_KEY not set")
    model = body.model
    if model not in KLING_MODELS:
        raise HTTPException(400, f"Unknown model '{model}'. Choose from: {', '.join(KLING_MODELS.keys())}")
    if pipeline_state["phase"] in ("generating_scenes", "generating_media", "rendering"):
        raise HTTPException(409, "Pipeline already running")

    scenes = body.scenes
    voice_id = resolve_voice(body.voice_id)
    with lock:
        pipeline_state.update(scenes=scenes, model=model, voice_id=voice_id, aspect_ratio=body.aspect_ratio,
                              style=resolve_style(body.style)["id"])
    log_event(request, "biblical_generate_video", model=model, scenes=len(scenes),
              voice=voice_id, style=resolve_style(body.style)["id"],
              words=sum(len((s.get("narration") or "").split()) for s in scenes))
    thread = threading.Thread(target=run_pipeline, args=(scenes, model), kwargs={"voice_id": voice_id}, daemon=True)
    thread.start()
    return {"status": "started", "total_scenes": len(scenes), "model": model, "voice_id": voice_id}


@biblical_router.post("/api/generate")
@limiter.limit(EXPENSIVE_LIMIT)
async def api_generate(request: Request, body: BiblicalGenerateInput):
    """Legacy: generate scenes + start pipeline in one call."""
    if not ANTHROPIC_API_KEY:
        raise HTTPException(400, "ANTHROPIC_API_KEY not set")
    if not FAL_KEY:
        raise HTTPException(400, "FAL_KEY not set")
    if not JSON2VIDEO_API_KEY:
        raise HTTPException(400, "JSON2VIDEO_API_KEY not set")
    if body.model not in KLING_MODELS:
        raise HTTPException(400, f"Unknown model '{body.model}'. Choose from: {', '.join(KLING_MODELS.keys())}")
    if pipeline_state["phase"] in ("generating_scenes", "generating_media", "rendering"):
        raise HTTPException(409, "Pipeline already running")

    try:
        voice_id = resolve_voice(body.voice_id)
        with lock:
            pipeline_state.update(phase="generating_scenes", message="Splitting scripture and generating scene visuals with Claude AI...",
                                  scenes=None, error=None, video_url=None, video_urls=[], processed=[],
                                  book=body.book, chapter=body.chapter, model=body.model, aspect_ratio=body.aspect_ratio, voice_id=voice_id,
                                  style=resolve_style(body.style)["id"])

        words_target = WORDS_PER_SCENE.get(body.model, 30)
        narration_chunks = split_scripture_into_scenes(body.text, words_target)
        scenes = generate_image_prompts(narration_chunks, body.book, body.chapter, resolve_style(body.style)["id"])

        with lock:
            pipeline_state.update(scenes=scenes, message=f"Generated {len(scenes)} scenes — starting media pipeline...")
            save_state()

        log_event(request, "biblical_generate_legacy", model=body.model, scenes=len(scenes),
                  book=body.book, chapter=body.chapter, voice=voice_id)
        thread = threading.Thread(target=run_pipeline, args=(scenes, body.model), kwargs={"voice_id": voice_id}, daemon=True)
        thread.start()

        return {"status": "started", "total_scenes": len(scenes), "scenes": scenes}
    except Exception as e:
        with lock:
            pipeline_state.update(phase="error", error=str(e))
        raise HTTPException(500, str(e))


@biblical_router.post("/api/retry")
@limiter.limit(EXPENSIVE_LIMIT)
async def api_retry(request: Request):
    if not FAL_KEY or not JSON2VIDEO_API_KEY:
        raise HTTPException(400, "Missing FAL_KEY or JSON2VIDEO_API_KEY")
    with lock:
        if pipeline_state["phase"] not in ("error", "idle", "done"):
            raise HTTPException(409, "Pipeline is still running")
        scenes = pipeline_state.get("scenes")
        processed = pipeline_state.get("processed", [])
        resume_from = len(processed)
        model = pipeline_state.get("model") or "v3.0"
        voice_id = resolve_voice(pipeline_state.get("voice_id"))
    if not scenes:
        raise HTTPException(400, "No scenes to retry — generate first")
    if model not in KLING_MODELS:
        model = "v3.0"
    log_event(request, "biblical_retry", model=model, scenes=len(scenes), resume_from=resume_from, voice=voice_id)
    thread = threading.Thread(target=run_pipeline, args=(scenes, model, resume_from, processed), kwargs={"voice_id": voice_id}, daemon=True)
    thread.start()
    return {"status": "resuming", "resume_from": resume_from + 1, "total_scenes": len(scenes), "model": model}


@biblical_router.post("/api/fix-scene")
@limiter.limit(EXPENSIVE_LIMIT)
async def api_fix_scene(request: Request, body: BiblicalFixSceneInput):
    if not FAL_KEY or not JSON2VIDEO_API_KEY:
        raise HTTPException(400, "Missing FAL_KEY or JSON2VIDEO_API_KEY")
    if pipeline_state["phase"] in ("generating_media", "rendering"):
        raise HTTPException(409, "Pipeline already running")
    with lock:
        processed = pipeline_state.get("processed", [])
    if not processed:
        raise HTTPException(400, "No completed video to fix")
    if body.scene_index < 0 or body.scene_index >= len(processed):
        raise HTTPException(400, f"Scene index {body.scene_index} out of range")
    voice_id = resolve_voice(body.voice_id)
    with lock:
        pipeline_state["voice_id"] = voice_id
        pipeline_state["aspect_ratio"] = body.aspect_ratio
        pipeline_state["style"] = resolve_style(body.style)["id"]
    log_event(request, "biblical_fix_scene", model=body.model, scene_index=body.scene_index,
              total_scenes=len(processed), voice=voice_id, style=pipeline_state["style"])
    thread = threading.Thread(target=run_fix_scene, args=(body.scene_index, body.scene, list(processed), body.model), kwargs={"voice_id": voice_id}, daemon=True)
    thread.start()
    return {"status": "fixing", "scene": body.scene_index + 1, "total_scenes": len(processed)}


@biblical_router.post("/api/fix-scenes")
@limiter.limit(EXPENSIVE_LIMIT)
async def api_fix_scenes(request: Request, body: BiblicalFixScenesInput):
    if not FAL_KEY or not JSON2VIDEO_API_KEY:
        raise HTTPException(400, "Missing FAL_KEY or JSON2VIDEO_API_KEY")
    if pipeline_state["phase"] in ("generating_media", "rendering"):
        raise HTTPException(409, "Pipeline already running")
    with lock:
        processed = pipeline_state.get("processed", [])
    if not processed:
        raise HTTPException(400, "No completed video to fix")
    if not body.fixes:
        raise HTTPException(400, "No fixes provided")
    for fix in body.fixes:
        idx = fix.get("scene_index")
        if idx is None or idx < 0 or idx >= len(processed):
            raise HTTPException(400, f"Scene index {idx} out of range")
        if "scene" not in fix:
            raise HTTPException(400, f"Missing scene data for index {idx}")
    voice_id = resolve_voice(body.voice_id)
    with lock:
        pipeline_state["voice_id"] = voice_id
        pipeline_state["aspect_ratio"] = body.aspect_ratio
        pipeline_state["style"] = resolve_style(body.style)["id"]
    log_event(request, "biblical_fix_scenes", model=body.model, fix_count=len(body.fixes),
              total_scenes=len(processed), voice=voice_id, style=pipeline_state["style"])
    thread = threading.Thread(target=run_fix_scenes, args=(body.fixes, list(processed), body.model), kwargs={"voice_id": voice_id}, daemon=True)
    thread.start()
    return {"status": "fixing", "scenes": len(body.fixes), "total_scenes": len(processed)}


@biblical_router.get("/api/history")
async def api_history():
    if not HISTORY_FILE.exists():
        return JSONResponse([])
    history = json.loads(HISTORY_FILE.read_text())
    # Return newest first, without full scenes array (keep response light)
    summary = [{k: v for k, v in entry.items() if k != "scenes"} for entry in reversed(history)]
    return JSONResponse(summary)


@biblical_router.get("/api/history/{render_id}")
async def api_history_detail(render_id: str):
    if not HISTORY_FILE.exists():
        raise HTTPException(404, "No history found")
    history = json.loads(HISTORY_FILE.read_text())
    for entry in history:
        if entry["id"] == render_id:
            return JSONResponse(entry)
    raise HTTPException(404, f"Render {render_id} not found")


@biblical_router.post("/api/stop")
async def api_stop():
    if pipeline_state["phase"] not in ("generating_media", "generating_scenes", "rendering"):
        raise HTTPException(400, "No active pipeline to stop")
    request_stop()
    return {"status": "stop_requested"}


@biblical_router.get("/api/status")
async def api_status():
    with lock:
        return JSONResponse(dict(pipeline_state))


@biblical_router.get("/api/voices")
async def api_voices():
    return JSONResponse({"voices": VOICES, "default": VOICE_ID})


@biblical_router.get("/api/styles")
async def api_styles():
    """Style pack catalog for the audience picker."""
    return JSONResponse({"styles": style_list(), "default": DEFAULT_STYLE})
