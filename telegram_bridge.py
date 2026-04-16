"""
telegram_bridge.py
──────────────────
Secure Telegram → OpenManus control bridge for Apple Silicon Mac.

Security model
  - ALLOWED_CHAT_ID loaded from .env
  - Every handler verifies update.effective_user.id before acting
  - Unrecognised users are silently ignored

Usage
  source .venv/bin/activate
  python telegram_bridge.py
"""

import asyncio
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

import psutil
from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────────

BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
_raw_id: str = os.getenv("ALLOWED_CHAT_ID", "0")
ALLOWED_CHAT_ID: int = int(_raw_id) if _raw_id.lstrip("-").isdigit() else 0
OPENMANUS_DIR: Path = Path(__file__).parent.resolve()

# How often (seconds) the progress message is edited while OpenManus runs
_EDIT_INTERVAL: float = 8.0
# Max output lines shown per progress update
_TAIL: int = 15

# ── Hardcoded prompts ──────────────────────────────────────────────────────────

EPOXY_PROMPT = (
    "Search for epoxy flooring contractors and companies in South Carolina. "
    "Use Google, Yelp, Angi, HomeAdvisor, the BBB website, and local business "
    "directories. For each result extract: business name, phone number, website "
    "URL, city, and any visible email address. Compile all results into a clean "
    "numbered list. Aim for at least 30 unique leads."
)

# ── Keyboard ───────────────────────────────────────────────────────────────────

MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        ["🤖 Custom Prompt", "🏢 Scrape Epoxy Leads"],
        ["📸 Mac Screenshot", "📊 System Status"],
        ["🛑 Kill Tasks"],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

# ── Mutable state ──────────────────────────────────────────────────────────────

_active_proc: Optional[asyncio.subprocess.Process] = None
_awaiting_prompt: set[int] = set()

# ── Auth ───────────────────────────────────────────────────────────────────────


def _authorized(update: Update) -> bool:
    return (
        update.effective_user is not None
        and update.effective_user.id == ALLOWED_CHAT_ID
    )


# ══════════════════════════════════════════════════════════════════════════════
# /start
# ══════════════════════════════════════════════════════════════════════════════


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return
    await update.message.reply_text(
        "👋 *OpenManus Bridge online.*\n\nPick an action from the menu.",
        parse_mode="Markdown",
        reply_markup=MAIN_KB,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Message router
# ══════════════════════════════════════════════════════════════════════════════


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return

    text = (update.message.text or "").strip()
    uid = update.effective_user.id

    match text:
        case "🤖 Custom Prompt":
            _awaiting_prompt.add(uid)
            await update.message.reply_text(
                "✏️ Type your OpenManus prompt and send it:",
                reply_markup=MAIN_KB,
            )

        case "🏢 Scrape Epoxy Leads":
            await update.message.reply_text(
                "🏢 Starting South Carolina epoxy lead scrape…",
                reply_markup=MAIN_KB,
            )
            await _run_manus(update, EPOXY_PROMPT)

        case "📸 Mac Screenshot":
            await _screenshot(update)

        case "📊 System Status":
            await _system_status(update)

        case "🛑 Kill Tasks":
            await _kill_tasks(update)

        case _:
            if uid in _awaiting_prompt:
                _awaiting_prompt.discard(uid)
                preview = text[:120] + ("…" if len(text) > 120 else "")
                await update.message.reply_text(
                    f"🤖 Running prompt:\n_{preview}_",
                    parse_mode="Markdown",
                    reply_markup=MAIN_KB,
                )
                await _run_manus(update, text)
            else:
                await update.message.reply_text(
                    "Use the menu below, or tap *🤖 Custom Prompt* first.",
                    parse_mode="Markdown",
                    reply_markup=MAIN_KB,
                )


# ══════════════════════════════════════════════════════════════════════════════
# OpenManus subprocess runner
# ══════════════════════════════════════════════════════════════════════════════


async def _run_manus(update: Update, prompt: str) -> None:
    """
    Launches `python main.py --prompt <prompt>` as a subprocess,
    streams its stdout/stderr, and edits a single Telegram message
    with rolling progress updates every _EDIT_INTERVAL seconds.
    """
    global _active_proc

    status_msg = await update.message.reply_text(
        "⚙️ *Launching OpenManus…*", parse_mode="Markdown"
    )

    env = {**os.environ, "PYTHONUNBUFFERED": "1"}

    try:
        # args passed as list → no shell injection risk even with special chars
        _active_proc = await asyncio.create_subprocess_exec(
            sys.executable,
            str(OPENMANUS_DIR / "main.py"),
            "--prompt",
            prompt,
            cwd=str(OPENMANUS_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )

        lines: list[str] = []
        last_edit = time.monotonic()

        async for raw in _active_proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            if line:
                lines.append(line)

            if time.monotonic() - last_edit >= _EDIT_INTERVAL and lines:
                snippet = "\n".join(lines[-_TAIL:])
                try:
                    await status_msg.edit_text(
                        f"⚙️ *OpenManus running…*\n```\n{snippet}\n```",
                        parse_mode="Markdown",
                    )
                except Exception:
                    # Telegram rejects edits when text is unchanged; ignore
                    pass
                last_edit = time.monotonic()

        await _active_proc.wait()
        rc = _active_proc.returncode
        icon = "✅" if rc == 0 else "⚠️"
        tail = "\n".join(lines[-_TAIL:]) if lines else "(no output captured)"
        await status_msg.edit_text(
            f"{icon} *OpenManus finished* (exit {rc})\n```\n{tail}\n```",
            parse_mode="Markdown",
        )

    except Exception as exc:
        await status_msg.edit_text(
            f"❌ Failed to launch OpenManus:\n`{exc}`", parse_mode="Markdown"
        )
    finally:
        _active_proc = None


# ══════════════════════════════════════════════════════════════════════════════
# Mac Screenshot  (macOS screencapture)
# ══════════════════════════════════════════════════════════════════════════════


async def _screenshot(update: Update) -> None:
    await update.effective_chat.send_action(ChatAction.UPLOAD_PHOTO)

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    path = Path(tmp.name)

    try:
        result = subprocess.run(
            ["screencapture", "-x", str(path)],  # -x = no shutter sound
            capture_output=True,
            timeout=20,
        )
        if result.returncode != 0 or path.stat().st_size == 0:
            await update.message.reply_text(
                "❌ `screencapture` failed.\n\n"
                "Grant *Screen Recording* permission to Terminal / iTerm2 in:\n"
                "System Settings → Privacy & Security → Screen Recording",
                parse_mode="Markdown",
            )
            return

        with path.open("rb") as fh:
            await update.message.reply_photo(
                photo=fh,
                caption=f"📸 {time.strftime('%Y-%m-%d  %H:%M:%S')}",
            )

    except FileNotFoundError:
        await update.message.reply_text(
            "❌ `screencapture` not found — this feature requires macOS.",
            parse_mode="Markdown",
        )
    except subprocess.TimeoutExpired:
        await update.message.reply_text("❌ Screenshot timed out (>20 s).")
    finally:
        path.unlink(missing_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# System Status  (psutil)
# ══════════════════════════════════════════════════════════════════════════════


def _find_procs(keywords: set[str]) -> list[psutil.Process]:
    found: list[psutil.Process] = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = (proc.info["name"] or "").lower()
            cmd = " ".join(proc.info.get("cmdline") or []).lower()
            if any(kw in name or kw in cmd for kw in keywords):
                found.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return found


async def _system_status(update: Update) -> None:
    cpu = psutil.cpu_percent(interval=1.0)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    chromium_procs = _find_procs({"chromium", "chrome"})
    manus_procs = _find_procs({"main.py"})

    def dot(procs: list) -> str:
        return "🟢" if procs else "⚫"

    text = (
        f"📊 *System Status*\n\n"
        f"🖥  CPU     *{cpu:.1f}%*\n"
        f"💾  RAM     *{mem.used / 2**30:.1f} GB* / {mem.total / 2**30:.1f} GB"
        f"  ({mem.percent:.1f}% used)\n"
        f"💿  Disk    *{disk.used / 2**30:.1f} GB* / {disk.total / 2**30:.1f} GB"
        f"  ({disk.percent:.1f}% used)\n\n"
        f"{dot(chromium_procs)} Chromium   "
        + (f"running  ({len(chromium_procs)} proc)" if chromium_procs else "not running")
        + f"\n{dot(manus_procs)} OpenManus  "
        + ("running" if manus_procs else "idle")
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ══════════════════════════════════════════════════════════════════════════════
# Kill Tasks
# ══════════════════════════════════════════════════════════════════════════════

_KILL_KEYWORDS = {"main.py", "chromium", "chrome"}


async def _kill_tasks(update: Update) -> None:
    global _active_proc
    killed: list[str] = []

    # 1. Gracefully stop the subprocess we launched
    if _active_proc is not None and _active_proc.returncode is None:
        try:
            _active_proc.terminate()
            await asyncio.sleep(1.0)
            if _active_proc.returncode is None:
                _active_proc.kill()
            killed.append("OpenManus (bridge subprocess)")
        except ProcessLookupError:
            pass
        _active_proc = None

    # 2. Sweep the OS process table
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = (proc.info["name"] or "").lower()
            cmd = " ".join(proc.info.get("cmdline") or []).lower()
            if any(kw in name or kw in cmd for kw in _KILL_KEYWORDS):
                proc.send_signal(signal.SIGTERM)
                killed.append(f"{proc.info['name']}  (PID {proc.info['pid']})")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if killed:
        lines = "\n".join(f"  • {k}" for k in killed)
        await update.message.reply_text(
            f"🛑 *Terminated {len(killed)} process(es):*\n{lines}",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "✅ No OpenManus or Chromium processes found running."
        )


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════


def main() -> None:
    if not BOT_TOKEN:
        sys.exit(
            "\n❌  TELEGRAM_BOT_TOKEN is missing.\n"
            "    Open .env and paste your bot token, then re-run.\n"
        )
    if not ALLOWED_CHAT_ID:
        sys.exit(
            "\n❌  ALLOWED_CHAT_ID is missing or zero.\n"
            "    Message @userinfobot on Telegram to get your numeric ID,\n"
            "    paste it into .env, then re-run.\n"
        )

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print(f"\n✅  OpenManus Telegram Bridge is running")
    print(f"    Authorised user ID : {ALLOWED_CHAT_ID}")
    print(f"    OpenManus root     : {OPENMANUS_DIR}")
    print("    Press Ctrl-C to stop.\n")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
