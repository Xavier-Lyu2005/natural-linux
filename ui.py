import gradio as gr
import main as engine

_pending = {"command": None, "explanation": ""}

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');

body, .gradio-container {
    background-color: #0a0a0a !important;
    color: #00ff41 !important;
    font-family: 'Share Tech Mono', monospace !important;
}

/* Title */
.prose h1 {
    color: #00ff41 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 2rem !important;
    text-shadow: 0 0 10px #00ff41 !important;
    letter-spacing: 4px !important;
    border-bottom: 1px solid rgba(0,255,65,0.3) !important;
    padding-bottom: 10px !important;
}
.prose p { color: rgba(0,255,65,0.6) !important; letter-spacing: 1px !important; }

/* All textboxes */
textarea, input[type="text"] {
    background-color: #0d0d0d !important;
    color: #00ff41 !important;
    border: 1px solid rgba(0,255,65,0.3) !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 13px !important;
}
textarea:focus, input:focus {
    border-color: #00ff41 !important;
    box-shadow: 0 0 8px rgba(0,255,65,0.3) !important;
}

/* Labels */
label span, .block label span {
    color: rgba(0,255,65,0.5) !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 11px !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
}

/* Parse button */
button.primary {
    background-color: #003b00 !important;
    color: #00ff41 !important;
    border: 1px solid #00ff41 !important;
    font-family: 'Share Tech Mono', monospace !important;
    letter-spacing: 2px !important;
    font-size: 13px !important;
    box-shadow: 0 0 10px rgba(0,255,65,0.2) !important;
}
button.primary:hover {
    background-color: #00ff41 !important;
    color: #000 !important;
    box-shadow: 0 0 20px rgba(0,255,65,0.5) !important;
}

/* Execute button */
button.stop {
    background-color: #1a0000 !important;
    color: #ff3131 !important;
    border: 1px solid #ff3131 !important;
    font-family: 'Share Tech Mono', monospace !important;
    letter-spacing: 2px !important;
    box-shadow: 0 0 8px rgba(255,49,49,0.2) !important;
}
button.stop:hover {
    background-color: #ff3131 !important;
    color: #000 !important;
}

/* Cancel button */
button.secondary {
    background-color: #0d0d0d !important;
    color: rgba(0,255,65,0.4) !important;
    border: 1px solid rgba(0,255,65,0.2) !important;
    font-family: 'Share Tech Mono', monospace !important;
    letter-spacing: 2px !important;
}

/* Block borders */
.block, .form {
    background-color: #0d0d0d !important;
    border: 1px solid rgba(0,255,65,0.15) !important;
    border-radius: 0 !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #0a0a0a; }
::-webkit-scrollbar-thumb { background: rgba(0,255,65,0.2); }
"""

def on_parse(user_input: str):
    if not user_input.strip():
        return (
            "[ERROR] Input is empty.",
            "",
            "",
            gr.update(visible=False),
            gr.update(visible=False),
        )

    result = engine.run_pipeline(user_input, confirmed=False)

    if result["stage"] == "ai_error":
        _pending["command"]     = None
        _pending["explanation"] = ""
        return (
            result["message"], "", "",
            gr.update(visible=False), gr.update(visible=False),
        )

    if result["stage"] == "blocked":
        _pending["command"]     = None
        _pending["explanation"] = ""
        return (
            f"[BLOCKED] {result['reason']}",
            f"$ {result['command']}",
            result.get("explanation", ""),
            gr.update(visible=False), gr.update(visible=False),
        )

    _pending["command"]     = result["command"]
    _pending["explanation"] = result.get("explanation", "")
    safety_msg = result.get("warning") or "[SAFE] No risks detected."
    return (
        safety_msg,
        f"$ {result['command']}",
        result.get("explanation", ""),
        gr.update(visible=True), gr.update(visible=True),
    )


def on_execute():
    if not _pending["command"]:
        return "[ERROR] No command pending."
    result = engine.run_pipeline(_pending["command"], confirmed=True)
    _pending["command"]     = None
    _pending["explanation"] = ""
    stdout = result.get("stdout", "").strip()
    stderr = result.get("stderr", "").strip()
    rc     = result.get("returncode", "?")
    parts  = []
    if stdout: parts.append(f"[STDOUT]\n{stdout}")
    if stderr: parts.append(f"[STDERR]\n{stderr}")
    parts.append(f"\n[EXIT CODE] {rc}")
    return "\n\n".join(parts)


def on_cancel():
    _pending["command"]     = None
    _pending["explanation"] = ""
    return (
        "[CANCELLED] Command discarded.", "", "",
        gr.update(visible=False), gr.update(visible=False),
    )


with gr.Blocks(title="Natural Linux") as app:

    gr.Markdown("""
# NATURAL LINUX
**Describe a Linux administration task in plain English.**
The AI generates the command and explains it — you confirm before anything runs.
""")

    with gr.Row():
        user_input = gr.Textbox(
            label="YOUR INSTRUCTION",
            placeholder='e.g.  kill whatever is running on port 80',
            lines=2,
            scale=4,
        )
        parse_btn = gr.Button("PARSE →", variant="primary", scale=1)

    with gr.Row():
        safety_out = gr.Textbox(label="SAFETY CHECK",      interactive=False, scale=1)
        cmd_out    = gr.Textbox(label="GENERATED COMMAND", interactive=False, scale=1)

    explanation_out = gr.Textbox(
        label="COMMAND EXPLANATION",
        interactive=False,
        lines=6,
    )

    with gr.Row():
        exec_btn   = gr.Button("▶  EXECUTE", variant="stop",      visible=False)
        cancel_btn = gr.Button("✕  CANCEL",  variant="secondary", visible=False)

    result_out = gr.Textbox(label="EXECUTION OUTPUT", lines=10, interactive=False)

    parse_btn.click(
        fn=on_parse,
        inputs=[user_input],
        outputs=[safety_out, cmd_out, explanation_out, exec_btn, cancel_btn],
    )
    exec_btn.click(
        fn=on_execute, inputs=[],
        outputs=[result_out],
    ).then(fn=lambda: gr.update(visible=False), outputs=[exec_btn]
    ).then(fn=lambda: gr.update(visible=False), outputs=[cancel_btn])

    cancel_btn.click(
        fn=on_cancel, inputs=[],
        outputs=[safety_out, cmd_out, explanation_out, exec_btn, cancel_btn],
    )


if __name__ == "__main__":
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        css=CSS,
    )