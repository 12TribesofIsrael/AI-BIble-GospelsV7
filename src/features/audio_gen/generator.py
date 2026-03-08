from pathlib import Path
from openai import OpenAI
from src.shared.config import settings

_client: OpenAI | None = None

VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def generate_narration(text: str, output_path: Path, voice: str = "nova") -> Path | None:
    """Generate spoken narration for a scene. Returns None if text is empty."""
    if not text.strip():
        return None
    client = _get_client()
    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
    )
    output_path.write_bytes(response.content)
    return output_path
