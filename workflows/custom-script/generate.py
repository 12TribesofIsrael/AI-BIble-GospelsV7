#!/usr/bin/env python3
"""
Custom Script → Cinematic Video Pipeline

Takes a raw script/concept as a text file, uses Claude AI to break it into
cinematic scenes (with image prompts, motion, lighting), then generates
a full video via FLUX → Kling → ElevenLabs → JSON2Video.

Usage:
  python generate.py script.txt
  python generate.py script.txt --post-produce
  python generate.py script.txt --scenes-only   # just output scenes JSON, no video
"""

import argparse
import json
import os
import subprocess
import sys
import time

import requests
from dotenv import find_dotenv, load_dotenv

# Style packs live with the server module; add it to the path so the CLI shares
# the exact same audience definitions as the web app (one source of truth).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "biblical-cinematic", "server"))
from style_packs import (  # noqa: E402
    DEFAULT_STYLE, ETHNICITY_RULES, apply_subtitle_style, resolve_style,
)

load_dotenv(find_dotenv())

# Set once from --style in main(); every stage reads it. The CLI runs one video
# per process, so a module-level pack is simpler than threading it through.
ACTIVE_PACK = resolve_style(DEFAULT_STYLE)

FAL_KEY = os.getenv("FAL_KEY")
JSON2VIDEO_API_KEY = os.getenv("JSON2VIDEO_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

FLUX_URL = "https://fal.run/fal-ai/flux-pro"
# When a LoRA URL is passed via --lora-url, FLUX requests route to the LoRA-
# enabled endpoint (uses FLUX.1-dev base + custom LoRA weights). Slight base-
# quality drop vs flux-pro, but the trained LoRA dominates the aesthetic so
# the practical difference is minimal — and it's the only fal endpoint that
# actually accepts user-trained LoRA weights.
FLUX_LORA_URL = "https://fal.run/fal-ai/flux-lora"
KLING_URL = "https://fal.run/fal-ai/kling-video/v3/standard/image-to-video"  # legacy default — superseded by KLING_MODELS
KLING_MODELS = {
    "v1.6":     {"url": "https://fal.run/fal-ai/kling-video/v1.6/standard/image-to-video", "duration": "10"},
    "v2.1":     {"url": "https://fal.run/fal-ai/kling-video/v2.1/standard/image-to-video", "duration": "10"},
    "v3.0":     {"url": "https://fal.run/fal-ai/kling-video/v3/standard/image-to-video",   "duration": "15"},
    "v3.0-pro": {"url": "https://fal.run/fal-ai/kling-video/v3/pro/image-to-video",        "duration": "15"},
    "o3":       {"url": "https://fal.run/fal-ai/kling-video/o3/standard/image-to-video",   "duration": "15"},
    "o3-pro":   {"url": "https://fal.run/fal-ai/kling-video/o3/pro/image-to-video",        "duration": "15"},
    # Seedance 2.5 — mirrors router.py: no cfg_scale/negative_prompt, aspect ratio
    # comes from the source image, ~$0.46/sec at 720p so clips are 10s not 15.
    "seedance-2.5": {"url": "https://fal.run/bytedance/seedance-2.5/image-to-video",
                     "duration": "10", "engine": "seedance", "resolution": "720p"},
}
JSON2VIDEO_URL = "https://api.json2video.com/v2/movies"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

VOICE_ID = "NgBYGKDDq2Z8Hnhatgma"
VOICE_SPEED = 0.9

POST_PRODUCE_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "biblical-cinematic", "scripts", "post_produce.py"
)

def scene_generation_prompt(pack) -> str:
    """Build the CLI system prompt for a style pack (shared defs in style_packs.py).

    `cinematic` reproduces the original CLI prompt; `epic` and `kids` swap the
    visual + narration language. Ethnicity rules are fixed for every pack.
    """
    extra = "\n" + pack["extra_guidelines"] if pack["extra_guidelines"] else ""
    narration_note = "\n\n" + pack["narration_note"] if pack["narration_note"] else ""
    return f"""You are a {pack['director_role']} for AI Bible Gospels — a channel revealing the hidden identity of the 12 Tribes of Israel through Scripture, history, and prophecy.

BRAND STYLE:
{pack['brand_style']}

{ETHNICITY_RULES}{pack['ethnicity_extra']}

YOUR TASK:
Read the script/concept below and break it into scenes for video production. You are NOT narrating it word-for-word — you are a creative director interpreting the concept into powerful narration and visuals.

For each scene, create:
1. **narration**: Your own narration inspired by the script (not word-for-word copy). Write prose that captures the spirit and message. Keep each scene's narration between 20-60 words.
2. **imagePrompt**: Extremely detailed visual description for AI image generation. Include character ethnicity per rules above, clothing details, setting, camera angle, atmosphere. End with "{pack['image_suffix_custom']}". {pack['forbidden_line']}
3. **motion**: {pack['motion_note']}
4. **lighting**: {pack['lighting_note']}

GUIDELINES:
- Create as many scenes as the content naturally needs (don't pad, don't compress)
- Vary camera angles: close-up → wide shot → medium → aerial → over-shoulder
- Vary lighting: {pack['lighting_examples']}
{pack['script_tone_line']}
- Each scene should be visually distinct from the one before it{extra}
- For channel branding scenes (subscribe, logo, etc.), describe the visual elements in this style{narration_note}

Return ONLY valid JSON in this exact format:
{{
  "scenes": [
    {{
      "narration": "...",
      "imagePrompt": "...",
      "motion": "...",
      "lighting": "..."
    }}
  ]
}}"""


def generate_scenes_from_script(script_text):
    """Use Claude to break a raw script into cinematic scenes."""
    print("Generating cinematic scenes with Claude AI...")
    resp = requests.post(
        ANTHROPIC_URL,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 8000,
            "thinking": {"type": "disabled"},
            "output_config": {"effort": "low"},
            "messages": [
                {
                    "role": "user",
                    "content": f"{scene_generation_prompt(ACTIVE_PACK)}\n\n---\n\nSCRIPT/CONCEPT:\n\n{script_text}",
                }
            ],
        },
        timeout=120,
    )
    resp.raise_for_status()
    content = resp.json()["content"][0]["text"]

    # Strip markdown fences if present
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]

    data = json.loads(content.strip())
    scenes = data["scenes"]
    print(f"Claude generated {len(scenes)} scenes\n")
    return scenes


def fal_headers():
    return {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json",
    }


def generate_image(scene, index, total, lora_url=None, lora_trigger=None, lora_scale=1.0):
    """Generate a FLUX image for a scene.

    lora_url: optional URL to a trained LoRA. When provided, routes the
    request to the LoRA-enabled FLUX endpoint and prepends lora_trigger
    to the prompt.

    Retries on ConnectionError / Timeout / 5xx. Does NOT retry on 4xx
    (403, 401, 429) — those are credit / auth / rate-limit issues that
    won't fix themselves and should surface immediately.
    """
    prompt = scene["imagePrompt"]
    if scene.get("lighting"):
        prompt += f", {scene['lighting']}"
    if lora_url and lora_trigger:
        # Prepend the trigger so the LoRA activates. The trigger is a single
        # rare token that biases the model toward the trained look.
        prompt = f"{lora_trigger} {prompt}"

    # Belt-and-braces: if Claude ignored the style instruction, the suffix still
    # lands on the prompt so FLUX renders in the right medium.
    if ACTIVE_PACK["image_suffix_custom"].split(",")[0].strip().lower() not in prompt.lower():
        prompt += f", {ACTIVE_PACK['image_suffix_custom']}"

    if lora_url:
        endpoint = FLUX_LORA_URL
        payload = {
            "prompt": prompt,
            "negative_prompt": ACTIVE_PACK["negative_prompt"],
            "image_size": "landscape_16_9",
            "num_inference_steps": 28,
            "num_images": 1,
            "loras": [{"path": lora_url, "scale": lora_scale}],
        }
    else:
        endpoint = FLUX_URL
        payload = {
            "prompt": prompt,
            "negative_prompt": ACTIVE_PACK["negative_prompt"],
            "image_size": "landscape_16_9",
            "num_inference_steps": 28,
            "num_images": 1,
        }

    backoff_seconds = [15, 45, 90]
    for attempt, sleep_before_retry in enumerate(backoff_seconds + [None], start=1):
        try:
            print(f"  [{index}/{total}] Generating FLUX image (attempt {attempt})...")
            resp = requests.post(endpoint, headers=fal_headers(), json=payload, timeout=120)
            resp.raise_for_status()
            break
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            if sleep_before_retry is None:
                print(f"  [{index}/{total}] FLUX network failure after {attempt} attempts: {e}")
                raise
            print(f"  [{index}/{total}] Network error: {type(e).__name__} — retry in {sleep_before_retry}s")
            time.sleep(sleep_before_retry)
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            # 4xx → fail fast (credit / auth / rate-limit need user intervention)
            if 400 <= status < 500:
                print(f"  [{index}/{total}] FLUX returned {status} — not retrying (likely billing/auth/rate-limit)")
                raise
            # 5xx → retry
            if sleep_before_retry is None:
                print(f"  [{index}/{total}] FLUX 5xx after {attempt} attempts: {status}")
                raise
            print(f"  [{index}/{total}] FLUX {status} server error — retry in {sleep_before_retry}s")
            time.sleep(sleep_before_retry)

    url = resp.json()["images"][0]["url"]
    print(f"  [{index}/{total}] Image ready: {url[:80]}...")
    return url


def generate_video(image_url, scene, index, total, kling_model="v3.0"):
    """Generate a Kling video from a FLUX image.

    kling_model: one of KLING_MODELS keys (default v3.0, the legacy CLI default).

    Retries on ConnectionError / Timeout (fal.ai TCP connections frequently
    reset during long o3-pro renders). 3 attempts with exponential backoff:
    30s, 90s, 180s. Per-attempt timeout is 1800s to accommodate o3-pro.
    """
    model_cfg = KLING_MODELS.get(kling_model, KLING_MODELS["v3.0"])
    motion = scene.get("motion", "Slow cinematic camera movement")
    if model_cfg.get("engine") == "seedance":
        # Seedance takes no cfg_scale/negative_prompt, so the anachronism guard
        # rides the prompt; audio off — narration is laid over downstream.
        payload = {
            "image_url": image_url,
            "prompt": motion + " Stay strictly faithful to the source image. "
                      "Preserve every character's exact skin tone and hair from the "
                      "source frame: deeply melanated dark brown skin stays deeply "
                      "melanated — never lightened, brightened, or washed out, even "
                      "under divine glow or backlight — and natural Afro-textured "
                      "hair stays unchanged. Period-accurate biblical setting only — "
                      "no modern objects, vehicles, or text.",
            "duration": model_cfg["duration"],
            "resolution": model_cfg["resolution"],
            "generate_audio": False,
        }
    else:
        payload = {
            "image_url": image_url,
            "prompt": motion,
            "duration": model_cfg["duration"],
            "cfg_scale": ACTIVE_PACK["cfg_scale"],
            "negative_prompt": ACTIVE_PACK["kling_negative"],
        }

    backoff_seconds = [30, 90, 180]
    last_err = None
    for attempt, sleep_before_retry in enumerate(backoff_seconds + [None], start=1):
        try:
            print(f"  [{index}/{total}] Generating Kling {kling_model} video (attempt {attempt})...")
            resp = requests.post(
                model_cfg["url"],
                headers=fal_headers(),
                json=payload,
                timeout=1800,
            )
            resp.raise_for_status()
            break  # success — exit retry loop
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            last_err = e
            if sleep_before_retry is None:
                print(f"  [{index}/{total}] Kling failed after {attempt} attempts: {e}")
                raise
            print(f"  [{index}/{total}] Network error: {type(e).__name__} — sleeping {sleep_before_retry}s before retry")
            time.sleep(sleep_before_retry)
    resp.raise_for_status()
    data = resp.json()
    url = data.get("video", {}).get("url") or data["data"]["video"]["url"]
    print(f"  [{index}/{total}] Video ready: {url[:80]}...")
    return url


def build_json2video_payload(scenes_data, voice_id=None):
    """Build a JSON2Video project payload dynamically for N scenes.

    voice_id (optional): override the module-level VOICE_ID. If None, falls
    back to the module constant so existing callers see no behavior change.
    """
    effective_voice = voice_id or VOICE_ID
    subtitle_settings = {
        "style": "classic",
        "font-family": "Oswald Bold",
        "font-size": 80,
        "position": "bottom-center",
        "line-color": "#CCCCCC",
        "word-color": "#FFFF00",
        "outline-color": "#000000",
        "outline-width": 8,
        "shadow-color": "#000000",
        "shadow-offset": 6,
        "max-words-per-line": 4,
    }
    subtitle_settings = apply_subtitle_style(subtitle_settings, ACTIVE_PACK)

    scenes = []
    for i, s in enumerate(scenes_data, 1):
        scenes.append({
            "id": f"scene{i}",
            "comment": f"Scene {i}",
            "duration": "auto",
            "elements": [
                {
                    "id": f"scene{i}_bg",
                    "type": "video",
                    "src": s["video_url"],
                    "resize": "cover",
                    "loop": -1,
                    "duration": -2,
                },
                {
                    "id": f"scene{i}_voice",
                    "type": "voice",
                    "text": s["narration"],
                    "voice": effective_voice,
                    "model": "elevenlabs",
                    "speed": VOICE_SPEED,
                },
                {
                    "id": f"scene{i}_subs",
                    "type": "subtitles",
                    "language": "en",
                    "model": "transcription",
                    "settings": subtitle_settings,
                    "transcript": s["narration"],
                },
            ],
        })

    return {
        "resolution": "full-hd",
        "quality": "high",
        "scenes": scenes,
    }


def submit_json2video(payload):
    """Submit project to JSON2Video and return the project ID."""
    print("\nSubmitting to JSON2Video...")
    resp = requests.post(
        JSON2VIDEO_URL,
        headers={
            "x-api-key": JSON2VIDEO_API_KEY,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    project_id = data.get("project") or data.get("id")
    print(f"Project submitted: {project_id}")
    return project_id


def poll_json2video(project_id):
    """Poll JSON2Video until done or error. Returns the MP4 URL."""
    print("Polling for render completion...")
    while True:
        time.sleep(10)
        resp = requests.get(
            JSON2VIDEO_URL,
            headers={"x-api-key": JSON2VIDEO_API_KEY},
            params={"project": project_id},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        movie = data.get("movie", data)
        status = movie.get("status", "unknown")
        print(f"  Status: {status}")

        if status == "done":
            url = movie["url"]
            print(f"\nVideo ready: {url}")
            return url
        elif status == "error":
            raise RuntimeError(f"JSON2Video render failed: {movie.get('message')}")


def run_post_produce(video_url):
    """Run post_produce.py against a finished video.

    Accepts a URL (JSON2Video path) or a local file path (local assembler path) —
    the local assembler hands back a path on disk, not a download link.
    """
    os.makedirs("output", exist_ok=True)
    raw_path = os.path.join("output", "raw_video.mp4")

    if not str(video_url).startswith("http"):
        raw_path = str(video_url)
        print(f"\nPost-producing local file {raw_path}...")
        subprocess.run([sys.executable, POST_PRODUCE_SCRIPT, raw_path], check=True)
        return

    print(f"\nDownloading raw video to {raw_path}...")
    resp = requests.get(video_url, stream=True, timeout=300)
    resp.raise_for_status()
    with open(raw_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    print("Running post-production...")
    subprocess.run(
        [sys.executable, POST_PRODUCE_SCRIPT, raw_path],
        check=True,
    )


def main():
    parser = argparse.ArgumentParser(description="Custom script → cinematic video")
    parser.add_argument("script_file", help="Path to script text file (or .json for pre-built scenes)")
    parser.add_argument("--post-produce", action="store_true", help="Run post-production (intro/outro/logo)")
    parser.add_argument("--scenes-only", action="store_true", help="Only generate scenes JSON, skip video production")
    parser.add_argument("--voice-id", default=None, help="ElevenLabs voice ID override (default: module-level VOICE_ID constant)")
    parser.add_argument("--kling-model", default="v3.0", choices=list(KLING_MODELS.keys()),
                        help="Kling model variant (default v3.0). Cost/quality varies by model.")
    parser.add_argument("--assembler", default="json2video", choices=["json2video", "local"],
                        help="Final assembly: 'local' uses the in-house FFmpeg assembler "
                             "(burned captions, no JSON2Video credits, any ElevenLabs voice).")
    parser.add_argument("--aspect-ratio", default="16:9", choices=["16:9", "1:1", "9:16"],
                        help="Output canvas for the local assembler.")
    parser.add_argument("--out", default=None, help="Output MP4 path (local assembler).")
    parser.add_argument("--no-captions", action="store_true",
                        help="Skip burned-in captions (local assembler).")
    parser.add_argument("--style", default=DEFAULT_STYLE, choices=["cinematic", "epic", "kids"],
                        help="Audience style pack: cinematic (default, the classic look), "
                             "epic (High Cinematic, adults), kids (animated, child-safe).")
    parser.add_argument("--lora-url", default=None,
                        help="Trained FLUX LoRA URL (from scripts/train-flux-lora.py output). "
                             "When set, routes FLUX to the LoRA-enabled endpoint.")
    parser.add_argument("--lora-trigger", default=None,
                        help="LoRA trigger word — prepended to every imagePrompt to activate the LoRA.")
    parser.add_argument("--lora-scale", type=float, default=1.0,
                        help="LoRA strength (default 1.0). Lower if LoRA overpowers the base prompts.")
    parser.add_argument("--skip-json2video", action="store_true",
                        help="Stop after Kling; write clips_manifest.json for local FFmpeg assembly "
                             "(youtubeoptermizer/scripts/assemble-video.py). No JSON2Video_API_KEY needed.")
    parser.add_argument("--topic", default=None,
                        help="Topic slug for manifest filename (default: derived from script filename)")
    parser.add_argument("--manifest-out", default=None,
                        help="Path to write clips_manifest.json (default: output/<topic>_manifest.json)")
    args = parser.parse_args()

    # Lock in the style pack for this run — every stage reads ACTIVE_PACK.
    global ACTIVE_PACK
    ACTIVE_PACK = resolve_style(args.style)
    print(f"Style: {ACTIVE_PACK['name']} ({ACTIVE_PACK['audience']})")

    # Validate env
    required = {"ANTHROPIC_API_KEY": ANTHROPIC_API_KEY}
    if not args.scenes_only and not args.skip_json2video:
        required.update({"FAL_KEY": FAL_KEY, "JSON2VIDEO_API_KEY": JSON2VIDEO_API_KEY})
    elif not args.scenes_only:
        required.update({"FAL_KEY": FAL_KEY})
    missing = [k for k, v in required.items() if not v]
    if missing:
        print(f"Error: Missing env vars: {', '.join(missing)}")
        print("Set them in .env or environment.")
        sys.exit(1)

    # Load input — either a raw script (.txt/.md) or pre-built scenes (.json)
    with open(args.script_file) as f:
        raw = f.read()

    if args.script_file.endswith(".json"):
        scenes = json.loads(raw)["scenes"]
        print(f"Loaded {len(scenes)} pre-built scenes from {args.script_file}\n")
    else:
        scenes = generate_scenes_from_script(raw)
        # Save generated scenes for reference
        out_path = args.script_file.rsplit(".", 1)[0] + "_scenes.json"
        with open(out_path, "w") as f:
            json.dump({"scenes": scenes}, f, indent=2)
        print(f"Scenes saved to {out_path}\n")

    if args.scenes_only:
        print("Scenes-only mode — skipping video generation.")
        for i, s in enumerate(scenes, 1):
            print(f"\n--- Scene {i} ---")
            print(f"  Narration: {s['narration'][:80]}...")
            print(f"  Motion: {s['motion']}")
            print(f"  Lighting: {s['lighting']}")
        return

    total = len(scenes)
    print(f"Processing {total} scenes through FLUX → Kling pipeline\n")

    # Generate images and videos for each scene
    processed = []
    for i, scene in enumerate(scenes, 1):
        print(f"--- Scene {i}/{total} ---")
        image_url = generate_image(scene, i, total,
                                    lora_url=args.lora_url,
                                    lora_trigger=args.lora_trigger,
                                    lora_scale=args.lora_scale)
        video_url = generate_video(image_url, scene, i, total, kling_model=args.kling_model)
        processed.append({
            "narration": scene["narration"],
            "video_url": video_url,
        })
        print()

    # --assembler local: finish the video here with the in-house FFmpeg assembler
    # instead of JSON2Video. Same captions, no third-party credits, no last-step
    # failure after the FLUX/Kling spend, and any ElevenLabs voice the account owns.
    if args.assembler == "local":
        from local_assembler import assemble
        topic = args.topic or os.path.basename(args.script_file).rsplit(".", 1)[0]
        out_file = args.out or os.path.join("output", f"{topic}_{args.style}.mp4")
        os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
        voice = args.voice_id or ACTIVE_PACK["suggested_voice"]
        print(f"\nAssembling locally (style={args.style}, voice={voice})...")
        final = assemble(processed, voice, aspect_ratio=args.aspect_ratio,
                         style=args.style, out_path=out_file,
                         captions=not args.no_captions)
        print(f"\nDone: {final}")
        if args.post_produce:
            run_post_produce(final)
        return

    # --skip-json2video: dump manifest for local FFmpeg assembly and stop here.
    # The existing JSON2Video path below is untouched when this flag is absent.
    if args.skip_json2video:
        topic = args.topic or os.path.basename(args.script_file).rsplit(".", 1)[0]
        manifest_out = args.manifest_out or os.path.join("output", f"{topic}_manifest.json")
        os.makedirs(os.path.dirname(os.path.abspath(manifest_out)), exist_ok=True)
        effective_voice = args.voice_id or VOICE_ID
        manifest = {
            "topic": topic,
            "aspect": "16x9",
            "voice_id": effective_voice,
            "voice_speed": VOICE_SPEED,
            "scenes": [
                {
                    "scene_id": f"{i + 1:02d}",
                    "kling_url": p["video_url"],
                    "narration_text": p["narration"],
                    "duration_hint": float(KLING_MODELS.get(args.kling_model, {}).get("duration", 15)),
                    "prompt": scenes[i].get("imagePrompt", ""),
                    "motion": scenes[i].get("motion", ""),
                }
                for i, p in enumerate(processed)
            ],
        }
        with open(manifest_out, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"\nManifest written: {manifest_out}")
        print(f"Next: python youtubeoptermizer/scripts/assemble-video.py --manifest {manifest_out}")
        return manifest_out

    # Build and submit JSON2Video payload
    payload = build_json2video_payload(processed, voice_id=args.voice_id)
    project_id = submit_json2video(payload)
    mp4_url = poll_json2video(project_id)

    # Optional post-production
    if args.post_produce:
        run_post_produce(mp4_url)

    print(f"\nDone! Final video: {mp4_url}")
    return mp4_url


if __name__ == "__main__":
    main()
