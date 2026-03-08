"""
upload_youtube.py — Biblical Cinematic YouTube Uploader
=======================================================
Uploads a final MP4 to YouTube as an unlisted draft.

Usage:
  python upload_youtube.py output/video_final.mp4 "Genesis 1"
  python upload_youtube.py output/video_final.mp4 "1 Kings 3" --no-thumbnail

Requirements (install once):
  pip install google-api-python-client google-auth-oauthlib Pillow

Setup (do once):
  1. Go to console.cloud.google.com → create a project
  2. Enable YouTube Data API v3
  3. Credentials → Create → OAuth 2.0 Client ID → Desktop app
  4. Download the JSON → rename to client_secrets.json
  5. Place client_secrets.json in this script's directory
  6. OAuth consent screen → add your Google account as a Test User
"""

import argparse
import re
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

SCRIPT_DIR     = Path(__file__).parent
CLIENT_SECRETS = SCRIPT_DIR / "client_secrets.json"
TOKEN_FILE     = SCRIPT_DIR / ".youtube_token.json"
ASSETS_DIR     = SCRIPT_DIR.parent / "assets"
FONT_PATH      = ASSETS_DIR / "fonts" / "Cinzel-Regular.ttf"

DESCRIPTION_TEMPLATE = """\
📖 {ref} — narrated word-for-word from the King James Bible.

A cinematic vision of Scripture brought to life through AI.
Watch. Reflect. Share the Word.

📌 Subscribe for new chapters weekly.

#{book} #KJV #Bible #BibleStudy #AIBible #Scripture #Gospel #Jesus #God #Biblical #KingJamesBible #Christianity"""


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_credentials():
    """Load saved credentials or run OAuth2 browser flow on first use."""
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRETS.exists():
                sys.exit(
                    f"\n✗ client_secrets.json not found at:\n  {CLIENT_SECRETS}\n\n"
                    "  To fix this:\n"
                    "  1. Go to console.cloud.google.com\n"
                    "  2. Enable YouTube Data API v3\n"
                    "  3. Credentials → Create → OAuth 2.0 Client ID → Desktop app\n"
                    "  4. Download JSON → rename to client_secrets.json\n"
                    "  5. Place it in this directory.\n"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return creds


# ── Parsing ───────────────────────────────────────────────────────────────────

def parse_scripture(ref: str) -> tuple:
    """'1 Kings 3' → ('1 Kings', '3') | 'Genesis 1' → ('Genesis', '1')"""
    ref = ref.strip()
    match = re.match(r"^((?:[1-3]\s)?[A-Za-z ]+?)\s+(\d+)$", ref)
    if match:
        return match.group(1).strip().title(), match.group(2)
    return ref.title(), ""


# ── Thumbnail ─────────────────────────────────────────────────────────────────

def make_thumbnail(book: str, chapter: str) -> Path:
    """Generate a 1280×720 dark thumbnail with gold scripture text."""
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), "#0a0a1a")
    draw = ImageDraw.Draw(img)

    # Subtle dark-to-slightly-lighter gradient
    for y in range(H):
        t = y / H
        draw.line(
            [(0, y), (W, y)],
            fill=(int(10 + 16 * t), int(10 + 16 * t), int(26 + 20 * t)),
        )

    # Load font (Cinzel gives a biblical/cinematic feel); fallback to default
    try:
        font_lg = ImageFont.truetype(str(FONT_PATH), 110)
        font_sm = ImageFont.truetype(str(FONT_PATH), 48)
    except Exception:
        font_lg = ImageFont.load_default()
        font_sm = font_lg

    title    = f"{book} {chapter}".strip()
    subtitle = "King James Bible"

    # Drop shadow
    for dx, dy in [(5, 5), (4, 4)]:
        draw.text(
            (W // 2 + dx, H // 2 - 50 + dy), title,
            font=font_lg, fill="#000000", anchor="mm",
        )
    # Gold title
    draw.text((W // 2, H // 2 - 50), title, font=font_lg, fill="#D4AF37", anchor="mm")
    # Cream subtitle
    draw.text((W // 2, H // 2 + 70), subtitle, font=font_sm, fill="#F5E6C8", anchor="mm")

    tmp = Path(tempfile.mktemp(suffix=".png"))
    img.save(tmp, "PNG")
    return tmp


# ── Upload ────────────────────────────────────────────────────────────────────

def upload_video(youtube, video_path: Path, book: str, chapter: str) -> str:
    """Upload the video and return the YouTube video ID."""
    ref   = f"{book} {chapter}".strip()
    title = f"{ref} | KJV Bible | AI Cinematic"

    # Strip spaces from book name for hashtag (e.g. "1 Kings" → "#1Kings")
    book_tag = book.replace(" ", "")
    description = DESCRIPTION_TEMPLATE.format(ref=ref, book=book_tag)

    tags = [
        "KJV", "Bible", "King James Bible", "Scripture", "AI Bible",
        "Biblical", "Gospel", "Jesus", "God", "Christianity", "Bible Study",
        book,
    ]

    body = {
        "snippet": {
            "title":       title,
            "description": description,
            "tags":        tags,
            "categoryId":  "29",   # Nonprofits & Activism
        },
        "status": {
            "privacyStatus":            "unlisted",
            "selfDeclaredMadeForKids":  False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=10 * 1024 * 1024,  # 10 MB chunks
    )

    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    print("  Uploading... 0%", flush=True)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"  Uploading... {pct}%", flush=True)
    print("  Uploading... 100% ✓")
    return response["id"]


def set_thumbnail(youtube, video_id: str, thumb_path: Path):
    youtube.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(str(thumb_path), mimetype="image/png"),
    ).execute()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Upload a Biblical Cinematic video to YouTube as an unlisted draft"
    )
    parser.add_argument("video",      help="Path to the final MP4 (e.g. output/video_final.mp4)")
    parser.add_argument("scripture",  help='Scripture reference (e.g. "Genesis 1" or "1 Kings 3")')
    parser.add_argument(
        "--no-thumbnail", action="store_true",
        help="Skip thumbnail generation and upload",
    )
    args = parser.parse_args()

    video_path = Path(args.video).resolve()
    if not video_path.exists():
        sys.exit(f"\n✗ Video not found: {video_path}\n")
    if video_path.suffix.lower() not in (".mp4", ".mov", ".mkv"):
        sys.exit(f"\n✗ Unsupported file type: {video_path.suffix}\n")

    book, chapter = parse_scripture(args.scripture)
    ref = f"{book} {chapter}".strip()

    print("\nBiblical Cinematic — YouTube Upload")
    print("=====================================")
    print(f"  Scripture: {ref}")
    print(f"  Video:     {video_path.name}  ({video_path.stat().st_size / 1e6:.1f} MB)")
    print(f"  Title:     {ref} | KJV Bible | AI Cinematic")
    print(f"  Status:    unlisted  (publish from YouTube Studio when ready)\n")

    creds   = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    video_id = upload_video(youtube, video_path, book, chapter)

    print(f"\n  ✓ Video:   https://youtu.be/{video_id}")
    print(f"  ✓ Studio:  https://studio.youtube.com/video/{video_id}/edit\n")

    if not args.no_thumbnail:
        print("  → Generating thumbnail...")
        thumb = make_thumbnail(book, chapter)
        try:
            set_thumbnail(youtube, video_id, thumb)
            print("  ✓ Thumbnail set\n")
        except Exception as e:
            print(f"  ⚠ Thumbnail failed (video still uploaded): {e}\n")
        finally:
            thumb.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
