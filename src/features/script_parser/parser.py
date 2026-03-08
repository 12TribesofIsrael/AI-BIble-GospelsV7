import json
from openai import OpenAI
from src.shared.config import settings
from .models import Scene, Script

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


SYSTEM_PROMPT = """You are a film director's assistant. Break the given script or story into cinematic scenes.

Return a JSON object with this exact structure:
{
  "title": "movie title",
  "scenes": [
    {
      "title": "short scene name",
      "description": "vivid visual description for AI image generation — include lighting, composition, color palette, mood, and cinematic style",
      "narration": "the dialogue or narration spoken in this scene (empty string if none)",
      "duration": 5
    }
  ]
}

Rules:
- 3 to 12 scenes maximum
- description must be rich and specific enough to generate a compelling image
- duration is an integer between 3 and 10 seconds
- narration should be natural spoken text, not stage directions"""


def parse_script(text: str) -> Script:
    client = _get_client()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)
    scenes = [
        Scene(
            index=i,
            title=s["title"],
            description=s["description"],
            narration=s.get("narration", ""),
            duration=float(s.get("duration", 5)),
        )
        for i, s in enumerate(data["scenes"])
    ]
    return Script(title=data.get("title", "AI Movie"), scenes=scenes)
