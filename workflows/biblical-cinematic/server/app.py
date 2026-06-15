"""
Anointed — Web Server
==========================================
Run:  python app.py
URL:  http://localhost:8000

Endpoints:
  GET  /             → landing page
  POST /api/clean    → clean biblical text, return sections
  POST /api/generate → send approved text to n8n webhook
  GET  /api/status   → real-time generation status (polls JSON2Video)
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv, find_dotenv
from typing import Optional
import base64
import secrets

# find_dotenv() walks up the directory tree from this file to locate .env
load_dotenv(find_dotenv(), override=True)

# Make the text_processor module importable
sys.path.insert(0, str(Path(__file__).parent.parent / "text_processor"))

# Make the custom-script router importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "custom-script"))

import json as json_module
import re
import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel
from slowapi.errors import RateLimitExceeded

from biblical_text_processor_v2 import (
    clean_text,
    kjv_narration_fix,
    split_into_words,
    create_sections,
    format_section,
)
from rate_limit import limiter, rate_limit_exceeded_handler, EXPENSIVE_LIMIT, MEDIUM_LIMIT
from usage import log_event, get_summary

app = FastAPI(title="Anointed")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# ── Admin auth middleware ─────────────────────────────────────────────────────
# The app itself is PUBLIC (anyone can generate videos). Only the /admin/* zone —
# which exposes waitlist PII, invite tokens, and usage — is gated by Basic Auth.
# Fail CLOSED: if creds aren't configured, /admin/* returns 401 rather than opening.
_AUTH_USER = os.getenv("APP_USERNAME")
_AUTH_PASS = os.getenv("APP_PASSWORD")

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

_PROTECTED_PREFIX = "/admin"

class AdminAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        # Everything outside /admin/* is public.
        if not path.startswith(_PROTECTED_PREFIX):
            return await call_next(request)
        # /admin/* — deny if creds aren't configured (fail closed).
        if not (_AUTH_USER and _AUTH_PASS):
            return StarletteResponse("Admin auth not configured", status_code=401)
        auth = request.headers.get("Authorization")
        if auth and auth.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth[6:]).decode()
                user, pwd = decoded.split(":", 1)
                if secrets.compare_digest(user, _AUTH_USER) and secrets.compare_digest(pwd, _AUTH_PASS):
                    return await call_next(request)
            except Exception:
                pass
        return StarletteResponse(
            "Unauthorized", status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Anointed Admin"'},
        )

app.add_middleware(AdminAuthMiddleware)
print(
    "Admin auth middleware installed — /admin/* requires Basic Auth (fail-closed); "
    f"creds configured: {bool(_AUTH_USER and _AUTH_PASS)}"
)

# Mount custom script router
try:
    from router import custom_router
    app.include_router(custom_router, prefix="/custom")
    print("Custom Script router mounted at /custom")
except Exception as e:
    import traceback
    print(f"WARNING: Custom Script router not loaded: {e}")
    traceback.print_exc()

# Mount biblical v9 pipeline router (no n8n)
try:
    from biblical_pipeline import biblical_router
    app.include_router(biblical_router, prefix="/v9")
    print("Biblical v9 pipeline router mounted at /v9")
except Exception as e:
    import traceback
    print(f"WARNING: Biblical v9 router not loaded: {e}")
    traceback.print_exc()

# ── Generation state (single-user, in-memory) ─────────────────────────────────
# Resets each time a new video is triggered.
generation_state: dict = {
    "started_at": None,    # datetime (UTC) when /api/generate was called
    "project_id": None,    # JSON2Video project ID once discovered
    "video_url":  None,    # Final MP4 URL when render completes
}

JSON2VIDEO_BASE = "https://api.json2video.com/v2/movies"

# ── Bible chapter data (loaded once at startup) ──────────────────────────────
_BIBLE_JSON_PATH = Path(__file__).parent.parent / "assets" / "bible_chapters.json"
_BIBLE_DATA: list = []  # populated below

# OT/Apocrypha/NT grouping for the dropdown
_OT_BOOKS = {
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua",
    "Judges", "Ruth", "1 Samuel", "2 Samuel", "1 Kings", "2 Kings",
    "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah", "Esther", "Job",
    "Psalms", "Proverbs", "Ecclesiastes", "Song of Songs", "Isaiah",
    "Jeremiah", "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel",
    "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk",
    "Zephaniah", "Haggai", "Zechariah", "Malachi",
}
_APOCRYPHA_BOOKS = {
    "Tobit", "Judith", "Esther (Greek)", "Wisdom",
    "Sirach (Ecclesiasticus)", "Baruch", "Letter of Jeremiah",
    "Prayer of Azariah and the Song of the Three Jews", "Susanna",
    "Bel and the Dragon", "1 Maccabees", "2 Maccabees",
    "1 Esdras", "2 Esdras", "Prayer of Manassah",
}

if _BIBLE_JSON_PATH.exists():
    with open(_BIBLE_JSON_PATH, "r", encoding="utf-8") as _bf:
        _raw = json_module.load(_bf)
    _BIBLE_DATA = _raw.get("books", [])
    print(f"Loaded {len(_BIBLE_DATA)} Bible books from {_BIBLE_JSON_PATH.name}")
else:
    print(f"WARNING: Bible data not found at {_BIBLE_JSON_PATH}")

# ── Request / Response models ─────────────────────────────────────────────────

class CleanRequest(BaseModel):
    text: str
    book: Optional[str] = None
    chapter: Optional[str] = None


class Section(BaseModel):
    index: int
    text: str
    word_count: int
    estimated_minutes: float
    estimated_scenes: int


class CleanResponse(BaseModel):
    sections: list[Section]
    total_sections: int


class GenerateRequest(BaseModel):
    text: str           # The approved (possibly edited) section text
    section_index: int = 0
    model: str = "v1.6"  # Kling model version (v1.6, v2.1, v3.0)


class GenerateResponse(BaseModel):
    status: str
    message: str


class WaitlistRequest(BaseModel):
    email: str


class InviteIssueRequest(BaseModel):
    email: str


class InviteClaimRequest(BaseModel):
    chapter: str  # e.g. "Genesis 1", "Psalm 23"


class RenderDoneRequest(BaseModel):
    # Optional. If omitted, the endpoint auto-pulls from public.renders.video_url
    # via the waitlist row's render_id. If provided, this overrides — useful when
    # the admin wants to send a different URL (e.g. a YouTube link instead of the
    # raw .mp4) without touching the renders row.
    video_url: Optional[str] = None


# ── Bible Selector API ────────────────────────────────────────────────────────

@app.get("/api/bible/books")
async def api_bible_books():
    """Return list of all Bible books with chapter counts, grouped by testament."""
    ot, apoc, nt = [], [], []
    for book in _BIBLE_DATA:
        entry = {"name": book["name"], "chapters": len(book["chapters"])}
        if book["name"] in _OT_BOOKS:
            ot.append(entry)
        elif book["name"] in _APOCRYPHA_BOOKS:
            apoc.append(entry)
        else:
            nt.append(entry)
    return {"old_testament": ot, "apocrypha": apoc, "new_testament": nt}


@app.get("/api/bible/chapter")
async def api_bible_chapter(book: str, chapter: str):
    """Return the full text of a specific Bible chapter."""
    for b in _BIBLE_DATA:
        if b["name"] == book:
            text = b["chapters"].get(chapter)
            if text:
                return {"text": text}
            raise HTTPException(status_code=404, detail=f"Chapter {chapter} not found in {book}")
    raise HTTPException(status_code=404, detail=f"Book '{book}' not found")


# ── Voice preview (ElevenLabs TTS, ~5s sample, cached on disk) ────────────────

_VOICE_PREVIEW_TEXT = "In the beginning, God created the heavens and the earth."
_VOICE_PREVIEW_DIR = (Path("/data") if Path("/data").exists() else Path(__file__).parent) / "voice_previews"
_VOICE_PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
_ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


@app.get("/api/voice-preview")
async def api_voice_preview(voice_id: str):
    """Return a ~5-second MP3 sample of the requested ElevenLabs voice. Each
    voice_id is synthesized once and cached on disk, so repeat plays are free."""
    vid = (voice_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", vid):
        raise HTTPException(status_code=400, detail="Invalid voice_id")
    cache_path = _VOICE_PREVIEW_DIR / f"{vid}.mp3"
    if not cache_path.exists():
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            raise HTTPException(status_code=503, detail="ELEVENLABS_API_KEY not configured on server")
        try:
            resp = httpx.post(
                _ELEVENLABS_TTS_URL.format(voice_id=vid),
                headers={
                    "xi-api-key": api_key,
                    "accept": "audio/mpeg",
                    "content-type": "application/json",
                },
                json={
                    "text": _VOICE_PREVIEW_TEXT,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                },
                timeout=30.0,
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"ElevenLabs request failed: {e}")
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=f"ElevenLabs error: {resp.text[:200]}")
        cache_path.write_bytes(resp.content)
    return FileResponse(
        cache_path,
        media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=31536000"},
    )


# ── Cinematic Intro Generator ─────────────────────────────────────────────────

_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
         "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
         "Seventeen", "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

def _number_to_words(n: int) -> str:
    """Convert 1-150 to words. E.g. 1 → 'One', 42 → 'Forty Two', 150 → 'One Hundred Fifty'."""
    if n <= 0:
        return str(n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        return (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")).strip()
    h = n // 100
    remainder = n % 100
    result = _ONES[h] + " Hundred"
    if remainder:
        result += " " + _number_to_words(remainder)
    return result


async def _generate_cinematic_intro(book: str, chapter: str, passage_text: str) -> str:
    """Use GPT-4o-mini to generate a brief cinematic intro for the chapter."""
    chapter_word = _number_to_words(int(chapter)) if chapter.isdigit() else chapter

    try:
        import openai
        client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=120,
            temperature=0.7,
            messages=[{
                "role": "system",
                "content": (
                    "You write brief cinematic introductions for King James Bible chapters. "
                    "These intros will be narrated by a voice-over artist at the start of a cinematic video."
                ),
            }, {
                "role": "user",
                "content": (
                    f"Write a cinematic introduction for {book}, Chapter {chapter_word} from the King James Bible.\n\n"
                    f"Rules:\n"
                    f"- Start with exactly: 'The Book of {book}. Chapter {chapter_word}.'\n"
                    f"- Then add 1-2 sentences summarizing what happens in this chapter in a dramatic, cinematic tone.\n"
                    f"- Use present tense (e.g., 'God speaks', 'Moses leads').\n"
                    f"- Keep the total under 40 words.\n"
                    f"- Do NOT use quotes or colons.\n\n"
                    f"Here is the beginning of the chapter text for context:\n"
                    f"{passage_text[:500]}"
                ),
            }],
        )
        intro = resp.choices[0].message.content.strip()
        return intro
    except Exception as e:
        # Fallback to static intro if AI fails
        print(f"[WARN] AI intro generation failed: {e}. Using static fallback.")
        return f"The Book of {book}. Chapter {chapter_word}."


# ── API Routes ────────────────────────────────────────────────────────────────

@app.post("/api/clean", response_model=CleanResponse)
@limiter.limit(MEDIUM_LIMIT)
async def api_clean(request: Request, req: CleanRequest):
    """Clean and split raw biblical text into video-ready sections."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    cleaned = clean_text(req.text)
    cleaned = kjv_narration_fix(cleaned)
    cleaned = kjv_narration_fix(cleaned)  # Second pass catches cascading substitutions

    # Generate cinematic intro if book/chapter provided
    cinematic_intro = ""
    if req.book and req.chapter:
        cinematic_intro = await _generate_cinematic_intro(req.book, req.chapter, cleaned)

    words = split_into_words(cleaned)

    if not words:
        raise HTTPException(status_code=400, detail="No text remained after cleaning.")

    raw_sections = create_sections(words)

    sections: list[Section] = []
    for i, section_words in enumerate(raw_sections):
        formatted = format_section(section_words, i + 1)
        # Strip UI-only metadata header so the textarea + downstream chunker
        # see pure scripture only. Stats live in the dashboard's stats-bar.
        formatted = re.sub(r'^\s*={3,}\s*SECTION\s+\d+\s*={3,}\s*$', '',
                           formatted, flags=re.MULTILINE)
        formatted = re.sub(r'^\s*Words:\s*\d+.*\|.*Est\.?\s*Video:.*\|.*Scenes?:\s*\d+\s*$',
                           '', formatted, flags=re.MULTILINE)
        formatted = re.sub(r'^\s*Ready for Biblical Video Generator\s*$', '',
                           formatted, flags=re.MULTILINE)
        formatted = re.sub(r'\n\s*\n\s*\n+', '\n\n', formatted).strip()
        # Prepend cinematic intro to the first section only
        if i == 0 and cinematic_intro:
            formatted = cinematic_intro + "\n\n" + formatted.strip()
        else:
            formatted = formatted.strip()
        word_count = len(formatted.split())
        sections.append(
            Section(
                index=i,
                text=formatted,
                word_count=word_count,
                estimated_minutes=round(word_count / 214, 1),
                estimated_scenes=word_count // 40,
            )
        )

    return CleanResponse(sections=sections, total_sections=len(sections))


@app.post("/api/generate", response_model=GenerateResponse)
@limiter.limit(EXPENSIVE_LIMIT)
async def api_generate(request: Request, req: GenerateRequest):
    """Send approved text to the n8n webhook to trigger video generation."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Approved text cannot be empty.")

    # Model → webhook mapping (published n8n workflows)
    KLING_WEBHOOKS = {
        "v1.6": "https://bmbautomations.app.n8n.cloud/webhook/biblical-v8-kling-v16",
        "v2.1": "https://bmbautomations.app.n8n.cloud/webhook/biblical-v8-kling-v21",
        "v3.0": "https://bmbautomations.app.n8n.cloud/webhook/biblical-v8-kling-v30",
    }

    N8N_WEBHOOK_URL = KLING_WEBHOOKS.get(req.model)
    if not N8N_WEBHOOK_URL:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model '{req.model}'. Choose from: {', '.join(KLING_WEBHOOKS.keys())}",
        )

    print(f"🎬 Generating with Kling {req.model} → {N8N_WEBHOOK_URL[:60]}...")

    log_event(request, "app_generate_n8n", model=req.model, words=len(req.text.split()))

    payload = {"text": req.text.strip()}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(N8N_WEBHOOK_URL, json=payload)
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"n8n webhook returned an error: {e.response.status_code} — {e.response.text}",
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach n8n webhook: {e}",
        )

    # Record start time and reset state for this generation
    generation_state["started_at"] = datetime.now(timezone.utc)
    generation_state["project_id"] = None
    generation_state["video_url"]  = None

    return GenerateResponse(
        status="sent",
        message="Workflow triggered. Tracking progress in real time...",
    )


@app.get("/api/status")
async def api_status():
    """
    Real-time generation status.

    Phases (returned as JSON):
      idle            → no generation running
      perplexity      → n8n/Perplexity generating scenes  (0–90 s, time-estimated)
      fal_generation  → FLUX images + Kling videos         (90–2000 s, time-estimated)
      json2video      → JSON2Video assembling video        (2000 s+, real API poll)
      done            → video_url is ready
      error           → something went wrong
    """
    if not generation_state["started_at"]:
        return {"phase": "idle", "elapsed": 0}

    now     = datetime.now(timezone.utc)
    elapsed = (now - generation_state["started_at"]).total_seconds()

    # ── Already finished ──────────────────────────────────────────────────────
    if generation_state["video_url"]:
        return {"phase": "done", "elapsed": elapsed,
                "video_url": generation_state["video_url"]}

    # ── Phase 1: n8n / Perplexity (0–90 s) ──────────────────────────────────
    if elapsed < 90:
        return {"phase": "perplexity", "elapsed": elapsed}

    # ── Phase 2: fal.ai FLUX + Kling generation (90–2000 s) ─────────────────
    if elapsed < 2000:
        scene_estimate = min(20, int((elapsed - 90) / 90) + 1)
        return {"phase": "fal_generation", "elapsed": elapsed,
                "scenes_estimated": scene_estimate}

    # ── Phase 3: JSON2Video assembly (2000 s+) — poll real API ───────────────
    load_dotenv(find_dotenv(), override=True)
    api_key = os.getenv("JSON2VIDEO_API_KEY", "")

    if not api_key:
        # No API key — fall back to time estimate
        return {"phase": "json2video", "status": "rendering",
                "elapsed": elapsed, "realtime": False}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            headers = {"x-api-key": api_key}

            # ── Known project: just check its status ─────────────────────────
            if generation_state["project_id"]:
                r = await client.get(
                    JSON2VIDEO_BASE,
                    params={"project": generation_state["project_id"]},
                    headers=headers,
                )
                r.raise_for_status()
                movie = r.json().get("movie", {})
                status = movie.get("status", "rendering")

                if status == "done":
                    generation_state["video_url"] = movie.get("url", "")
                    return {"phase": "done", "elapsed": elapsed,
                            "video_url": generation_state["video_url"]}

                if status == "error":
                    return {"phase": "error", "elapsed": elapsed,
                            "message": movie.get("message", "JSON2Video render failed.")}

                return {"phase": "json2video", "status": status,
                        "elapsed": elapsed, "realtime": True}

            # ── No project ID yet: list recent projects, find ours ────────────
            r = await client.get(JSON2VIDEO_BASE, headers=headers)
            r.raise_for_status()
            data = r.json()

            # The response may be a list or {"movies": [...]}
            movies = data if isinstance(data, list) else data.get("movies", [])

            # Find the most recent project created at or after our trigger time
            trigger_ts = generation_state["started_at"].timestamp()
            found = None
            for m in movies:
                raw_ts = m.get("date") or m.get("created_at") or m.get("createdAt", "")
                if not raw_ts:
                    continue
                try:
                    # Handle both Z-suffix and +00:00 formats
                    created_ts = datetime.fromisoformat(
                        raw_ts.replace("Z", "+00:00")
                    ).timestamp()
                    if created_ts >= trigger_ts - 120:   # 2-min buffer for clock skew
                        found = m
                        break
                except ValueError:
                    continue

            if found:
                pid = found.get("id") or found.get("project") or found.get("project_id")
                generation_state["project_id"] = pid
                status = found.get("status", "queued")

                if status == "done":
                    generation_state["video_url"] = found.get("url", "")
                    return {"phase": "done", "elapsed": elapsed,
                            "video_url": generation_state["video_url"]}

                return {"phase": "json2video", "status": status,
                        "elapsed": elapsed, "realtime": True}

            # Project not in JSON2Video yet (n8n still running)
            return {"phase": "json2video", "status": "queued",
                    "elapsed": elapsed, "realtime": True}

    except Exception:
        # Network / parse error — fall back gracefully
        return {"phase": "json2video", "status": "rendering",
                "elapsed": elapsed, "realtime": False}


# ── Landing Page ──────────────────────────────────────────────────────────────

LANDING_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Anointed — Scripture Mode</title>
  <!-- build-marker: 2026-05-10T19:50 — js-bundle-fix -->

  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Inter:wght@300;400;500;600&display=swap');
    body { font-family: 'Inter', sans-serif; }
    .title-font { font-family: 'Cinzel', serif; }
    .step-panel { transition: all 0.4s ease; }
    textarea { resize: vertical; }
    .spinner {
      border: 3px solid rgba(255,255,255,0.1);
      border-top-color: #f59e0b;
      border-radius: 50%;
      width: 20px; height: 20px;
      animation: spin 0.8s linear infinite;
      display: inline-block;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .nav-tab { transition: all 0.2s ease; }
    .nav-tab:hover { background: rgba(245,158,11,0.1); }
    .nav-tab.active { border-bottom: 2px solid #f59e0b; color: #f59e0b; }
  </style>
</head>
<body class="bg-gray-950 text-gray-100 min-h-screen">

  <!-- Navigation -->
  <nav class="border-b border-gray-800 bg-gray-950 sticky top-0 z-50">
    <div class="max-w-4xl mx-auto flex items-center">
      <a href="/" class="text-amber-500 text-2xl px-4 hover:text-amber-400 transition-colors" title="Home">✦</a>
      <a href="/app" class="nav-tab active px-5 py-4 text-sm font-medium">Scripture Mode</a>
      <a href="/custom" class="nav-tab px-5 py-4 text-sm text-gray-400 font-medium">Custom Script Mode</a>
      <div class="ml-auto flex items-center gap-4 pr-4">
        <span class="text-xs text-gray-600">Anointed · v13</span>
      </div>
    </div>
  </nav>

  <main class="max-w-4xl mx-auto px-6 py-12">

    <!-- Hero -->
    <div class="text-center mb-12">
      <h2 class="title-font text-3xl font-bold text-white mb-3">Transform Scripture into Cinema</h2>
      <p class="text-gray-400 text-base max-w-xl mx-auto">
        Paste your KJV biblical text below. The pipeline will clean it,
        let you review, then automatically generate a professional 12–20 minute cinematic video.
      </p>
    </div>

    <!-- Step indicators -->
    <div class="flex items-center justify-center gap-2 mb-10 text-sm">
      <div id="step-dot-1" class="flex items-center gap-2">
        <div class="w-7 h-7 rounded-full bg-amber-500 text-black font-bold flex items-center justify-center text-xs">1</div>
        <span class="text-amber-400 font-medium">Input</span>
      </div>
      <div class="h-px w-10 bg-gray-700"></div>
      <div id="step-dot-2" class="flex items-center gap-2 opacity-40">
        <div class="w-7 h-7 rounded-full bg-gray-700 text-gray-300 font-bold flex items-center justify-center text-xs">2</div>
        <span class="text-gray-400 font-medium">Review</span>
      </div>
      <div class="h-px w-10 bg-gray-700"></div>
      <div id="step-dot-3" class="flex items-center gap-2 opacity-40">
        <div class="w-7 h-7 rounded-full bg-gray-700 text-gray-300 font-bold flex items-center justify-center text-xs">3</div>
        <span class="text-gray-400 font-medium">Generating</span>
      </div>
    </div>

    <!-- ── STEP 1: Input ── -->
    <div id="step1" class="step-panel">
      <!-- Bible Chapter Selector -->
      <div class="bg-gray-900 border border-gray-800 rounded-2xl p-6 mb-4">
        <div class="flex items-center justify-between mb-4 cursor-pointer" onclick="toggleBibleSelector()">
          <label class="block text-sm font-medium text-gray-300">
            Select from Bible <span class="text-gray-500 font-normal">(81 books, KJV + Apocrypha)</span>
          </label>
          <svg id="bible-selector-arrow" class="w-5 h-5 text-gray-400 transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
        </div>
        <div id="bible-selector-panel" class="hidden">
          <div class="flex flex-wrap gap-3 items-end">
            <div class="flex-1 min-w-[200px]">
              <label class="block text-xs text-gray-500 mb-1">Book</label>
              <select id="bible-book" onchange="onBookChange()" class="w-full bg-gray-950 border border-gray-700 rounded-lg px-3 py-2.5 text-gray-100 text-sm focus:outline-none focus:border-amber-500">
                <option value="">-- Select a book --</option>
              </select>
            </div>
            <div class="w-32">
              <label class="block text-xs text-gray-500 mb-1">Chapter</label>
              <select id="bible-chapter" class="w-full bg-gray-950 border border-gray-700 rounded-lg px-3 py-2.5 text-gray-100 text-sm focus:outline-none focus:border-amber-500">
                <option value="">--</option>
              </select>
            </div>
            <button onclick="loadBibleChapter()" class="bg-amber-600 hover:bg-amber-500 text-black font-semibold px-5 py-2.5 rounded-lg transition-colors duration-200 text-sm">
              Load Chapter
            </button>
          </div>
          <p id="bible-load-status" class="text-xs text-gray-500 mt-2 hidden"></p>
        </div>
      </div>

      <!-- Text Input -->
      <div class="bg-gray-900 border border-gray-800 rounded-2xl p-6">
        <label class="block text-sm font-medium text-gray-300 mb-3">
          Biblical Text <span class="text-gray-500 font-normal">(KJV scripture — any length)</span>
        </label>
        <textarea
          id="raw-text"
          rows="14"
          placeholder="Select a chapter above, or paste your KJV scripture here...&#10;&#10;Example: In the beginning God created the heaven and the earth..."
          class="w-full bg-gray-950 border border-gray-700 rounded-xl px-4 py-3 text-gray-100 placeholder-gray-600 text-sm focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500"
        ></textarea>
        <div class="flex items-center justify-between mt-4">
          <span id="char-count" class="text-xs text-gray-600">0 characters</span>
          <button
            id="convert-btn"
            onclick="convertText()"
            class="bg-amber-500 hover:bg-amber-400 text-black font-semibold px-8 py-3 rounded-xl transition-colors duration-200 flex items-center gap-2"
          >
            <span>Convert &amp; Clean</span>
          </button>
        </div>
        <div id="convert-error" class="mt-3 text-red-400 text-sm hidden"></div>
      </div>
    </div>

    <!-- ── STEP 2: Review ── -->
    <div id="step2" class="step-panel hidden">
      <div class="bg-gray-900 border border-gray-800 rounded-2xl p-6">

        <div class="flex items-start justify-between mb-4">
          <div>
            <h3 class="text-base font-semibold text-white">Review Cleaned Text</h3>
            <p class="text-sm text-gray-400 mt-0.5">Edit if needed, then approve to start video generation.</p>
          </div>
          <button onclick="backToStep1()" class="text-xs text-gray-500 hover:text-gray-300 underline">← Start over</button>
        </div>

        <!-- Section tabs (hidden when only 1 section) -->
        <div id="section-tabs" class="flex gap-2 mb-4 hidden"></div>

        <!-- Stats bar -->
        <div id="stats-bar" class="flex gap-6 mb-4 p-3 bg-gray-800 rounded-lg text-xs text-gray-400"></div>

        <!-- Cleaned text area -->
        <textarea
          id="cleaned-text"
          rows="14"
          class="w-full bg-gray-950 border border-gray-700 rounded-xl px-4 py-3 text-gray-100 text-sm focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500"
        ></textarea>

        <!-- Model selector -->
        <div class="mt-4 mb-4 p-4 bg-gray-800 rounded-xl border border-gray-700">
          <label class="block text-sm font-medium text-gray-300 mb-2">Kling AI Model</label>
          <div class="grid grid-cols-3 gap-3">
            <label class="relative cursor-pointer">
              <input type="radio" name="kling-model" value="v1.6" class="peer sr-only">
              <div class="p-3 rounded-lg border-2 border-gray-600 peer-checked:border-amber-500 peer-checked:bg-amber-500/10 transition-all">
                <div class="text-sm font-semibold text-white">v1.6 Standard</div>
                <div class="text-xs text-gray-400 mt-1">Basic motion · Fastest</div>
                <div class="text-xs text-amber-400 mt-1 font-medium">~$10/chapter</div>
              </div>
            </label>
            <label class="relative cursor-pointer">
              <input type="radio" name="kling-model" value="v2.1" class="peer sr-only">
              <div class="p-3 rounded-lg border-2 border-gray-600 peer-checked:border-amber-500 peer-checked:bg-amber-500/10 transition-all">
                <div class="text-sm font-semibold text-white">v2.1 Standard</div>
                <div class="text-xs text-gray-400 mt-1">Better motion · Mid-tier</div>
                <div class="text-xs text-amber-400 mt-1 font-medium">~$10/chapter</div>
              </div>
            </label>
            <label class="relative cursor-pointer">
              <input type="radio" name="kling-model" value="v3.0" class="peer sr-only" checked>
              <div class="p-3 rounded-lg border-2 border-gray-600 peer-checked:border-amber-500 peer-checked:bg-amber-500/10 transition-all">
                <div class="text-sm font-semibold text-white">v3.0 Standard</div>
                <div class="text-xs text-gray-400 mt-1">Best value · 15s clips</div>
                <div class="text-xs text-amber-400 mt-1 font-medium">~$27/chapter</div>
              </div>
            </label>
            <label class="relative cursor-pointer">
              <input type="radio" name="kling-model" value="v3.0-pro" class="peer sr-only">
              <div class="p-3 rounded-lg border-2 border-gray-600 peer-checked:border-amber-500 peer-checked:bg-amber-500/10 transition-all">
                <div class="text-sm font-semibold text-white">v3.0 Pro</div>
                <div class="text-xs text-gray-400 mt-1">Higher quality · 15s clips</div>
                <div class="text-xs text-amber-400 mt-1 font-medium">~$35/chapter</div>
              </div>
            </label>
            <label class="relative cursor-pointer">
              <input type="radio" name="kling-model" value="o3" class="peer sr-only">
              <div class="p-3 rounded-lg border-2 border-gray-600 peer-checked:border-purple-500 peer-checked:bg-purple-500/10 transition-all">
                <div class="text-sm font-semibold text-white">O3 Standard</div>
                <div class="text-xs text-gray-400 mt-1">Character consistency</div>
                <div class="text-xs text-purple-400 mt-1 font-medium">~$45/chapter</div>
              </div>
            </label>
            <label class="relative cursor-pointer">
              <input type="radio" name="kling-model" value="o3-pro" class="peer sr-only">
              <div class="p-3 rounded-lg border-2 border-gray-600 peer-checked:border-purple-500 peer-checked:bg-purple-500/10 transition-all">
                <div class="text-sm font-semibold text-white">O3 Pro</div>
                <div class="text-xs text-gray-400 mt-1">Best consistency · Premium</div>
                <div class="text-xs text-purple-400 mt-1 font-medium">~$60/chapter</div>
              </div>
            </label>
          </div>
        </div>

        <!-- Aspect ratio selector -->
        <div class="mt-4 mb-4 p-4 bg-gray-800 rounded-xl border border-gray-700">
          <label class="block text-sm font-medium text-gray-300 mb-2">Aspect Ratio</label>
          <div class="grid grid-cols-3 gap-3">
            <label class="relative cursor-pointer">
              <input type="radio" name="aspect-ratio" value="16:9" class="peer sr-only" checked>
              <div class="p-3 rounded-lg border-2 border-gray-600 peer-checked:border-amber-500 peer-checked:bg-amber-500/10 transition-all">
                <div class="text-sm font-semibold text-white">LONG · 16:9</div>
                <div class="text-xs text-gray-400 mt-1">YouTube / TV</div>
                <div class="text-xs text-amber-400 mt-1 font-medium">1920×1080</div>
              </div>
            </label>
            <label class="relative cursor-pointer">
              <input type="radio" name="aspect-ratio" value="1:1" class="peer sr-only">
              <div class="p-3 rounded-lg border-2 border-gray-600 peer-checked:border-amber-500 peer-checked:bg-amber-500/10 transition-all">
                <div class="text-sm font-semibold text-white">MIDDLE · 1:1</div>
                <div class="text-xs text-gray-400 mt-1">IG / FB Feed</div>
                <div class="text-xs text-amber-400 mt-1 font-medium">1080×1080</div>
              </div>
            </label>
            <label class="relative cursor-pointer">
              <input type="radio" name="aspect-ratio" value="9:16" class="peer sr-only">
              <div class="p-3 rounded-lg border-2 border-gray-600 peer-checked:border-amber-500 peer-checked:bg-amber-500/10 transition-all">
                <div class="text-sm font-semibold text-white">SHORT · 9:16</div>
                <div class="text-xs text-gray-400 mt-1">Reels / TikTok / Shorts</div>
                <div class="text-xs text-amber-400 mt-1 font-medium">1080×1920</div>
              </div>
            </label>
          </div>
        </div>

        <!-- Voice selector -->
        <div class="mt-4 mb-4 p-4 bg-gray-800 rounded-xl border border-gray-700">
          <label for="bible-voice" class="block text-sm font-medium text-gray-300 mb-2">ElevenLabs Voice</label>
          <div class="flex items-center gap-2">
            <select id="bible-voice"
              class="flex-1 bg-gray-950 border border-gray-700 rounded-lg px-3 py-2.5 text-gray-100 text-sm focus:outline-none focus:border-amber-500">
              <option value="">Loading voices...</option>
            </select>
            <button type="button" id="bible-voice-play" onclick="playVoicePreview(selectedBibleVoice(), this)"
              title="Play 5-second sample"
              class="bg-gray-950 border border-gray-700 hover:border-amber-500 hover:text-amber-400 text-gray-300 rounded-lg w-10 h-10 flex items-center justify-center text-sm transition-colors">▶</button>
          </div>
          <label for="bible-voice-custom" class="block text-xs text-gray-400 mt-3 mb-1">Or paste your own voice ID (overrides the dropdown)</label>
          <input id="bible-voice-custom" type="text" placeholder="e.g. 21m00Tcm4TlvDq8ikWAM" spellcheck="false"
            class="w-full bg-gray-950 border border-gray-700 rounded-lg px-3 py-2 text-gray-100 text-xs font-mono focus:outline-none focus:border-amber-500" />
          <p class="text-xs text-gray-500 mt-2">Used by ElevenLabs for narration. Applies to fresh renders and fix-scene re-renders.</p>
        </div>

        <div class="flex items-center justify-between mt-4 flex-wrap gap-3">
          <p class="text-xs text-gray-500">✏️ You can edit the text above before approving.</p>
          <div class="flex items-center gap-3 flex-wrap">
            <button
              id="approve-all-btn"
              onclick="approveAllText()"
              class="bg-amber-600 hover:bg-amber-500 text-black font-semibold px-6 py-3 rounded-xl transition-colors duration-200 hidden items-center gap-2"
              title="Render all sections as one combined video. Costs proportionally more than a single section."
            >
              <span>🎬 Generate ALL Sections</span>
              <span id="approve-all-stats" class="text-xs font-normal opacity-80"></span>
            </button>
            <button
              id="approve-btn"
              onclick="approveText()"
              class="bg-green-600 hover:bg-green-500 text-white font-semibold px-8 py-3 rounded-xl transition-colors duration-200 flex items-center gap-2"
            >
              <span>✓ Generate Scenes</span>
            </button>
          </div>
        </div>
        <div id="approve-error" class="mt-3 text-red-400 text-sm hidden"></div>
      </div>
    </div>

    <!-- ── STEP 2b: Scene Preview & Edit ── -->
    <div id="step2b" class="step-panel hidden">
      <div class="bg-gray-900 border border-gray-800 rounded-2xl p-6">
        <div class="flex items-center gap-3 mb-4">
          <span class="bg-amber-500 text-black text-xs font-bold px-2.5 py-1 rounded-full">2b</span>
          <h2 class="title-font text-lg font-semibold text-white">Review &amp; Edit Scenes</h2>
        </div>
        <p class="text-xs text-gray-400 mb-4">Claude AI generated these scenes from your scripture. Edit any field before generating video.</p>
        <div id="v9ScenesContainer" class="space-y-4"></div>
        <div class="flex items-center gap-4 mt-6">
          <button onclick="addV9Scene()" class="border border-gray-600 hover:border-amber-500 text-gray-300 hover:text-amber-400 px-4 py-2 rounded-lg transition-colors text-sm">
            + Add Scene
          </button>
          <button onclick="setStep(2)" class="border border-gray-600 hover:border-gray-400 text-gray-400 hover:text-white px-4 py-2 rounded-lg transition-colors text-sm">
            ← Back to Text
          </button>
          <button onclick="startV9Video()" id="btnV9GenVideo"
            class="bg-green-600 hover:bg-green-500 text-white font-semibold px-6 py-2.5 rounded-lg transition-colors text-sm ml-auto">
            Generate Video →
          </button>
        </div>
      </div>
    </div>

    <!-- ── STEP 3: Generating ── -->
    <div id="step3" class="step-panel hidden">
      <div class="bg-gray-900 border border-gray-800 rounded-2xl p-8 text-center">
        <div id="step3-icon" class="text-5xl mb-5">🎬</div>
        <h3 id="step3-title" class="title-font text-xl font-semibold text-amber-400 mb-2">Video Generation In Progress</h3>

        <!-- Progress bar -->
        <div class="max-w-md mx-auto mb-2">
          <div class="flex justify-between text-xs text-gray-500 mb-1">
            <span id="progress-stage-label">Starting pipeline...</span>
            <span id="progress-percent">0%</span>
          </div>
          <div class="w-full bg-gray-800 rounded-full h-3 overflow-hidden">
            <div id="progress-bar"
              class="h-3 rounded-full transition-all duration-1000 ease-linear"
              style="width:0%; background: linear-gradient(90deg, #f59e0b, #fbbf24);">
            </div>
          </div>
          <div class="flex justify-between text-xs text-gray-600 mt-1">
            <span id="realtime-badge" class="text-gray-700"></span>
            <span><span id="progress-elapsed">0:00</span> elapsed</span>
          </div>
        </div>

        <!-- Per-scene progress -->
        <div id="v9-scene-progress" class="bg-gray-800 rounded-xl p-5 text-left text-sm max-w-md mx-auto mb-6 mt-4">
          <div class="flex items-center gap-3 text-gray-300 mb-3">
            <span class="text-green-400">✓</span> Text cleaned and processed
          </div>
          <div id="v9-scenes-list" class="space-y-1"></div>
        </div>

        <!-- Stop rendering button (visible during generation) -->
        <div id="v9-stop-panel" class="mb-4">
          <button onclick="stopV9Pipeline()" id="v9-stop-btn"
            class="bg-red-700 hover:bg-red-600 text-white font-semibold px-6 py-2 rounded-lg text-sm">
            ⏹ Stop Rendering
          </button>
          <p class="text-xs text-gray-500 mt-1">Stops the pipeline to save credits. Completed scenes are preserved.</p>
        </div>

        <!-- Video ready panel (hidden until done) -->
        <div id="video-ready-panel" class="hidden mb-6">
          <div class="bg-green-900/30 border border-green-700 rounded-xl p-5 max-w-md mx-auto">
            <p class="text-green-400 font-semibold mb-3">🎉 Your video is ready!</p>
            <a id="video-download-link" href="#" target="_blank"
              class="block w-full bg-green-600 hover:bg-green-500 text-white font-semibold py-3 rounded-xl transition-colors text-center">
              ⬇ Download Video
            </a>
            <div id="video-parts-panel" class="hidden mt-3 space-y-2"></div>
          </div>
        </div>

        <!-- Error panel with retry -->
        <div id="v9-error-panel" class="hidden mb-6">
          <div class="bg-red-900/30 border border-red-700 rounded-xl p-5 max-w-md mx-auto">
            <p class="text-red-400 font-semibold mb-2">Pipeline Error</p>
            <p id="v9-error-msg" class="text-xs text-red-300 mb-3"></p>
            <button onclick="retryV9()"
              class="bg-amber-600 hover:bg-amber-500 text-black font-semibold px-6 py-2 rounded-lg text-sm">
              Retry from Failed Scene →
            </button>
          </div>
        </div>

        <!-- Multi-Fix Scenes panel -->
        <div id="v9-fix-panel" class="hidden mb-6">
          <div class="bg-gray-800 border border-gray-700 rounded-xl p-5 max-w-2xl mx-auto text-left">
            <h4 class="text-sm font-semibold text-purple-400 mb-1">Fix Scenes</h4>
            <p class="text-xs text-gray-400 mb-3">Select scenes to fix, edit their prompts, then regenerate all at once with ONE render.</p>
            <div id="v9-fix-scene-list" class="space-y-2 mb-4 max-h-96 overflow-y-auto pr-1"></div>
            <div class="flex items-center justify-between mb-3">
              <p id="v9-fix-cost" class="text-xs text-yellow-400">Select scenes above</p>
              <p class="text-xs text-yellow-500">Tip: Never put text/words in image prompts</p>
            </div>
            <button onclick="fixV9Scenes()" id="v9-fix-btn"
              class="bg-purple-600 hover:bg-purple-500 text-white font-semibold px-6 py-2 rounded-lg text-sm disabled:opacity-40 disabled:cursor-not-allowed" disabled>
              Regenerate Selected Scenes →
            </button>
          </div>
        </div>

        <button
          onclick="startOver()"
          class="text-sm text-gray-400 hover:text-white border border-gray-700 hover:border-gray-500 px-6 py-2 rounded-lg transition-colors"
        >
          Generate Another Video
        </button>
      </div>
    </div>

    <!-- History divider -->
    <div class="flex items-center gap-4 mt-12 mb-6">
      <div class="flex-1 h-px bg-gray-800"></div>
      <span class="text-xs text-gray-600 font-semibold tracking-widest uppercase">History</span>
      <div class="flex-1 h-px bg-gray-800"></div>
    </div>

    <!-- ── Render History ── -->
    <div id="history-panel">
      <div class="bg-gray-900 border border-gray-800 rounded-2xl p-6 mb-6">
        <div class="flex items-start justify-between mb-5">
          <div class="flex items-start gap-3">
            <div class="w-7 h-7 rounded-full bg-indigo-600 text-white font-bold flex items-center justify-center text-xs flex-shrink-0 mt-0.5">H</div>
            <div>
              <h3 class="text-base font-semibold text-white">Render History</h3>
              <p class="text-sm text-gray-400 mt-0.5">Past renders with scenes and video links.</p>
            </div>
          </div>
          <button onclick="loadHistory()" title="Refresh"
            class="text-xs text-gray-500 hover:text-gray-200 border border-gray-700 hover:border-gray-500 px-2.5 py-1 rounded-lg transition-colors">
            ↺
          </button>
        </div>
        <div id="history-list" class="space-y-2 max-h-96 overflow-y-auto">
          <p class="text-xs text-gray-600">Click ↺ to load history</p>
        </div>
      </div>
    </div>

  </main>

  <script>
    // ── State ──
    let allSections = [];
    let activeSectionIndex = 0;
    let pollTimer = null;

    // ── Helpers ──────────────────────────────────────────────────────────────
    function fmt(s) {
      s = Math.floor(s);
      const m = Math.floor(s / 60), sec = s % 60;
      return m + ':' + String(sec).padStart(2, '0');
    }

    // ── V9 per-scene progress ─────────────────────────────────────────────
    let v9Scenes = [];

    function initV9Progress(total) {
      const list = document.getElementById('v9-scenes-list');
      list.innerHTML = '';
      for (let i = 0; i < total; i++) {
        list.innerHTML += `<div class="flex items-center gap-2" id="v9sp_${i}">
          <span class="w-2 h-2 rounded-full bg-gray-600" id="v9dot_${i}"></span>
          <span class="text-xs text-gray-500" id="v9txt_${i}">Scene ${i+1} — waiting</span>
        </div>`;
      }
      document.getElementById('v9-error-panel').classList.add('hidden');
      document.getElementById('v9-fix-panel').classList.add('hidden');
      document.getElementById('video-ready-panel').classList.add('hidden');
    }

    function setBar(pct, label) {
      document.getElementById('progress-bar').style.width = Math.min(pct, 100) + '%';
      document.getElementById('progress-percent').textContent = Math.min(pct, 100) + '%';
      document.getElementById('progress-stage-label').textContent = label;
      document.getElementById('realtime-badge').textContent = '● Live';
      document.getElementById('realtime-badge').className = 'text-green-500 font-medium';
    }

    // ── Polling ───────────────────────────────────────────────────────────────
    function startPolling() {
      stopPolling();
      pollStatus();
      pollTimer = setInterval(pollStatus, 2000);
    }

    function stopPolling() {
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    }

    async function pollStatus() {
      try {
        const res = await fetch('/v9/api/status');
        if (!res.ok) return;
        const data = await res.json();
        applyV9Status(data);
      } catch (_) {}
    }

    function applyV9Status(data) {
      const msg = data.message || '';

      if (data.phase === 'generating_scenes') {
        setBar(5, 'Claude AI generating scene visuals...');
      } else if (data.phase === 'generating_media') {
        const pct = data.total_scenes > 0 ? Math.round((data.current_scene / data.total_scenes) * 80) : 0;
        setBar(pct, msg);
        for (let i = 0; i < data.total_scenes; i++) {
          const dot = document.getElementById('v9dot_' + i);
          const txt = document.getElementById('v9txt_' + i);
          if (!dot) continue;
          if (i < (data.processed || []).length) {
            dot.className = 'w-2 h-2 rounded-full bg-green-500';
            txt.className = 'text-xs text-green-400';
            txt.textContent = `Scene ${i+1} — done`;
          } else if (i === data.current_scene - 1) {
            dot.className = 'w-2 h-2 rounded-full bg-amber-500';
            txt.className = 'text-xs text-amber-400';
            txt.textContent = `Scene ${i+1} — ${msg.includes('FLUX') ? 'generating image...' : 'generating video...'}`;
          }
        }
      } else if (data.phase === 'rendering') {
        setBar(90, 'JSON2Video assembling final video...');
        // Mark all scenes done
        for (let i = 0; i < data.total_scenes; i++) {
          const dot = document.getElementById('v9dot_' + i);
          const txt = document.getElementById('v9txt_' + i);
          if (!dot) continue;
          dot.className = 'w-2 h-2 rounded-full bg-green-500';
          txt.className = 'text-xs text-green-400';
          txt.textContent = `Scene ${i+1} — done`;
        }
      } else if (data.phase === 'done') {
        stopPolling();
        setBar(100, 'Video ready!');
        document.getElementById('v9-stop-panel').classList.add('hidden');
        document.getElementById('step3-icon').textContent = '✅';
        document.getElementById('step3-title').textContent = 'Your Video Is Ready';
        document.getElementById('step3-title').className = 'title-font text-xl font-semibold text-green-400 mb-2';
        if (data.video_url) {
          document.getElementById('video-download-link').href = data.video_url;
          document.getElementById('video-ready-panel').classList.remove('hidden');
        }
        if (data.video_urls && data.video_urls.length > 1) {
          const partsPanel = document.getElementById('video-parts-panel');
          partsPanel.innerHTML = '<p class="text-yellow-400 text-sm font-semibold">Long chapter — auto-split into ' + data.video_urls.length + ' parts:</p>';
          data.video_urls.forEach((url, i) => {
            const a = document.createElement('a');
            a.href = url; a.target = '_blank';
            a.className = 'block w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold py-2 rounded-xl transition-colors text-center text-sm';
            a.textContent = '⬇ Download Part ' + (i + 1);
            partsPanel.appendChild(a);
          });
          partsPanel.classList.remove('hidden');
          document.getElementById('video-download-link').textContent = '⬇ Download Part 1';
        }
        // Sync v9Scenes from backend so fix panel always shows latest scene data
        if (data.scenes && data.scenes.length) v9Scenes = data.scenes;
        showV9FixPanel();
      } else if (data.phase === 'error' || data.phase === 'stopped') {
        stopPolling();
        document.getElementById('v9-stop-panel').classList.add('hidden');
        if (data.phase === 'stopped') {
          setBar(0, 'Pipeline stopped by user');
          document.getElementById('v9-error-panel').classList.remove('hidden');
          document.getElementById('v9-error-msg').textContent = 'Stopped by user. Completed scenes preserved — use Retry to resume.';
        } else {
          setBar(0, 'Error');
          document.getElementById('v9-error-panel').classList.remove('hidden');
          document.getElementById('v9-error-msg').textContent = data.error || data.message || 'Unknown error';
        }
      }
    }

    async function retryV9() {
      document.getElementById('v9-error-panel').classList.add('hidden');
      document.getElementById('video-ready-panel').classList.add('hidden');
      document.getElementById('v9-stop-panel').classList.remove('hidden');
      try {
        const res = await fetch('/v9/api/retry', {method: 'POST', headers: {'Content-Type': 'application/json'}});
        if (!res.ok) { const err = await res.json(); throw new Error(err.detail); }
        const data = await res.json();
        setBar(0, `Resuming from Scene ${data.resume_from}...`);
        startPolling();
      } catch(e) {
        document.getElementById('v9-error-panel').classList.remove('hidden');
        document.getElementById('v9-error-msg').textContent = e.message;
      }
    }

    async function stopV9Pipeline() {
      if (!confirm('Stop rendering? Completed scenes are saved, but the current scene will be lost.')) return;
      try {
        const res = await fetch('/v9/api/stop', {method: 'POST'});
        if (!res.ok) { const err = await res.json(); throw new Error(err.detail); }
        stopPolling();
        setBar(0, 'Pipeline stopped by user');
        document.getElementById('v9-stop-panel').classList.add('hidden');
      } catch(e) {
        alert('Failed to stop: ' + e.message);
      }
    }

    function showV9FixPanel() {
      if (!v9Scenes.length) return;
      document.getElementById('v9-fix-panel').classList.remove('hidden');
      const list = document.getElementById('v9-fix-scene-list');
      list.innerHTML = '';
      for (let i = 0; i < v9Scenes.length; i++) {
        const s = v9Scenes[i] || {};
        const narr = (s.narration || '').substring(0, 60) + ((s.narration || '').length > 60 ? '...' : '');
        const type = s.type ? ` [${s.type}]` : '';
        list.innerHTML += `
          <div class="border border-gray-700 rounded-lg">
            <label class="flex items-start gap-3 p-3 cursor-pointer hover:bg-gray-750">
              <input type="checkbox" class="v9-fix-cb mt-1 accent-purple-500" data-idx="${i}" onchange="updateFixCost()">
              <div class="flex-1 min-w-0">
                <span class="text-xs font-semibold text-gray-300">Scene ${i+1}${type}</span>
                <span class="text-xs text-gray-500 ml-2">${narr}</span>
              </div>
            </label>
            <div id="v9-fix-editor-${i}" class="hidden px-3 pb-3">
              <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
                <div>
                  <label class="text-xs text-gray-500 block mb-1">Image Prompt</label>
                  <textarea id="v9-fix-img-${i}" rows="3" class="w-full bg-gray-900 border border-gray-600 rounded-lg px-2 py-1.5 text-xs text-gray-200 focus:outline-none focus:border-purple-500">${s.imagePrompt || ''}</textarea>
                </div>
                <div>
                  <label class="text-xs text-gray-500 block mb-1">Narration (read-only)</label>
                  <textarea rows="3" class="w-full bg-gray-900 border border-gray-600 rounded-lg px-2 py-1.5 text-xs text-gray-400" readonly>${s.narration || ''}</textarea>
                </div>
                <div>
                  <label class="text-xs text-gray-500 block mb-1">Motion</label>
                  <input id="v9-fix-motion-${i}" type="text" value="${s.motion || ''}" class="w-full bg-gray-900 border border-gray-600 rounded-lg px-2 py-1.5 text-xs text-gray-200 focus:outline-none focus:border-purple-500" />
                </div>
                <div>
                  <label class="text-xs text-gray-500 block mb-1">Lighting</label>
                  <input id="v9-fix-lighting-${i}" type="text" value="${s.lighting || ''}" class="w-full bg-gray-900 border border-gray-600 rounded-lg px-2 py-1.5 text-xs text-gray-200 focus:outline-none focus:border-purple-500" />
                </div>
              </div>
            </div>
          </div>`;
      }
      // Toggle inline editors when checkbox changes
      list.querySelectorAll('.v9-fix-cb').forEach(cb => {
        cb.addEventListener('change', () => {
          const editor = document.getElementById('v9-fix-editor-' + cb.dataset.idx);
          editor.classList.toggle('hidden', !cb.checked);
        });
      });
      updateFixCost();
    }

    function updateFixCost() {
      const checked = document.querySelectorAll('.v9-fix-cb:checked').length;
      const costEl = document.getElementById('v9-fix-cost');
      const btn = document.getElementById('v9-fix-btn');
      if (checked === 0) {
        costEl.textContent = 'Select scenes above';
        btn.disabled = true;
      } else {
        costEl.textContent = `~$1.50 for 1 render (${checked} scene${checked > 1 ? 's' : ''} selected)`;
        btn.disabled = false;
      }
    }

    async function fixV9Scenes() {
      const cbs = document.querySelectorAll('.v9-fix-cb:checked');
      if (!cbs.length) return;
      const model = document.querySelector('input[name="kling-model"]:checked')?.value || 'v1.6';
      const aspect_ratio = document.querySelector('input[name="aspect-ratio"]:checked')?.value || '16:9';
      const fixes = [];
      cbs.forEach(cb => {
        const idx = parseInt(cb.dataset.idx);
        const s = v9Scenes[idx] || {};
        const scene = {
          narration: s.narration || '',
          imagePrompt: document.getElementById('v9-fix-img-' + idx)?.value || s.imagePrompt || '',
          motion: document.getElementById('v9-fix-motion-' + idx)?.value || s.motion || '',
          lighting: document.getElementById('v9-fix-lighting-' + idx)?.value || s.lighting || '',
        };
        v9Scenes[idx] = scene;
        fixes.push({scene_index: idx, scene});
      });

      document.getElementById('v9-fix-btn').disabled = true;
      document.getElementById('video-ready-panel').classList.add('hidden');
      document.getElementById('v9-fix-panel').classList.add('hidden');
      document.getElementById('step3-icon').textContent = '🎬';
      document.getElementById('step3-title').textContent = 'Fixing ' + fixes.length + ' Scene' + (fixes.length > 1 ? 's' : '');
      document.getElementById('step3-title').className = 'title-font text-xl font-semibold text-amber-400 mb-2';
      setBar(0, `Regenerating ${fixes.length} scenes...`);
      initV9Progress(v9Scenes.length);

      try {
        const res = await fetch('/v9/api/fix-scenes', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({fixes, model, aspect_ratio, voice_id: selectedBibleVoice()})
        });
        if (!res.ok) { const err = await res.json(); throw new Error(err.detail); }
        startPolling();
      } catch(e) {
        document.getElementById('v9-error-panel').classList.remove('hidden');
        document.getElementById('v9-error-msg').textContent = e.message;
      } finally {
        document.getElementById('v9-fix-btn').disabled = false;
      }
    }

    // ── Render History ────────────────────────────────────────────────────────
    async function loadHistory() {
      const list = document.getElementById('history-list');
      list.innerHTML = '<p class="text-xs text-gray-500">Loading...</p>';
      try {
        const res = await fetch('/v9/api/history');
        const data = await res.json();
        if (!data.length) { list.innerHTML = '<p class="text-xs text-gray-600">No renders yet</p>'; return; }
        list.innerHTML = '';
        data.forEach(h => {
          const label = [h.book, h.chapter].filter(Boolean).join(' ') || 'Custom';
          const date = new Date(h.created_at).toLocaleString();
          const statusColor = h.status === 'done' ? 'text-green-400' : 'text-red-400';
          list.innerHTML += `
            <div class="border border-gray-700 rounded-lg p-3">
              <div class="flex items-center justify-between">
                <div class="flex-1 min-w-0">
                  <span class="text-sm font-semibold text-gray-200">${label}</span>
                  <span class="text-xs text-gray-500 ml-2">${date}</span>
                  <span class="text-xs ${statusColor} ml-2">${h.status}</span>
                  <span class="text-xs text-gray-600 ml-2">${h.scene_count} scenes · ${h.model}</span>
                </div>
                <div class="flex gap-2 flex-shrink-0">
                  ${h.video_url ? `<a href="${h.video_url}" target="_blank" class="text-xs text-blue-400 hover:text-blue-300 border border-gray-700 px-2 py-1 rounded">Download</a>` : ''}
                  <button onclick="viewHistoryItem('${h.id}')" class="text-xs text-indigo-400 hover:text-indigo-300 border border-gray-700 px-2 py-1 rounded">View</button>
                  <button onclick="loadHistoryIntoFix('${h.id}')" class="text-xs text-purple-400 hover:text-purple-300 border border-gray-700 px-2 py-1 rounded">Load & Fix</button>
                </div>
              </div>
              <div id="history-detail-${h.id}" class="hidden mt-3"></div>
            </div>`;
        });
      } catch(e) {
        list.innerHTML = '<p class="text-xs text-red-400">Failed to load history</p>';
      }
    }

    async function viewHistoryItem(id) {
      const detail = document.getElementById('history-detail-' + id);
      if (!detail) return;
      if (!detail.classList.contains('hidden')) { detail.classList.add('hidden'); return; }
      detail.innerHTML = '<p class="text-xs text-gray-500">Loading scenes...</p>';
      detail.classList.remove('hidden');
      try {
        const res = await fetch('/v9/api/history/' + id);
        const data = await res.json();
        if (!data.scenes || !data.scenes.length) { detail.innerHTML = '<p class="text-xs text-gray-600">No scene data</p>'; return; }
        let html = '<div class="space-y-1">';
        data.scenes.forEach((s, i) => {
          const type = s.type ? ` [${s.type}]` : '';
          const narr = (s.narration || '').substring(0, 80) + ((s.narration || '').length > 80 ? '...' : '');
          html += `<div class="text-xs text-gray-400 py-1 border-b border-gray-800">
            <span class="text-gray-300 font-semibold">Scene ${i+1}${type}</span> — ${narr}
          </div>`;
        });
        html += '</div>';
        detail.innerHTML = html;
      } catch(e) {
        detail.innerHTML = '<p class="text-xs text-red-400">Failed to load</p>';
      }
    }

    async function loadHistoryIntoFix(id) {
      try {
        const res = await fetch('/v9/api/history/' + id);
        const data = await res.json();
        if (!data.scenes || !data.scenes.length) { alert('No scene data to load'); return; }
        v9Scenes = data.scenes;
        // Switch to step 3 and show fix panel
        setStep(3);
        document.getElementById('step3-icon').textContent = '🔧';
        document.getElementById('step3-title').textContent = 'Fixing Scenes from History';
        document.getElementById('step3-title').className = 'title-font text-xl font-semibold text-purple-400 mb-2';
        document.getElementById('v9-scene-progress').classList.add('hidden');
        document.getElementById('v9-stop-panel').classList.add('hidden');
        document.getElementById('video-ready-panel').classList.add('hidden');
        document.getElementById('v9-error-panel').classList.add('hidden');
        setBar(0, 'Loaded from history — select scenes to fix');
        showV9FixPanel();
      } catch(e) {
        alert('Failed to load: ' + e.message);
      }
    }

    // ── Bible Chapter Selector ─────────────────────────────────────────────────
    let bibleBooks = null;  // cached from /api/bible/books

    function toggleBibleSelector() {
      const panel = document.getElementById('bible-selector-panel');
      const arrow = document.getElementById('bible-selector-arrow');
      panel.classList.toggle('hidden');
      arrow.style.transform = panel.classList.contains('hidden') ? '' : 'rotate(180deg)';
      if (!panel.classList.contains('hidden') && !bibleBooks) loadBibleBooks();
    }

    async function loadBibleBooks() {
      try {
        const res = await fetch('/api/bible/books');
        const data = await res.json();
        bibleBooks = data;
        const sel = document.getElementById('bible-book');
        sel.innerHTML = '<option value="">-- Select a book --</option>';
        const groups = [
          ['Old Testament', data.old_testament],
          ['Apocrypha', data.apocrypha],
          ['New Testament', data.new_testament],
        ];
        for (const [label, books] of groups) {
          if (!books || books.length === 0) continue;
          const og = document.createElement('optgroup');
          og.label = label;
          for (const b of books) {
            const opt = document.createElement('option');
            opt.value = b.name;
            opt.dataset.chapters = b.chapters;
            opt.textContent = b.name;
            og.appendChild(opt);
          }
          sel.appendChild(og);
        }
      } catch (e) {
        console.error('Failed to load Bible books:', e);
      }
    }

    function onBookChange() {
      const sel = document.getElementById('bible-book');
      const chSel = document.getElementById('bible-chapter');
      chSel.innerHTML = '<option value="">--</option>';
      const opt = sel.options[sel.selectedIndex];
      if (!opt || !opt.dataset.chapters) return;
      const count = parseInt(opt.dataset.chapters);
      for (let i = 1; i <= count; i++) {
        const o = document.createElement('option');
        o.value = i;
        o.textContent = 'Chapter ' + i;
        chSel.appendChild(o);
      }
      if (count === 1) chSel.value = '1';
    }

    async function loadBibleChapter() {
      const book = document.getElementById('bible-book').value;
      const chapter = document.getElementById('bible-chapter').value;
      if (!book || !chapter) return alert('Please select a book and chapter.');
      const textarea = document.getElementById('raw-text');
      if (textarea.value.trim() && !confirm('This will replace the current text. Continue?')) return;
      const status = document.getElementById('bible-load-status');
      status.textContent = 'Loading...';
      status.classList.remove('hidden');
      try {
        const res = await fetch(`/api/bible/chapter?book=${encodeURIComponent(book)}&chapter=${chapter}`);
        if (!res.ok) throw new Error('Chapter not found');
        const data = await res.json();
        textarea.value = data.text;
        textarea.dispatchEvent(new Event('input'));
        status.textContent = `Loaded ${book} Chapter ${chapter}`;
        status.className = 'text-xs text-green-500 mt-2';
        setTimeout(() => { status.classList.add('hidden'); }, 3000);
      } catch (e) {
        status.textContent = 'Failed to load chapter: ' + e.message;
        status.className = 'text-xs text-red-400 mt-2';
      }
    }

    // Auto-load bible books on page load
    fetch('/api/bible/books').then(r => r.json()).then(data => {
      bibleBooks = data;
      const sel = document.getElementById('bible-book');
      sel.innerHTML = '<option value="">-- Select a book --</option>';
      const groups = [
        ['Old Testament', data.old_testament],
        ['Apocrypha', data.apocrypha],
        ['New Testament', data.new_testament],
      ];
      for (const [label, books] of groups) {
        if (!books || books.length === 0) continue;
        const og = document.createElement('optgroup');
        og.label = label;
        for (const b of books) {
          const opt = document.createElement('option');
          opt.value = b.name;
          opt.dataset.chapters = b.chapters;
          opt.textContent = b.name;
          og.appendChild(opt);
        }
        sel.appendChild(og);
      }
    }).catch(() => {});

    // ── Character counter ─────────────────────────────────────────────────────
    document.getElementById('raw-text').addEventListener('input', function() {
      const count = this.value.length;
      const words = this.value.trim() ? this.value.trim().split(/\\s+/).length : 0;
      document.getElementById('char-count').textContent = `${words.toLocaleString()} words · ${count.toLocaleString()} characters`;
    });

    // ── Step 1: Convert ───────────────────────────────────────────────────────
    async function convertText() {
      const rawText = document.getElementById('raw-text').value.trim();
      if (!rawText) {
        showError('convert-error', 'Please paste some biblical text first.');
        return;
      }

      const btn = document.getElementById('convert-btn');
      btn.innerHTML = '<span class="spinner"></span><span>Cleaning...</span>';
      btn.disabled = true;
      hideError('convert-error');

      try {
        const res = await fetch('/api/clean', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: rawText,
            book: document.getElementById('bible-book')?.value || null,
            chapter: document.getElementById('bible-chapter')?.value || null,
          }),
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Cleaning failed.');
        }

        const data = await res.json();
        allSections = data.sections;
        activeSectionIndex = 0;
        showStep2();
      } catch (e) {
        showError('convert-error', e.message);
      } finally {
        btn.innerHTML = '<span>Convert &amp; Clean</span>';
        btn.disabled = false;
      }
    }

    function showStep2() {
      const tabsEl = document.getElementById('section-tabs');
      tabsEl.innerHTML = '';
      if (allSections.length > 1) {
        tabsEl.classList.remove('hidden');
        allSections.forEach((s, i) => {
          const btn = document.createElement('button');
          btn.textContent = `Section ${i + 1}`;
          btn.className = `px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            i === 0 ? 'bg-amber-500 text-black' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
          }`;
          btn.onclick = () => switchSection(i);
          tabsEl.appendChild(btn);
        });
      }
      displaySection(0);
      setStep(2);
    }

    function switchSection(index) {
      activeSectionIndex = index;
      displaySection(index);
      const tabs = document.querySelectorAll('#section-tabs button');
      tabs.forEach((t, i) => {
        t.className = `px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
          i === index ? 'bg-amber-500 text-black' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
        }`;
      });
    }

    function displaySection(index) {
      const s = allSections[index];
      document.getElementById('cleaned-text').value = s.text;
      document.getElementById('stats-bar').innerHTML = `
        <span>📝 <strong class="text-white">${s.word_count.toLocaleString()}</strong> words</span>
        <span>⏱ ~<strong class="text-amber-400">${s.estimated_minutes} min</strong> video</span>
        <span>🎬 ~${s.estimated_scenes} scenes</span>
        ${allSections.length > 1 ? `<span class="ml-auto text-amber-500">Section ${index + 1} of ${allSections.length}</span>` : ''}
      `;
      // Make the Approve button name the active section so it's never ambiguous
      // which slice of text is about to be rendered.
      const approveBtn = document.getElementById('approve-btn');
      if (approveBtn) {
        const span = approveBtn.querySelector('span');
        if (span) {
          span.textContent = allSections.length > 1
            ? `✓ Generate Scenes from Section ${index + 1}`
            : '✓ Generate Scenes';
        }
      }
      // Show "Generate ALL Sections" button only when there's more than one
      // section, and populate it with total word/duration estimates so the
      // user can see what they're committing to.
      const approveAllBtn = document.getElementById('approve-all-btn');
      if (approveAllBtn) {
        if (allSections.length > 1) {
          approveAllBtn.classList.remove('hidden');
          approveAllBtn.classList.add('inline-flex');
          const totalWords = allSections.reduce((sum, x) => sum + (x.word_count || 0), 0);
          const totalMin = allSections.reduce((sum, x) => sum + (x.estimated_minutes || 0), 0);
          const statsSpan = document.getElementById('approve-all-stats');
          if (statsSpan) {
            statsSpan.textContent = `(~${totalWords.toLocaleString()} words · ~${totalMin.toFixed(1)} min)`;
          }
        } else {
          approveAllBtn.classList.add('hidden');
          approveAllBtn.classList.remove('inline-flex');
        }
      }
    }

    // ── Step 2: Approve ───────────────────────────────────────────────────────
    async function _submitForRender(text, btn, restoreLabel) {
      if (!text) {
        showError('approve-error', 'Text cannot be empty.');
        return;
      }
      const model = document.querySelector('input[name="kling-model"]:checked')?.value || 'v3.0';
      const aspect_ratio = document.querySelector('input[name="aspect-ratio"]:checked')?.value || '16:9';
      const originalHtml = btn.innerHTML;
      btn.innerHTML = '<span class="spinner"></span><span>Claude AI generating scenes...</span>';
      btn.disabled = true;
      // Disable the sibling button too so the user can't double-submit.
      const sibling = btn.id === 'approve-btn'
        ? document.getElementById('approve-all-btn')
        : document.getElementById('approve-btn');
      if (sibling) sibling.disabled = true;
      hideError('approve-error');

      try {
        const res = await fetch('/v9/api/generate-scenes', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: text,
            model: model,
            aspect_ratio: aspect_ratio,
            book: document.getElementById('bible-book')?.value || '',
            chapter: document.getElementById('bible-chapter')?.value || '',
            voice_id: selectedBibleVoice(),
          }),
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Failed to generate scenes.');
        }

        const data = await res.json();
        v9Scenes = data.scenes || [];
        renderV9Scenes();
        setStep('2b');
      } catch (e) {
        showError('approve-error', e.message);
      } finally {
        btn.innerHTML = restoreLabel || originalHtml;
        btn.disabled = false;
        if (sibling) sibling.disabled = false;
      }
    }

    async function approveText() {
      const approvedText = document.getElementById('cleaned-text').value.trim();
      const btn = document.getElementById('approve-btn');
      const label = allSections.length > 1
        ? `<span>✓ Generate Scenes from Section ${activeSectionIndex + 1}</span>`
        : '<span>✓ Generate Scenes</span>';
      await _submitForRender(approvedText, btn, label);
    }

    async function approveAllText() {
      if (!allSections || allSections.length < 2) return;
      // Concatenate the cleaned text of every section. Each section's text
      // already had its metadata header stripped server-side at /api/clean.
      // Use fromCharCode(10) for the paragraph break so we never put a
      // backslash escape inside a quoted string — the surrounding Python
      // triple-quoted literal eats those and breaks JS parsing.
      const NL2 = String.fromCharCode(10) + String.fromCharCode(10);
      const combined = allSections.map(s => s.text.trim()).filter(Boolean).join(NL2);
      const btn = document.getElementById('approve-all-btn');
      const totalWords = allSections.reduce((sum, x) => sum + (x.word_count || 0), 0);
      const totalMin = allSections.reduce((sum, x) => sum + (x.estimated_minutes || 0), 0);
      const label = `<span>🎬 Generate ALL Sections</span><span class="text-xs font-normal opacity-80">(~${totalWords.toLocaleString()} words · ~${totalMin.toFixed(1)} min)</span>`;
      await _submitForRender(combined, btn, label);
    }

    function escHtml(s) { return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

    function renderV9Scenes() {
      const c = document.getElementById('v9ScenesContainer');
      c.innerHTML = '';
      v9Scenes.forEach((s, i) => {
        c.innerHTML += '<div class="scene-card bg-gray-800 border border-gray-700 rounded-xl p-5" data-idx="'+i+'">'
          +'<div class="flex items-center justify-between mb-3">'
          +'<span class="text-amber-400 font-semibold text-sm">Scene '+(i+1)+' <span class="text-gray-500 text-xs ml-2">('+(s.type||'scripture')+')</span></span>'
          +'<button onclick="removeV9Scene('+i+')" class="text-red-500 hover:text-red-400 text-xs">✕ Remove</button></div>'
          +'<div class="grid grid-cols-1 md:grid-cols-2 gap-3">'
          +'<div><label class="text-xs text-gray-500 block mb-1">Narration</label>'
          +'<textarea rows="3" class="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-xs text-gray-200 focus:outline-none focus:border-amber-500" onchange="v9Scenes['+i+'].narration=this.value">'+escHtml(s.narration||'')+'</textarea></div>'
          +'<div><label class="text-xs text-gray-500 block mb-1">Image Prompt</label>'
          +'<textarea rows="3" class="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-xs text-gray-200 focus:outline-none focus:border-amber-500" onchange="v9Scenes['+i+'].imagePrompt=this.value">'+escHtml(s.imagePrompt||'')+'</textarea></div>'
          +'<div><label class="text-xs text-gray-500 block mb-1">Motion</label>'
          +'<input type="text" class="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-xs text-gray-200 focus:outline-none focus:border-amber-500" value="'+escHtml(s.motion||'')+'" onchange="v9Scenes['+i+'].motion=this.value" /></div>'
          +'<div><label class="text-xs text-gray-500 block mb-1">Lighting</label>'
          +'<input type="text" class="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-xs text-gray-200 focus:outline-none focus:border-amber-500" value="'+escHtml(s.lighting||'')+'" onchange="v9Scenes['+i+'].lighting=this.value" /></div>'
          +'</div></div>';
      });
    }

    function removeV9Scene(i) { v9Scenes.splice(i, 1); renderV9Scenes(); }
    function addV9Scene() {
      v9Scenes.push({type:'scripture', narration:'', imagePrompt:'', motion:'Slow cinematic camera movement', lighting:'Golden divine light from above'});
      renderV9Scenes();
    }

    async function startV9Video() {
      if (v9Scenes.length === 0) return alert('No scenes to generate');
      const model = document.querySelector('input[name="kling-model"]:checked')?.value || 'v3.0';
      const aspect_ratio = document.querySelector('input[name="aspect-ratio"]:checked')?.value || '16:9';
      const btn = document.getElementById('btnV9GenVideo');
      btn.disabled = true;
      btn.textContent = 'Starting...';
      try {
        const res = await fetch('/v9/api/generate-video', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            scenes: v9Scenes,
            model: model,
            aspect_ratio: aspect_ratio,
            voice_id: selectedBibleVoice(),
          }),
        });
        if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Failed to start pipeline'); }
        setStep(3);
        initV9Progress(v9Scenes.length);
        startPolling();
      } catch(e) { alert(e.message); }
      finally { btn.disabled = false; btn.textContent = 'Generate Video →'; }
    }

    // ── Navigation ────────────────────────────────────────────────────────────
    function backToStep1() { setStep(1); }

    function startOver() {
      stopPolling();
      // Reset step 3 visual state
      document.getElementById('progress-bar').style.width = '0%';
      document.getElementById('progress-percent').textContent = '0%';
      document.getElementById('progress-elapsed').textContent = '0:00';
      document.getElementById('progress-stage-label').textContent = 'Starting pipeline...';
      document.getElementById('realtime-badge').textContent = '';
      document.getElementById('video-ready-panel').classList.add('hidden');
      document.getElementById('v9-error-panel').classList.add('hidden');
      document.getElementById('v9-fix-panel').classList.add('hidden');
      document.getElementById('v9-scenes-list').innerHTML = '';
      document.getElementById('step3-icon').textContent = '🎬';
      document.getElementById('step3-title').textContent = 'Video Generation In Progress';
      document.getElementById('step3-title').className = 'title-font text-xl font-semibold text-amber-400 mb-2';
      v9Scenes = [];
      setStep(1);
      document.getElementById('raw-text').value = '';
      document.getElementById('char-count').textContent = '0 characters';
    }

    function setStep(n) {
      // Hide all panels including 2b
      ['1', '2', '2b', '3'].forEach(id => {
        const el = document.getElementById(`step${id}`);
        if (el) el.classList.toggle('hidden', id !== String(n));
      });
      // Update step dots (1, 2, 3) — '2b' shares dot 2
      const numericStep = n === '2b' ? 2 : n;
      [1, 2, 3].forEach(i => {
        const dot    = document.getElementById(`step-dot-${i}`);
        const circle = dot.querySelector('div');
        if (i < numericStep) {
          dot.classList.remove('opacity-40');
          circle.className = 'w-7 h-7 rounded-full bg-green-600 text-white font-bold flex items-center justify-center text-xs';
        } else if (i === numericStep) {
          dot.classList.remove('opacity-40');
          circle.className = 'w-7 h-7 rounded-full bg-amber-500 text-black font-bold flex items-center justify-center text-xs';
        } else {
          dot.classList.add('opacity-40');
          circle.className = 'w-7 h-7 rounded-full bg-gray-700 text-gray-300 font-bold flex items-center justify-center text-xs';
        }
      });
    }

    function showError(id, msg) { const el = document.getElementById(id); el.textContent = '⚠ ' + msg; el.classList.remove('hidden'); }
    function hideError(id) { document.getElementById(id).classList.add('hidden'); }

    // Populate voice picker from server. Runs once at load — voices rarely change.
    async function loadV9Voices() {
      const sel = document.getElementById('bible-voice');
      if (!sel) return;
      try {
        const res = await fetch('/v9/api/voices');
        const data = await res.json();
        const voices = data.voices || [];
        const def = data.default;
        sel.innerHTML = voices.map(v =>
          '<option value="' + v.id + '"' + (v.id === def ? ' selected' : '') + '>' + escHtml(v.name) + '</option>'
        ).join('');
      } catch(e) {
        sel.innerHTML = '<option value="">Voice list unavailable</option>';
      }
    }

    // Custom-ID input wins over the dropdown when filled — lets users paste any ElevenLabs id.
    function selectedBibleVoice() {
      const custom = (document.getElementById('bible-voice-custom')?.value || '').trim();
      if (custom) return custom;
      return document.getElementById('bible-voice')?.value || '';
    }

    // Voice preview — singleton audio so a second click stops the first.
    let _voicePreviewAudio = null;
    async function playVoicePreview(voiceId, btn) {
      const id = (voiceId || '').trim();
      if (!id) return;
      if (_voicePreviewAudio && !_voicePreviewAudio.paused && _voicePreviewAudio.dataset.voiceId === id) {
        _voicePreviewAudio.pause();
        return;
      }
      if (_voicePreviewAudio) { try { _voicePreviewAudio.pause(); } catch(e) {} _voicePreviewAudio = null; }
      const restore = () => { if (btn) { btn.textContent = '▶'; btn.disabled = false; } };
      if (btn) { btn.textContent = '⏳'; btn.disabled = true; }
      const audio = new Audio('/api/voice-preview?voice_id=' + encodeURIComponent(id));
      audio.dataset.voiceId = id;
      audio.onplay  = () => { if (btn) { btn.textContent = '⏸'; btn.disabled = false; } };
      audio.onended = restore;
      audio.onpause = restore;
      audio.onerror = () => {
        if (btn) {
          btn.textContent = '⚠';
          btn.disabled = false;
          setTimeout(() => { if (btn.textContent === '⚠') btn.textContent = '▶'; }, 2000);
        }
      };
      _voicePreviewAudio = audio;
      try { await audio.play(); } catch(e) { restore(); }
    }

    // Populate the voice picker on page load.
    window.addEventListener('load', () => { loadV9Voices(); });

  </script>
</body>
</html>"""


# ── Marketing landing page (public) ──────────────────────────────────────────
# Locate landingpage/web/ — Modal bakes it at /app/landingpage/web,
# locally we walk up 4 levels from this file (server → biblical-cinematic → workflows → repo root)
if os.getenv("DEPLOYED"):
    _LANDING_DIR = Path("/app/landingpage/web")
else:
    _LANDING_DIR = Path(__file__).parent.parent.parent.parent / "landingpage" / "web"

_LANDING_HTML_PATH = _LANDING_DIR / "index.html"
_INVITE_HTML_PATH  = _LANDING_DIR / "invite.html"
_ADMIN_HTML_PATH   = _LANDING_DIR / "admin.html"
_ROADMAP_HTML_PATH = _LANDING_DIR / "roadmap.html"
_LANDING_ASSET_WHITELIST = {
    "hero-loop.mp4", "sample-1.mp4", "sample-2.mp4", "sample-3.mp4", "sample-4.mp4",
    "hero-poster.jpg", "sample-1-poster.jpg", "sample-2-poster.jpg",
}


@app.get("/", response_class=HTMLResponse)
async def landing_marketing():
    """Public marketing landing page. Falls back to the app if assets are missing."""
    if _LANDING_HTML_PATH.exists():
        return HTMLResponse(content=_LANDING_HTML_PATH.read_text(encoding="utf-8"))
    # Fallback: if landing assets weren't deployed, show the tool directly
    return HTMLResponse(content=LANDING_PAGE)


@app.get("/admin/", response_class=HTMLResponse)
async def admin_panel():
    """Admin panel — single page wrapping /admin/waitlist + per-row buttons.
    Gated by Basic Auth via the existing middleware."""
    if _ADMIN_HTML_PATH.exists():
        return HTMLResponse(content=_ADMIN_HTML_PATH.read_text(encoding="utf-8"))
    return HTMLResponse(
        content="<h1>Admin panel not deployed</h1>",
        status_code=503,
    )


@app.get("/admin/roadmap", response_class=HTMLResponse)
async def admin_roadmap():
    """SaaS roadmap status dashboard — visual mirror of docs/SAAS_ROADMAP.md.
    Gated by Basic Auth via the existing /admin/* middleware."""
    if _ROADMAP_HTML_PATH.exists():
        return HTMLResponse(content=_ROADMAP_HTML_PATH.read_text(encoding="utf-8"))
    return HTMLResponse(
        content="<h1>Roadmap dashboard not deployed</h1>",
        status_code=503,
    )


@app.get("/invite/{token}", response_class=HTMLResponse)
async def invite_landing(token: str):
    """Public — invite landing page. Serves invite.html (which reads the token
    from the URL path via JS and calls /api/invite/{token} to validate)."""
    if _INVITE_HTML_PATH.exists():
        return HTMLResponse(content=_INVITE_HTML_PATH.read_text(encoding="utf-8"))
    return HTMLResponse(
        content="<h1>Invite page not deployed</h1>",
        status_code=503,
    )


@app.get("/landing/{filename}")
async def landing_asset(filename: str):
    """Serves whitelisted videos and posters used by the marketing landing page."""
    if filename not in _LANDING_ASSET_WHITELIST:
        return JSONResponse({"error": "not found"}, status_code=404)
    path = _LANDING_DIR / filename
    if not path.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    media_type = "video/mp4" if filename.endswith(".mp4") else "image/jpeg"
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/app", response_class=HTMLResponse)
async def app_tool_page():
    """The Scripture Mode tool itself. Was at `/`, demoted to `/app` for the marketing site."""
    return HTMLResponse(content=LANDING_PAGE)


# ── Waitlist signup (public) ─────────────────────────────────────────────────
import db as _db_mod  # imported here to keep top-of-file imports unchanged

_RESEND_API_KEY = os.getenv("RESEND_API_KEY")
_WAITLIST_NOTIFY_EMAIL = "aibiblegospels444@gmail.com"
_WAITLIST_FROM = "Anointed <hello@anointed.app>"
_YOUTUBE_CHANNEL_URL = "https://www.youtube.com/@AIBibleGospels"
_ANOINTED_BASE_URL = "https://anointed.app"
_STRIPE_LINK_25 = os.getenv("STRIPE_LINK_25", "")  # 1 paid chapter
_STRIPE_LINK_50 = os.getenv("STRIPE_LINK_50", "")  # 3 paid chapters (bundle)
_STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _resend_send(to: list[str], subject: str, html: str, reply_to: Optional[str] = None) -> None:
    """Tiny wrapper around the Resend HTTP API. Swallows all errors."""
    if not _RESEND_API_KEY:
        print(f"[waitlist] RESEND_API_KEY not set — skipping email to {to}")
        return
    try:
        payload = {"from": _WAITLIST_FROM, "to": to, "subject": subject, "html": html}
        if reply_to:
            payload["reply_to"] = reply_to
        with httpx.Client(timeout=10.0) as client:
            r = client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {_RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            r.raise_for_status()
    except Exception as e:
        print(f"[waitlist] Resend send to {to} failed: {e}")


_CRM_BASE = os.environ.get("BMB_CRM_INGEST_URL", "").rstrip("/")
_CRM_KEY = os.environ.get("BMB_CRM_API_KEY", "")


def _push_lead_to_crm(email: str, source: str,
                      pipeline_stage: Optional[str] = None) -> None:
    """Fire-and-forget: mirror a signup into the BMB LeadStack CRM.

    Swallows all errors so a CRM outage never affects the signup flow. Skips
    silently when the CRM env vars aren't configured. Email-only signups land
    as contacts (no pipeline stage) — in the database and reachable, but not on
    the sales board.
    """
    if not _CRM_BASE or not _CRM_KEY:
        return
    name = (email or "").strip().lower()
    if not name:
        return
    try:
        with httpx.Client(timeout=8.0) as client:
            r = client.post(
                f"{_CRM_BASE}/api/v1/contacts",
                headers={
                    "Authorization": f"Bearer {_CRM_KEY}",
                    "Content-Type": "application/json",
                    # 24h idempotency so a double-submit doesn't create two contacts.
                    # CRM only allows [A-Za-z0-9_-:.]; strip the rest (e.g. "@" in emails).
                    "Idempotency-Key": re.sub(r"[^A-Za-z0-9_:.-]", "-", f"{source}:{name}")[:255],
                },
                json={
                    "name": name,
                    "email": name,
                    "source": "website-form",
                    "tags": ["anointed", source],
                    "pipeline_stage": pipeline_stage,
                },
            )
            r.raise_for_status()
    except Exception as e:
        print(f"[crm] ingest for {email} failed: {e}")


def _send_waitlist_notification(email: str, ip: str, source: str) -> None:
    """Fire-and-forget notification to the project inbox via Resend."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = (
        f"<h2 style='font-family:sans-serif'>New Anointed waitlist signup</h2>"
        f"<p style='font-family:sans-serif;font-size:16px'><strong>{email}</strong></p>"
        f"<p style='font-family:sans-serif;color:#666;font-size:13px'>"
        f"Source: {source}<br>IP: {ip}<br>Time: {ts}</p>"
        f"<p style='font-family:sans-serif;color:#888;font-size:12px;margin-top:24px'>"
        f"View the full waitlist at "
        f"<a href='https://anointed.app/admin/waitlist'>anointed.app/admin/waitlist</a></p>"
    )
    _resend_send([_WAITLIST_NOTIFY_EMAIL], f"New beta signup: {email}", html)


def _send_signer_confirmation(email: str) -> None:
    """Welcome email to the person who signed up — step 2 of the beta ROI flow."""
    html = (
        f"<div style='font-family:sans-serif;max-width:560px;margin:0 auto;color:#222'>"
        f"<h2 style='font-size:22px;margin-bottom:8px'>You're on the list 🙏</h2>"
        f"<p style='font-size:16px;line-height:1.5'>"
        f"Thanks for joining the Anointed beta. You'll get your private invite link "
        f"in the next few days — pick any chapter of scripture and we'll turn it into "
        f"a cinematic short for you.</p>"
        f"<p style='font-size:16px;line-height:1.5'>"
        f"While you wait, here's what we've already built — full chapters of scripture "
        f"as cinematic videos:</p>"
        f"<p style='margin:24px 0'>"
        f"<a href='{_YOUTUBE_CHANNEL_URL}' "
        f"style='background:#5b3df5;color:#fff;padding:12px 20px;border-radius:8px;"
        f"text-decoration:none;font-weight:600'>Watch on YouTube →</a></p>"
        f"<p style='font-size:14px;color:#666;line-height:1.5;margin-top:32px'>"
        f"Reply to this email if you have a specific chapter you want to see first — "
        f"we read every reply.</p>"
        f"<p style='font-size:13px;color:#999;margin-top:24px'>— Thomas, Anointed</p>"
        f"</div>"
    )
    _resend_send([email], "You're on the Anointed waitlist", html, reply_to=_WAITLIST_NOTIFY_EMAIL)


def _send_invite_email(email: str, token: str) -> None:
    """Step 4 of the beta ROI flow — admin-issued invite to claim the free chapter."""
    invite_url = f"{_ANOINTED_BASE_URL}/invite/{token}"
    preheader = "One free cinematic chapter, on the house. Pick any book."
    html = (
        # hidden preheader for inbox preview text
        f"<div style='display:none;font-size:1px;line-height:1px;max-height:0;"
        f"max-width:0;opacity:0;overflow:hidden'>{preheader}</div>"
        f"<div style='font-family:sans-serif;max-width:560px;margin:0 auto;color:#222'>"
        f"<h2 style='font-size:22px;margin-bottom:8px'>🙏 Your private link is ready, friend.</h2>"
        f"<p style='font-size:16px;line-height:1.5'>"
        f"Thank you for waiting. You're in the first wave of the Anointed beta — "
        f"and your first chapter is on us.</p>"
        f"<p style='font-size:16px;line-height:1.5'>"
        f"Pick <strong>any chapter of scripture</strong> (Genesis 1, Psalm 23, "
        f"Romans 8, Revelation 21 — your call) and we'll render it as a cinematic "
        f"short, narrated in a voice you choose. Yours to keep, share, send to your "
        f"pastor, post to your story.</p>"
        f"<p style='margin:28px 0'>"
        f"<a href='{invite_url}' "
        f"style='background:#5b3df5;color:#fff;padding:14px 24px;border-radius:8px;"
        f"text-decoration:none;font-weight:600;font-size:16px'>Claim your free chapter →</a></p>"
        f"<p style='font-size:13px;color:#888;line-height:1.5;font-style:italic'>"
        f"This link is yours — please don't share it. It's good for one chapter, no expiry.</p>"
        f"<p style='font-size:16px;line-height:1.5;margin-top:24px'>"
        f"<strong>What to expect:</strong> rendering takes ~6–10 minutes. We'll email "
        f"you the moment your video is ready. After that, you'll see what it costs to "
        f"do more — but no pressure, no auto-renew, no anything. The first one is just "
        f"for you.</p>"
        f"<p style='font-size:14px;color:#666;line-height:1.5;margin-top:32px'>"
        f"If a specific verse is on your heart, reply to this email and let me know. "
        f"I read every reply.</p>"
        f"<p style='font-size:13px;color:#999;margin-top:24px'>— Thomas, Anointed</p>"
        f"<p style='font-size:12px;color:#aaa;margin-top:24px;border-top:1px solid #eee;"
        f"padding-top:16px'>P.S. We're capping the beta at 25 invites/week so quality "
        f"stays high. Your spot is held.</p>"
        f"</div>"
    )
    _resend_send([email], "Your Anointed invite is here — claim your free chapter",
                 html, reply_to=_WAITLIST_NOTIFY_EMAIL)


def _send_render_complete_email(email: str, chapter: str, video_url: str) -> None:
    """Step 5 of the beta ROI flow — fired when a render completes.
    Includes Stripe upsell buttons IF both _STRIPE_LINK_25 / _STRIPE_LINK_50
    env vars are set (graceful degradation if not yet configured)."""
    chapter_safe = chapter or "your chapter"
    preheader = "Watch it, share it, and pick the next one when you're ready."

    upsell_block = ""
    if _STRIPE_LINK_25 and _STRIPE_LINK_50:
        upsell_block = (
            f"<hr style='border:none;border-top:1px solid #eee;margin:32px 0' />"
            f"<h3 style='font-size:18px;margin-bottom:8px'>Want to do another?</h3>"
            f"<p style='font-size:15px;line-height:1.5;color:#555'>"
            f"If something stirred in you watching that, here's how to bring more "
            f"chapters to life. No subscription, no auto-renew — top up only when "
            f"you want to.</p>"
            f"<p style='margin:20px 0 8px'>"
            f"<a href='{_STRIPE_LINK_25}' "
            f"style='background:#5b3df5;color:#fff;padding:12px 22px;border-radius:8px;"
            f"text-decoration:none;font-weight:600;display:inline-block'>"
            f"$25 — one more chapter →</a></p>"
            f"<p style='font-size:13px;color:#888;margin:0 0 16px'>"
            f"Whatever book is on your heart next.</p>"
            f"<p style='margin:8px 0'>"
            f"<a href='{_STRIPE_LINK_50}' "
            f"style='background:#5b3df5;color:#fff;padding:12px 22px;border-radius:8px;"
            f"text-decoration:none;font-weight:600;display:inline-block'>"
            f"$50 — three chapters →</a> "
            f"<span style='font-size:13px;color:#888;margin-left:8px'>"
            f"<em>save $25</em></span></p>"
            f"<p style='font-size:13px;color:#888;margin:0 0 24px'>"
            f"Build a series — Genesis 1–3, the parables of Christ, the seven "
            f"churches of Revelation.</p>"
        )

    html = (
        f"<div style='display:none;font-size:1px;line-height:1px;max-height:0;"
        f"max-width:0;opacity:0;overflow:hidden'>{preheader}</div>"
        f"<div style='font-family:sans-serif;max-width:560px;margin:0 auto;color:#222'>"
        f"<h2 style='font-size:22px;margin-bottom:8px'>🎬 Your chapter is ready.</h2>"
        f"<p style='font-size:16px;line-height:1.5'>"
        f"<strong>{chapter_safe}</strong> — cinematic, yours to keep.</p>"
        f"<p style='margin:28px 0'>"
        f"<a href='{video_url}' "
        f"style='background:#5b3df5;color:#fff;padding:14px 24px;border-radius:8px;"
        f"text-decoration:none;font-weight:600;font-size:16px'>"
        f"Watch &amp; download your video →</a></p>"
        f"<p style='font-size:13px;color:#888;font-style:italic'>"
        f"Link stays live for 30 days.</p>"
        f"{upsell_block}"
        f"<p style='font-size:14px;color:#666;line-height:1.5;margin-top:24px'>"
        f"Reply to this email if there's a specific verse calling you. I'll help "
        f"you think through what would translate best to cinema before you spend "
        f"a dime.</p>"
        f"<p style='font-size:13px;color:#999;margin-top:24px'>— Thomas, Anointed</p>"
        f"</div>"
    )
    subject = f"Your {chapter_safe} is ready 🎬"
    _resend_send([email], subject, html, reply_to=_WAITLIST_NOTIFY_EMAIL)


@app.post("/api/waitlist")
@limiter.limit(MEDIUM_LIMIT)
async def api_waitlist_signup(request: Request, req: WaitlistRequest):
    """Public waitlist signup. Stores email in Supabase + emails admin via Resend."""
    email = req.email.strip().lower()
    if not email or not _EMAIL_RE.match(email) or len(email) > 254:
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")

    xff = request.headers.get("x-forwarded-for")
    ip = (xff.split(",")[0].strip() if xff else (request.client.host if request.client else "unknown"))
    user_agent = (request.headers.get("user-agent") or "")[:512]

    result = _db_mod.insert_waitlist(email=email, ip=ip, user_agent=user_agent, source="landing-page")

    if result == "duplicate":
        return {"status": "already_signed_up",
                "message": "You're already on the list — we'll be in touch."}
    if result == "error":
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")
    if result == "unconfigured":
        # No Supabase wired up — still notify admin so signups aren't lost
        print(f"[waitlist] Supabase unconfigured — signup not persisted: {email}")

    _send_waitlist_notification(email, ip, "landing-page")
    _send_signer_confirmation(email)
    _push_lead_to_crm(email, "landing-page")
    return {"status": "ok",
            "message": "You're on the list. We'll send your private link soon."}


@app.get("/api/invite/{token}")
async def api_invite_status(token: str):
    """Public — page-load check for the invite landing page.

    Returns {valid, email, redeemed, chapter_picked, free_used} on success,
    or {valid: False} if the token is unknown / Supabase down. Never raises —
    a clean 200 false is friendlier UX than a 404 on a typo'd URL.
    """
    if not token or len(token) > 100:
        return {"valid": False}
    row = _db_mod.get_invite(token)
    if row is None:
        return {"valid": False}
    return {
        "valid": True,
        "email": row.get("email"),
        "redeemed": row.get("redeemed_at") is not None,
        "chapter_picked": row.get("chapter_picked"),
        "free_used": bool(row.get("free_used", False)),
    }


@app.post("/api/invite/{token}/claim")
@limiter.limit(MEDIUM_LIMIT)
async def api_invite_claim(request: Request, token: str, req: InviteClaimRequest):
    """Public — claim the free chapter. Marks the invite redeemed and stores the
    chapter pick on the waitlist row. The actual render is triggered manually
    from the admin panel (Path B / admin-mediated for beta).
    """
    chapter = req.chapter.strip()
    if not chapter or len(chapter) > 200:
        raise HTTPException(status_code=400, detail="Pick a chapter (e.g. 'Genesis 1').")

    result = _db_mod.redeem_invite(token, chapter)

    if result == "unconfigured":
        raise HTTPException(status_code=503, detail="Backend not configured.")
    if result == "invalid":
        raise HTTPException(status_code=404, detail="Invalid or expired invite link.")
    if result == "already":
        return {"status": "already_claimed",
                "message": "You've already picked your chapter — your video is on its way."}

    return {"status": "claimed",
            "message": "Got it. Your video will land in your inbox within 24 hours."}


@app.get("/admin/waitlist")
async def admin_waitlist():
    """View all waitlist signups. Gated by Basic Auth when APP_USERNAME/PASSWORD set."""
    rows = _db_mod.list_waitlist(limit=1000)
    if rows is None:
        return JSONResponse(
            {"error": "Supabase not configured — waitlist storage unavailable.",
             "configured": False}, status_code=503)
    return {"configured": True, "count": len(rows), "signups": rows}


@app.delete("/admin/waitlist/{email}")
async def admin_delete_waitlist(email: str):
    """Delete a waitlist row by email. Gated by Basic Auth middleware.

    Used by the admin panel's per-row Delete button to remove test rows and
    bad signups. Returns 404 if no row matched.
    """
    if not _db_mod.is_enabled():
        raise HTTPException(status_code=503, detail="Supabase not configured")
    normalized = email.strip().lower()
    if not _EMAIL_RE.match(normalized) or len(normalized) > 254:
        raise HTTPException(status_code=400, detail="Invalid email")
    deleted = _db_mod.delete_waitlist(normalized)
    if deleted is None:
        raise HTTPException(status_code=500, detail="Delete failed — see server logs")
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"No waitlist row for {normalized}")
    return {"status": "deleted", "email": normalized, "rows": deleted}


@app.post("/admin/invites/issue")
async def admin_issue_invite(req: InviteIssueRequest):
    """Issue (or re-fetch) a one-time invite token for an existing waitlist row
    and send the Step 4 invite email. Gated by Basic Auth middleware.

    Idempotent: calling this twice for the same email returns the same token
    while the invite is still unredeemed — the email is re-sent each call.

    TODO(admin-panel): once the HTML admin panel exists, wire a per-row
    'Issue invite' button that POSTs here with the row's email.
    """
    if not _db_mod.is_enabled():
        raise HTTPException(status_code=503, detail="Supabase not configured")
    email = req.email.strip().lower()
    if not _EMAIL_RE.match(email) or len(email) > 254:
        raise HTTPException(status_code=400, detail="Invalid email")
    token = _db_mod.issue_invite(email)
    if token is None:
        raise HTTPException(
            status_code=404,
            detail=f"No waitlist row for {email} — they need to sign up first.",
        )
    _send_invite_email(email, token)
    return {
        "status": "sent",
        "email": email,
        "token": token,
        "invite_url": f"{_ANOINTED_BASE_URL}/invite/{token}",
    }


@app.post("/admin/invites/{token}/send-done")
async def admin_send_done(token: str, req: RenderDoneRequest):
    """Send the 'video ready' (Step 5 monetize) email for a redeemed invite.

    Video URL precedence:
      1. req.video_url if provided (admin override — useful for YouTube links etc.)
      2. Auto-pulled from public.renders.video_url via waitlist.render_id
    Returns 400 if neither path yields a URL.

    TODO(admin-panel): wire a 'Send done email' button per row that POSTs here.
    """
    if not _db_mod.is_enabled():
        raise HTTPException(status_code=503, detail="Supabase not configured")
    row = _db_mod.get_invite(token)
    if row is None:
        raise HTTPException(status_code=404, detail="Invalid invite token")
    email = row.get("email") or ""
    chapter = row.get("chapter_picked") or ""
    if not email or not chapter:
        raise HTTPException(
            status_code=400,
            detail="Invite has no chapter pick yet — user hasn't claimed.",
        )

    video_url = (req.video_url or "").strip()
    source = "admin_override" if video_url else "auto_renders"
    if not video_url:
        render_id = row.get("render_id")
        if not render_id:
            raise HTTPException(
                status_code=400,
                detail="No render_id linked to this invite. Either trigger a render "
                       "and attach it, or pass video_url explicitly.",
            )
        rec = _db_mod.get_render(str(render_id))
        if rec is None or not rec.get("video_url"):
            raise HTTPException(
                status_code=400,
                detail="Linked render has no video_url yet — render may still be "
                       "in progress, or pass video_url explicitly to override.",
            )
        video_url = rec["video_url"]

    _send_render_complete_email(email, chapter, video_url)
    return {
        "status": "sent",
        "email": email,
        "chapter": chapter,
        "video_url": video_url,
        "url_source": source,
    }


@app.get("/admin/usage")
async def admin_usage():
    """Usage stats. Already behind Basic Auth middleware when APP_USERNAME/PASSWORD set."""
    return get_summary()


# ── Stripe billing ────────────────────────────────────────────────────────────

# Amount-to-credits map (Stripe sends cents).
_STRIPE_CREDITS = {2500: 1, 5000: 3}

@app.post("/billing/webhook")
async def stripe_webhook(request: Request):
    """Stripe webhook — no auth needed (signature verified via STRIPE_WEBHOOK_SECRET).
    Handles checkout.session.completed → adds paid_credits to the waitlist row."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    if not _STRIPE_WEBHOOK_SECRET:
        print("[stripe] STRIPE_WEBHOOK_SECRET not configured — ignoring webhook")
        return {"status": "unconfigured"}

    try:
        import stripe as _stripe
        event = _stripe.Webhook.construct_event(payload, sig, _STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        print(f"[stripe] Signature verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email = ((session.get("customer_details") or {}).get("email") or "").lower().strip()
        amount = session.get("amount_total", 0)  # cents
        credits = _STRIPE_CREDITS.get(amount, 1)

        if not email:
            print(f"[stripe] checkout.session.completed — no email, session={session.get('id')}")
        else:
            ok = _db_mod.add_paid_credits(email, credits)
            print(f"[stripe] +{credits} credit(s) for {email} (${amount//100}) → ok={ok}")

    return {"status": "ok"}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _webhook = os.getenv("N8N_WEBHOOK_URL", "")
    _j2v     = os.getenv("JSON2VIDEO_API_KEY", "")

    if not _webhook:
        print("\n⚠  WARNING: N8N_WEBHOOK_URL is not set in your .env file.")
        print("   The /api/generate endpoint will not work until you set it.\n")
    else:
        print(f"\n✓ n8n webhook configured")

    if not _j2v:
        print("⚠  WARNING: JSON2VIDEO_API_KEY is not set — live render tracking disabled.")
        print("   Add it to .env to enable real-time status polling.\n")
    else:
        print("✓ JSON2Video API key configured — real-time tracking enabled\n")

    print("Starting Anointed at http://localhost:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
