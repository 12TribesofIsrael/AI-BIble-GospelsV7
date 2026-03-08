"""
Full movie generation pipeline.

Stages:
  1. parse_script   → break script text into Scene objects (GPT-4o)
  2. generate_image → create a cinematic still per scene (FLUX via fal.ai)
  3. generate_video → animate each still into a clip (Kling via fal.ai)
  4. generate_narration → TTS voiceover per scene (OpenAI TTS)
  5. assemble_movie → stitch clips + audio into final .mp4 (FFmpeg)
"""

import os
import uuid
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

load_dotenv()

# fal_client reads FAL_KEY from environment — must load .env before importing
import fal_client  # noqa: E402

from src.shared.config import settings
from src.features.script_parser.parser import parse_script
from src.features.image_gen.generator import generate_image
from src.features.video_gen.generator import generate_video
from src.features.audio_gen.generator import generate_narration
from src.features.assembler.assembler import assemble_movie


def run_pipeline(
    script_text: str,
    progress: Callable[[str], None] | None = None,
) -> Path:
    def log(msg: str) -> None:
        print(msg)
        if progress:
            progress(msg)

    output_dir = Path(settings.output_dir)
    run_id = uuid.uuid4().hex[:8]
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Stage 1: parse
    log("Parsing script into scenes...")
    script = parse_script(script_text)
    log(f'"{script.title}" — {len(script.scenes)} scenes')

    # Stage 2: images
    for scene in script.scenes:
        log(f"[{scene.index + 1}/{len(script.scenes)}] Generating image: {scene.title}")
        image_path = run_dir / f"scene_{scene.index:02d}_image.jpg"
        scene.image_path = str(generate_image(scene.description, image_path))

    # Stage 3: videos
    for scene in script.scenes:
        log(f"[{scene.index + 1}/{len(script.scenes)}] Animating: {scene.title}")
        video_path = run_dir / f"scene_{scene.index:02d}_video.mp4"
        scene.video_path = str(
            generate_video(Path(scene.image_path), scene.description, scene.duration, video_path)
        )

    # Stage 4: narration
    for scene in script.scenes:
        if scene.narration.strip():
            log(f"[{scene.index + 1}/{len(script.scenes)}] Narrating: {scene.title}")
            audio_path = run_dir / f"scene_{scene.index:02d}_audio.mp3"
            result = generate_narration(scene.narration, audio_path)
            if result:
                scene.audio_path = str(result)

    # Stage 5: assemble
    log("Assembling final movie...")
    final_path = run_dir / "movie.mp4"
    assemble_movie(script.scenes, final_path)
    log(f"Done → {final_path}")
    return final_path


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pipeline.py <script-file.txt>")
        sys.exit(1)

    script_text = Path(sys.argv[1]).read_text()
    output = run_pipeline(script_text)
    print(f"\nMovie saved to: {output}")
