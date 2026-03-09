# Kling v2.1 Standard

## Model Details
- **Endpoint:** `https://fal.run/fal-ai/kling-video/v2.1/standard/image-to-video`
- **Supported durations:** 5s, 10s
- **Configured duration:** 10s
- **Timeout:** 300,000ms (5 min)

## Cost
- **Per second:** $0.056
- **Per clip (10s):** $0.56
- **20 scenes:** $11.20

## Generation Time
- **Per clip:** ~2-3 minutes
- **20 scenes (sequential):** ~40-60 minutes

## Known Limitations
- Standard mode only (no Pro tier)
- 10s max duration
- Same price as v1.6 but noticeably better motion quality

## How to Use
1. Import `Biblical-Video-Workflow-v8-kling-v2.1-standard.json` into n8n
2. Activate the workflow
3. Trigger via the webhook with biblical text input
