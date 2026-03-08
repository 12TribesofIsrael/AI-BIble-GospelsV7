import subprocess
from pathlib import Path
from src.features.script_parser.models import Scene


def _combine_video_audio(video_path: Path, audio_path: Path, output_path: Path) -> Path:
    """Merge a video clip with an audio track, trimming to the shorter duration."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )
    return output_path


def assemble_movie(scenes: list[Scene], output_path: Path) -> Path:
    """Concatenate all scene clips (with audio) into a single movie file."""
    work_dir = output_path.parent
    combined_clips: list[Path] = []

    for scene in scenes:
        if not scene.video_path:
            continue

        video = Path(scene.video_path)

        if scene.audio_path and Path(scene.audio_path).exists():
            combined = work_dir / f"scene_{scene.index}_combined.mp4"
            _combine_video_audio(video, Path(scene.audio_path), combined)
            combined_clips.append(combined)
        else:
            combined_clips.append(video)

    if not combined_clips:
        raise RuntimeError("No video clips to assemble.")

    # Write concat manifest
    concat_file = work_dir / "concat.txt"
    concat_file.write_text(
        "\n".join(f"file '{clip.resolve()}'" for clip in combined_clips)
    )

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )
    return output_path
