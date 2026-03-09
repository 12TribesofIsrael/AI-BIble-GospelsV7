# Kling Model Variants for Biblical Video Workflow v8.0

Each subfolder contains a ready-to-import n8n workflow configured for a specific Kling AI model.

## Model Comparison

| Model | Duration | Cost/sec | Cost/clip (max) | Cost/20 scenes | Quality | Gen time/clip | Total gen time | Best For |
|---|---|---|---|---|---|---|---|---|
| v1.6 Standard | 5-10s | $0.056 | $0.56 | $11.20 | Good | ~2-3 min | ~40-60 min | Budget runs, testing |
| v2.1 Standard | 5-10s | $0.056 | $0.56 | $11.20 | Better | ~2-3 min | ~40-60 min | Better motion, same price |
| v3 Standard | 3-15s | $0.224 | $3.36 | $67.20 | Best | ~3-5 min | ~60-100 min | Final production quality |

## Full Video Cost Breakdown

| Component | v1.6 Standard | v2.1 Standard | v3 Standard |
|---|---|---|---|
| FLUX Pro images (20x ~$0.46) | $9.20 | $9.20 | $9.20 |
| Kling video clips (20 scenes) | $11.20 | $11.20 | $67.20 |
| ElevenLabs narration (~2000 chars) | ~$0.30 | ~$0.30 | ~$0.30 |
| JSON2Video rendering | ~$0.50 | ~$0.50 | ~$0.50 |
| **Total per video** | **~$21.20** | **~$21.20** | **~$77.20** |

### FLUX Pro Cost Detail
- FLUX Pro v1.1: $0.05/megapixel
- At 1920x1080 (~2.07 MP): ~$0.10/image, ~$2.00 for 20 images
- At higher quality settings: ~$0.46/image, ~$9.20 for 20 images

## How to Use

1. Pick a model folder based on your budget and quality needs
2. Import the JSON file into n8n (Settings > Import Workflow)
3. The FAL_KEY is already configured in the HTTP Request node headers
4. Activate the workflow and trigger via the webhook

## Folder Structure

```
models/
  v1.6-standard/   Kling v1.6 — good quality, cheapest
  v2.1-standard/   Kling v2.1 — better motion, same price as v1.6
  v3-standard/     Kling v3   — best quality, 4x cost
```
