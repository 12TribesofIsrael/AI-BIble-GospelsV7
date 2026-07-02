# Post-Production — Drop & Run

Drop a raw video in **this folder**, run one command, and get a finished video
with your branded intro + outro and a logo watermark.

```
[ intro ]  →  [ your video + logo ]  →  [ outro ]
```

The intro and outro both come from a single saved brand clip
(`workflows/biblical-cinematic/assets/intro_outro.mp4`), split at a timecode.

---

## How to run

1. **Drop your raw video** (`.mp4`) into this folder.
2. From the project root, run:

   ```bash
   python workflows/biblical-cinematic/scripts/post_produce.py
   ```

   With no arguments it auto-picks the **newest** video in this folder.

3. The finished file lands in **`output/<video-name>_final.mp4`**.

That's it.

---

## What it does automatically

- **Intro/outro** — pulled from `assets/intro_outro.mp4`, split at **26 seconds**
  (everything before 26s = intro, everything after = outro).
- **Logo** — watermarks the **main video only** (the brand clip is already
  branded, so it isn't watermarked again — no double logo).
- **Resolution** — matches your source video (won't upscale a 720p render).
- **Audio** — if a clip has no audio track, a silent one is added so the
  join stays in sync.

---

## Options (only if you need them)

| Command | What it does |
|---|---|
| `... post_produce.py "path/to/video.mp4"` | Use a specific file instead of auto-pick |
| `... post_produce.py --split 30` | Move the intro/outro seam to 30s |
| `... post_produce.py --width 1920` | Force 1080p output (default = match source) |
| `... post_produce.py --no-logo` | Skip the logo watermark |

---

## Changing the intro/outro branding

Replace this one file:

```
workflows/biblical-cinematic/assets/intro_outro.mp4
```

It's a single clip with the intro at the front and the outro at the back.
If your new clip's intro is a different length, pass the new seam with
`--split <seconds>`.

---

## Requirements

- **FFmpeg + ffprobe** installed and on your PATH
  (https://ffmpeg.org/download.html)
- `assets/intro_outro.mp4` (brand clip) and `assets/logo1.png` (watermark)
  — already in place.
