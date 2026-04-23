"""
safety.py  —  NL-Shell Safety & Risk Classification
─────────────────────────────────────────────────────
Three-tier risk model:

  BLOCKED  — command is never shown; session is protected
  HIGH     — shown only after user types a random confirmation code
  MEDIUM   — shown with a prominent amber warning, one-click confirm
  LOW      — shown immediately, no friction
"""

import re
import random
import string

# ── Blacklist: commands that are ALWAYS blocked ───────────────────────────────
BLACKLIST = [
    (r"rm\s+.*-rf\s*/",             "rm -rf / detected — filesystem wipe blocked"),
    (r"rm\s+.*--no-preserve-root",  "--no-preserve-root flag blocked"),
    (r"\bmkfs\b",                   "mkfs detected — disk format blocked"),
    (r"dd\s+.*if=/dev/zero",        "dd zero-write — disk overwrite blocked"),
    (r"dd\s+.*if=/dev/urandom",     "dd random-write — disk overwrite blocked"),
    (r":\(\)\{.*\};",               "Fork bomb pattern detected"),
    (r">\s*/dev/sd[a-z]",           "Direct raw disk write blocked"),
    (r"chmod\s+-R\s+777\s+/",       "chmod 777 on root blocked"),
    (r"\bshutdown\b",               "shutdown command blocked"),
    (r"\breboot\b",                 "reboot command blocked"),
    (r"\bhalt\b",                   "halt command blocked"),
    (r"\bpoweroff\b",               "poweroff command blocked"),
    (r"passwd\s+root",              "root password change blocked"),
    (r">\s*/etc/passwd",            "Overwrite /etc/passwd blocked"),
    (r">\s*/etc/shadow",            "Overwrite /etc/shadow blocked"),
]

# ── Risk tiers: HIGH requires confirmation code, MEDIUM shows warning ─────────
# Each entry: (regex, risk_level, warning_message)
RISK_RULES = [
    # HIGH — destructive or privilege-escalating, require confirmation code
    (r"\brm\s+-rf\b",       "HIGH",   "Recursive force-delete — files cannot be recovered"),
    (r"\brm\s+",            "HIGH",   "File deletion — this action is permanent"),
    (r">\s*/etc/",          "HIGH",   "Overwriting a system config file"),
    (r"\bchmod\b.*777",     "HIGH",   "World-writable permission — serious security risk"),
    (r"\bcrontab\s+-r\b",   "HIGH",   "Removes all cron jobs — cannot be undone"),
    (r"\bdropdb\b",         "HIGH",   "Drops an entire database permanently"),

    # MEDIUM — elevated privileges or multi-process impact
    (r"\bsudo\b",           "MEDIUM", "Command uses sudo — elevated privileges required"),
    (r"kill\s+-9",          "MEDIUM", "SIGKILL (-9) — process will not clean up resources"),
    (r"\bpkill\b",          "MEDIUM", "pkill can affect multiple processes — verify the target"),
    (r"\biptables\b",       "MEDIUM", "Modifies firewall rules — may affect SSH access"),
    (r"\bufw\b",            "MEDIUM", "Modifies firewall rules — may affect SSH access"),
    (r"\bsystemctl\s+stop", "MEDIUM", "Stopping a system service — may affect availability"),
    (r"\bnohup\b",          "MEDIUM", "Runs process detached — remember to manage it later"),
]


def generate_code(length: int = 6) -> str:
    """Generate a random alphanumeric confirmation code."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def check(command: str) -> dict:
    """
    Analyse a command and return its safety classification.

    Returns one of:
      {
        "allowed":    False,
        "reason":     str,          # why it was blocked
        "risk_level": "BLOCKED",
      }
      {
        "allowed":    True,
        "risk_level": "HIGH" | "MEDIUM" | "LOW",
        "warning":    str | None,   # human-readable risk description
        "confirm_code": str | None, # set for HIGH — user must type this
      }
    """
    cmd_lower = command.lower()

    # 1. Hard block
    for pattern, reason in BLACKLIST:
        if re.search(pattern, cmd_lower):
            return {
                "allowed":    False,
                "reason":     reason,
                "risk_level": "BLOCKED",
            }

    # 2. Risk classification (first matching rule wins)
    for pattern, level, warning in RISK_RULES:
        if re.search(pattern, cmd_lower):
            result = {
                "allowed":      True,
                "risk_level":   level,
                "warning":      warning,
                "confirm_code": generate_code() if level == "HIGH" else None,
            }
            return result

    # 3. Safe
    return {
        "allowed":      True,
        "risk_level":   "LOW",
        "warning":      None,
        "confirm_code": None,
    }


if __name__ == "__main__":
    tests = [
        "ls -la /var/log",
        "rm -rf /tmp/test",
        "sudo systemctl restart nginx",
        "rm -rf /",
        "kill -9 1234",
        "iptables -F",
        "dropdb mydb",
    ]
    print(f"{'Command':<40}  {'Level':<8}  Detail")
    print("─" * 80)
    for t in tests:
        r = check(t)
        level = r["risk_level"]
        msg   = r.get("reason") or r.get("warning") or "safe"
        code  = f"  [code: {r['confirm_code']}]" if r.get("confirm_code") else ""
        print(f"{t:<40}  {level:<8}  {msg}{code}")