"""
batch_post_produce.py — Batch Post-Production
==============================================
Processes every .mp4/.mov/.mkv/.webm in output/raw/ through the
full post-production pipeline (intro, 3 outros, logo).
Music is disabled until caption sync is resolved.

Usage:
  python workflows/biblical-cinematic/scripts/batch_post_produce.py

  # 4K output:
  python workflows/biblical-cinematic/scripts/batch_post_produce.py --width 3840

Output:
  output/<video-name>_final.mp4  (one per raw video)
"""

import argparse
import sys
from pathlib import Path

# Import shared helpers from post_produce.py in the same folder
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
from post_produce import check_ffmpeg, check_assets, process, PROJECT_ROOT

RAW_DIR = PROJECT_ROOT / "output" / "raw"
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm"}


def main():
    parser = argparse.ArgumentParser(
        description="Batch post-produce all videos in output/raw/"
    )
    parser.add_argument(
        "--width", type=int, default=1920, metavar="PIXELS",
        help="Output width in pixels (default: 1920, use 3840 for 4K)"
    )
    args = parser.parse_args()

    print("\nBiblical Cinematic — Batch Post-Production")
    print("===========================================")

    check_ffmpeg()
    check_assets()

    if not RAW_DIR.exists():
        print(f"\n✗ Raw folder not found: {RAW_DIR}")
        print("  Create it and drop your downloaded videos in there.\n")
        sys.exit(1)

    videos = sorted(f for f in RAW_DIR.iterdir() if f.suffix.lower() in VIDEO_EXTS)

    if not videos:
        print(f"\n✗ No video files found in {RAW_DIR}")
        print(f"  Supported formats: {', '.join(VIDEO_EXTS)}\n")
        sys.exit(1)

    print(f"\nFound {len(videos)} video(s) to process:")
    for v in videos:
        print(f"  • {v.name}")

    print(f"\nProcessing {len(videos)} video(s)...\n")

    failed = []
    for i, video in enumerate(videos, 1):
        print(f"\n[{i}/{len(videos)}] {video.name}")
        try:
            process(video, args.width)
        except SystemExit:
            print(f"  ✗ Failed: {video.name}")
            failed.append(video.name)

    print("\n" + "=" * 55)
    succeeded = len(videos) - len(failed)
    print(f"  Done: {succeeded}/{len(videos)} videos processed successfully")
    if failed:
        print(f"\n  Failed:")
        for name in failed:
            print(f"    • {name}")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    main()
