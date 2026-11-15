"""Run one headless turn of an agent CLI (Claude Code or Codex) and return its reply.

Both engines run with the user's own CLI login; this module never touches
credentials. Claude gets only the Read tool; Codex runs in a read-only sandbox.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

import api_engines

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ENGINES = {"claude": "Claude Code", "codex": "Codex", "claude_api": "Claude API", "openai_api": "Other API"}
CLIS = ("claude", "codex")
API = tuple(api_engines.PROVIDERS)
ATTACHES = {"codex", *API}   # engines that receive frames as attached images (Claude Code opens files itself)
MAX_IMAGES = api_engines.MAX_IMAGES

SIGN_IN = {
    "claude": ("Claude Code is installed but not signed in. To sign in: open a terminal (press Win+R, type cmd, "
               "press Enter), run   claude auth login   and finish signing in in the browser window that opens, "
               "with a Claude Pro or Max plan or an Anthropic Console account. Then press \"Check again\" in "
               "Video Watch. The \"Open a terminal to sign in\" button does the first step for you."),
    "codex": ("Codex is installed but not signed in. To sign in: open a terminal (press Win+R, type cmd, press "
              "Enter), run   codex login   and sign in with your ChatGPT account in the browser window that opens. "
              "Then press \"Check again\" in Video Watch. The \"Open a terminal to sign in\" button does the first "
              "step for you."),
}
INSTALL = {
    "claude": "Claude Code is not installed. Run the Video Watch installer again and tick Claude Code, or see "
              "docs.claude.com/claude-code for the install command.",
    "codex": "Codex is not installed. Run the Video Watch installer again and tick Codex, or install Node.js "
             "and run   npm install -g @openai/codex   in a terminal.",
}
_AUTH_WORDS = ("please run /login", "invalid api key", "not logged in", "oauth token has expired", "login required",
               "401 unauthorized", "unauthorized", "authentication_error", "please sign in", "token expired")


class Cancelled(Exception):
    pass


# A model's usage limit (Codex: "You've hit your usage limit ... try again in 2 hours 13 minutes";
# Claude Code: "Claude AI usage limit reached|1748458800", "5-hour limit reached · resets 4am";
# APIs: HTTP 429 with retry-after). Billing problems (no credit) are not limits that come back by themselves.
_LIMIT_WORDS = ("usage limit", "hit your limit", "limit reached", "rate limit", "rate_limit", "too many requests",
                "429", "try again in", "try again at", "resets ")
_BILLING_WORDS = ("credit balance", "insufficient_quota", "billing", "payment required", "purchase credits")
_UNITS = {"d": 86400, "day": 86400, "h": 3600, "hr": 3600, "hour": 3600, "m": 60, "min": 60, "minute": 60,
          "s": 1, "sec": 1, "second": 1}


def parse_reset(text: str) -> float | None:
    """When a limit resets, as a timestamp, from the wording of the message; None when it does not say."""
    low = (text or "").lower()
    m = re.search(r"\|(\d{10})\b", low)
    if m:
        return float(m.group(1))
    m = re.search(r"(?:try again in|retry in|resets in|available in)\s+((?:\d+\s*[a-z]+[\s,]*(?:and\s+)?)+)", low)
    if m:
        total = 0
        for n, unit in re.findall(r"(\d+)\s*([a-z]+)", m.group(1)):
            unit = unit.rstrip("s") if unit not in ("s",) else unit
            total += int(n) * _UNITS.get(unit, _UNITS.get(unit[:1], 0))
        if total:
            return time.time() + total
    m = re.search(r"(?:resets?|try again at|available again at)\s*(?:at\s*)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", low)
    if m:
        h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
        if ap == "pm" and h < 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
        if h < 24 and mi < 60:
            now = time.localtime()
            t = time.mktime((now.tm_year, now.tm_mon, now.tm_mday, h, mi, 0, 0, 0, -1))
            return t if t > time.time() else t + 86400
    return None


def limit_info(text: str, strict: bool = False) -> dict | None:
    """{"until": timestamp or None, "message": ...} when text says a usage or rate limit was hit.
    strict: for a model's reply rather than an error, only the CLIs' own limit wording counts."""
    low = (text or "").lower()
    words = ("usage limit reached", "hit your usage limit", "hit your limit", "-hour limit reached") if strict else _LIMIT_WORDS
    if not low or any(w in low for w in _BILLING_WORDS) or not any(w in low for w in words):
        return None
    line = next((ln.strip() for ln in (text or "").splitlines() if any(w in ln.lower() for w in _LIMIT_WORDS)), text.strip())
    return {"until": parse_reset(text), "message": line[:300]}


def available(engine: str, s: dict | None = None) -> bool:
    if engine == "openai_api":
        return bool(api_engines._openai_key(s or {})[0])
    return bool(api_engines.get_key("anthropic")[0]) if engine in API else bool(resolve(engine))


def sees_images(engine: str, s: dict) -> bool:
    return api_engines.sees_images(engine, s)


def image_limit(engine: str, s: dict) -> int | None:
    return api_engines.image_limit(engine, s)


def label(engine: str, s: dict) -> str:
    """Engine name for messages; the OpenAI-compatible engine is named after its provider."""
    if engine != "openai_api":
        return ENGINES[engine]
    p = api_engines.provider(engine, s)
    model = (s.get("openai_api_model") or "").strip()
    return model or "The chosen model" if p == "custom" else api_engines.PRESETS[p]["name"]


def login_status(engine: str) -> bool | None:
    """True/False for a CLI's sign-in, None when it is not installed or the check could not run."""
    base = resolve(engine)
    if not base:
        return None
    cmd = base + (["auth", "status"] if engine == "claude" else ["login", "status"])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=30, creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = (r.stdout or "") + (r.stderr or "")
    if engine == "claude":
        try:
            return bool(json.loads(r.stdout).get("loggedIn"))
        except ValueError:
            return r.returncode == 0 and "not logged" not in out.lower()
    return r.returncode == 0 and "logged in" in out.lower() and "not logged in" not in out.lower()


def problem(engine: str, signed_in: bool | None = None, s: dict | None = None) -> str | None:
    """Why this engine cannot run now, in words for the user; None when it can."""
    if engine in API:
        if available(engine, s):
            return None
        p = api_engines.provider(engine, s or {})
        return f"No {api_engines.NAMES[p]} key is set. Add one under Model, {'Claude API' if p == 'anthropic' else 'Other APIs'}."
    if not resolve(engine):
        return INSTALL[engine]
    if signed_in is None:
        signed_in = login_status(engine)
    return SIGN_IN[engine] if signed_in is False else None


def _auth_problem(engine: str, text: str) -> str | None:
    low = (text or "").lower()
    return SIGN_IN[engine] if engine in SIGN_IN and any(w in low for w in _AUTH_WORDS) else None


def resolve(engine: str) -> list[str] | None:
    """argv prefix for the engine, skipping npm's .cmd shim where possible
    (cmd.exe caps a command line at ~8k characters and mangles some arguments)."""
    found = shutil.which(engine)
    if not found:
        return None
    root = Path(found).parent / "node_modules"
    if engine == "claude":
        exe = root / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        return [str(exe)] if exe.exists() else [found]
    js = root / "@openai" / "codex" / "bin" / "codex.js"
    node = shutil.which("node")
    return [node, str(js)] if js.exists() and node else [found]


def version(engine: str) -> str | None:
    base = resolve(engine)
    if not base:
        return None
    try:
        r = subprocess.run(base + ["--version"], capture_output=True, text=True, timeout=20, creationflags=NO_WINDOW)
        return (r.stdout or r.stderr).strip().splitlines()[0]
    except Exception:  # noqa: BLE001
        return "installed (version check failed)"


def _kill(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, creationflags=NO_WINDOW)
    else:
        proc.kill()


def run(engine: str, prompt: str, cwd: Path, s: dict, images: list[str] | None = None,
        session: str | None = None, on_activity=None, cancel: threading.Event | None = None) -> dict:
    """One turn. Returns {text, session, cost, turns, tokens, error, opened}; opened is
    the list of file paths Claude read with its Read tool during the turn."""
    if engine in API:
        try:
            r = api_engines.run(engine, prompt, s, images=images, session=session, on_activity=on_activity, cancel=cancel)
        except api_engines.Cancelled:
            raise Cancelled() from None
        if r.get("error") and not r.get("limit"):
            lim = limit_info(r["error"])
            if lim:
                r["limit"] = lim
        return r
    base = resolve(engine)
    if not base:
        return {"text": "", "session": session, "error": f"`{engine}` CLI not found on PATH"}
    model = (s.get(f"{engine}_model") or "").strip()
    effort = (s.get(f"{engine}_effort") or "").strip()
    last_file = cwd / f"_{engine}_last_{uuid.uuid4().hex[:8]}.txt"   # unique: sub-agents run in parallel here

    if engine == "claude":
        cmd = base + ["-p", "--output-format", "stream-json", "--verbose",
                      "--strict-mcp-config", "--disable-slash-commands",
                      "--max-turns", str(int(s.get("max_turns") or 60)),
                      "--tools", "Read", "--allowedTools", "Read"]
        if model:
            cmd += ["--model", model]
        if effort:
            cmd += ["--effort", effort]
        if session:
            cmd += ["--resume", session]
    else:
        cmd = base + ["exec"] + (["resume", session] if session else [])
        for img in images or []:
            cmd += ["-i", os.path.relpath(img, cwd)]
        cmd += ["--json", "--skip-git-repo-check", "-c", "sandbox_mode=read-only"]
        if model:
            cmd += ["-m", model]
        if effort:
            cmd += ["-c", f"model_reasoning_effort={effort}"]
        last_file.unlink(missing_ok=True)
        cmd += ["-o", str(last_file), "-"]

    out = {"text": "", "session": session, "cost": 0.0, "turns": 0, "tokens": 0, "error": None, "opened": []}
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDECODE")}
    with open(cwd / f"_{engine}_stderr.log", "ab") as errlog:
        proc = subprocess.Popen(cmd, cwd=str(cwd), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=errlog, env=env, creationflags=NO_WINDOW)
        deadline = time.time() + 60 * float(s.get("timeout_min") or 30)
        state = {"why": None}

        def watchdog() -> None:
            while proc.poll() is None:
                if cancel is not None and cancel.is_set():
                    state["why"] = "cancelled"
                elif time.time() > deadline:
                    state["why"] = "timeout"
                if state["why"]:
                    _kill(proc)
                    return
                time.sleep(0.5)

        threading.Thread(target=watchdog, daemon=True).start()
        try:
            proc.stdin.write(prompt.encode("utf-8"))
            proc.stdin.close()
        except OSError:
            pass

        viewed = 0
        for raw in proc.stdout:
            try:
                ev = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue
            kind = ev.get("type")
            if engine == "claude":
                if kind == "system" and ev.get("subtype") == "init":
                    out["session"] = ev.get("session_id") or out["session"]
                    out["model"] = ev.get("model")
                elif kind == "assistant":
                    for block in (ev.get("message") or {}).get("content") or []:
                        if block.get("type") == "tool_use" and block.get("name") == "Read":
                            viewed += 1
                            target = str((block.get("input") or {}).get("file_path") or "")
                            if target:
                                out["opened"].append(target if os.path.isabs(target) else str(cwd / target))
                            if on_activity:
                                on_activity(f"viewing frames ({viewed} opened)")
                        elif block.get("type") == "text" and on_activity:
                            on_activity("writing")
                elif kind == "result":
                    out["text"] = ev.get("result") or ""
                    out["session"] = ev.get("session_id") or out["session"]
                    out["cost"] = float(ev.get("total_cost_usd") or 0)
                    out["turns"] = int(ev.get("num_turns") or 0)
                    if ev.get("is_error") or ev.get("subtype") not in (None, "success"):
                        out["error"] = f"claude ended with {ev.get('subtype') or 'an error'}: {str(ev.get('result') or '')[:300]}"
            else:
                item = ev.get("item") or {}
                if kind == "thread.started":
                    out["session"] = ev.get("thread_id") or out["session"]
                elif kind == "item.completed" and item.get("type") == "agent_message":
                    out["text"] = item.get("text") or out["text"]
                    if on_activity:
                        on_activity("writing")
                elif kind in ("item.started", "item.completed") and on_activity:
                    on_activity(f"working ({item.get('type', 'step')})")
                elif kind == "turn.completed":
                    u = ev.get("usage") or {}
                    out["tokens"] += int(u.get("input_tokens") or 0) + int(u.get("output_tokens") or 0)
                    out["turns"] += 1
                elif kind in ("error", "turn.failed"):
                    msg = ev.get("message") or (ev.get("error") or {}).get("message") or "unknown error"
                    out["error"] = f"codex: {str(msg)[:400]}"
        code = proc.wait()

    if state["why"] == "cancelled":
        raise Cancelled()
    if state["why"] == "timeout":
        out["error"] = f"{engine} timed out after {s.get('timeout_min')} minutes"
    if engine == "codex" and last_file.exists():
        out["text"] = last_file.read_text(encoding="utf-8", errors="replace") or out["text"]
    if not out["text"] and not out["error"]:
        tail = ""
        try:
            tail = (cwd / f"_{engine}_stderr.log").read_text(encoding="utf-8", errors="replace")[-500:].strip()
        except OSError:
            pass
        out["error"] = f"{engine} returned nothing (exit {code}). {tail}"
    # The CLIs' own words for a missing sign-in ("Invalid API key · Please run /login") help nobody.
    hint = None
    if out["error"]:
        try:
            tail = (cwd / f"_{engine}_stderr.log").read_text(encoding="utf-8", errors="replace")[-1500:]
        except OSError:
            tail = ""
        hint = _auth_problem(engine, out["error"] + " " + tail)
    elif engine == "claude" and len(out["text"]) < 200:   # Claude Code answers a lost login as its "result"
        low = out["text"].lower()
        hint = SIGN_IN["claude"] if any(w in low for w in _AUTH_WORDS[:3]) else None
    if hint:
        out.update(error=hint, text="")
        return out
    # A usage limit: the caller waits for it to reset and asks again, instead of failing the run.
    probe = ""
    if out["error"]:
        try:
            probe = out["error"] + "\n" + (cwd / f"_{engine}_stderr.log").read_text(encoding="utf-8", errors="replace")[-1500:]
        except OSError:
            probe = out["error"]
    elif engine == "claude" and len(out["text"]) < 300:
        probe = out["text"]
    lim = limit_info(probe, strict=not out["error"])
    if lim:
        out.update(limit=lim, error=f"{ENGINES[engine]} usage limit reached: {lim['message']}", text="")
    return out
