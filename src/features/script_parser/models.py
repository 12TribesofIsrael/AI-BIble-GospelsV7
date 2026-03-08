from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Scene:
    index: int
    title: str
    description: str   # visual description → used for image generation
    narration: str     # dialogue/narration → used for TTS
    duration: float = 5.0
    image_path: Optional[str] = None
    video_path: Optional[str] = None
    audio_path: Optional[str] = None


@dataclass
class Script:
    title: str
    scenes: list[Scene] = field(default_factory=list)
