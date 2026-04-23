"""
cli.py  —  NL-Shell  ·  Main Interface
────────────────────────────────────────
Run:  python cli.py

Features
  · Cinematic multi-stage progress bars (real AI call runs in parallel thread)
  · Word-by-word typewriter with punctuation-aware cadence
  · Three-tier risk system: LOW / MEDIUM / HIGH — HIGH requires confirmation code
  · Self-healing: paste a stderr error, AI diagnoses and suggests a fix
  · Multi-turn conversation history — follow-up questions work naturally
  · Audit logging: every session written to logs/session_<ts>.log + .jsonl
"""

import time
import os
import random
import threading
from datetime import datetime
from rich.console  import Console
from rich.panel    import Panel
from rich.text     import Text
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich          import box
from rich.rule     import Rule
from rich.prompt   import Prompt
import main   as engine
import audit

console = Console()

# ── Palette ───────────────────────────────────────────────────────────────────
PRIMARY = "bold #00FF9C"
ACCENT  = "#5B8CFF"
WARNING = "bold #FFB800"
DANGER  = "bold #FF3B3B"
HEAL    = "bold #C084FC"    # purple — self-healing suggestions
MUTED   = "#4A5568"
DIM     = "dim #8899AA"
WHITE   = "white"


# ══════════════════════════════════════════════════════════════════════════════
#  CINEMATIC PROGRESS BAR
#  Real AI call runs in a background thread in parallel.
#  Bar crawls through named semantic stages with micro-jitter.
#  Slows near each checkpoint — simulates real I/O wait.
# ══════════════════════════════════════════════════════════════════════════════

def cinematic_progress(stages: list, ai_thread: threading.Thread = None):
    """
    stages       : list of (label: str, target_pct: float), must end at 100
    ai_thread    : if provided, the final stage waits for the thread to finish
                   before completing — bar genuinely reflects real work.
    """
    with Progress(
        TextColumn(
            "  [bold #5B8CFF]{task.fields[stage_label]:<42}[/bold #5B8CFF]"
        ),
        BarColumn(
            bar_width      = 32,
            style          = "#0d1f0d",
            complete_style = "#00FF9C",
            finished_style = "bold #00FF9C",
        ),
        TextColumn(" [{task.percentage:>5.1f}%]", style=DIM),
        TimeElapsedColumn(),
        console   = console,
        transient = False,
    ) as bar:
        task    = bar.add_task("", total=100.0, stage_label=stages[0][0])
        current = 0.0

        for i, (label, target) in enumerate(stages):
            bar.update(task, stage_label=label)
            is_last = (i == len(stages) - 1)

            while current < target:
                # If this is the final stage and we have a thread, don't
                # advance past 95% until the thread is actually done.
                if is_last and ai_thread and ai_thread.is_alive() and current >= 94.0:
                    time.sleep(0.05)
                    continue

                step    = random.uniform(0.5, 2.2)
                current = min(current + step, target)
                bar.update(task, completed=current)
                near = (target - current) < 5
                time.sleep(
                    random.uniform(0.07, 0.16) if near
                    else random.uniform(0.022, 0.052)
                )

        bar.update(task, completed=100.0, stage_label="Done")
        time.sleep(0.12)


# ══════════════════════════════════════════════════════════════════════════════
#  CINEMATIC TYPEWRITER
#  Word-by-word, punctuation-aware pauses, ±10 ms jitter.
# ══════════════════════════════════════════════════════════════════════════════

def cinema_type(text: str, style: str = WHITE, base: float = 0.055):
    words = text.split(" ")
    for i, word in enumerate(words):
        console.print(word, style=style, end="", highlight=False)
        if i < len(words) - 1:
            console.print(" ", end="", highlight=False)

        if word.endswith((".", "!", "?")):
            pause = random.uniform(0.18, 0.28)
        elif word.endswith((",", ";", ":")):
            pause = random.uniform(0.09, 0.15)
        elif word.endswith("—"):
            pause = random.uniform(0.12, 0.20)
        else:
            lf    = min(len(word) / 8, 1.2)
            pause = base * (0.6 + lf * 0.7) + random.uniform(-0.01, 0.02)

        time.sleep(max(pause, 0.02))
    print()


def cinema_block(text: str, style: str = DIM, indent: str = "    "):
    for line in text.strip().splitlines():
        console.print(indent, end="", highlight=False)
        cinema_type(line.strip(), style=style, base=0.038)
        time.sleep(0.05)


# ══════════════════════════════════════════════════════════════════════════════
#  RISK GATE  —  confirmation code for HIGH-risk commands
# ══════════════════════════════════════════════════════════════════════════════

def risk_gate(result: dict) -> bool:
    """
    Enforces risk-based access control before showing the command.

    LOW    → pass through immediately
    MEDIUM → show warning, require [y/n] confirmation
    HIGH   → show warning, require user to TYPE the exact confirmation code

    Returns True if the user passed the gate, False if they aborted.
    """
    level = result.get("risk_level", "LOW")
    warning = result.get("warning", "")

    if level == "LOW":
        return True

    # ── MEDIUM — amber warning + one-click confirm ────────────────────────────
    if level == "MEDIUM":
        console.print()
        console.print(Panel(
            f"[{WARNING}]⚠  MEDIUM RISK[/{WARNING}]\n\n"
            f"[white]{warning}[/white]\n\n"
            f"[{MUTED}]Review the command carefully before running it on your system.[/{MUTED}]",
            border_style="#FFB800",
            box=box.HEAVY,
            title=f"[{WARNING}] RISK REVIEW REQUIRED [/{WARNING}]",
            padding=(1, 2),
        ))
        answer = Prompt.ask(
            f"\n  [{ACCENT}]?[/{ACCENT}]  Proceed and view this command",
            choices=["y", "n"],
            default="n",
        )
        console.print()
        return answer == "y"

    # ── HIGH — red panel + must type confirmation code ────────────────────────
    if level == "HIGH":
        code = result.get("confirm_code", "??????")
        console.print()
        console.print(Panel(
            f"[{DANGER}]🔴  HIGH RISK — DESTRUCTIVE OPERATION[/{DANGER}]\n\n"
            f"[white]{warning}[/white]\n\n"
            f"[{MUTED}]This command can cause irreversible damage.[/{MUTED}]\n\n"
            f"  To proceed, type the confirmation code exactly:\n\n"
            f"  [{WARNING}]  {code}  [/{WARNING}]",
            border_style="#FF3B3B",
            box=box.DOUBLE_EDGE,
            title=f"[{DANGER}] CONFIRMATION REQUIRED [/{DANGER}]",
            padding=(1, 3),
        ))
        entered = Prompt.ask(f"\n  [{DANGER}]!![/{DANGER}]  Enter confirmation code")
        console.print()
        if entered.strip().upper() == code.upper():
            console.print(f"  [{PRIMARY}]✓[/{PRIMARY}]  [{MUTED}]Code accepted. Showing command.[/{MUTED}]\n")
            return True
        else:
            console.print(
                f"  [{DANGER}]✗[/{DANGER}]  [{MUTED}]Incorrect code. Command hidden. Stay safe.[/{MUTED}]\n"
            )
            return False

    return True


# ══════════════════════════════════════════════════════════════════════════════
#  SELF-HEALING FLOW
# ══════════════════════════════════════════════════════════════════════════════

def maybe_offer_healing(result: dict, history: list) -> tuple[dict | None, list]:
    """
    After displaying a command, offer the user a chance to paste stderr output.
    If they do, trigger the self-healing pipeline and return the heal result.

    Returns (heal_result_or_None, updated_history).
    """
    console.print(
        f"  [{MUTED}]Ran the command and got an error?  "
        f"[{ACCENT}]Type 'heal'[/{ACCENT}][{MUTED}] to paste your error output.[/{MUTED}]"
    )
    trigger = Prompt.ask(
        f"[{MUTED}]└─[/{MUTED}][{PRIMARY}]❯[/{PRIMARY}]",
        default="",
    )
    console.print()

    if trigger.strip().lower() != "heal":
        return None, history

    console.print(
        f"  [{HEAL}]SELF-HEAL MODE[/{HEAL}]  "
        f"[{MUTED}]Paste your stderr output below. Enter a blank line when done.[/{MUTED}]\n"
    )

    lines = []
    while True:
        line = Prompt.ask("  ", default="__END__")
        if line == "__END__" or line.strip() == "":
            break
        lines.append(line)

    stderr_text = "\n".join(lines)
    if not stderr_text.strip():
        console.print(f"  [{MUTED}]No error provided — skipping heal.[/{MUTED}]\n")
        return None, history

    console.print()

    # Run healing pipeline with stderr injection
    result_holder = {}

    def _heal_call():
        result_holder["result"] = engine.run_heal(
            "diagnose this error and suggest a fix",
            stderr=stderr_text,
            history=history,
        )

    t = threading.Thread(target=_heal_call, daemon=True)
    t.start()

    cinematic_progress([
        ("Analysing error output …",      20),
        ("Identifying root cause …",      55),
        ("Generating fix suggestion …",   85),
        ("Self-heal ready",              100),
    ], ai_thread=t)

    t.join()
    heal = result_holder["result"]
    console.print()

    if heal and heal.get("stage") == "advisory":
        # Purple heal banner
        heal_text = Text()
        heal_text.append("  $ ", style=f"bold {HEAL}")
        heal_text.append(heal.get("command", ""), style="bold white")

        console.print(Panel(
            heal_text,
            border_style="#C084FC",
            box=box.MINIMAL_DOUBLE_HEAD,
            title=f"[{HEAL}] SELF-HEAL SUGGESTION [/{HEAL}]",
            subtitle=f"[{MUTED}] AI-diagnosed fix [/{MUTED}]",
            padding=(0, 1),
        ))
        console.print(f"\n  [{HEAL}]DIAGNOSIS[/{HEAL}]")
        cinema_block(heal.get("explanation", ""), style=DIM)

        if heal.get("next_hint"):
            console.print()
            console.print(f"  [{HEAL}]→[/{HEAL}]  ", end="", highlight=False)
            cinema_type(heal["next_hint"], style=f"italic #C084FC", base=0.05)

        console.print()

        # Append heal turn to history
        heal_history = history + [
            {"role": "user",      "content": f"[STDERR]\n{stderr_text}\n[/STDERR]"},
            {"role": "assistant", "content":
                f"Heal command: {heal.get('command', '')}\n{heal.get('explanation', '')}"},
        ]
        return heal, heal_history

    return None, history


# ══════════════════════════════════════════════════════════════════════════════
#  HISTORY MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

def history_append(history: list, user_input: str, result: dict) -> list:
    assistant_text = (
        f"Command: {result.get('command', '')}\n"
        f"{result.get('explanation', '')}"
    )
    if result.get("next_hint"):
        assistant_text += f"\nNext: {result['next_hint']}"

    return history + [
        {"role": "user",      "content": user_input},
        {"role": "assistant", "content": assistant_text},
    ]


# ══════════════════════════════════════════════════════════════════════════════
#  BOOT SEQUENCE
# ══════════════════════════════════════════════════════════════════════════════

def boot_sequence(session_id: str, log_path: str):
    os.system("cls" if os.name == "nt" else "clear")
    now = datetime.now().strftime("%Y-%m-%d  %H:%M:%S UTC")

    header = Text()
    header.append("  NL-SHELL  ", style="bold black on #00FF9C")
    header.append("  Natural Language Linux Interface", style="bold white")
    header.append(
        f"\n  v2.0.0  ·  {now}  ·  Groq / LLaMA-3.3-70B  ·  Advisory + Self-Heal",
        style=DIM,
    )
    header.append(f"\n  Session   : {session_id}  ·  Log: {log_path}", style=DIM)

    console.print(Panel(header, border_style="#00FF9C", box=box.DOUBLE_EDGE, padding=(0, 2)))
    console.print()

    cinematic_progress([
        ("Connecting to Groq API …",        22),
        ("Compiling safety ruleset …",      45),
        ("Verifying GCP instance link …",   75),
        ("Initialising audit logger …",    100),
    ])

    console.print()
    console.print(Rule(style="#4A5568"))
    console.print(
        f"  [{PRIMARY}]ALL SYSTEMS OPERATIONAL[/{PRIMARY}]"
        f"  [dim]·  Advisory Mode  ·  'heal' after a command  ·  'exit' to quit[/dim]"
    )
    console.print(Rule(style="#4A5568"))
    console.print()


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN LOOP
# ══════════════════════════════════════════════════════════════════════════════

def main():
    # Init audit logger first
    session_id = audit.init()
    log_path   = audit.get_log_path()

    boot_sequence(session_id, log_path)

    history = []

    while True:
        # ── Prompt ────────────────────────────────────────────────────────────
        turn_label = f"  [{MUTED}][{len(history)//2} turns][/{MUTED}]" if history else ""
        console.print(
            f"[{MUTED}]┌──[/{MUTED}][{PRIMARY}] nl-shell[/{PRIMARY}]"
            f"[{MUTED}] ·[/{MUTED}] [{ACCENT}]{datetime.now().strftime('%H:%M:%S')}[/{ACCENT}]"
            + turn_label
        )
        user_input = Prompt.ask(f"[{MUTED}]└─[/{MUTED}][{PRIMARY}]❯[/{PRIMARY}]")

        if user_input.lower() in ("exit", "quit"):
            audit.close()
            console.print(
                f"\n  [{DANGER}]SESSION TERMINATED[/{DANGER}]"
                f"  [{MUTED}]Log saved → {log_path}[/{MUTED}]\n"
            )
            break

        if not user_input.strip():
            continue

        console.print()

        # ── AI pipeline (parallel thread + cinematic progress) ────────────────
        result_holder = {}

        def _call():
            result_holder["r"] = engine.run_pipeline(user_input, history=history)

        t = threading.Thread(target=_call, daemon=True)
        t.start()

        cinematic_progress([
            ("Tokenising input …",         15),
            ("Inferring intent …",         48),
            ("Generating bash command …",  80),
            ("Running safety analysis …", 100),
        ], ai_thread=t)

        t.join()
        result = result_holder["r"]
        console.print()

        # ── Error states ──────────────────────────────────────────────────────
        if result["stage"] == "ai_error":
            console.print(Panel(
                f"[{DANGER}]AI ERROR[/{DANGER}]\n\n[white]{result['message']}[/white]",
                border_style="#FF3B3B", box=box.HEAVY, padding=(1, 2),
            ))
            audit.record(user_input, result)
            console.print()
            continue

        if result["stage"] == "blocked":
            console.print(Panel(
                f"[{DANGER}]RULE VIOLATION[/{DANGER}]\n\n"
                f"[white]{result['reason']}[/white]\n\n"
                f"[{MUTED}]Blocked command:[/{MUTED}] [{WARNING}]{result['command']}[/{WARNING}]",
                border_style="#FF3B3B", box=box.HEAVY,
                title="[bold #FF3B3B] BLOCKED [/bold #FF3B3B]",
                padding=(1, 2),
            ))
            audit.record(user_input, result)
            console.print()
            continue

        # ── Risk gate — may block HIGH commands behind confirmation code ───────
        passed = risk_gate(result)
        if not passed:
            audit.record(user_input, result)
            continue

        # ── Command panel ─────────────────────────────────────────────────────
        is_healed = result.get("healed", False)
        cmd_color = HEAL if is_healed else PRIMARY

        cmd_text = Text()
        if result["command"]:
            cmd_text.append("  $ ", style=f"bold {cmd_color}")
            cmd_text.append(result["command"], style="bold white")
        else:
            cmd_text.append("  (conceptual answer — see explanation below)", style=DIM)

        risk_badge = {
            "LOW":    "",
            "MEDIUM": f"  [{WARNING}]⚠  MEDIUM RISK[/{WARNING}]",
            "HIGH":   f"  [{DANGER}]🔴  HIGH RISK[/{DANGER}]",
        }.get(result.get("risk_level", "LOW"), "")

        heal_badge = f"  [{HEAL}]✦ SELF-HEALED[/{HEAL}]" if is_healed else ""

        console.print(Panel(
            cmd_text,
            border_style="#C084FC" if is_healed else "#00FF9C",
            box=box.MINIMAL_DOUBLE_HEAD,
            title=(
                f"[{HEAL}] SELF-HEAL SUGGESTION [/{HEAL}]"
                if is_healed else
                f"[{MUTED}] SUGGESTED COMMAND [/{MUTED}]"
            ),
            subtitle=f"[{MUTED}] copy & run this yourself [/{MUTED}]{risk_badge}{heal_badge}",
            padding=(0, 1),
        ))

        # ── Explanation ───────────────────────────────────────────────────────
        label = f"[{HEAL}]DIAGNOSIS[/{HEAL}]" if is_healed else f"[{ACCENT}]EXPLANATION[/{ACCENT}]"
        console.print(f"\n  {label}")
        cinema_block(result["explanation"], style=DIM)

        # ── Next hint ─────────────────────────────────────────────────────────
        if result.get("next_hint"):
            console.print()
            hint_color = f"italic #C084FC" if is_healed else f"italic {ACCENT}"
            console.print(f"  [{cmd_color}]→[/{cmd_color}]  ", end="", highlight=False)
            cinema_type(result["next_hint"], style=hint_color, base=0.05)

        console.print()

        # ── Audit record ──────────────────────────────────────────────────────
        audit.record(user_input, result, healed=is_healed)

        # ── Update conversation history ───────────────────────────────────────
        history = history_append(history, user_input, result)

        # ── Offer self-healing for errors ─────────────────────────────────────
        if result["command"]:
            heal_result, history = maybe_offer_healing(result, history)
            if heal_result:
                audit.record(
                    "[SELF-HEAL]",
                    heal_result,
                    healed=True,
                )


if __name__ == "__main__":
    main()