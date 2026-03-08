# Biblical Cinematic — Development Log

Chronological record of all versions and changes. Newest first.

Separate from:
- `ERRORS.md` — bug root causes and fixes
- `docs/v7-upgrade-plan.md` — forward-looking Phase 2 spec

---

## v7.2 — Field-Name-Anchored JSON Parsing  [2026-03-07]

**Status:** Production (current)
**Cost:** ~$1.32/video
**Time:** ~8–13 min
**Workflow file:** `n8n/Biblical-Video-Workflow-v7.2.json`
**Template:** `templates/JSON2Video-Template-FIXED.json` (template ID: `h5yD4ZbxhCPNFQ2WoVUs`)

### What changed

- Replaced broken `repairJson()` state machine with `extractScenes()` — field-name-anchored extraction that is immune to unescaped quotes in Perplexity responses
- Two-pass parsing: `JSON.parse()` fast path (~50% of runs) → `extractScenes()` fallback (100% reliable)
- Added `motionDescription` field to Perplexity schema (also used by Phase 2 Kling prompts)
- Added cinematic title card as scene 0 (8 sec, Book + Chapter name, gold text on biblical skyline)
- Dramatic Ken Burns motion values: zoom-in=5, zoom-out=-4, ken-burns=3 (was 2/−2/2)
- Title card variables: `title_bookChapter`, `title_subtitle`, `title_backgroundPrompt`

### Why

Perplexity sonar-pro returns unescaped double quotes inside JSON string values — e.g. `"the so-called "Pharisees" confronted him"`. `JSON.parse()` fails 30–50% of runs, especially on dialogue-heavy chapters (Matthew 12, etc.). Eight previous heuristic repair approaches all failed. Field-name anchoring bypasses the problem entirely because the 4 field names (`overlaidText`, `voiceOverText`, `imagePrompt`, `motionDescription`) are guaranteed never to appear inside biblical text or image prompt values.

### Key insight

`indexOf('"voiceOverText"')` always finds the actual JSON key — never something inside a value. Walk backwards from that anchor to find the closing quote of the previous field. No quote interpretation needed at all.

---

## v7.1 — json_schema + charCode State Machine  [2026-03-07]

**Status:** Failed — abandoned
**Root cause 1:** Perplexity `response_format: { type: "json_schema" }` requires Tier-3 account ($500+ spend). Silently ignored on lower tiers — no error, just no effect.
**Root cause 2:** charCode-based state machine still accumulated errors across 20 scenes. Parse failed at position 22910 in a 23860-char response.

---

## v7.0 — Phase 1 Draft  [2026-03-07]

**Status:** Superseded by v7.2 (same features, broken parser)

---

## v6.0.2 — Stable Baseline  [2026-02-XX]

**Status:** Legacy reference — do not edit
**Cost:** ~$1.27/video
**Time:** ~8–13 min
**Workflow file:** `n8n/Biblical-Video-Workflow-v6.0.2.json`

### What it does

- Paste KJV scripture → FastAPI server cleans text → sends to n8n webhook
- Perplexity sonar-pro generates 20 cinematic scene descriptions
- ElevenLabs narration (voice: `NgBYGKDDq2Z8Hnhatgma`, 214 WPM, speed 0.9)
- JSON2Video renders 20 scenes with Ken Burns (zoom/pan) motion → full HD MP4
- FastAPI server (`server/app.py`) polls render status, serves progress bar at `http://localhost:8000`
- Step 4: FFmpeg post-production (concat intro/outro, overlay logo, mix music)
- Step 5: YouTube auto-upload (OAuth2, unlisted, auto-generates title/description/thumbnail)

### Known issues fixed in v7.2

- JSON.parse failure on unescaped quotes (30–50% failure rate)
- Conservative Ken Burns values (low visual impact)
- No cinematic title card

---

## Roadmap

### v8.0 — Phase 2: Kling AI Video Motion  [planned]

**Estimated cost:** ~$7.31/video
**Estimated time:** ~35–45 min (sequential Kling processing)
**Spec:** `docs/v7-upgrade-plan.md`
**Base:** Duplicate v7.2 — never edit v7.2 directly

#### Architecture change

Before (v7.2): n8n passes `imagePrompt` → JSON2Video generates FLUX images internally + Ken Burns
After (v8.0): n8n generates FLUX image → Kling animates → video URL → JSON2Video assembles clips

#### Cost breakdown

| Item | Unit cost | Count | Total |
|---|---|---|---|
| Perplexity sonar-pro | ~$0.03 | 1 | $0.03 |
| fal.ai FLUX Pro | ~$0.055/image | 20 | $1.10 |
| fal.ai Kling v1.6 Pro (5s) | ~$0.28/clip | 20 | $5.60 |
| ElevenLabs (via JSON2Video) | ~$0.18 | 1 | $0.18 |
| JSON2Video (assembly only) | ~$0.40 | 1 | $0.40 |
| **Total** | | | **~$7.31** |

Budget option: Kling Standard (~$0.14/clip) → ~$4.15/video, ~15 min total

#### New n8n node chain (to add after duplicating v7.2)

```
Parse Scenes + Init     → splits Perplexity output into 20 separate items
Split In Batches (1)
  → Generate FLUX Image   (fal.ai REST, sync, returns image URL)
  → Submit Kling Job      (fal.ai queue, async, returns request_id + status_url)
  → Wait 60s
  → Poll Kling Status     (GET status_url)
  → Kling Complete?       (Switch: COMPLETED / IN_PROGRESS / error)
      → if not done: Wait 15s → back to Poll
  → Fetch Kling Result    (GET response_url, extract video URL)
Merge All Scenes          (collect all 20 items)
Build v8 Template Vars    (video elements, not image elements)
JSON2Video v8 Template    (new template with video type elements)
```

#### Risk

n8n cloud plans often have a 30-min execution timeout. 20 scenes × ~90s = ~30 min (at the limit).
Mitigation: use Kling Standard instead of Pro — ~45s/clip → ~15 min total.

#### app.py changes needed

Update phase timing thresholds to add `fal_generation` phase (90–2000s).
Update version label to `v8.0 · ~$7.31/video · 35–45 min`.
