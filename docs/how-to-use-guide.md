# Biblical Cinematic Generator - How to Use Guide

**A step-by-step instruction manual for making Bible videos with AI.**

> This guide is written so that anyone can follow along, even if you've never made a video before. Just follow the steps one at a time!

---

## What This App Does

This app takes Bible scripture (like Genesis 1 or Psalm 23) and turns it into a **cinematic video** with:
- Beautiful AI-generated images for each scene
- Smooth camera motion and animation
- A professional voice reading the narration
- Background music, intro, outro, and a logo watermark

**Total time from start to finish: about 25-35 minutes** (most of that is waiting for the AI to work).

**See the overview diagram:** [pipeline-overview.png](pipeline-overview.png) (or open [pipeline-overview.excalidraw](pipeline-overview.excalidraw) in Excalidraw)

---

## Before You Start (One-Time Setup)

You only need to do these things **once**, the very first time:

### 1. Start the server
1. Open a terminal (Command Prompt or PowerShell)
2. Type this command and press Enter:
   ```
   cd C:\Users\Tommy\V7AIBible\workflows\biblical-cinematic\server
   python app.py
   ```
3. You should see a message that says the server is running
4. **Leave this terminal window open** - don't close it!

### 2. Make sure n8n is running
- The n8n workflow must be **Active/Published** (the toggle in n8n should be ON)
- If n8n is not running, the video generation won't work

### 3. Open the app in your web browser
- Open **Google Chrome** (or any browser)
- Go to: **http://localhost:8000**
- You should see a dark-themed page that says **"Biblical Cinematic Generator"** at the top

---

## STEP 1: Paste Your Scripture (~1 minute)

This is where you tell the app which Bible chapter you want to turn into a video.

### Option A: Use the Bible Selector (Easiest)

1. **Click the little arrow** next to "Select from Bible (81 books, KJV + Apocrypha)" to expand the selector
2. **Pick a book** from the first dropdown menu
   - The books are organized into 3 groups: Old Testament, Apocrypha, and New Testament
   - Example: Click the dropdown and scroll to find "Genesis"
3. **Pick a chapter** from the second dropdown menu
   - The chapters will show up automatically based on which book you picked
   - Example: Select "1" for Chapter 1
4. **Click the amber "Load Chapter" button**
   - The scripture text will appear in the big text box below
   - You'll see a status message confirming it loaded

### Option B: Paste Text Manually

1. **Copy** your KJV scripture text from wherever you have it (a website, a document, etc.)
2. **Click inside the big text box** that says "Select a chapter above, or paste your KJV scripture here..."
3. **Paste** the text (Ctrl+V on your keyboard)

### What you should see:
- The text box is filled with your Bible scripture
- Below the text box, you'll see a **word and character count** (like "523 words, 2,841 characters")

### Click "Convert & Clean"

1. **Click the amber "Convert & Clean" button** below the text box
2. Wait a moment - you'll see a spinner and "Cleaning..." text
3. The app will clean up the text and take you to Step 2

> **What does "cleaning" mean?** The app removes verse numbers, fixes formatting, and splits long chapters into sections so the video isn't too long.

---

## STEP 2: Review & Pick Your AI Model (~1 minute)

Now you can review the cleaned text and choose which AI model will animate your video.

### Review the Cleaned Text

1. **Read through the text** in the text box
   - The text has been cleaned up - verse numbers are removed, formatting is nice
2. **You can edit the text** if you want!
   - Click inside the text box and type to make changes
   - This is optional - you don't have to change anything

### If Your Chapter Was Split Into Sections

- If the chapter was long, it gets split into sections (each section becomes one video)
- You'll see **tabs at the top** like "Section 1", "Section 2", etc.
- Click a tab to switch between sections
- Each section shows stats: word count, estimated video length, and number of scenes

### Choose Your AI Model

Below the text box, you'll see **3 options** for the AI video model:

| Model | What It Does | Cost | Speed |
|-------|-------------|------|-------|
| **v1.6 Standard** | Basic motion, simplest animations | ~$4.50 | Fastest |
| **v2.1 Standard** | Better motion, smoother animations | ~$5.50 | Medium |
| **v3.0 Standard** | Best quality, most detailed motion | ~$7.00 | Slowest |

- **Click on the one you want** - a golden border will appear around your choice
- If you're not sure, **v1.6 Standard** is a good starting choice (cheapest and fastest)

### Click "Approve & Generate Video"

1. **Click the green "Approve & Generate Video" button**
2. Wait a moment - you'll see "Sending to n8n..."
3. The app will send your text to the AI pipeline and take you to Step 3

---

## STEP 3: Wait While AI Makes Your Video (~15-25 minutes)

This is the longest step. The AI is doing all the hard work! You just need to wait.

### What You'll See

- A **progress bar** (amber/gold colored) that fills up as the AI works
- A **percentage** showing how far along it is (like "42%")
- A **timer** showing how long it's been running (like "5:23")
- A **green "Live" badge** means the app is checking progress in real-time
- A **stage label** telling you what the AI is currently doing

### The AI Pipeline (What's Happening Behind the Scenes)

The progress bar tracks 3 main stages:

#### Stage 1: Perplexity AI (0% - 10%)
- **What it does:** Reads your scripture and writes 20 cinematic scene descriptions
- **Example:** For "In the beginning God created the heaven and the earth," it might write: *"A vast cosmic void transforms as brilliant light erupts across infinite darkness, with swirling nebulae and forming galaxies..."*
- **Time:** About 1-2 minutes

#### Stage 2: fal.ai Image + Video Generation (10% - 85%)
- **What it does:** For each of the 20 scenes:
  1. **FLUX** draws a beautiful HD image from the scene description
  2. **Kling AI** animates that image into a 5-second video clip with camera motion
- You'll see progress like "fal.ai: generating scene 7/20..."
- **Time:** About 10-20 minutes (this is the longest part)

#### Stage 3: JSON2Video Assembly (85% - 100%)
- **What it does:** Takes all 20 video clips + the narration audio and combines them into one final video
- Also adds the text overlays and timing
- **Time:** About 3-5 minutes

### The Step Checklist

Below the progress bar, you'll see checkmarks appear:
- ✓ Text cleaned and processed
- ✓ Sent to n8n workflow
- (spinner) Perplexity AI generating 20 scenes...
- (spinner) fal.ai generating FLUX images + Kling video clips...
- (spinner) JSON2Video assembling final video...

Each spinner turns into a ✓ checkmark when that step is done.

### When It's Done

1. The progress bar hits **100%**
2. The title changes to **"Your Video Is Ready"** with a green checkmark
3. A **green panel** appears that says "Your video is ready!"
4. A **"Download Video" button** appears

### Click "Download Video"

1. **Click the green "Download Video" button**
2. Your browser will download an MP4 file
3. **Save it to this folder:** `C:\Users\Tommy\V7AIBible\output\raw\`
   - This is important for Step 4!

> **Tip:** You can open the video file to watch it, but we still need to add the intro, outro, and logo in Step 4.

---

## STEP 4: Post-Production (~5 minutes)

This step adds the professional finishing touches to your video: an intro, outro, and logo watermark.

### Before You Start

- Make sure you saved the downloaded video to `output\raw\` (from Step 3)
- Scroll down on the web page to find the **purple "Step 4 - Post-Production"** section

### Find Your Video

1. **Click the ↺ Refresh button** (the circular arrow next to the file status badge)
2. The badge should turn **green** and say something like "1 raw video(s) ready"
3. If you have multiple videos, use the dropdown to select the one you want

> **If the badge says "No raw video found":** Make sure you saved the MP4 file to the `output\raw\` folder, then click ↺ Refresh again.

### Start Rendering

1. **Click the purple "Start Rendering" button**
2. A purple progress bar will appear showing 3 stages:
   - **Normalizing segments** - makes sure all video parts have the same format (fps, audio, etc.)
   - **Concatenating** - joins intro + your video + outro together
   - **Overlaying logo** - adds the logo watermark on top
3. Wait for each stage to complete (each gets a ✓ checkmark)

### When It's Done

1. The progress bar hits **100%**
2. A **purple panel** appears that says "Post-production complete!"
3. A **"Download Final Video" button** appears

### Click "Download Final Video"

1. **Click the purple "Download Final Video" button**
2. Your browser will download the finished MP4 with intro, outro, and logo
3. This is your **finished video** - ready for YouTube!

---

## STEP 5: Upload to YouTube (~2 minutes)

This step uploads your finished video directly to YouTube as an **unlisted draft**. You can review it in YouTube Studio before making it public.

### Before You Start

- Make sure you completed Step 4 (Post-Production)
- Scroll down on the web page to find the **red "Step 5 - Upload to YouTube"** section

### Find Your Video

1. **Click the ↺ Refresh button** next to the file status badge
2. The badge should turn **green** and say something like "1 video(s) ready"
3. If you have multiple final videos, use the dropdown to select the right one

### Enter the Scripture Reference

1. **Click inside the text box** that says "e.g. Matthew 10 or 1 Kings 3"
2. **Type the name of the Bible chapter** your video is about
   - Examples: `Genesis 1`, `Psalm 23`, `Matthew 5`, `1 Kings 3`
   - This is used to create the video title, tags, and thumbnail

### Upload

1. **Click the red "Upload to YouTube" button**
2. A red progress bar will appear showing 2 stages:
   - **Uploading video to YouTube** - sends the video file
   - **Generating & setting thumbnail** - creates and sets a custom thumbnail
3. Wait for both stages to complete

### First Time Only: Google Sign-In

- The **very first time** you upload, your browser will open a Google sign-in page
- Sign in with your YouTube/Google account
- Give permission for the app to upload videos
- After this first time, it won't ask again

### When It's Done

1. A **red panel** appears that says "Uploaded as unlisted draft!"
2. Two buttons appear:
   - **"View on YouTube"** - opens your video on YouTube
   - **"Edit in YouTube Studio"** - opens the video in YouTube's editing dashboard

### What to Do in YouTube Studio

1. **Click "Edit in YouTube Studio"**
2. Review your video - make sure it looks good
3. Add or edit the **description** if you want
4. Change the visibility from **Unlisted** to **Public** when you're ready to publish
5. That's it - your Bible video is live!

---

## Quick Reference Card

| Step | What You Do | Button to Click | Time |
|------|------------|----------------|------|
| 1 | Pick a Bible chapter or paste text | **Convert & Clean** (amber) | ~1 min |
| 2 | Review text + pick AI model | **Approve & Generate Video** (green) | ~1 min |
| 3 | Wait for AI to finish | **Download Video** (green) | ~15-25 min |
| 4 | Save to `output\raw\`, click Refresh, Render | **Download Final Video** (purple) | ~5 min |
| 5 | Type scripture name, upload | **Upload to YouTube** (red) | ~2 min |

---

## Troubleshooting (If Something Goes Wrong)

### "No raw video found" in Step 4
- **Fix:** Make sure you saved the downloaded MP4 into the `output\raw\` folder, then click the ↺ Refresh button

### "No final video found" in Step 5
- **Fix:** You need to complete Step 4 (Post-Production) first. The final video will appear after rendering.

### The progress bar is stuck / not moving
- **Check:** Is the green "Live" badge showing? If it says "Estimated" in gray, the app might not have an API key to check progress. Just wait - it's probably still working.
- **If it's been more than 30 minutes:** Something may have gone wrong in n8n. Check the n8n workflow for errors.

### Error message appears (red text)
- **Read the error message** - it usually tells you what went wrong
- **Common causes:**
  - n8n workflow is not active/published
  - Server was restarted during generation
  - API key expired or missing

### The server won't start
- **Make sure Python is installed** and you're in the right folder
- **Run:** `pip install -r requirements.txt` first
- **Check:** Is another server already running on port 8000? Close it first.

### Video quality doesn't look good
- **Try a better model:** Go back to Step 2 and choose v2.1 or v3.0 instead of v1.6
- **Note:** Better models cost more and take longer, but produce better animations

---

## Glossary (What These Words Mean)

| Word | What It Means |
|------|--------------|
| **KJV** | King James Version - a classic English translation of the Bible |
| **Perplexity AI** | An AI that reads your text and writes creative scene descriptions |
| **FLUX** | An AI that draws pictures from text descriptions |
| **Kling AI** | An AI that takes a still picture and makes it move (like a short video clip) |
| **ElevenLabs** | An AI that reads text out loud with a human-sounding voice |
| **JSON2Video** | A service that takes all the clips and assembles them into one video |
| **n8n** | The automation tool that connects all the AI services together |
| **Post-Production** | Adding finishing touches (intro, outro, logo) to a raw video |
| **Unlisted** | A YouTube setting where only people with the link can see your video |
| **YouTube Studio** | YouTube's dashboard where you manage and edit your videos |
| **FFmpeg** | A tool that edits and combines video files (runs in the background) |
| **Webhook** | A special URL that triggers the video-making process |

---

## Cost Per Video

| AI Model | Cost | Best For |
|----------|------|----------|
| Kling v1.6 | ~$4.50 | Quick drafts, testing |
| Kling v2.1 | ~$5.50 | Good quality, everyday use |
| Kling v3.0 | ~$7.00 | Best quality, final videos |

The cost comes from the AI services (Perplexity, FLUX, Kling, ElevenLabs, JSON2Video). Each video uses about 20 AI-generated images and 20 animated video clips.
