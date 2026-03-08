ASSETS FOLDER
=============

Required files for post-production scripts:

  logo1.png
    Your "AI Bible Gospels" logo — PNG with transparent background.
    Export from Canva: Share → Download → PNG → check "Transparent background"

  Into.mp4
    Intro clip — plays before the main video.

  outro_1.mp4
  outro_2.mp4
  outro_3.mp4
    Outro clips — stitched in order (1 → 2 → 3) after the main video.

  *.mp3 / *.wav
    Background music tracks — drop any number of files here.
    The script will list them by number so you pick one each run.

USAGE
-----
From the project root:

  # Single video:
  python workflows/biblical-cinematic/scripts/post_produce.py output/raw/your-video.mp4

  # All videos in output/raw/ at once:
  python workflows/biblical-cinematic/scripts/batch_post_produce.py

Output saved to: output/{video-name}_final.mp4
