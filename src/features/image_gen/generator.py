import fal_client
import httpx
from pathlib import Path


def generate_image(description: str, output_path: Path) -> Path:
    """Generate a cinematic still image from a scene description using FLUX."""
    result = fal_client.subscribe(
        "fal-ai/flux/dev",
        arguments={
            "prompt": description,
            "image_size": "landscape_16_9",
            "num_inference_steps": 28,
            "guidance_scale": 3.5,
            "num_images": 1,
            "enable_safety_checker": False,
        },
    )
    image_url = result["images"][0]["url"]
    response = httpx.get(image_url, timeout=60)
    response.raise_for_status()
    output_path.write_bytes(response.content)
    return output_path
