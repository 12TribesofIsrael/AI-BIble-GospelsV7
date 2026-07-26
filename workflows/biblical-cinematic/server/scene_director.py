"""
Scene director — Claude turns fixed narration into visual direction.

Pulled out of biblical_pipeline.py so it can be imported WITHOUT dragging in
FastAPI. The pipeline module builds an APIRouter at import time, which makes it
unusable from a plain script or a CLI on a machine whose FastAPI/Starlette
versions disagree. The prompt logic itself is pure — narration in, imagePrompt /
motion / lighting out — so it belongs here.

biblical_pipeline.py re-exports everything below, so existing imports and the
web app are unaffected.
"""

import json
import os

import requests

from style_packs import DEFAULT_STYLE, ETHNICITY_RULES, resolve_style

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


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
