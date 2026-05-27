"""Modal deployment for AI Bible Gospels unified web app.

Deploy: ai-bible-gospels-2026-05-10-v4-fromCharCode
"""
import modal

app = modal.App("ai-bible-gospels")
volume = modal.Volume.from_name("ai-bible-gospels-data", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi>=0.111.0",
        "uvicorn[standard]>=0.29.0",
        "httpx>=0.27.0",
        "python-dotenv>=1.0.0",
        "requests>=2.31.0",
        "slowapi>=0.1.9",
        "supabase>=2.8.0",
        "stripe>=7.0.0",
    )
    .add_local_dir(
        "workflows/biblical-cinematic/server",
        remote_path="/app/workflows/biblical-cinematic/server",
    )
    .add_local_dir(
        "workflows/biblical-cinematic/text_processor",
        remote_path="/app/workflows/biblical-cinematic/text_processor",
    )
    .add_local_dir(
        "workflows/biblical-cinematic/assets",
        remote_path="/app/workflows/biblical-cinematic/assets",
    )
    .add_local_dir(
        "workflows/custom-script",
        remote_path="/app/workflows/custom-script",
    )
    .add_local_dir(
        "landingpage/web",
        remote_path="/app/landingpage/web",
    )
)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("ai-bible-gospels")],
    schedule=modal.Period(days=5),
)
def supabase_keepalive():
    """Ping Supabase every 5 days so the free-tier project never auto-pauses."""
    import os
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        print("[keepalive] Supabase not configured — skipping")
        return
    try:
        client = create_client(url, key)
        resp = client.table("waitlist").select("count", count="exact").limit(0).execute()
        print(f"[keepalive] OK — waitlist rows={resp.count}")
    except Exception as e:
        print(f"[keepalive] FAILED: {e}")


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("ai-bible-gospels"),
        modal.Secret.from_name("ai-bible-gospels-stripe"),
    ],
    volumes={"/data": volume},
    scaledown_window=300,
    timeout=1800,
)
@modal.asgi_app()
def web():
    import sys
    import os

    sys.path.insert(0, "/app/workflows/biblical-cinematic/server")
    sys.path.insert(0, "/app/workflows/biblical-cinematic/text_processor")
    sys.path.insert(0, "/app/workflows/custom-script")

    os.chdir("/app/workflows/biblical-cinematic/server")
    os.environ.setdefault("DEPLOYED", "true")

    from app import app as fastapi_app
    return fastapi_app
