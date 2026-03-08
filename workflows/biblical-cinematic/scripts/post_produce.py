"""
post_produce.py — Biblical Cinematic Post-Production
=====================================================
Adds intro, 3 outros, and logo watermark to a raw video from JSON2Video.
Music is disabled until caption sync is resolved.

Usage:
  python post_produce.py path/to/raw-video.mp4
  python post_produce.py path/to/raw-video.mp4 --width 3840  (for 4K output)

Output:
  output/<video-name>_final.mp4  (relative to project root)

Requirements:
  - FFmpeg installed and on PATH
  - assets/logo1.png      (transparent background PNG)
  - assets/Into.mp4       (intro clip)
  - assets/outro_1.mp4    (outro part 1)
  - assets/outro_2.mp4    (outro part 2)
  - assets/outro_3.mp4    (outro part 3)
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


# ── Paths ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
BIBLICAL_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BIBLICAL_DIR.parent.parent  # c:/Users/Tommy/AI Movie

ASSETS_DIR = BIBLICAL_DIR / "assets"
OUTPUT_DIR = PROJECT_ROOT / "output"

LOGO  = ASSETS_DIR / "logo1.png"
INTRO = ASSETS_DIR / "Into.mp4"
OUTROS = [
    ASSETS_DIR / "outro_1.mp4",
    ASSETS_DIR / "outro_2.mp4",
    ASSETS_DIR / "outro_3.mp4",
]

# Logo size in pixels wide (≈ 1.5–2 inches on a 1080p display)
LOGO_WIDTH = 500


# ── Helpers ───────────────────────────────────────────────────────────────────

def check_ffmpeg():
    """Verify FFmpeg is available on PATH."""
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        if result.returncode != 0:
            raise FileNotFoundError
    except FileNotFoundError:
        print("\n✗ FFmpeg not found on PATH.")
        print("  Install it from https://ffmpeg.org/download.html")
        print("  and make sure it's added to your system PATH.\n")
        sys.exit(1)


def check_assets():
    """Verify required asset files exist."""
    missing = []
    if not LOGO.exists():
        missing.append(f"  logo1.png      → {LOGO}")
    if not INTRO.exists():
        missing.append(f"  Into.mp4       → {INTRO}")
    for outro in OUTROS:
        if not outro.exists():
            missing.append(f"  {outro.name:<14} → {outro}")

    if missing:
        print("\n✗ Missing required assets:")
        for item in missing:
            print(item)
        sys.exit(1)


def run(cmd, label):
    """Run an FFmpeg command, show progress, exit on failure."""
    print(f"\n  → {label}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"\n✗ FFmpeg error during: {label}")
        print(result.stderr[-3000:])
        sys.exit(1)


# ── Pipeline ──────────────────────────────────────────────────────────────────

def normalize_segment(src: Path, dst: Path, scale: str):
    """Re-encode a single clip to consistent specs (fps, audio rate, pixel format)."""
    run(
        [
            "ffmpeg", "-y",
            "-i", str(src),
            "-vf", f"scale={scale},fps=30,format=yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
            "-movflags", "+faststart",
            str(dst),
        ],
        f"Normalizing {src.name}"
    )


def build_concat_list(paths: list, tmp_dir: str) -> Path:
    """Write an FFmpeg concat list from a list of Paths."""
    concat_file = Path(tmp_dir) / "concat_list.txt"
    lines = [f"file '{p.as_posix()}'" for p in paths]
    concat_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return concat_file


def process(input_video: Path, output_width: int):
    """Run the full FFmpeg post-production pipeline."""

    check_assets()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    stem = input_video.stem
    final_output = OUTPUT_DIR / f"{stem}_final.mp4"

    output_height = (output_width * 9) // 16
    scale = f"{output_width}:{output_height}"

    print(f"\n{'─'*55}")
    print(f"  Input:    {input_video.name}")
    print(f"  Logo:     logo1.png  ({LOGO_WIDTH}px wide)")
    print(f"  Outros:   outro_1 → outro_2 → outro_3")
    print(f"  Output:   {output_width}×{output_height}  →  {final_output.name}")
    print(f"{'─'*55}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)

        # ── Stage 1: Normalize all segments to identical specs ─────────────
        # This prevents freezes caused by mismatched fps/audio/pixel format
        # between the intro, main video, and outro files.
        segments_in = [INTRO, input_video] + OUTROS
        segments_out = []
        for i, seg in enumerate(segments_in):
            out = tmp / f"seg_{i:02d}.mp4"
            normalize_segment(seg, out, scale)
            segments_out.append(out)

        # ── Stage 2: Concatenate all normalized segments ───────────────────
        temp_concat = tmp / "concat.mp4"
        concat_list = build_concat_list(segments_out, tmp_dir)

        run(
            [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_list),
                "-c", "copy",
                str(temp_concat),
            ],
            "Stage 2/2 — Concatenating intro + video + outro_1 + outro_2 + outro_3"
        )

        # ── Stage 3: Overlay logo (bottom-left, 20px margin) ──────────────
        logo_filter = (
            f"[1:v]scale={LOGO_WIDTH}:-1[logo];"
            f"[0:v][logo]overlay=x=20:y=H-h-20[vout]"
        )

        run(
            [
                "ffmpeg", "-y",
                "-i", str(temp_concat),
                "-i", str(LOGO),
                "-filter_complex", logo_filter,
                "-map", "[vout]",
                "-map", "0:a",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "copy",
                "-movflags", "+faststart",
                str(final_output),
            ],
            "Stage 3/3 — Overlaying logo"
        )

    size_mb = final_output.stat().st_size / (1024 * 1024)
    print(f"\n{'─'*55}")
    print(f"  ✓ Done!  {final_output.name}  ({size_mb:.1f} MB)")
    print(f"  Path: {final_output}")
    print(f"{'─'*55}\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Post-produce a Biblical Cinematic video (logo + intro/outros, no music)"
    )
    parser.add_argument("input_video", help="Path to the raw video from JSON2Video")
    parser.add_argument(
        "--width", type=int, default=1920, metavar="PIXELS",
        help="Output width in pixels (default: 1920, use 3840 for 4K)"
    )
    args = parser.parse_args()

    input_video = Path(args.input_video).resolve()
    if not input_video.exists():
        print(f"\n✗ Input video not found: {input_video}\n")
        sys.exit(1)
    if input_video.suffix.lower() not in (".mp4", ".mov", ".mkv", ".webm"):
        print(f"\n✗ Unsupported file type: {input_video.suffix}\n")
        sys.exit(1)

    print("\nBiblical Cinematic — Post-Production")
    print("=====================================")

    check_ffmpeg()
    check_assets()
    process(input_video, args.width)


if __name__ == "__main__":
    main()
