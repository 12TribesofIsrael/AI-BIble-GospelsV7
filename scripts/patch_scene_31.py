"""One-off: patch scene 31 (index 30) image prompt in the custom-script Modal state file.
Reads the downloaded state, replaces scene[30].imagePrompt, writes alongside as *_patched.json.
"""
import json
import sys
from pathlib import Path

state_path = Path(sys.argv[1])
data = json.loads(state_path.read_text(encoding="utf-8"))

scenes = data["scenes"]
processed_count = len(data.get("processed", []))
print(f"total scenes: {len(scenes)} | processed: {processed_count} | phase: {data.get('phase')}")

scene_idx = 30  # scene 31, 0-indexed
scene = scenes[scene_idx]
print(f"\n--- scene {scene_idx + 1} BEFORE ---")
print(f"narration:   {scene.get('narration', '')[:120]}")
print(f"imagePrompt: {scene.get('imagePrompt', '')}")

new_prompt = (
    "Stone wall under construction at dusk, a single dramatic bolt of golden divine "
    "light striking down from storm clouds onto a tall stone tower in the distance, "
    "Caucasian European Edomite masons with pale fair skin tinged red, brown wavy hair, "
    "reddish-brown beards in red robes turning to look up in shock, fine dust and small "
    "stones falling from the tower in the impact moment, dramatic golden-red lighting, "
    "photorealistic, cinematic, 8K detail"
)

scene["imagePrompt"] = new_prompt
print(f"\n--- scene {scene_idx + 1} AFTER ---")
print(f"imagePrompt: {scene['imagePrompt']}")

out_path = state_path.with_name(state_path.stem + "_patched.json")
out_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
print(f"\nwrote: {out_path}")
