"""Video Watch Setup: the installer people download and run.

    Video Watch Setup.exe                     the install wizard
    Video Watch Setup.exe --uninstall         remove (this is what Windows' "Uninstall" runs)
    Video Watch Setup.exe --silent --dir D    copy the app only (no tools, no questions); for testing
        [--no-shortcuts] [--no-registry]

The app itself ("Video Watch.exe") travels inside this exe and is copied to the folder the
person picks. Tools the app relies on (yt-dlp, FFmpeg, and an AI CLI) are checked, and installed on
request through winget, Anthropic's installer or npm. Signing in is always left to the person: the
installer only opens the CLI's own sign-in in a terminal window.
"""
from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

APP = "Video Watch"
VERSION = "1.1.0"
EXE = "Video Watch.exe"
UNINSTALLER = "Uninstall Video Watch.exe"
REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\VideoWatch"
HERE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
PAYLOAD = HERE / "payload" / EXE if getattr(sys, "frozen", False) else Path(__file__).parent / "dist" / EXE
ICON = HERE / "payload" / "icon.ico" if getattr(sys, "frozen", False) else Path(__file__).parent / ".build" / "icon.ico"
LOCAL = Path(os.environ.get("LOCALAPPDATA") or Path.home())
DEFAULT_DIR = LOCAL / "Programs" / APP
DATA_DIR = LOCAL / "VideoWatch"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)

WINGET = ["--source", "winget", "--accept-package-agreements", "--accept-source-agreements", "--disable-interactivity"]
TOOLS = [
    {"id": "yt-dlp", "name": "yt-dlp", "why": "downloads videos from YouTube, Bilibili and most other sites",
     "need": True, "version": ["--version"], "how": "winget", "pkg": "yt-dlp.yt-dlp"},
    {"id": "ffmpeg", "name": "FFmpeg", "why": "takes the frames out of each video",
     "need": True, "version": ["-version"], "how": "winget", "pkg": "Gyan.FFmpeg"},
    {"id": "claude", "name": "Claude Code", "why": "AI model, with your Claude plan or Anthropic Console account",
     "version": ["--version"], "how": "claude"},
    {"id": "node", "name": "Node.js", "why": "needed only to install Codex",
     "version": ["--version"], "how": "winget", "pkg": "OpenJS.NodeJS.LTS"},
    {"id": "codex", "name": "Codex", "why": "AI model, with your ChatGPT plan",
     "version": ["--version"], "how": "npm", "pkg": "@openai/codex"},
]
SIGN_IN = {
    "claude": ("claude auth login", "a Claude Pro or Max plan, or an Anthropic Console account"),
    "codex": ("codex login", "your ChatGPT account"),
}

DESCRIPTION = (
    "Video Watch watches videos for you. Paste links (YouTube, Bilibili and most other video sites) or add "
    "video files from your computer, say what you want to know, and an AI model looks at frames taken from "
    "the video together with its transcript. It writes a report you open in your browser: a summary, the key "
    "moments with timestamps, the frames that matter and, for a batch of videos, a combined summary across "
    "all of them. Reports are kept in a library, filed by date and topic, and can be copied to a folder such "
    "as Google Drive.\n\n"
    "Everything runs on this computer. yt-dlp downloads each video, FFmpeg takes the frames, and the AI model "
    "of your choice looks at them: Claude Code or Codex with your own subscription sign-in, or the Claude API "
    "or OpenAI API with an API key (billed per use by Anthropic or OpenAI)."
)
NEEDS = [
    "Windows 10 or 11, with Microsoft Edge (part of Windows) to show the app.",
    "yt-dlp and FFmpeg. The next steps can install both for you through winget, which comes with Windows.",
    "At least one AI model to watch with, any of:\n"
    "    •  Claude Code, signed in with a Claude Pro or Max plan or an Anthropic Console account\n"
    "    •  Codex, signed in with a ChatGPT plan (installing it needs Node.js)\n"
    "    •  an API key from Anthropic or OpenAI, added inside the app after installing\n"
    "  The next steps can install Claude Code and Codex for you and open their sign-in.",
    "An internet connection, about 60 MB for the app, and free space for the videos it downloads while it works "
    "(they are deleted after each run unless you choose to keep them).",
]


# ---------------- system helpers ----------------

def refresh_path() -> None:
    """Re-read PATH from the registry so tools installed a moment ago are found."""
    if os.name != "nt":
        return
    import winreg
    parts: list[str] = []
    for root, key in ((winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                      (winreg.HKEY_CURRENT_USER, "Environment")):
        try:
            with winreg.OpenKey(root, key) as k:
                parts += [os.path.expandvars(p) for p in winreg.QueryValueEx(k, "Path")[0].split(os.pathsep) if p]
        except OSError:
            pass
    home = Path.home()
    parts += [str(home / ".local" / "bin"), str(Path(os.environ.get("APPDATA", home)) / "npm"),
              str(LOCAL / "Microsoft" / "WinGet" / "Links"), r"C:\Program Files\nodejs"]
    seen, out = set(), []
    for p in os.environ.get("PATH", "").split(os.pathsep) + parts:
        k = p.rstrip("\\").lower()
        if p and k not in seen and os.path.isdir(p):
            seen.add(k)
            out.append(p)
    os.environ["PATH"] = os.pathsep.join(out)


def add_user_path(folder: Path) -> None:
    """Put a folder on the user's PATH (for tools whose installer leaves that to us)."""
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as k:
        try:
            cur, kind = winreg.QueryValueEx(k, "Path")
        except OSError:
            cur, kind = "", winreg.REG_EXPAND_SZ
        if str(folder).lower() in [p.rstrip("\\").lower() for p in os.path.expandvars(cur).split(os.pathsep)]:
            return
        winreg.SetValueEx(k, "Path", 0, kind, (cur.rstrip(os.pathsep) + os.pathsep if cur else "") + str(folder))
    _broadcast_env()


def _broadcast_env() -> None:
    try:
        import ctypes
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0x0002, 3000, None)
    except (OSError, AttributeError):
        pass


def which(tool: str) -> str | None:
    return shutil.which(tool)


def run_quiet(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return None


def tool_version(t: dict) -> str | None:
    exe = which(t["id"])
    if not exe:
        return None
    r = run_quiet([exe, *t["version"]], 30)
    text = ((r.stdout or r.stderr) if r else "").strip().splitlines()
    first = text[0] if text else "installed"
    m = re.search(r"\d+(\.\d+)+", first)
    return m.group(0) if m else first[:40]


def signed_in(tool: str) -> bool | None:
    exe = which(tool)
    if not exe:
        return None
    r = run_quiet([exe, "auth", "status"] if tool == "claude" else [exe, "login", "status"], 40)
    if r is None:
        return None
    out = (r.stdout or "") + (r.stderr or "")
    if tool == "claude":
        try:
            return bool(json.loads(r.stdout).get("loggedIn"))
        except ValueError:
            return r.returncode == 0 and "not logged" not in out.lower()
    return r.returncode == 0 and "logged in" in out.lower() and "not logged in" not in out.lower()


def open_sign_in(tool: str) -> None:
    exe = which(tool)
    if not exe:
        return
    cmd = subprocess.list2cmdline([exe, *(["auth", "login"] if tool == "claude" else ["login"])])
    subprocess.Popen(f'cmd /k "echo Signing in to {tool}. Finish in the browser window that opens. && {cmd} && echo. '
                     f'&& echo Done. Close this window and press Check again in the installer."', creationflags=NEW_CONSOLE)


def special_folder(csidl: int) -> Path:
    import ctypes
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
    return Path(buf.value)


def desktop() -> Path:
    return special_folder(0x10)


def start_menu() -> Path:
    return special_folder(0x02)


def make_shortcut(lnk: Path, target: Path) -> None:
    q = lambda p: str(p).replace("'", "''")  # noqa: E731
    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{q(lnk)}');$s.TargetPath='{q(target)}';"
          f"$s.WorkingDirectory='{q(target.parent)}';$s.IconLocation='{q(target)},0';"
          f"$s.Description='Watch videos with an AI model';$s.Save()")
    r = run_quiet(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], 60)
    if r is None or r.returncode != 0 or not lnk.exists():
        raise OSError(f"could not create the shortcut {lnk}: {(r.stderr if r else '').strip()[:200]}")


def app_state() -> str | None:
    """None when Video Watch is not running, else its job status ("running" while it watches)."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:8756/api/job", timeout=3) as r:
            return json.loads(r.read().decode("utf-8")).get("status") or "idle"
    except (OSError, ValueError):
        return None


def quit_running_app() -> bool:
    """Ask a running Video Watch to quit, so its exe can be replaced. True if one was running."""
    try:
        req = urllib.request.Request("http://127.0.0.1:8756/api/quit", data=b"{}", method="POST",
                                     headers={"X-Video-Watch": "1", "Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=3).read()
    except OSError:
        return False
    time.sleep(3)
    return True


def write_registry(folder: Path) -> None:
    import winreg
    size = sum(f.stat().st_size for f in folder.glob("*") if f.is_file()) // 1024
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY) as k:
        for name, value in (("DisplayName", APP), ("DisplayVersion", VERSION), ("Publisher", APP),
                            ("InstallLocation", str(folder)), ("DisplayIcon", str(folder / EXE)),
                            ("UninstallString", f'"{folder / UNINSTALLER}" --uninstall'),
                            ("QuietUninstallString", f'"{folder / UNINSTALLER}" --uninstall --silent')):
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)
        for name, value in (("NoModify", 1), ("NoRepair", 1), ("EstimatedSize", size)):
            winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, value)


def installed_folder() -> Path | None:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY) as k:
            return Path(winreg.QueryValueEx(k, "InstallLocation")[0])
    except OSError:
        return None


# ---------------- install / uninstall steps ----------------

def install_tool(t: dict, log) -> bool:
    """Install one tool; log(line) receives progress. True when the tool is found afterwards."""
    if t["how"] == "winget":
        if not which("winget"):
            log("winget is not available on this computer, so this cannot be installed automatically.")
            return False
        cmd = ["winget", "install", "-e", "--id", t["pkg"], *WINGET]
    elif t["how"] == "claude":   # Anthropic's own installer for the native Claude Code
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "irm https://claude.ai/install.ps1 | iex"]
    else:
        npm = which("npm") or which("npm.cmd") or (r"C:\Program Files\nodejs\npm.cmd" if Path(r"C:\Program Files\nodejs\npm.cmd").exists() else None)
        if not npm:
            log("Node.js is needed first (tick it as well).")
            return False
        cmd = [npm, "install", "-g", t["pkg"]]
    log("> " + " ".join(cmd))
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
    except OSError as exc:
        log(f"could not start: {exc}")
        return False
    for raw in p.stdout:
        line = raw.decode("utf-8", "replace").replace("\r", "\n").split("\n")
        for ln in line:
            ln = re.sub(r"[^\x20-\x7e\u00a0-\uffff]", "", ln).strip()
            if ln and not re.fullmatch(r"[-\\|/█▒ \d.%KMGBs]+", ln):   # drop spinners and progress bars
                log("  " + ln[:200])
    code = p.wait()
    refresh_path()
    if t["how"] == "claude":
        local_bin = Path.home() / ".local" / "bin"
        if (local_bin / "claude.exe").exists():
            add_user_path(local_bin)
            refresh_path()
    if t["how"] == "npm":
        npm_bin = Path(os.environ.get("APPDATA", Path.home())) / "npm"
        if npm_bin.exists():
            add_user_path(npm_bin)
            refresh_path()
    ok = bool(which(t["id"]))
    log(f"{t['name']}: " + ("installed." if ok else f"not found after installing (exit {code})."))
    return ok


def install_app(folder: Path, shortcuts: bool, start: bool, registry: bool, log, close_app: bool = True) -> None:
    if not PAYLOAD.exists():
        raise OSError(f"the app is missing from this installer ({PAYLOAD})")
    if close_app and quit_running_app():
        log("Closed the running Video Watch so it can be updated.")
    folder.mkdir(parents=True, exist_ok=True)
    for attempt in range(5):
        try:
            shutil.copy2(PAYLOAD, folder / EXE)
            break
        except PermissionError:
            if attempt == 4:
                raise OSError(f"{folder / EXE} is in use. Close Video Watch and try again.") from None
            time.sleep(2)
    log(f"Copied the app to {folder}")
    if getattr(sys, "frozen", False):   # this exe doubles as the uninstaller
        try:
            shutil.copy2(sys.executable, folder / UNINSTALLER)
        except OSError as exc:
            log(f"Could not copy the uninstaller: {exc}")
    if shortcuts:
        make_shortcut(desktop() / f"{APP}.lnk", folder / EXE)
        log("Added a desktop shortcut.")
    if start:
        make_shortcut(start_menu() / f"{APP}.lnk", folder / EXE)
        log("Added Video Watch to the Start menu.")
    if registry:
        write_registry(folder)
        log("Registered with Windows (Settings, Apps can uninstall it).")


def uninstall(folder: Path, delete_data: bool, log=print, close_app: bool = True) -> None:
    if close_app:
        quit_running_app()
    for lnk in (desktop() / f"{APP}.lnk", start_menu() / f"{APP}.lnk"):
        try:
            lnk.unlink(missing_ok=True)
        except OSError:
            pass
    try:
        import winreg
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG_KEY)
    except OSError:
        pass
    (folder / EXE).unlink(missing_ok=True)
    if delete_data and DATA_DIR.exists():
        shutil.rmtree(DATA_DIR, ignore_errors=True)
        log("Deleted your reports and settings.")
    me = Path(sys.executable).resolve()
    if getattr(sys, "frozen", False) and me.parent == folder.resolve():
        # A running exe cannot delete itself: a detached command removes the folder once this one exits.
        subprocess.Popen(f'cmd /c ping 127.0.0.1 -n 4 > nul & rmdir /s /q "{folder}"', creationflags=NO_WINDOW)
    else:
        shutil.rmtree(folder, ignore_errors=True)
    log("Video Watch was removed.")


# ---------------- the wizard ----------------

def wizard() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    ACCENT, INK, MUTE, OK, BAD, BG = "#a5481f", "#1d1c1a", "#6b6a65", "#2f6b3c", "#a3281c", "#ffffff"
    root = tk.Tk()
    root.title(f"{APP} Setup")
    root.geometry("780x640")
    root.minsize(700, 600)
    root.configure(bg=BG)
    try:
        if ICON.exists():
            root.iconbitmap(str(ICON))
    except tk.TclError:
        pass
    style = ttk.Style()
    try:
        style.theme_use("vista")
    except tk.TclError:
        pass
    for name, opts in {
        "TFrame": {"background": BG}, "TLabel": {"background": BG, "foreground": INK, "font": ("Segoe UI", 10)},
        "H.TLabel": {"font": ("Segoe UI Semibold", 14)}, "B.TLabel": {"font": ("Segoe UI Semibold", 10)},
        "M.TLabel": {"foreground": MUTE, "font": ("Segoe UI", 9)}, "Ok.TLabel": {"foreground": OK, "font": ("Segoe UI", 9)},
        "Bad.TLabel": {"foreground": BAD, "font": ("Segoe UI", 9)}, "TCheckbutton": {"background": BG, "font": ("Segoe UI", 10)},
        "TLabelframe": {"background": BG}, "TLabelframe.Label": {"background": BG, "foreground": MUTE, "font": ("Segoe UI", 9)},
    }.items():
        style.configure(name, **opts)

    head = tk.Frame(root, bg=ACCENT, height=78)
    head.pack(fill="x")
    head.pack_propagate(False)
    tk.Label(head, text=APP, bg=ACCENT, fg="white", font=("Segoe UI Semibold", 18)).pack(anchor="w", padx=24, pady=(12, 0))
    sub = tk.Label(head, text="", bg=ACCENT, fg="#f6e6dc", font=("Segoe UI", 10))
    sub.pack(anchor="w", padx=24)
    body = ttk.Frame(root, padding=(28, 18, 28, 8))
    body.pack(fill="both", expand=True)
    ttk.Separator(root).pack(fill="x")
    foot = ttk.Frame(root, padding=(20, 12))
    foot.pack(fill="x")
    ttk.Label(foot, text=f"Version {VERSION}", style="M.TLabel").pack(side="left")
    cancel_b = ttk.Button(foot, text="Cancel", command=root.destroy)
    cancel_b.pack(side="right")
    next_b = ttk.Button(foot, text="Next  >")
    next_b.pack(side="right", padx=(0, 8))
    back_b = ttk.Button(foot, text="<  Back")
    back_b.pack(side="right", padx=(0, 4))

    state = {
        "dir": tk.StringVar(value=str(installed_folder() or DEFAULT_DIR)),
        "desk": tk.BooleanVar(value=True), "start": tk.BooleanVar(value=True), "launch": tk.BooleanVar(value=True),
        "pick": {t["id"]: tk.BooleanVar(value=False) for t in TOOLS},
        "found": {}, "signed": {}, "page": 0,
    }

    def clear() -> None:
        state["show"] = None
        for w in body.winfo_children():
            w.destroy()

    for v in state["pick"].values():   # ticking a tool updates the sign-in notes on the tools page
        v.trace_add("write", lambda *_: state["show"]() if state.get("show") and state["found"] else None)

    def para(parent, text, style_name="TLabel", **pack) -> ttk.Label:
        lab = ttk.Label(parent, text=text, style=style_name, wraplength=700, justify="left")
        lab.pack(anchor="w", **({"pady": (0, 8)} | pack))
        return lab

    # --- page 1: what it is and what it needs
    def page_welcome() -> None:
        sub.config(text="Watch videos with an AI model and get a written report")
        para(body, "What Video Watch does", "H.TLabel")
        para(body, DESCRIPTION)
        para(body, "What you need", "H.TLabel", pady=(6, 6))
        for n in NEEDS:
            row = ttk.Frame(body)
            row.pack(anchor="w", fill="x", pady=(0, 4))
            ttk.Label(row, text="•", style="B.TLabel").pack(side="left", anchor="n", padx=(0, 8))
            ttk.Label(row, text=n, wraplength=670, justify="left").pack(side="left", anchor="w")
        para(body, "Nothing is installed until you press Install on a later page.", "M.TLabel", pady=(8, 0))

    # --- page 2: where
    def page_folder() -> None:
        sub.config(text="Choose where to install")
        para(body, "Install folder", "H.TLabel")
        para(body, "Video Watch is installed for your Windows account only, so no administrator rights are needed "
                   "for the app itself.")
        row = ttk.Frame(body)
        row.pack(fill="x", pady=(4, 6))
        ttk.Entry(row, textvariable=state["dir"], font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True, ipady=3)

        def browse() -> None:
            got = filedialog.askdirectory(initialdir=str(Path(state["dir"].get()).parent), title="Choose the install folder")
            if got:
                p = Path(got)
                state["dir"].set(str(p if p.name.lower() == APP.lower() else p / APP))

        ttk.Button(row, text="Browse…", command=browse).pack(side="left", padx=(8, 0))
        para(body, "Choosing a parent folder adds a \"Video Watch\" folder inside it.", "M.TLabel")
        try:
            free = shutil.disk_usage(Path(state["dir"].get()).anchor or "C:\\").free / 1e9
            para(body, f"Needs about 60 MB. Free on that drive: {free:.0f} GB.", "M.TLabel")
        except OSError:
            pass
        para(body, "Shortcuts", "H.TLabel", pady=(12, 6))
        ttk.Checkbutton(body, text="Put a shortcut on the desktop", variable=state["desk"]).pack(anchor="w", pady=2)
        ttk.Checkbutton(body, text="Add to the Start menu", variable=state["start"]).pack(anchor="w", pady=2)
        para(body, f"Your reports, settings and API keys are kept separately in {DATA_DIR}, so updating or "
                   "reinstalling keeps them.", "M.TLabel", pady=(14, 0))

    # --- page 3: tools and sign-in
    def page_tools() -> None:
        sub.config(text="Check the tools Video Watch works with")
        top = ttk.Frame(body)
        top.pack(fill="x")
        ttk.Label(top, text="Tools", style="H.TLabel").pack(side="left")
        again = ttk.Button(top, text="Check again")
        again.pack(side="right")
        para(body, "Tick anything missing that you want installed now. Tools come from their official sources "
                   "(winget, claude.ai, npm); Windows may ask for permission for some of them.", "M.TLabel")
        grid = ttk.Frame(body)
        grid.pack(fill="x")
        grid.columnconfigure(1, weight=1)
        status: dict[str, ttk.Label] = {}
        boxes: dict[str, ttk.Checkbutton] = {}
        for i, t in enumerate(TOOLS):
            ttk.Label(grid, text=t["name"] + ("" if not t.get("need") else "  (required)"), style="B.TLabel").grid(row=i * 2, column=0, sticky="w", pady=(6, 0))
            ttk.Label(grid, text=t["why"], style="M.TLabel").grid(row=i * 2 + 1, column=0, columnspan=2, sticky="w")
            status[t["id"]] = ttk.Label(grid, text="checking…", style="M.TLabel")
            status[t["id"]].grid(row=i * 2, column=1, sticky="e", padx=12, pady=(6, 0))
            boxes[t["id"]] = ttk.Checkbutton(grid, text="Install", variable=state["pick"][t["id"]])
            boxes[t["id"]].grid(row=i * 2, column=2, sticky="e", pady=(6, 0))
        sign = ttk.LabelFrame(body, text="  Sign-in  ", padding=(12, 8))
        sign.pack(fill="x", pady=(14, 0))
        sign_rows: dict[str, tuple] = {}
        for tool in ("claude", "codex"):
            row = ttk.Frame(sign)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text="Claude Code" if tool == "claude" else "Codex", style="B.TLabel", width=12).pack(side="left")
            lab = ttk.Label(row, text="checking…", style="M.TLabel")
            lab.pack(side="left")
            btn = ttk.Button(row, text="Sign in…", command=lambda tl=tool: open_sign_in(tl))
            sign_rows[tool] = (lab, btn)
        help_lab = para(sign, "", "M.TLabel", pady=(6, 0))

        def show() -> None:
            for t in TOOLS:
                v = state["found"].get(t["id"])
                lab, box = status[t["id"]], boxes[t["id"]]
                if v:
                    lab.config(text=f"installed ({v})", style="Ok.TLabel")
                    if state["pick"][t["id"]].get():   # (setting it re-runs show() through the trace)
                        state["pick"][t["id"]].set(False)
                    box.state(["disabled"])
                else:
                    lab.config(text="not found", style="Bad.TLabel" if t.get("need") else "M.TLabel")
                    box.state(["!disabled"])
            notes = []
            for tool, (lab, btn) in sign_rows.items():
                s = state["signed"].get(tool)
                if not state["found"].get(tool):
                    lab.config(text="not installed" + (" (ticked above: sign in after installing)" if state["pick"][tool].get() else ""), style="M.TLabel")
                    btn.pack_forget()
                elif s:
                    lab.config(text="signed in ✓", style="Ok.TLabel")
                    btn.pack_forget()
                else:
                    lab.config(text="not signed in", style="Bad.TLabel")
                    btn.pack(side="right")
                    cmd, who = SIGN_IN[tool]
                    notes.append(f"{'Claude Code' if tool == 'claude' else 'Codex'}: press Sign in… (or open a terminal and run  {cmd} ), "
                                 f"then finish in the browser window that opens, with {who}.")
            notes.append("You need at least one model: Claude Code or Codex signed in, or an API key added in the app "
                         "afterwards (Model, Claude API or OpenAI API). You can sign in later too; the app shows the same help.")
            help_lab.config(text="\n".join(notes))
            again.state(["!disabled"])

        def check() -> None:
            again.state(["disabled"])
            for lab in status.values():
                lab.config(text="checking…", style="M.TLabel")

            def work() -> None:
                refresh_path()
                found = {t["id"]: tool_version(t) for t in TOOLS}
                signed = {tl: signed_in(tl) if found.get(tl) else None for tl in ("claude", "codex")}
                def done() -> None:
                    first = not state["found"]
                    state["found"].update(found)
                    state["signed"].update(signed)
                    if first:   # required tools that are missing start ticked
                        for t in TOOLS:
                            if t.get("need") and not found.get(t["id"]):
                                state["pick"][t["id"]].set(True)
                    show()

                root.after(0, done)

            threading.Thread(target=work, daemon=True).start()

        again.config(command=check)
        state["show"] = show
        if state["found"]:
            show()
        else:
            check()

    # --- page 4: install
    def page_install() -> None:
        sub.config(text="Installing")
        para(body, "Installing Video Watch", "H.TLabel")
        bar = ttk.Progressbar(body, mode="indeterminate")
        bar.pack(fill="x", pady=(4, 10))
        bar.start(12)
        frame = ttk.Frame(body)
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, height=16, wrap="word", font=("Consolas", 9), relief="flat", bg="#f6f5f1", fg=INK,
                       padx=10, pady=8)
        scroll = ttk.Scrollbar(frame, command=text.yview)
        text.config(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        q: queue.Queue = queue.Queue()
        result = {"error": None, "tools": {}}

        def log(line: str) -> None:
            q.put(line)

        def work() -> None:
            try:
                picked = [t for t in TOOLS if state["pick"][t["id"]].get()]
                order = sorted(picked, key=lambda t: ["yt-dlp", "ffmpeg", "node", "claude", "codex"].index(t["id"]))
                for t in order:
                    log(f"\nInstalling {t['name']}…")
                    result["tools"][t["id"]] = install_tool(t, log)
                log("\nInstalling the app…")
                install_app(Path(state["dir"].get()), state["desk"].get(), state["start"].get(), True, log)
                refresh_path()
                state["found"] = {t["id"]: tool_version(t) for t in TOOLS}
                state["signed"] = {tl: signed_in(tl) if state["found"].get(tl) else None for tl in ("claude", "codex")}
            except Exception as exc:  # noqa: BLE001  (shown to the person, never a crash)
                result["error"] = str(exc)
            q.put(None)

        def pump() -> None:
            while True:
                try:
                    line = q.get_nowait()
                except queue.Empty:
                    root.after(150, pump)
                    return
                if line is None:
                    bar.stop()
                    if result["error"]:
                        text.insert("end", f"\nInstallation failed: {result['error']}\n")
                        text.see("end")
                        messagebox.showerror(f"{APP} Setup", f"Installation failed:\n\n{result['error']}")
                        back_b.state(["!disabled"])
                        cancel_b.state(["!disabled"])
                        return
                    state["failed_tools"] = [t["name"] for t in TOOLS if result["tools"].get(t["id"]) is False]
                    go(4)
                    return
                text.insert("end", line + "\n")
                text.see("end")

        back_b.state(["disabled"])
        next_b.state(["disabled"])
        cancel_b.state(["disabled"])
        threading.Thread(target=work, daemon=True).start()
        pump()

    # --- page 5: done
    def page_done() -> None:
        sub.config(text="Done")
        para(body, "Video Watch is installed", "H.TLabel")
        para(body, f"Installed in {state['dir'].get()}. Open it from the desktop or Start menu shortcut. To remove it "
                   "later, use Windows Settings, Apps, Installed apps, Video Watch, Uninstall.")
        found, signed = state["found"], state["signed"]
        missing = [t["name"] for t in TOOLS if t.get("need") and not found.get(t["id"])]
        if missing:
            para(body, f"Still missing: {', '.join(missing)}. Videos cannot be downloaded or cut into frames until "
                       "they are installed (run this setup again and tick them).", "Bad.TLabel")
        if state.get("failed_tools"):
            para(body, f"These could not be installed: {', '.join(state['failed_tools'])}. The log on the previous "
                       "page says why; you can run this setup again.", "Bad.TLabel")
        ready = [n for tl, n in (("claude", "Claude Code"), ("codex", "Codex")) if signed.get(tl)]
        todo = [tl for tl in ("claude", "codex") if found.get(tl) and not signed.get(tl)]
        if ready:
            para(body, f"Ready to watch with: {', '.join(ready)}.", "Ok.TLabel")
        for tl in todo:
            cmd, who = SIGN_IN[tl]
            row = ttk.Frame(body)
            row.pack(fill="x", pady=(2, 6))
            ttk.Label(row, text=f"{'Claude Code' if tl == 'claude' else 'Codex'} is installed but not signed in. "
                                f"Sign in with {who}:", wraplength=520, justify="left").pack(side="left")
            ttk.Button(row, text="Sign in…", command=lambda x=tl: open_sign_in(x)).pack(side="right")
        if not ready:
            para(body, "No AI model is ready yet. Sign in above, or open Video Watch and add an API key under "
                       "Model, Claude API or OpenAI API. The app explains each step too.", "M.TLabel")
        ttk.Checkbutton(body, text="Open Video Watch now", variable=state["launch"]).pack(anchor="w", pady=(12, 0))
        back_b.state(["disabled"])
        cancel_b.pack_forget()
        next_b.state(["!disabled"])

    pages = [page_welcome, page_folder, page_tools, page_install, page_done]

    def go(i: int) -> None:
        state["page"] = i
        clear()
        pages[i]()
        back_b.state(["disabled"] if i in (0, 3, 4) else ["!disabled"])
        if i < 3:
            next_b.state(["!disabled"])
        next_b.config(text="Install" if i == 2 else "Finish" if i == 4 else "Next  >")

    def on_next() -> None:
        i = state["page"]
        if i == 1:
            d = Path(state["dir"].get().strip().strip('"'))
            if not d.is_absolute():
                messagebox.showwarning(f"{APP} Setup", "Choose a full folder path, for example C:\\Users\\you\\Apps\\Video Watch.")
                return
            if d.exists() and any(d.iterdir()) and not (d / EXE).exists():
                if not messagebox.askyesno(f"{APP} Setup", f"{d} already holds other files. Install into it anyway?"):
                    return
            state["dir"].set(str(d))
        if i == 2:
            if not state["found"]:
                return
            running = app_state()
            if running and not messagebox.askyesno(f"{APP} Setup", "Video Watch is open" + (
                    " and is watching videos right now; closing it stops that run" if running == "running" else "")
                    + ". It has to close so it can be updated. Close it and continue?"):
                return
            gone = [t["name"] for t in TOOLS if t.get("need") and not state["found"].get(t["id"]) and not state["pick"][t["id"]].get()]
            if gone and not messagebox.askyesno(f"{APP} Setup", f"{' and '.join(gone)} {'is' if len(gone) == 1 else 'are'} "
                                                f"not installed and not ticked. Video Watch cannot watch videos without "
                                                f"{'it' if len(gone) == 1 else 'them'}. Continue anyway?"):
                return
            if state["pick"]["codex"].get() and not state["found"].get("node") and not state["pick"]["node"].get():
                state["pick"]["node"].set(True)   # Codex installs through Node's npm
        if i == 4:
            if state["launch"].get():
                exe = Path(state["dir"].get()) / EXE
                if exe.exists():
                    subprocess.Popen([str(exe)], cwd=str(exe.parent), close_fds=True)
            root.destroy()
            return
        go(i + 1)

    next_b.config(command=on_next)
    back_b.config(command=lambda: go(max(0, state["page"] - 1)))
    go(0)
    root.mainloop()


def uninstall_window() -> None:
    import tkinter as tk
    from tkinter import messagebox, ttk
    folder = installed_folder() or Path(sys.executable).resolve().parent
    root = tk.Tk()
    root.withdraw()
    try:
        if ICON.exists():
            root.iconbitmap(str(ICON))
    except tk.TclError:
        pass
    win = tk.Toplevel(root)
    win.title(f"Uninstall {APP}")
    win.geometry("520x220")
    win.resizable(False, False)
    win.protocol("WM_DELETE_WINDOW", root.destroy)
    f = ttk.Frame(win, padding=20)
    f.pack(fill="both", expand=True)
    ttk.Label(f, text=f"Remove {APP} from this computer?", font=("Segoe UI Semibold", 12)).pack(anchor="w")
    ttk.Label(f, text=f"The app in {folder} and its shortcuts will be removed. Tools such as yt-dlp, FFmpeg, "
                      "Claude Code and Codex stay installed.", wraplength=470, justify="left").pack(anchor="w", pady=(6, 8))
    data = tk.BooleanVar(value=False)
    ttk.Checkbutton(f, text=f"Also delete my reports, settings and saved API keys ({DATA_DIR})", variable=data).pack(anchor="w")
    row = ttk.Frame(f)
    row.pack(side="bottom", fill="x")

    def go() -> None:
        try:
            uninstall(folder, data.get(), log=lambda m: None)
            messagebox.showinfo(f"Uninstall {APP}", f"{APP} was removed.", parent=win)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(f"Uninstall {APP}", f"Could not remove everything: {exc}", parent=win)
        root.destroy()

    ttk.Button(row, text="Cancel", command=root.destroy).pack(side="right")
    ttk.Button(row, text="Uninstall", command=go).pack(side="right", padx=8)
    root.mainloop()


def main() -> None:
    args = sys.argv[1:]
    silent = "--silent" in args
    folder = Path(args[args.index("--dir") + 1]) if "--dir" in args else None
    if "--uninstall" in args:
        if silent:
            uninstall(folder or installed_folder() or DEFAULT_DIR, "--delete-data" in args, close_app="--close-app" in args)
        else:
            uninstall_window()
        return
    if silent:
        install_app(folder or DEFAULT_DIR, "--no-shortcuts" not in args, "--no-shortcuts" not in args,
                    "--no-registry" not in args, print, close_app="--close-app" in args)
        return
    wizard()


if __name__ == "__main__":
    main()
