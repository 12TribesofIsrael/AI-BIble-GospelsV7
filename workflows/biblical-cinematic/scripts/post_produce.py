"""
post_produce.py — Biblical Cinematic Post-Production
=====================================================
Wraps a raw video with a branded intro + outro and a logo watermark.

The intro and outro live in ONE merged brand clip (assets/intro_outro.mp4).
A single split point decides where the intro ends and the outro begins:

    [ brand 0..SPLIT ]  →  [ your main video + logo ]  →  [ brand SPLIT..end ]
        (intro)                    (middle)                     (outro)

The logo watermark is applied to the MAIN video ONLY — the brand clip is
already branded, so watermarking it again produces a double logo.

Drop-and-run:
  python post_produce.py
      → auto-picks the newest video in postproduction/, wraps it, done.

Explicit:
  python post_produce.py path/to/raw-video.mp4
  python post_produce.py path/to/raw-video.mp4 --split 30   (intro ends at 0:30)
  python post_produce.py path/to/raw-video.mp4 --width 1920 (force 1080p output)
  python post_produce.py path/to/raw-video.mp4 --no-logo    (skip watermark)

Output:
  output/<video-name>_final.mp4  (relative to project root)

Requirements:
  - FFmpeg + ffprobe installed and on PATH
  - assets/intro_outro.mp4   (merged intro+outro brand clip)
  - assets/logo1.png         (transparent-background PNG watermark)
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


# ── Paths ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
BIBLICAL_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BIBLICAL_DIR.parent.parent  # c:/Users/Claude/ai-bible-gospels

ASSETS_DIR = BIBLICAL_DIR / "assets"
OUTPUT_DIR = PROJECT_ROOT / "output"
DROP_DIR = PROJECT_ROOT / "postproduction"   # where you drop the raw video

BRAND = ASSETS_DIR / "intro_outro.mp4"       # merged intro+outro clip
LOGO = ASSETS_DIR / "logo1.png"

# Logo width in pixels (~1.5 in on a 1080p display)
LOGO_WIDTH = 500
# Default split: seconds into the brand clip where intro ends / outro begins
DEFAULT_SPLIT = 26

VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".webm")


# ── Helpers ───────────────────────────────────────────────────────────────────

def die(msg: str):
    print(f"\n[X] {msg}\n")
    sys.exit(1)


def check_tools():
    for tool in ("ffmpeg", "ffprobe"):
        try:
            r = subprocess.run([tool, "-version"], capture_output=True, text=True)
            if r.returncode != 0:
                raise FileNotFoundError
        except FileNotFoundError:
            die(f"{tool} not found on PATH. Install FFmpeg: https://ffmpeg.org/download.html")


def check_assets():
    missing = []
    if not BRAND.exists():
        missing.append(f"  intro_outro.mp4 -> {BRAND}")
    if not LOGO.exists():
        missing.append(f"  logo1.png       -> {LOGO}")
    if missing:
        die("Missing required assets:\n" + "\n".join(missing))


def run(cmd, label):
    print(f"\n  -> {label}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"\n[X] FFmpeg error during: {label}")
        print(r.stderr[-3000:])
        sys.exit(1)


def probe_dimensions(video: Path):
    """Return (width, height) of a video's first video stream."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", str(video)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        die(f"Could not probe dimensions of {video.name}")
    s = json.loads(r.stdout)["streams"][0]
    return int(s["width"]), int(s["height"])


def has_audio(video: Path) -> bool:
    """True if the video has at least one audio stream."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True,
    )
    return bool(r.stdout.strip())


def auto_pick_video() -> Path:
    """Newest video file in postproduction/ (that isn't the brand clip)."""
    if not DROP_DIR.exists():
        die(f"No input given and drop folder doesn't exist: {DROP_DIR}")
    vids = [
        p for p in DROP_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS
        and p.resolve() != BRAND.resolve()
    ]
    if not vids:
        die(f"No video found in {DROP_DIR}. Drop a .mp4 there or pass a path.")
    newest = max(vids, key=lambda p: p.stat().st_mtime)
    return newest


# ── Pipeline ──────────────────────────────────────────────────────────────────

def normalize(src: Path, dst: Path, scale: str, add_logo: bool,
              ss: float = None, t: float = None):
    """Re-encode a clip to uniform specs (WxH, 30fps, yuv420p, aac 44.1k stereo).

    add_logo=True overlays the logo bottom-left. If the source has no audio
    stream (e.g. a silent outro), a silent stereo track is injected so the
    concat demuxer sees identical streams on every segment.
    """
    inputs = []
    if ss is not None:
        inputs += ["-ss", str(ss)]
    inputs += ["-i", str(src)]
    if t is not None:
        inputs += ["-t", str(t)]

    silent = not has_audio(src)

    if add_logo:
        inputs += ["-i", str(LOGO)]
        vf = (f"[0:v]scale={scale},fps=30,format=yuv420p[bg];"
              f"[1:v]scale={LOGO_WIDTH}:-1[lg];[bg][lg]overlay=20:H-h-20[v]")
        maps = ["-filter_complex", vf, "-map", "[v]"]
    else:
        maps = ["-vf", f"scale={scale},fps=30,format=yuv420p", "-map", "0:v"]

    if silent:
        inputs += ["-f", "lavfi", "-t", "999", "-i", "anullsrc=r=44100:cl=stereo"]
        audio_idx = 2 if add_logo else 1
        maps += ["-map", f"{audio_idx}:a", "-shortest"]
    else:
        maps += ["-map", "0:a"]

    run(
        ["ffmpeg", "-y", *inputs, *maps,
         "-c:v", "libx264", "-preset", "fast", "-crf", "20",
         "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
         "-movflags", "+faststart", str(dst)],
        f"Normalizing {dst.name}"
    )


def process(input_video: Path, split: float, output_width: int, add_logo: bool):
    check_assets()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Output resolution: match the source unless overridden, keep it even.
    if output_width is None:
        w, h = probe_dimensions(input_video)
    else:
        w = output_width
        h = (output_width * 9) // 16
    w -= w % 2
    h -= h % 2
    scale = f"{w}:{h}"

    stem = input_video.stem
    final_output = OUTPUT_DIR / f"{stem}_final.mp4"

    print(f"\n{'-'*55}")
    print(f"  Input:   {input_video.name}")
    print(f"  Brand:   intro_outro.mp4  (split at {split:g}s)")
    print(f"  Logo:    {'logo1.png on main only' if add_logo else 'disabled'}")
    print(f"  Output:  {w}x{h}  ->  {final_output.name}")
    print(f"{'-'*55}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        s0, s1, s2 = tmp / "s0.mp4", tmp / "s1.mp4", tmp / "s2.mp4"

        # 1/4 intro = brand[0..split]  (no extra logo — already branded)
        normalize(BRAND, s0, scale, add_logo=False, t=split)
        # 2/4 main = your video (+ logo)
        normalize(input_video, s1, scale, add_logo=add_logo)
        # 3/4 outro = brand[split..end]  (no extra logo)
        normalize(BRAND, s2, scale, add_logo=False, ss=split)

        # 4/4 concat (stream copy — segments already share identical specs)
        concat_list = tmp / "concat_list.txt"
        concat_list.write_text(
            "\n".join(f"file '{p.as_posix()}'" for p in (s0, s1, s2)) + "\n",
            encoding="utf-8",
        )
        run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", str(concat_list), "-c", "copy",
             "-movflags", "+faststart", str(final_output)],
            "Concatenating intro + video + outro"
        )

    size_mb = final_output.stat().st_size / (1024 * 1024)
    print(f"\n{'-'*55}")
    print(f"  [OK] Done!  {final_output.name}  ({size_mb:.1f} MB)")
    print(f"  Path: {final_output}")
    print(f"{'-'*55}\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Wrap a video with a branded intro/outro + logo watermark."
    )
    parser.add_argument(
        "input_video", nargs="?",
        help="Path to the raw video. Omit to auto-pick the newest in postproduction/."
    )
    parser.add_argument(
        "--split", type=float, default=DEFAULT_SPLIT, metavar="SECONDS",
        help=f"Seconds into the brand clip where intro ends / outro begins (default: {DEFAULT_SPLIT})"
    )
    parser.add_argument(
        "--width", type=int, default=None, metavar="PIXELS",
        help="Output width. Default: match the source video (no upscaling). Use 1920 for 1080p, 3840 for 4K."
    )
    parser.add_argument(
        "--no-logo", action="store_true",
        help="Skip the logo watermark on the main video."
    )
    args = parser.parse_args()

    print("\nBiblical Cinematic - Post-Production")
    print("=====================================")

    check_tools()
    check_assets()

    if args.input_video:
        input_video = Path(args.input_video).resolve()
        if not input_video.exists():
            die(f"Input video not found: {input_video}")
    else:
        input_video = auto_pick_video()
        print(f"  Auto-picked newest video: {input_video.name}")

    if input_video.suffix.lower() not in VIDEO_EXTS:
        die(f"Unsupported file type: {input_video.suffix}")

    process(input_video, args.split, args.width, add_logo=not args.no_logo)


if __name__ == "__main__":
    main()
