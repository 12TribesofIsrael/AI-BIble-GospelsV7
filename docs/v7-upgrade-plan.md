# Plan: Biblical Cinematic v7 — AI Video Motion + Cinematic Title Cards

## Context

Current videos use FLUX Pro static images with Ken Burns (zoom/pan) simulation. This creates artificial movement rather than real motion. Competitors in the AI Biblical niche (AIBIBLESAGAS, AIBIBLEMOVIES) use actual AI video clips where robes move, wind blows, fire flickers. The goal is to:

1. **Add real AI video motion** via Kling (image-to-video) for all 20 scenes
2. **Add a cinematic title card** intro with book/chapter name and dramatic text animation
3. **Better visual style** via improved image prompts and scene composition

Budget tolerance: up to $8 extra → ~$9/video total.

---

## Two Phases

### Phase 1 — Free Upgrade (improve existing pipeline, no new APIs)
**Cost impact:** ~$0.05 extra (one extra FLUX image for title card) → ~$1.32/video

### Phase 2 — Kling Video Motion (~$7.31/video total)
Replaces JSON2Video's internal FLUX image generation with external FLUX + Kling clips.

---

## Phase 1: Free Upgrade

**3 changes, all in n8n + JSON2Video — no code edits.**

### Change 1: Improve Perplexity prompt (n8n: `Biblical Content Prompt Builder` node)

Add `motionDescription` to the output schema (used in Phase 2, harmless now). Add to image prompt instructions:

```
- CAMERA ANGLE VARIETY: Alternate close-up / medium shot / wide shot / aerial — never same angle twice in a row.
- LIGHTING CONTRAST: Specify a dramatic light source per scene — "shaft of divine light from above", "torch-lit darkness with one focal point", "golden hour rays behind silhouette".
```

Add to JSON schema:
```json
"motionDescription": "Natural motion for this moment — e.g. 'Camera slowly pulls back as figure raises hands toward golden sky' or 'Robes ripple in wind, crowd parts like a wave'"
```

### Change 2: More dramatic Ken Burns values (n8n: `Enhanced Format for 16:9 Template` node)

Replace conservative zoom values with dramatic ones:

| Effect | Old zoomStart | New zoomStart | Other |
|---|---|---|---|
| zoom-in | 2 | 5 | panStart/End: center |
| zoom-out | -2 | -4 | panStart/End: center |
| ken-burns | 2 | 3 | panStart: left, panEnd: right |
| pan-right | 0 | 1 | panStart: left, panEnd: right |
| pan-left | 0 | 1 | panStart: right, panEnd: left |

Also change `pan-distance` in the JSON2Video template from `0.2` → `0.35` for all 20 scenes.

### Change 3: Add cinematic title card scene (JSON2Video template)

Add 3 variables to the template `variables` block:
```json
"title_bookChapter": "{{title_bookChapter}}",
"title_subtitle": "{{title_subtitle}}",
"title_backgroundPrompt": "{{title_backgroundPrompt}}"
```

Insert as the **first scene** in the `scenes` array (8 seconds):

```json
{
  "id": "scene0_title_card",
  "duration": 8,
  "elements": [
    {
      "id": "title_bg",
      "type": "image",
      "prompt": "{{title_backgroundPrompt}}, dramatic divine light rays, rich gold and deep indigo, cinematic wide shot, 8K",
      "model": "flux-pro",
      "resize": "cover",
      "zoom": { "start": 3, "end": 0 },
      "pan": { "start": "center", "end": "center" }
    },
    {
      "id": "title_overlay",
      "type": "rectangle",
      "x": 0, "y": 0, "width": "100%", "height": "100%",
      "color": "#000000", "opacity": 0.5
    },
    {
      "id": "title_text",
      "type": "text",
      "text": "{{title_bookChapter}}",
      "font-family": "Cinzel Decorative",
      "font-size": 120,
      "color": "#D4AF37",
      "x": "center", "y": "40%", "width": "80%",
      "text-align": "center",
      "shadow-color": "#000000", "shadow-offset": 8,
      "animation": { "type": "fade-in", "duration": 1.5, "delay": 0.5 }
    },
    {
      "id": "title_divider",
      "type": "rectangle",
      "x": "25%", "y": "55%", "width": "50%", "height": 3,
      "color": "#D4AF37", "opacity": 0.8,
      "animation": { "type": "fade-in", "duration": 1.0, "delay": 1.5 }
    },
    {
      "id": "title_subtitle_text",
      "type": "text",
      "text": "{{title_subtitle}}",
      "font-family": "Cinzel",
      "font-size": 52,
      "color": "#F5E6C8",
      "x": "center", "y": "60%", "width": "70%",
      "text-align": "center",
      "shadow-color": "#000000", "shadow-offset": 5,
      "animation": { "type": "fade-in", "duration": 1.5, "delay": 2.0 }
    }
  ]
}
```

Also in the `Enhanced Format` Code node, extract book/chapter from the input and populate title vars:

```javascript
const rawInput = $('Bible Chapter Text Input').item.json.inputText;
const titleMatch = rawInput.match(/^((?:[1-3]\s)?[A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s+(\d+)/);
const bookName = titleMatch ? titleMatch[1] : "The Word of God";
const chapterNum = titleMatch ? titleMatch[2] : "";
templateVariables['title_bookChapter'] = chapterNum ? `${bookName} ${chapterNum}` : bookName;
templateVariables['title_subtitle'] = "A Cinematic Vision of Scripture";
templateVariables['title_backgroundPrompt'] =
  "Majestic ancient biblical skyline at golden dawn, divine light, cinematic";
```

---

## Phase 2: Kling AI Video Motion

### Architecture change

**Before (v6):** n8n passes `imagePrompt` → JSON2Video generates FLUX images internally + Ken Burns
**After (v7):** n8n generates FLUX image → animates with Kling → passes video URL → JSON2Video assembles clips

### Cost Breakdown

| Item | Unit | Count | Cost |
|---|---|---|---|
| Perplexity sonar-pro | ~$0.03 | 1 | $0.03 |
| fal.ai FLUX Pro | ~$0.055/image | 20 | $1.10 |
| fal.ai Kling v1.6 Pro (5s) | ~$0.28/clip | 20 | $5.60 |
| ElevenLabs (via JSON2Video) | ~$0.18 | 1 | $0.18 |
| JSON2Video (assembly only) | ~$0.40 | 1 | $0.40 |
| **Total** | | | **~$7.31** |

> Budget option: Kling Standard (~$0.14/clip) → ~$4.15/video total

### New JSON2Video Template v7

Create: `workflows/biblical-cinematic/templates/JSON2Video-Template-v7-Kling.json`

Each scene uses a `video` element (accepts Kling CDN URL) instead of an `image` element:

```json
{
  "id": "scene1_biblical",
  "duration": "auto",
  "elements": [
    {
      "id": "scene1_bg",
      "type": "video",
      "src": "{{scene1_videoUrl}}",
      "resize": "cover",
      "trim": { "start": 0, "end": 5 }
    },
    {
      "id": "scene1_voice",
      "type": "voice",
      "text": "{{scene1_voiceOverText}}",
      "voice": "NgBYGKDDq2Z8Hnhatgma",
      "model": "elevenlabs",
      "speed": 0.9
    }
  ]
}
```

Variables per scene (all Ken Burns variables dropped):
```json
"scene1_videoUrl": "{{scene1_videoUrl}}",
"scene1_voiceOverText": "{{scene1_voiceOverText}}",
"scene1_overlaidText": "{{scene1_overlaidText}}"
```

> **Note on long narration:** If voice exceeds 5s (it usually will), JSON2Video holds the last Kling frame and continues audio. Upgrade to `"duration": "10"` Kling clips (~$0.56/clip → ~$13/video) if you want motion throughout.

### New n8n Workflow v7 Node Chain

**Duplicate v6.0.2 workflow — never edit the working v6 directly.**

```
Webhook
  → Bible Chapter Text Input (unchanged)
  → Biblical Content Prompt Builder v7 (add motionDescription to schema)
  → Perplexity AI Scene Generator (unchanged)
  → Parse Scenes + Init [NEW] — outputs 20 separate items (one per scene)
  → Split In Batches (batch size: 1)
    → Generate FLUX Image [NEW] — fal.ai REST API, returns image URL
    → Submit Kling Job [NEW] — fal.ai queue API, returns request_id
    → Wait 60s [NEW]
    → Poll Kling Status [NEW] — GET status_url
    → Kling Complete? [NEW] — Switch: COMPLETED / IN_PROGRESS / error
      → (if not done) Wait 15s → back to Poll
    → Fetch Kling Result [NEW] — GET response_url, extract video URL
  → Merge All Scenes [NEW] — collect all 20 items
  → Build v7 Template Variables [NEW] — replaces "Enhanced Format" node
  → Generate v7 Spiritual Video (updated template ID + new variables)
  → Check Video Status (unchanged)
  → Video Status Router / Final Output (unchanged)
```

### Key HTTP Request payloads

**FLUX Pro (synchronous — returns image URL directly):**
```
POST https://fal.run/fal-ai/flux-pro
Authorization: Key {{FAL_API_KEY}}
{
  "prompt": "={{ $json.imagePrompt }}",
  "image_size": "landscape_16_9",
  "num_inference_steps": 28,
  "num_images": 1
}
→ Response: { "images": [{ "url": "https://fal.media/..." }] }
```

**Kling v1.6 Pro (async queue):**
```
POST https://queue.fal.run/fal-ai/kling-video/v1.6/pro/image-to-video
Authorization: Key {{FAL_API_KEY}}
{
  "image_url": "={{ $json.imageUrl }}",
  "prompt": "={{ $json.motionDescription }}",
  "duration": "5",
  "cfg_scale": 0.5
}
→ Response: { "request_id": "...", "status_url": "...", "response_url": "..." }
```

**Poll status:**
```
GET {{ $json.status_url }}
→ { "status": "IN_PROGRESS" } or { "status": "COMPLETED" }
```

**Fetch result (after COMPLETED):**
```
GET {{ $json.response_url }}
→ { "video": { "url": "https://fal.media/...mp4" } }
```

### fal.ai Credential in n8n

Add Header Auth credential:
- Name: `fal.ai`
- Header name: `Authorization`
- Header value: `Key YOUR_FAL_KEY` (same key as `FAL_KEY` in `.env`)

### `app.py` changes (Phase 2 only)

Update `api_status()` timing thresholds:

```python
# Perplexity: 0–90s
# fal.ai generation: 90–2000s (~33 min for 20 scenes)
if 90 <= elapsed < 2000:
    scene_estimate = min(20, int((elapsed - 90) / 90) + 1)
    return {"phase": "fal_generation", "scenes_estimated": scene_estimate, ...}
# JSON2Video: 2000s+
```

Add `fal_generation` phase to frontend HTML step list.
Update version label: `v7.0.0 · ~$7.31/video · 35–45 min`

---

## Critical Risk: n8n Execution Timeout

20 scenes × ~90s per Kling clip = ~30 minutes sequential. If your n8n cloud plan has a 30-minute execution limit, you're at the edge.

**Mitigations (in order of preference):**
1. **Use Kling Standard** (not Pro) — ~45s per clip → ~15 min total — well within limit
2. **Reduce to 10 scenes** — half cost and time, still full motion
3. **Use fal.ai webhooks** — Kling calls n8n back when done, no polling loop (more complex)

---

## Files to Modify

| File | Phase | Change |
|---|---|---|
| n8n: `Biblical Content Prompt Builder` node | 1+2 | Add `motionDescription` + cinematic prompt instructions |
| n8n: `Enhanced Format for 16:9 Template` node | 1 | Dramatic Ken Burns values + title card variables |
| `workflows/biblical-cinematic/templates/JSON2Video-Template-FIXED.json` | 1 | Add title card scene 0, increase pan-distance |
| `workflows/biblical-cinematic/templates/JSON2Video-Template-v7-Kling.json` | 2 | **NEW** — video elements, title card, new variables |
| `workflows/biblical-cinematic/n8n/Biblical-Video-Workflow-v7.0.0.json` | 2 | **NEW** — full Kling loop workflow (duplicate of v6, not edit) |
| `workflows/biblical-cinematic/server/app.py` | 2 | Phase timing updates, new fal_generation UI step |
| `CLAUDE.md` | Both | Cost/time + file table updates |

**Reference file** (read, not changed): `src/features/video_gen/generator.py` — shows how Kling is called in Workflow 1 (Python SDK pattern to translate to n8n HTTP calls)

---

## Implementation Order

1. **Phase 1 first** — test with one run, verify title card + dramatic motion
2. Add fal.ai credential to n8n
3. Test FLUX HTTP call in isolation (single hardcoded prompt)
4. Test Kling queue submit + poll in isolation (use a pre-generated FLUX URL)
5. Build full v7 n8n workflow (duplicate v6, never edit v6)
6. Test with 3 scenes (set Perplexity to return 3 for speed)
7. Test with 20 scenes (expect ~30–40 min)
8. Update `app.py` with new phase timings
9. Update n8n production webhook if using new workflow

---

## Answering Your Original Questions

**Can I see videos?** No — I can't watch or play video. To share inspiration, you can:
- Paste a YouTube video link (I can read titles/descriptions but not watch)
- Screenshot a specific moment
- Describe what you see: "I want a slow camera orbit around a figure", "I want dramatic text flying in from the sides", etc.

**Does JSON2Video support video clips?** Yes — it has a `video` element type that accepts any publicly accessible MP4 URL. fal.ai Kling output URLs are publicly accessible for 24h+.

**How to make videos more entertaining beyond this plan:**
- After Phase 2, the next biggest upgrade would be **better post-production music** (dramatic orchestral swells for key moments) and a proper **YouTube thumbnail pipeline** using the generated FLUX images.
