# Kling v3 Standard

## Model Details
- **Endpoint:** `https://fal.run/fal-ai/kling-video/v3/standard/image-to-video`
- **Supported durations:** 3s, 5s, 10s, 15s
- **Configured duration:** 15s
- **Timeout:** 600,000ms (10 min)

## Cost
- **Per second:** $0.224
- **Per clip (15s):** $3.36
- **20 scenes:** $67.20

## Generation Time
- **Per clip:** ~3-5 minutes
- **20 scenes (sequential):** ~60-100 minutes

## Known Limitations
- 4x more expensive per second than v1.6/v2.1
- Longer generation times due to higher quality processing
- Total video cost ~$77 vs ~$21 for older models

## How to Use
1. Import `Biblical-Video-Workflow-v8-kling-v3-standard.json` into n8n
2. Activate the workflow
3. Trigger via the webhook with biblical text input
