import fal_client
import httpx
from pathlib import Path


def generate_video(image_path: Path, prompt: str, duration: float, output_path: Path) -> Path:
    """Animate a scene image into a video clip using Kling image-to-video."""
    # Upload image to fal.ai storage to get a stable URL
    image_url = fal_client.upload_file(str(image_path))

    # Kling supports duration "5" or "10" seconds
    kling_duration = "10" if duration >= 8 else "5"

    result = fal_client.subscribe(
        "fal-ai/kling-video/v1.6/standard/image-to-video",
        arguments={
            "image_url": image_url,
            "prompt": prompt,
            "duration": kling_duration,
            "cfg_scale": 0.5,
        },
    )
    video_url = result["video"]["url"]
    response = httpx.get(video_url, timeout=120)
    response.raise_for_status()
    output_path.write_bytes(response.content)
    return output_path
