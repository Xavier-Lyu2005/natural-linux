"""
ai_parser.py  —  NL-Shell AI Backend
──────────────────────────────────────
Wraps the Groq API (LLaMA-3.3-70B).
Supports multi-turn conversation history and stderr self-healing injection.
"""

import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """You are an expert Linux system administrator and deployment guide.
Your role is to EDUCATE and ADVISE. You help users understand Linux commands and
guide them step-by-step through deployments and troubleshooting.
Always respond with valid JSON only. No markdown, no backticks, no extra text.

Use this exact JSON format:
{
  "command": "<single executable bash command, or empty string if not applicable>",
  "explanation": "<clear explanation of what this command does and WHY, with each flag on its own line>",
  "next_hint": "<one sentence guiding the user to their next logical step>",
  "healed": false
}

Rules:
- command: raw bash command only, no backticks. Empty string for conceptual questions.
- explanation: educational — assume the user wants to understand, not just copy-paste.
- next_hint: proactively guide the user forward.
- healed: set to true ONLY when you are responding to a stderr error and suggesting a fix.
- All text must be in English.
- Dangerous or impossible requests: set command to ERROR: <reason>
- For follow-up questions, use conversation history to give contextually accurate answers.

SELF-HEALING RULE:
If the user message contains a block like:
  [STDERR] <error text>
You must:
  1. Diagnose what went wrong based on the error text.
  2. Suggest the correct fix — either an alternative command or an install command.
  3. Set "healed" to true in your response.
  4. Make the explanation focus on WHY the original failed and what the fix does.
"""


def parse(user_input: str, history: list = None, stderr: str = "") -> dict:
    """
    Parameters
    ----------
    user_input : str
        The user's natural language query.
    history : list, optional
        Prior turns as {"role": "user"|"assistant", "content": str} dicts.
    stderr : str, optional
        Stderr output from the previous command execution.
        If non-empty, it is injected into the user message so the AI can self-heal.

    Returns dict with keys: command, explanation, next_hint, healed
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if history:
        messages.extend(history)

    # Inject stderr for self-healing
    if stderr and stderr.strip():
        augmented_input = (
            f"{user_input}\n\n"
            f"[STDERR]\n{stderr.strip()}\n"
            f"[/STDERR]\n\n"
            f"The command produced the above error. Please diagnose and suggest a fix."
        )
    else:
        augmented_input = user_input

    messages.append({"role": "user", "content": augmented_input})

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.0,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)

        return {
            "command":     result.get("command",     ""),
            "explanation": result.get("explanation", "No explanation provided."),
            "next_hint":   result.get("next_hint",   ""),
            "healed":      bool(result.get("healed", False)),
        }

    except json.JSONDecodeError:
        return {"command": "ERROR: Invalid JSON from model", "explanation": "",
                "next_hint": "", "healed": False}
    except Exception as e:
        return {"command": f"ERROR: {e}", "explanation": "",
                "next_hint": "", "healed": False}


if __name__ == "__main__":
    # Quick smoke test — no API key needed to import
    test = "show me which process is using port 80"
    print(f"Testing parse() with: {test!r}")
    result = parse(test)
    print(f"Command    : {result['command']}")
    print(f"Explanation:\n{result['explanation']}")
    print(f"Next Hint  : {result['next_hint']}")
    print(f"Healed     : {result['healed']}")