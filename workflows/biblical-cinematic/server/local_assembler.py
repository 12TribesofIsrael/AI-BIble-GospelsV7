"""
Local assembler — the in-house replacement for JSON2Video.

Takes the engine's finished scene list (each scene has a Kling clip URL plus its
narration text) and produces the final MP4 entirely on this machine:

    ElevenLabs (with character timestamps) -> narration audio + exact word timings
    FFmpeg                                 -> per-scene video/audio conform
    libass                                 -> burned-in word-by-word captions
    FFmpeg                                 -> concat + single burn pass

Why this exists:
  * JSON2Video is a paid dependency that fails at the LAST step, after every FLUX
    image and Kling clip has already been paid for. A bad voice id or an empty
    credit balance destroys a full render's worth of spend.
  * Its voice list is curated — it rejects perfectly valid ElevenLabs voices that
    the account owns (Alicia Calm Storyteller, for one).
  * Caption timing here is ground truth from the synthesizer, not a transcription
    guess after the fact, so the word highlight lands exactly on the word.

Caption styling comes from the active style pack, so Cinematic, High Cinematic and
Kids each get their own caption treatment with no extra wiring.

Usage (library):
    from local_assembler import assemble
    path = assemble(processed_scenes, voice_id="...", aspect_ratio="16:9", style="kids")

Usage (CLI):
    python local_assembler.py scenes.json --style kids --out final.mp4
"""

import base64
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests

from style_packs import DEFAULT_STYLE, apply_subtitle_style, resolve_style

ELEVEN_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
ELEVEN_MODEL = "eleven_multilingual_v2"

ASSETS = Path(__file__).parent.parent / "assets"
FONT_DIR = ASSETS / "fonts"

# Output canvas per canonical aspect ratio — mirrors ASPECT_RATIOS in the pipeline.
RESOLUTIONS = {
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
    "9:16": (1080, 1920),
}

# libass resolves fonts by FAMILY name, not by file name, and it will silently
# substitute a default if the family is missing. Every family we style with must
# therefore ship as a file in assets/fonts. Keys are the family names used in
# style_packs subtitle settings.
FONT_FILES = {
    "Oswald Bold": ("Oswald.ttf", "Oswald"),
    "Oswald": ("Oswald.ttf", "Oswald"),
    "Baloo 2": ("Baloo2.ttf", "Baloo 2"),
    "Archivo Black": ("ArchivoBlack.ttf", "Archivo Black"),
}
FALLBACK_FONT = ("ArchivoBlack.ttf", "Archivo Black")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _run(cmd):
    """Run FFmpeg/FFprobe and surface its stderr on failure — a silent
    CalledProcessError here is impossible to debug from a render log."""
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        tail = (proc.stderr or b"").decode("utf-8", "replace")[-2000:]
        raise RuntimeError(f"ffmpeg failed ({' '.join(str(c) for c in cmd[:3])}...):\n{tail}")
    return proc


def _run_in(cwd, cmd):
    """Same as _run but with a working directory — used for the caption burn so
    every path in the filter chain can stay relative."""
    proc = subprocess.run(cmd, capture_output=True, cwd=str(cwd))
    if proc.returncode != 0:
        tail = (proc.stderr or b"").decode("utf-8", "replace")[-2000:]
        raise RuntimeError(f"ffmpeg failed in {cwd}:\n{tail}")
    return proc


def _duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        raise RuntimeError(f"ffprobe could not read a duration from {path}")


def _download(url, dest):
    r = requests.get(url, timeout=600)
    r.raise_for_status()
    Path(dest).write_bytes(r.content)
    return dest


def _ass_colour(hex_colour, alpha="00"):
    """#RRGGBB -> &HAABBGGRR& . ASS stores colour byte-reversed with alpha first."""
    h = (hex_colour or "#FFFFFF").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha}{b}{g}{r}".upper() + "&"


# ---------------------------------------------------------------------------
# Narration + word timing
# ---------------------------------------------------------------------------
def synthesize(text, voice_id, dest, api_key=None):
    """ElevenLabs speech WITH character timestamps.

    Returns (audio_path, words) where words is [{"word","start","end"}, ...].
    The timings are emitted by the synthesizer itself, so they are exact rather
    than transcribed — this is what makes the word highlight land correctly.
    """
    key = api_key or os.getenv("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY not set")
    r = requests.post(
        ELEVEN_TTS_URL.format(voice_id=voice_id),
        headers={"xi-api-key": key, "Content-Type": "application/json"},
        json={"text": text, "model_id": ELEVEN_MODEL,
              "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}},
        timeout=300,
    )
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs {r.status_code}: {r.text[:300]}")
    data = r.json()
    Path(dest).write_bytes(base64.b64decode(data["audio_base64"]))

    align = data.get("alignment") or {}
    chars = align.get("characters") or []
    starts = align.get("character_start_times_seconds") or []
    ends = align.get("character_end_times_seconds") or []

    words, cur, cur_start, cur_end = [], "", None, None
    for i, ch in enumerate(chars):
        if ch.isspace():
            if cur:
                words.append({"word": cur, "start": cur_start, "end": cur_end})
                cur, cur_start, cur_end = "", None, None
            continue
        if cur_start is None:
            cur_start = starts[i] if i < len(starts) else 0.0
        cur += ch
        cur_end = ends[i] if i < len(ends) else cur_start
    if cur:
        words.append({"word": cur, "start": cur_start, "end": cur_end})
    return dest, words


# ---------------------------------------------------------------------------
# Captions
# ---------------------------------------------------------------------------
def resolve_font(family):
    """Map a style-pack font family to a shipped file. Falls back rather than
    letting libass silently substitute something unintended."""
    fname, ass_name = FONT_FILES.get(family, FALLBACK_FONT)
    if not (FONT_DIR / fname).exists():
        fname, ass_name = FALLBACK_FONT
        if not (FONT_DIR / fname).exists():
            return None, family  # let libass do whatever it can
    return FONT_DIR / fname, ass_name


def build_ass(timeline_words, settings, width, height, path):
    """Write an ASS file with word-by-word highlighting.

    `timeline_words` is the whole movie's words with absolute times. Words are
    grouped into lines of `max-words-per-line`, and each line is emitted once per
    word so the active word can carry its own colour — the same read as the
    engine's previous captions, produced locally.
    """
    font_file, font_name = resolve_font(settings.get("font-family", "Oswald Bold"))
    base = _ass_colour(settings.get("line-color", "#CCCCCC"))
    hi = _ass_colour(settings.get("word-color", "#FFFF00"))
    outline = _ass_colour(settings.get("outline-color", "#000000"))
    shadow = _ass_colour(settings.get("shadow-color", "#000000"), alpha="80")
    size = int(settings.get("font-size", 72))
    ow = float(settings.get("outline-width", 8)) / 2.0   # ASS outline units are chunkier
    sh = float(settings.get("shadow-offset", 6)) / 3.0
    per_line = max(1, int(settings.get("max-words-per-line", 3)))
    margin_v = int(height * 0.08)

    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font_name},{size},{base},{hi},{outline},{shadow},0,0,0,0,100,100,0,0,1,{ow:.1f},{sh:.1f},2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def ts(t):
        t = max(0.0, float(t))
        h = int(t // 3600); m = int((t % 3600) // 60); s = t % 60
        return f"{h:d}:{m:02d}:{s:05.2f}"

    # Group into caption lines. A fixed every-N-words chop reads badly: it runs
    # straight through full stops and across scene cuts, so a line can end up as
    # "world. Amen. Learn it," — the tail of one verse glued to the head of the
    # next scene's teaching. Break on sentence-ending punctuation and on scene
    # changes as well as on length.
    SENTENCE_END = (".", "!", "?", ":", ";", '."', '?"', '!"')
    lines, current = [], []
    for idx, w in enumerate(timeline_words):
        current.append(w)
        prev_scene = w.get("scene")
        next_scene = timeline_words[idx + 1].get("scene") if idx + 1 < len(timeline_words) else None
        ends_sentence = w["word"].endswith(SENTENCE_END)
        scene_changes = next_scene is not None and next_scene != prev_scene
        if len(current) >= per_line or ends_sentence or scene_changes:
            lines.append(current)
            current = []
    if current:
        lines.append(current)

    events = []
    for group in lines:
        line_end = group[-1]["end"]
        for idx, w in enumerate(group):
            start = w["start"]
            # Run each word up to the next word's start so the line never blinks
            # out in the gaps between words.
            end = group[idx + 1]["start"] if idx + 1 < len(group) else line_end
            if end <= start:
                end = start + 0.08
            parts = []
            for j, ww in enumerate(group):
                txt = ww["word"].replace("{", "(").replace("}", ")")
                if j == idx:
                    parts.append(f"{{\\c{hi}}}{txt}{{\\c{base}}}")
                else:
                    parts.append(txt)
            events.append(
                f"Dialogue: 0,{ts(start)},{ts(end)},Cap,,0,0,0,,{' '.join(parts)}")

    Path(path).write_text(head + "\n".join(events) + "\n", encoding="utf-8")
    return path, font_file


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------
def _conform_scene(clip, audio, target_seconds, width, height, dest):
    """One scene -> one part file at the movie's canvas size and frame rate.

    Holds the final frame if narration outlasts the clip (a visible loop reads as
    a glitch), and never stretches the audio.
    """
    vf = (f"scale={width}:{height}:force_original_aspect_ratio=increase,"
          f"crop={width}:{height},setsar=1,fps=30")
    if audio:
        _run(["ffmpeg", "-y", "-i", str(clip), "-i", str(audio), "-filter_complex",
              f"[0:v]{vf},tpad=stop_mode=clone:stop_duration=600,"
              f"trim=0:{target_seconds:.3f},setpts=PTS-STARTPTS[v];"
              f"[1:a]apad,atrim=0:{target_seconds:.3f},asetpts=PTS-STARTPTS[a]",
              "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
              "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
              "-ar", "48000", "-ac", "2", str(dest)])
    else:
        _run(["ffmpeg", "-y", "-i", str(clip), "-f", "lavfi", "-t",
              f"{target_seconds:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
              "-filter_complex",
              f"[0:v]{vf},tpad=stop_mode=clone:stop_duration=600,"
              f"trim=0:{target_seconds:.3f},setpts=PTS-STARTPTS[v]",
              "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "medium",
              "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
              "-ar", "48000", "-ac", "2", str(dest)])
    return dest


def assemble(scenes, voice_id, aspect_ratio="16:9", style=DEFAULT_STYLE,
             out_path=None, work_dir=None, captions=True, progress=None,
             tail_seconds=0.45):
    """Build the final MP4 locally.

    scenes: [{"narration": str, "video_url": str_or_path}, ...] — the engine's
            `processed` list shape, so this is a drop-in for the JSON2Video call.
    Returns the output path.
    """
    pack = resolve_style(style)
    width, height = RESOLUTIONS.get(aspect_ratio, RESOLUTIONS["16:9"])

    ratio_defaults = {"16:9": (80, 4), "1:1": (70, 3), "9:16": (64, 3)}
    fs, mw = ratio_defaults.get(aspect_ratio, ratio_defaults["16:9"])
    settings = apply_subtitle_style({
        "style": "classic", "font-family": "Oswald Bold", "font-size": fs,
        "position": "bottom-center", "line-color": "#CCCCCC", "word-color": "#FFFF00",
        "outline-color": "#000000", "outline-width": 8, "shadow-color": "#000000",
        "shadow-offset": 6, "max-words-per-line": mw,
    }, pack)

    tmp = Path(work_dir or tempfile.mkdtemp(prefix="assemble_"))
    tmp.mkdir(parents=True, exist_ok=True)
    out_path = Path(out_path or (tmp / "final.mp4"))

    def say(msg):
        if progress:
            progress(msg)
        else:
            print(msg, flush=True)

    parts, timeline, clock = [], [], 0.0
    for i, scene in enumerate(scenes, 1):
        say(f"Scene {i}/{len(scenes)} — narrating and conforming...")
        src = scene.get("video_url") or scene.get("clip")
        clip = tmp / f"s{i}_clip.mp4"
        if str(src).startswith("http"):
            _download(src, clip)
        else:
            shutil.copyfile(src, clip)

        narration = (scene.get("narration") or "").strip()
        audio, words = None, []
        if narration:
            audio = tmp / f"s{i}_vo.mp3"
            _, words = synthesize(narration, voice_id, audio)

        target = (_duration(audio) + tail_seconds) if audio else _duration(clip)
        parts.append(_conform_scene(clip, audio, target, width, height, tmp / f"s{i}_part.mp4"))

        for w in words:
            timeline.append({"word": w["word"], "scene": i,
                             "start": clock + w["start"],
                             "end": min(clock + w["end"], clock + target)})
        clock += target

    say("Joining scenes...")
    listing = tmp / "parts.txt"
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    joined = tmp / "joined.mp4"
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
          "-c", "copy", str(joined)])

    if not (captions and timeline):
        shutil.copyfile(joined, out_path)
        say(f"Done -> {out_path}")
        return str(out_path)

    say("Burning captions...")
    ass_path, font_file = build_ass(timeline, settings, width, height, tmp / "captions.ass")
    # Windows absolute paths inside an FFmpeg filter argument are a losing battle —
    # the drive colon collides with the filter's own option separator no matter how
    # it is escaped. Run the burn from inside the work dir and keep every path
    # relative instead. The font is copied in so fontsdir can just be ".".
    if font_file:
        shutil.copyfile(font_file, tmp / font_file.name)
    filt = "subtitles=captions.ass" + (":fontsdir=." if font_file else "")
    _run_in(tmp, ["ffmpeg", "-y", "-i", "joined.mp4", "-vf", filt,
                  "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                  "-pix_fmt", "yuv420p", "-c:a", "copy", "burned.mp4"])
    shutil.copyfile(tmp / "burned.mp4", out_path)
    say(f"Done -> {out_path}")
    return str(out_path)


if __name__ == "__main__":
    import argparse

    from dotenv import find_dotenv, load_dotenv
    load_dotenv(find_dotenv())

    ap = argparse.ArgumentParser(description="Assemble a final MP4 locally (no JSON2Video)")
    ap.add_argument("scenes_json", help="JSON file: {\"scenes\":[{narration, video_url}]} or a bare list")
    ap.add_argument("--voice-id", default=None, help="ElevenLabs voice id (default: the style pack's suggestion)")
    ap.add_argument("--style", default=DEFAULT_STYLE, choices=["cinematic", "epic", "kids"])
    ap.add_argument("--aspect-ratio", default="16:9", choices=list(RESOLUTIONS.keys()))
    ap.add_argument("--out", default="final.mp4")
    ap.add_argument("--work-dir", default=None)
    ap.add_argument("--no-captions", action="store_true")
    a = ap.parse_args()

    raw = json.loads(Path(a.scenes_json).read_text(encoding="utf-8"))
    scene_list = raw["scenes"] if isinstance(raw, dict) else raw
    voice = a.voice_id or resolve_style(a.style)["suggested_voice"]
    assemble(scene_list, voice, aspect_ratio=a.aspect_ratio, style=a.style,
             out_path=a.out, work_dir=a.work_dir, captions=not a.no_captions)
