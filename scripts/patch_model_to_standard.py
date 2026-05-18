"""One-off: switch pipeline_state.model from v3.0-pro to v3.0 (Standard) for remaining scenes."""
import json
import sys
from pathlib import Path

state_path = Path(sys.argv[1])
data = json.loads(state_path.read_text(encoding="utf-8"))

print(f"before — phase: {data.get('phase')} | model: {data.get('model')} | processed: {len(data.get('processed', []))}/{len(data.get('scenes', []))}")
data["model"] = "v3.0"
print(f"after  — phase: {data.get('phase')} | model: {data.get('model')} | processed: {len(data.get('processed', []))}/{len(data.get('scenes', []))}")

out_path = state_path.with_name(state_path.stem + "_modelpatched.json")
out_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
print(f"wrote: {out_path}")
