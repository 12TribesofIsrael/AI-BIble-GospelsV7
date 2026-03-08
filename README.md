# AI Movie

A personal workspace for building AI-generated video systems. Paste in text — get back a fully produced, narrated cinematic video.

Contains two independent workflows:

| Workflow | Status | What it does |
|---|---|---|
| **Biblical Cinematic** | Production — Working | KJV scripture → 12–20 min cinematic video with narration |
| **General AI Movie** | In Development | Script/prompt → images → animated video clips → narrated movie |

---

## Workflow 1: Biblical Cinematic

### What It Does

You paste in raw KJV scripture text. The app cleans and formats it, you review it, click one button, and 8–13 minutes later a fully produced cinematic video is waiting for you — complete with:

- 20 AI-generated cinematic scene descriptions
- Professional narration audio (ElevenLabs voices)
- HD video with Ken Burns (pan & zoom) effects
- Synchronized visuals and audio via JSON2Video

**Cost per video:** ~$1.27 | **Render time:** 8–13 minutes

---

### The Full Pipeline (What Happens Behind the Scenes)

```
You (browser at http://localhost:8000)
  │
  ▼
Step 1 — TEXT CLEANING
  Your raw KJV scripture is sent to the FastAPI server.
  The biblical_text_processor_v2.py script:
    - Removes verse numbers (e.g. "1:1", "[1]")
    - Fixes 95+ OCR artifacts and punctuation errors
    - Normalizes archaic spellings for TTS
    - Splits the text into ~1000-word narration sections
  → Cleaned text is returned to your browser for review.
  │
  ▼
Step 2 — YOUR REVIEW
  You read through the cleaned text in the browser.
  You can edit anything before approving.
  When satisfied, click "Approve & Generate Video."
  │
  ▼
Step 3 — WEBHOOK TRIGGER
  The server POSTs the cleaned text to your n8n webhook:
    POST https://your-n8n.cloud/webhook/your-id
    Body: { "text": "In the beginning God created..." }
  n8n receives it instantly and begins the pipeline.
  │
  ▼
Step 4 — SCENE GENERATION (Perplexity AI · sonar-pro)
  n8n sends the text to Perplexity AI with a detailed prompt.
  Perplexity generates exactly 20 cinematic scene descriptions,
  each tailored for 16:9 HD video with visual storytelling.
  Example output:
    Scene 1: "A vast, dark void stretches endlessly — then a single
    point of golden light explodes outward, illuminating swirling
    cosmic dust and newborn stars..."
  │
  ▼
Step 5 — NARRATION AUDIO (ElevenLabs)
  n8n sends the original cleaned text to ElevenLabs TTS.
  A professional narrator voice reads the full scripture passage.
  The audio is timed at ~214 words per minute.
  Output: a single narration audio file for the full video.
  │
  ▼
Step 6 — VIDEO RENDERING (JSON2Video · Ken Burns template)
  n8n sends the 20 scene descriptions + audio to JSON2Video.
  JSON2Video uses the FIXED template to:
    - Generate or source one image per scene
    - Apply Ken Burns pan & zoom effects to each image
    - Synchronize the narration audio across all 20 scenes
    - Render the final HD MP4 (12–20 minutes long)
  │
  ▼
Step 7 — DONE
  Check your JSON2Video dashboard for the finished video.
  Download the MP4.
```

---

### Prerequisites (Accounts You Need)

Before first use, make sure you have:

- **n8n** — [n8n.io](https://n8n.io) — cloud ($20/mo) or self-hosted (free)
- **Perplexity AI** — [perplexity.ai](https://perplexity.ai) — API key for sonar-pro model
- **ElevenLabs** — [elevenlabs.io](https://elevenlabs.io) — API key for TTS
- **JSON2Video** — [json2video.com](https://json2video.com) — API key + imported template
- **Python 3.7+** — installed locally

---

### One-Time Setup

#### 1. Configure your `.env` file

At the workspace root, copy the example and fill it in:

```bash
cp .env.example .env
```

Open `.env` and set:

```
N8N_WEBHOOK_URL=https://your-n8n-instance.app.n8n.cloud/webhook/your-webhook-id
```

> This is the **Production URL** from your n8n webhook node — it starts with `/webhook/`, not `/webhook-test/`.

---

#### 2. Set up the n8n Workflow (one-time)

1. Open your n8n instance
2. Import `workflows/biblical-cinematic/n8n/Biblical-Video-Workflow-v6.0.2.json`
3. Add your API credentials inside n8n:
   - **Perplexity node** → `Bearer YOUR_PERPLEXITY_API_KEY`
   - **ElevenLabs node** → your ElevenLabs API key
   - **JSON2Video node** → your JSON2Video API key
4. In n8n, make sure the **Webhook** node is connected to the **"Bible Chapter Text Input"** node
5. In the **"Bible Chapter Text Input"** Set node, the value must be: `{{ $json.body.text }}`
6. **Toggle the workflow to Published/Active** (green badge, top-right of editor)
7. Copy the Production webhook URL → paste into `.env` as `N8N_WEBHOOK_URL`

---

#### 3. Set up JSON2Video (one-time)

1. Log into [json2video.com](https://json2video.com)
2. Import `workflows/biblical-cinematic/templates/JSON2Video-Template-FIXED.json`
3. Copy the Template ID it generates
4. Paste that Template ID into the JSON2Video node inside your n8n workflow

---

#### 4. Install server dependencies (first time only)

```bash
cd workflows/biblical-cinematic/server
pip install -r requirements.txt
```

---

### How to Use the App (Step by Step)

#### Step 1 — Start the server

**Option A — Double-click (fastest):**
Double-click `start.bat` at the project root. A terminal opens, the server starts, and the window stays open.

**Option B — Terminal:**
```bash
cd workflows/biblical-cinematic/server
python app.py
# or: npm start
```

You'll see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

#### Step 2 — Open the web app

Go to **http://localhost:8000** in your browser.

You'll see the landing page with a text area and three-step progress indicator.

#### Step 3 — Paste your scripture

Paste raw KJV text into the text area. It can be messy — verse numbers, OCR artifacts, and formatting errors are all handled automatically.

Example input:
```
Genesis 1:1 In the beginning God created the heaven and the earth. 1:2 And the
earth was without form, and void; and darkness [was] upon the face of the deep.
```

Click **"Convert & Clean"**.

#### Step 4 — Review the cleaned text

The app processes your text and displays the cleaned version. It will have:
- Verse numbers removed
- Punctuation corrected
- Text split into natural narration sections

Read through it. You can edit directly in the browser if anything looks wrong.

#### Step 5 — Approve and generate

Click **"Approve & Generate Video"**.

The app immediately:
1. Sends the text to your n8n webhook
2. Shows a confirmation message

You'll see: *"Your video is being generated — check your JSON2Video dashboard in 8–13 minutes."*

#### Step 6 — Wait for the render

The n8n pipeline runs automatically:
- Perplexity generates 20 scene descriptions (~30 sec)
- ElevenLabs renders narration audio (~1–2 min)
- JSON2Video renders the full HD video (~8–13 min total)

#### Step 7 — Download your video

Log into [json2video.com](https://json2video.com), go to your dashboard, and download the finished MP4.

---

### Available Narrator Voices

Configured inside the n8n ElevenLabs node:

| Voice | ElevenLabs ID | Style |
|---|---|---|
| Young Jamal *(default)* | `6OzrBCQf8cjERkYgzSg8` | Young, clear narration |
| Tommy Israel *(personal)* | `T4sLxEj9xEGMREO21ACw` | Personal voice |
| William J | `C8OtYB0OTgD7K0YWkg7y` | Professional |
| Hakeem | `nJvj5shg2xu1GKGxqfkE` | Deep, authoritative |
| Lamar Lincoln | `CVRACyqNcQefTlxMj9b` | Rich narrator tone |

To change the voice, update the Voice ID in the ElevenLabs node inside n8n.

---

### Troubleshooting

**"N8N_WEBHOOK_URL is not set" error**
- Make sure `.env` exists at the workspace root (not inside `server/`)
- Restart the server after editing `.env`
- The URL must use `/webhook/` — not `/webhook-test/`

**Approved but nothing happens in n8n**
- Check that the workflow is **Published** (not just saved)
- Confirm the Webhook node is connected to "Bible Chapter Text Input"
- Confirm the Set node value is `{{ $json.body.text }}` (expression mode, not fixed)

**Port 8000 already in use (Windows)**
- Find the PID: `netstat -ano | findstr :8000`
- Kill it: `python -c "import subprocess; subprocess.run(['taskkill', '/F', '/PID', 'THE_PID'], shell=True)"`

---

---

## Workflow 2: General AI Movie Pipeline

### What It Does

Turn any script, screenplay, or text prompt into a fully produced movie with:
- AI-generated images for each scene (FLUX via fal.ai)
- Animated video clips from each image (Kling via fal.ai)
- AI narration audio for each scene (OpenAI TTS)
- Final assembled MP4 (FFmpeg)

**Status:** In development — pipeline is built, API keys not yet configured.

---

### The Full Pipeline

```
You enter a script or prompt into the Gradio UI
  │
  ▼
Step 1 — SCENE PARSING (GPT-4o)
  GPT-4o reads your script and breaks it into structured Scene objects.
  Each scene has: title, description, narration text, duration.
  │
  ▼
Step 2 — IMAGE GENERATION (FLUX via fal.ai)
  For each scene, FLUX generates a cinematic still image
  based on the scene description.
  │
  ▼
Step 3 — VIDEO ANIMATION (Kling via fal.ai)
  Each still image is animated into a short video clip
  using Kling's image-to-video model.
  │
  ▼
Step 4 — NARRATION AUDIO (OpenAI TTS)
  Each scene's narration text is converted to speech.
  │
  ▼
Step 5 — FINAL ASSEMBLY (FFmpeg)
  All video clips and audio tracks are stitched together
  into a single MP4 saved to output/<run-id>/movie.mp4
```

---

### Setup

```bash
# Install dependencies
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env — add OPENAI_API_KEY and FAL_KEY

# Also install FFmpeg and add to PATH
# Download: https://ffmpeg.org/download.html
```

### Run

```bash
python app.py          # Gradio UI at http://localhost:7860
# or
python pipeline.py path/to/script.txt   # CLI mode
```

---

## Project Structure

```
AI Movie/
├── README.md                               ← you are here
├── CLAUDE.md                               ← AI assistant context file
├── start.bat                               ← double-click to start Biblical server
├── .env.example                            ← copy to .env, fill in keys
├── app.py                                  ← General pipeline — Gradio UI
├── pipeline.py                             ← General pipeline — orchestrator
│
├── src/
│   └── features/
│       ├── script_parser/                  ← GPT-4o scene breakdown
│       ├── image_gen/                      ← FLUX image generation
│       ├── video_gen/                      ← Kling image-to-video
│       ├── audio_gen/                      ← OpenAI TTS narration
│       └── assembler/                      ← FFmpeg final assembly
│
├── workflows/
│   └── biblical-cinematic/
│       ├── README.md                       ← detailed biblical workflow docs
│       ├── server/
│       │   ├── app.py                      ← FastAPI web server (run this)
│       │   ├── requirements.txt
│       │   └── package.json                ← enables: npm start
│       ├── text_processor/
│       │   └── biblical_text_processor_v2.py  ← KJV text cleaner
│       ├── n8n/
│       │   └── Biblical-Video-Workflow-v6.0.2.json  ← import into n8n
│       ├── templates/
│       │   └── JSON2Video-Template-FIXED.json       ← import into JSON2Video
│       └── archive/                        ← v1.0 through v6.0.1 history
│
└── output/                                 ← generated videos saved here
```
