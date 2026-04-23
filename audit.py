"""
audit.py  —  NL-Shell Audit Logger
────────────────────────────────────
Writes two files per session:

  session_<timestamp>.log     — human-readable, one block per turn
  session_<timestamp>.jsonl   — structured JSON Lines for programmatic analysis

Call audit.init() once at boot, then audit.record() after each pipeline turn.
Call audit.close() on exit to write the session summary footer.
"""

import json
import os
from datetime import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
LOG_DIR = Path("logs")

_session_id:   str  = ""
_log_path:     Path = Path()
_jsonl_path:   Path = Path()
_turn_count:   int  = 0
_session_start: datetime = datetime.utcnow()


# ── Lifecycle ─────────────────────────────────────────────────────────────────

def init() -> str:
    """
    Initialise the audit logger for a new session.
    Creates the logs/ directory if it does not exist.
    Returns the session ID string.
    """
    global _session_id, _log_path, _jsonl_path, _turn_count, _session_start

    LOG_DIR.mkdir(exist_ok=True)

    _session_start = datetime.utcnow()
    _session_id    = _session_start.strftime("session_%Y%m%d_%H%M%S")
    _log_path      = LOG_DIR / f"{_session_id}.log"
    _jsonl_path    = LOG_DIR / f"{_session_id}.jsonl"
    _turn_count    = 0

    # Write session header
    _write_log(
        "═" * 72 + "\n"
        f"  NL-SHELL  Audit Log\n"
        f"  Session   : {_session_id}\n"
        f"  Started   : {_session_start.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        f"  Log file  : {_log_path}\n"
        + "═" * 72 + "\n"
    )

    return _session_id


def record(
    user_input:  str,
    result:      dict,
    stderr:      str = "",
    healed:      bool = False,
) -> None:
    """
    Record one pipeline turn to both log files.

    Parameters
    ----------
    user_input  : The raw natural language query.
    result      : The dict returned by main.run_pipeline().
    stderr      : Any stderr captured from local execution (optional).
    healed      : True if the AI provided a self-healing suggestion this turn.
    """
    global _turn_count
    _turn_count += 1

    now       = datetime.utcnow()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    stage     = result.get("stage", "unknown")
    command   = result.get("command") or ""
    risk      = result.get("risk_level", "LOW")

    # ── Human-readable log ────────────────────────────────────────────────────
    hr_lines = [
        f"\n── Turn {_turn_count:03d}  [{timestamp}] ──────────────────────────────────\n",
        f"  INPUT    : {user_input}\n",
        f"  STAGE    : {stage}\n",
        f"  RISK     : {risk}\n",
        f"  COMMAND  : {command or '(none)'}\n",
    ]
    if result.get("warning"):
        hr_lines.append(f"  WARNING  : {result['warning']}\n")
    if stage == "blocked":
        hr_lines.append(f"  BLOCKED  : {result.get('reason', '')}\n")
    if stderr:
        hr_lines.append(f"  STDERR   : {stderr.strip()}\n")
    if healed:
        hr_lines.append(f"  HEALED   : AI provided self-healing suggestion\n")
    hr_lines.append(f"  HINT     : {result.get('next_hint', '')}\n")

    _write_log("".join(hr_lines))

    # ── Structured JSONL ──────────────────────────────────────────────────────
    record_obj = {
        "session":    _session_id,
        "turn":       _turn_count,
        "timestamp":  timestamp,
        "input":      user_input,
        "stage":      stage,
        "command":    command,
        "risk_level": risk,
        "warning":    result.get("warning"),
        "blocked_reason": result.get("reason") if stage == "blocked" else None,
        "stderr":     stderr or None,
        "healed":     healed,
        "next_hint":  result.get("next_hint", ""),
    }
    _write_jsonl(record_obj)


def close() -> None:
    """Write session summary footer."""
    end_time = datetime.utcnow()
    duration = (end_time - _session_start).seconds
    mins, secs = divmod(duration, 60)

    _write_log(
        "\n" + "═" * 72 + "\n"
        f"  SESSION CLOSED\n"
        f"  Ended     : {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        f"  Duration  : {mins}m {secs}s\n"
        f"  Turns     : {_turn_count}\n"
        + "═" * 72 + "\n"
    )


def get_log_path() -> str:
    return str(_log_path)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _write_log(text: str) -> None:
    with open(_log_path, "a", encoding="utf-8") as f:
        f.write(text)


def _write_jsonl(obj: dict) -> None:
    with open(_jsonl_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")