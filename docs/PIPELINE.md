# Biblical Cinematic — Pipeline Evolution

This document shows the original manual workflow and the new automated workflow side by side. Use this as the master plan to track what's been built and what's next.

---

## Original Workflow (Manual)

Every step marked ⚙ required manual action. The average session took **45–90 minutes of hands-on work** per video.

```
Scripture text (copy from Bible)
│
▼
1. ⚙ MANUAL — Paste into web app (http://localhost:8000)
│
▼
2. ⚙ MANUAL — Click "Convert & Clean"
│    Text processor removes KJV formatting, verse numbers, old spellings
│
▼
3. ⚙ MANUAL — Review and edit cleaned text
│
▼
4. ⚙ MANUAL — Click "Approve & Generate Video"
│    Server POSTs to n8n webhook
│
▼
5. AUTO — n8n runs (hands-off, ~8–13 min)
│    → Perplexity AI   → 20 cinematic scenes
│    → ElevenLabs      → narration audio
│    → JSON2Video      → renders HD video
│
▼
6. ⚙ MANUAL — Open JSON2Video dashboard
│    Check if render is done (no notification, had to keep checking)
│
▼
7. ⚙ MANUAL — Download MP4 from JSON2Video
│
▼
8. ⚙ MANUAL — Open Canva
│    Import MP4
│    Add logo (position, resize)
│    Add intro video clip
│    Add outro video clip
│    Add background music track (adjust volume by ear)
│    Export — wait 10–20 min
│
▼
9. ⚙ MANUAL — Download final video from Canva
│
▼
10. ⚙ MANUAL — Open YouTube Studio
│    Upload video
│    Write title, description, tags
│    Set thumbnail
│    Schedule or publish
│
▼
Published ✓

Total hands-on time: ~45–90 min per video
```

---

## New Workflow (Automated) — Current + Planned

Steps marked ✓ AUTO are already built and working.
Steps marked ◯ PLANNED are designed but not yet built.

```
Scripture text (copy from Bible)
│
▼
1. ⚙ MANUAL — Paste into web app (http://localhost:8000)
│
▼
2. ⚙ MANUAL — Click "Convert & Clean"
│    Text processor cleans automatically
│
▼
3. ⚙ MANUAL — Review cleaned text (quick scan, usually no edits needed)
│
▼
4. ⚙ MANUAL — Click "Approve & Generate Video"
│    Server POSTs to n8n webhook
│
▼
5. ✓ AUTO — n8n runs (~8–13 min)
│    → Perplexity AI   → 20 cinematic scenes
│    → ElevenLabs      → narration audio
│    → JSON2Video      → renders HD video
│
▼
6. ✓ AUTO — Live progress bar on page (real-time JSON2Video polling)
│    Shows: Perplexity → ElevenLabs → Rendering → Done
│    No more dashboard-checking; server tells you when it's ready
│
▼
7. ⚙ MANUAL — Click Download button (appears automatically when render finishes)
│
▼
8. ✓ AUTO — Run post-produce.py (replaces Canva entirely)
│    python workflows/biblical-cinematic/scripts/post-produce.py video.mp4
│    → Concat intro + video + outro
│    → Overlay logo (bottom-left)
│    → Mix background music (pick track from numbered list)
│    → Outputs output/{name}_final.mp4
│    Time: ~2 min (FFmpeg)
│
▼
9. ✓ AUTO — Run upload_youtube.py (uploads as unlisted draft)
│    python workflows/biblical-cinematic/scripts/upload_youtube.py output/video_final.mp4 "Genesis 1"
│    → Authenticates via OAuth2 (browser on first run, token reused after)
│    → Auto-generates title: "Genesis 1 | KJV Bible | AI Cinematic"
│    → Auto-generates description + tags
│    → Generates thumbnail (dark background + gold scripture text via Pillow)
│    → Uploads to YouTube as unlisted
│    → Prints video URL + Studio edit link
│
▼
Published ✓

Total hands-on time: ~3–5 min per video (just paste, review, click, done)
```

---

## Side-by-Side Comparison

| Step | Original | New | Status |
|---|---|---|---|
| Paste scripture | Manual | Manual | unchanged |
| Clean text | Manual | Manual | unchanged |
| Review text | Manual | Manual | unchanged |
| Trigger n8n | Manual click | Manual click | unchanged |
| n8n pipeline | Auto | Auto | unchanged |
| Track render progress | Manual (check dashboard) | Auto (live progress bar on page) | ✓ built |
| Download video | Manual (JSON2Video site) | One click (Download button on page) | ✓ built |
| Add logo + intro + outro | Manual (Canva, 20+ min) | Auto (FFmpeg script, ~2 min) | ✓ built |
| Add music | Manual (Canva, by ear) | Auto (pick from numbered list) | ✓ built |
| YouTube upload | Manual (Studio, 10+ min) | Auto (YouTube API script) | ✓ built |
| Title / description | Manual | Auto-generated | ✓ built |

---

## Phase Roadmap

### Phase 1 — Post-Production Automation ✓ COMPLETE
- Built `scripts/post-produce.py`
- Intro + outro concat, logo overlay, music mixing via FFmpeg
- Drop assets into `assets/` folder once → reuse every video
- Eliminates Canva from the workflow entirely

### Phase 2 — Real-Time Progress Tracking ✓ COMPLETE
- Added `/api/status` endpoint to FastAPI server
- Polls JSON2Video API every 6s for live render status
- Progress bar on page: Perplexity → ElevenLabs → JSON2Video → Done
- Download button appears automatically when render completes
- Fixed JSON2VIDEO_API_KEY loading in `.env`

### Phase 3 — YouTube Auto-Upload ✓ COMPLETE
- `scripts/upload_youtube.py` — standalone script, mirrors post_produce.py style
- OAuth2 Desktop flow (browser on first run, token reused after)
- Auto-generates title (`{Book} {Chapter} | KJV Bible | AI Cinematic`), description, tags
- Generates thumbnail via Pillow (dark background + gold scripture text, 1280×720)
- Uploads as **unlisted** — user publishes from YouTube Studio when ready
- Prints YouTube URL + Studio edit link on completion

### Phase 4 — Full One-Click Pipeline ◯ FUTURE
- Single command: `python generate.py "Matthew 8"`
  1. Fetch scripture from API (no copy-paste)
  2. Clean text
  3. Trigger n8n → wait for render
  4. Download video
  5. Post-produce (auto-pick music)
  6. Upload to YouTube
- Fully headless — no browser required
- Optional: daily scheduler (generate + publish on a cadence)

---

## Files Built So Far

| File | Phase | Purpose |
|---|---|---|
| `workflows/biblical-cinematic/server/app.py` | 1 + 2 | FastAPI server with `/api/clean`, `/api/generate`, `/api/status` |
| `workflows/biblical-cinematic/scripts/post-produce.py` | 1 | FFmpeg post-production (logo, intro, outro, music) |
| `workflows/biblical-cinematic/assets/` | 1 | Drop-in folder for logo, intro, outro, music tracks |
| `workflows/biblical-cinematic/n8n/Biblical-Video-Workflow-v6.0.2.json` | — | n8n workflow (import once, runs forever) |
| `workflows/biblical-cinematic/templates/JSON2Video-Template-FIXED.json` | — | JSON2Video template (import once) |
| `workflows/biblical-cinematic/scripts/upload_youtube.py` | 3 | YouTube uploader — OAuth2, thumbnail gen, unlisted upload |

---

*Last updated: March 2026*
