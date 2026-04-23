# NL-Shell — Natural Language Linux Interface

> A natural-language advisor for the Linux terminal. It suggests, explains, and guards commands — but never runs them for you.

## What is this?

NL-Shell turns plain English into Bash commands. You describe what you want — *"what's using port 8080"*, *"find all log files modified this week"* — and the tool returns the correct command, explains each flag, and warns you if it's risky.

Unlike a typical AI agent, **NL-Shell never executes commands on your behalf**. It's strictly advisory. The AI suggests, a layered safety engine gates the result, and the human makes the final call.

\---

## Key Features

* **Plain-English to Bash** via Groq's LLaMA-3.3-70B (≈1 second latency)
* **Four-tier safety classifier** — BLOCKED / HIGH / MEDIUM / LOW, backed by regex patterns
* **Random confirmation codes** for HIGH-risk commands to break user muscle memory
* **Self-healing loop** — paste a command's stderr output, the AI diagnoses and suggests a fix, with full conversation context preserved
* **Multi-turn conversations** — follow-up questions like *"now kill that process"* resolve against prior context
* **Dual-format audit logging** — every session written to both a human-readable `.log` and a machine-readable `.jsonl`
* **Cinematic CLI** — typewriter output and threaded progress bars that reflect real work, not cosmetic pauses

\---

## How it works

Every request flows through four stages:

```
  Natural language input
          │
          ▼
  ┌─────────────────┐
  │ 1. Parse        │  ai\_parser.py
  │   LLM returns   │  Groq + LLaMA-3.3-70B
  │   structured    │  System prompt forces JSON output with
  │   JSON          │  command, explanation, next\_hint, healed
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │ 2. Classify     │  safety.py
  │   Regex-based   │  Blacklist → always block
  │   tier sorting  │  Risk rules → LOW / MEDIUM / HIGH
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │ 3. Gate         │  cli.py
  │   UX scales     │  HIGH: random 6-char code required
  │   with risk     │  MEDIUM: amber warning panel
  │                 │  LOW: pass through
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │ 4. Advise       │  User sees command + explanation
  │   Never execute │  + next-step hint
  └─────────────────┘

  Optional self-heal loop:
  After a failed command, paste the stderr →
  AI diagnoses → suggests fix → marked SELF-HEALED
```

\---

## Demo

```
┌──  nl-shell · 14:22:10
└─❯ how much free disk space do I have

    SUGGESTED COMMAND
    $ df -h
        copy \& run this yourself

    EXPLANATION
        The df command reports disk space usage statistics.
        The -h flag makes the output human-readable (MB, GB, etc).
        Run this on your system to see usage by partition.

    → Check the /home partition — it's the one that fills up first.
```

For a high-risk command:

```
┌──  nl-shell · 14:23:05
└─❯ force delete everything in my downloads folder

   ╔══════════ CONFIRMATION REQUIRED ══════════╗
   ║  🔴  HIGH RISK — DESTRUCTIVE OPERATION    ║
   ║                                           ║
   ║  Recursive force-delete —                 ║
   ║  files cannot be recovered                ║
   ║                                           ║
   ║  To proceed, type the confirmation code:  ║
   ║                                           ║
   ║            A3K9QM                         ║
   ╚═══════════════════════════════════════════╝

   !!  Enter confirmation code: \_
```

\---

## Installation

### Prerequisites

* Python 3.10 or later
* A Groq API key (free tier available at [console.groq.com](https://console.groq.com))
* Linux or macOS (Windows works via WSL)

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/Xavier-Lyu2005/natural-linux.git
cd natural-linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your API key
cp .env.example .env
# Edit .env and paste your Groq API key

# 4. Run the CLI
python cli.py
```

### Alternative: Gradio Web UI

```bash
python ui.py
# Open http://localhost:7860 in your browser
```

\---

## Project structure

```
natural-linux/
├── cli.py              # Rich-based terminal interface
├── ui.py               # Gradio web interface (alternative front-end)
├── main.py             # Pipeline orchestrator (pure function, no I/O)
├── ai\_parser.py        # Groq API wrapper + prompt engineering
├── safety.py           # Regex-based risk classifier
├── audit.py            # Dual-format session logger
├── requirements.txt
├── .env.example        # Template for environment variables
└── logs/               # Generated at runtime (git-ignored)
```

Each module has one job:

|File|Responsibility|
|-|-|
|`ai\_parser.py`|Talks to Groq. Builds messages, enforces JSON output, injects stderr for self-healing.|
|`safety.py`|Pure function. Takes a command string, returns a risk classification. No side effects.|
|`audit.py`|Module-level state. Writes two log files per session.|
|`main.py`|Orchestrates the pipeline. Returns a dict — does not print, does not execute.|
|`cli.py`|Renders results to the terminal. Handles the risk gate UX and the self-heal prompt.|
|`ui.py`|Alternative front-end. Shares the same `main.run\_pipeline()` backend.|

\---

## Safety model

The classifier has four tiers. A command is checked against the blacklist first, then the risk rules (first match wins).

### BLOCKED (hard blacklist)

These commands are never shown, regardless of how they're phrased. Examples:

* `rm -rf /` variants
* `mkfs` (disk format)
* Fork bombs
* `shutdown`, `reboot`, `halt`, `poweroff`
* Overwriting `/etc/passwd`, `/etc/shadow`

### HIGH (confirmation code required)

The command is hidden until the user types a randomly-generated 6-character code. Examples:

* `rm -rf <path>`
* `chmod 777 ...`
* `crontab -r`
* `dropdb`
* Writing to `/etc/\*`

### MEDIUM (amber warning)

The command is shown with a prominent warning panel. One-click confirmation. Examples:

* `sudo ...`
* `kill -9`
* `pkill`
* `iptables`, `ufw`
* `systemctl stop`

### LOW (no friction)

Shown immediately with no warning. Covers read-only commands (`ls`, `cat`, `grep`, `ps`, `df`) and safe utilities.

\---

## Design philosophy

**Advisory, not autonomous.** Most AI tools execute commands on your behalf. NL-Shell deliberately doesn't. The AI is a teacher and an assistant; the human is the decision-maker. This trade-off — less autonomy, more trust — is the central design choice.

**Layered defense.** The AI can be fooled by a clever prompt. Regex rules can't. The safety classifier runs *after* the AI, so no matter how the model is tricked, commands still have to pass through deterministic pattern checks.

**Observability.** Every interaction is written to two log files — one for humans to read, one for programs to parse. When the backend is a non-deterministic model, being able to replay and inspect sessions isn't optional.

\---

## What we learned

* **`ai\_parser.py`** — Forcing an LLM into a strict JSON template with `response\_format` is the difference between a tool that works and one that crashes every third request. Injecting error context at runtime (via `\[STDERR]` tags) was the cleanest way to enable multi-turn diagnosis.
* **`safety.py`** — A binary allow/deny gate creates friction in all the wrong places. Grading risk into tiers lets us match friction to consequence: read-only commands pass through, destructive ones need a typed code.
* **`audit.py`** — Module-level globals beat class instances for a single-session logger. Two output formats (human + machine) cost almost nothing to maintain but pay off the first time you need to debug a session.
* **`cli.py`** — A command that appears instantly feels unsafe. Threaded progress bars with named stages give the user time to read before deciding. Pacing is a safety feature.
* **`main.py`** — Keeping the pipeline a pure function (input → dict, no print, no subprocess) meant the same backend powers both the CLI and the Gradio UI without changes.

\---

## Known limitations

* **Regex coverage isn't exhaustive.** Cleverly concatenated commands (e.g. `find -delete`) can slip through specific blacklist rules. A production version would use an AST parser like `bashlex`.
* **Conversation history grows unbounded.** Long sessions will eventually hit token limits. Needs a sliding-window or summary strategy.
* **No unit tests.** Each module has a `\_\_main\_\_` smoke test, but no pytest harness yet.
* **English-only.** The system prompt and classifier messages are English. Multilingual support would require prompt translation and locale-aware rules.

\---

## Built with

* [**Groq**](https://groq.com) — LLM inference platform, LLaMA-3.3-70B
* [**Rich**](https://github.com/Textualize/rich) — Terminal UI framework
* [**Gradio**](https://www.gradio.app/) — Optional web interface
* [**python-dotenv**](https://github.com/theskumar/python-dotenv) — Environment variable loading

\---

## Authors

* **Jiahui Lyu** — Arcadia University
* **Xiaotong Zhu**
* **Kai Chen**

Operating Systems course project, April 2026.

\---

## License

MIT — see [LICENSE](LICENSE) for details.

