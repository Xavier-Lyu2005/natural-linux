"""
main.py  —  NL-Shell Pipeline Orchestrator
────────────────────────────────────────────
Pipeline stages:

  NL input
    → ai_parser  (LLM generates command + explanation)
    → safety     (classify risk: LOW / MEDIUM / HIGH / BLOCKED)
    → advisory   (return to CLI — user decides whether to run)

  Optional self-healing mode (called from CLI after user runs a command):
    → run_heal(user_input, stderr, history)
      passes stderr back to AI for diagnosis + fix suggestion
"""

import subprocess
import ai_parser
import safety as safety_module


# ── Advisory pipeline ─────────────────────────────────────────────────────────

def run_pipeline(user_input: str, history: list = None) -> dict:
    """
    Main advisory pipeline.
    Never executes anything — returns command + explanation for the user to run.

    Returns dict with 'stage':
      'ai_error'  — LLM call failed
      'blocked'   — safety hard-block
      'advisory'  — normal result ready for display
    """
    parsed      = ai_parser.parse(user_input, history=history)
    command     = parsed["command"]
    explanation = parsed["explanation"]
    next_hint   = parsed["next_hint"]

    if command.startswith("ERROR:"):
        return {
            "stage":   "ai_error",
            "message": command,
            "command": None,
        }

    safety_result = safety_module.check(command) if command else {
        "allowed": True, "risk_level": "LOW", "warning": None, "confirm_code": None
    }

    if not safety_result["allowed"]:
        return {
            "stage":       "blocked",
            "command":     command,
            "explanation": explanation,
            "reason":      safety_result["reason"],
            "risk_level":  "BLOCKED",
        }

    return {
        "stage":        "advisory",
        "command":      command,
        "explanation":  explanation,
        "next_hint":    next_hint,
        "risk_level":   safety_result["risk_level"],
        "warning":      safety_result.get("warning"),
        "confirm_code": safety_result.get("confirm_code"),
        "healed":       parsed.get("healed", False),
    }


# ── Self-healing pipeline ─────────────────────────────────────────────────────

def run_heal(user_input: str, stderr: str, history: list = None) -> dict:
    """
    Called when the user reports that a command produced an error.
    Injects the stderr into the AI call so it can diagnose and suggest a fix.

    Returns the same dict shape as run_pipeline() with healed=True.
    """
    parsed      = ai_parser.parse(user_input, history=history, stderr=stderr)
    command     = parsed["command"]
    explanation = parsed["explanation"]
    next_hint   = parsed["next_hint"]

    if command.startswith("ERROR:"):
        return {
            "stage":   "ai_error",
            "message": command,
            "command": None,
        }

    safety_result = safety_module.check(command) if command else {
        "allowed": True, "risk_level": "LOW", "warning": None, "confirm_code": None
    }

    if not safety_result["allowed"]:
        return {
            "stage":       "blocked",
            "command":     command,
            "explanation": explanation,
            "reason":      safety_result["reason"],
            "risk_level":  "BLOCKED",
        }

    return {
        "stage":        "advisory",
        "command":      command,
        "explanation":  explanation,
        "next_hint":    next_hint,
        "risk_level":   safety_result["risk_level"],
        "warning":      safety_result.get("warning"),
        "confirm_code": safety_result.get("confirm_code"),
        "healed":       True,
    }


# ── Local execution helper (used only for self-healing demo) ──────────────────

def execute_local(command: str, timeout: int = 30) -> dict:
    """
    Runs a command locally and returns stdout/stderr/returncode.
    Used when the user opts to test a command and wants AI feedback on errors.
    """
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return {
            "stdout":     result.stdout,
            "stderr":     result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "ERROR: Command timed out.", "returncode": -1}
    except Exception as e:
        return {"stdout": "", "stderr": f"ERROR: {e}", "returncode": -1}