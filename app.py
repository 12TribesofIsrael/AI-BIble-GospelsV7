import gradio as gr
from dotenv import load_dotenv

load_dotenv()

from pipeline import run_pipeline  # noqa: E402 (must load env first)


def generate_movie(script_text: str, progress=gr.Progress(track_tqdm=True)):
    if not script_text.strip():
        return None, "Please enter a script or story."

    log_lines: list[str] = []

    def log(msg: str) -> None:
        log_lines.append(msg)
        progress(0, desc=msg)

    try:
        output_path = run_pipeline(script_text, progress=log)
        return str(output_path), "\n".join(log_lines)
    except Exception as exc:
        log_lines.append(f"\nERROR: {exc}")
        return None, "\n".join(log_lines)


with gr.Blocks(title="AI Movie Generator", theme=gr.themes.Soft()) as app:
    gr.Markdown("# AI Movie Generator")
    gr.Markdown(
        "Enter a script, story, or simple prompt. The AI will break it into scenes, "
        "generate images, animate them, add narration, and assemble a final movie."
    )

    with gr.Row():
        with gr.Column(scale=1):
            script_input = gr.Textbox(
                label="Script / Story / Prompt",
                placeholder=(
                    "Example:\n\n"
                    "A lone astronaut discovers an ancient alien structure on Mars. "
                    "She enters cautiously, torch in hand, as glowing symbols illuminate the walls..."
                ),
                lines=16,
            )
            generate_btn = gr.Button("Generate Movie", variant="primary", size="lg")

        with gr.Column(scale=1):
            video_output = gr.Video(label="Generated Movie")
            log_output = gr.Textbox(
                label="Progress",
                lines=10,
                interactive=False,
                show_copy_button=True,
            )

    generate_btn.click(
        fn=generate_movie,
        inputs=[script_input],
        outputs=[video_output, log_output],
    )

if __name__ == "__main__":
    app.launch()
