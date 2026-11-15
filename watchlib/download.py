#!/usr/bin/env python3
"""Download a video via yt-dlp, or resolve a local file path.

Also fetches subtitles (manual first, then auto-generated) in VTT format so
transcribe.py can parse them without needing Whisper.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi", ".flv", ".wmv"}

# Matched with re.match against each available subtitle language code, so each
# pattern must match from the start of the string. Broadened beyond English so
# non-English auto-captions (e.g. Bilibili's "ai-zh") aren't silently skipped.
SUB_LANGS = "en.*,zh.*,zh-Hans,zh-Hant,zh-CN,zh-TW,ai-zh,ai-en,ja.*,ko.*"


def is_url(source: str) -> bool:
    if source.startswith("-"):
        return False
    parsed = urlparse(source)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def resolve_local(path: str) -> dict:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise SystemExit(f"File not found: {p}")
    if p.suffix.lower() not in VIDEO_EXTS:
        print(
            f"[watch] warning: {p.suffix} is not a known video extension, proceeding anyway",
            file=sys.stderr,
        )
    return {
        "video_path": str(p),
        "subtitle_path": None,
        "info": {"title": p.name, "url": str(p)},
        "downloaded": False,
    }


def _pick_subtitle(out_dir: Path) -> Path | None:
    candidates = sorted(out_dir.glob("video*.vtt"))
    if not candidates:
        return None
    preferred = [
        c for c in candidates
        if any(marker in c.name for marker in (".en.", ".en-US.", ".en-GB.", ".en-orig."))
    ]
    return preferred[0] if preferred else candidates[0]


NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def has_video(path: Path) -> bool:
    """True if the file holds a real video stream (not only audio, or audio plus cover art)."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                            "stream=codec_name:stream_disposition=attached_pic", "-of", "csv=p=0", str(path)],
                           capture_output=True, text=True, timeout=60, creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return True   # cannot tell; let frame extraction find out
    for line in r.stdout.splitlines():
        name, _, pic = line.partition(",")
        if name.strip() and pic.strip() != "1" and name.strip() not in ("mjpeg", "png", "bmp"):
            return True
    return False


def _pick_video(out_dir: Path, need_video: bool = False) -> Path | None:
    found = [c for ext in (".mp4", ".mkv", ".webm", ".mov", ".m4a", ".mp3", ".opus")
             for c in sorted(out_dir.glob(f"video*{ext}"))]
    found += [c for c in sorted(out_dir.glob("video.*")) if c.suffix.lower() in VIDEO_EXTS and c not in found]
    found = [c for c in found if not c.name.endswith((".part", ".ytdl"))]
    if need_video:   # a site that refuses the video stream can still leave its audio part behind
        found = [c for c in found if has_video(c)]
    return found[0] if found else None


RATE_LIMITED = "Bilibili is refusing downloads from this connection for now (HTTP 567, its anti-bot limit)."


def _run(cmd: list[str]) -> tuple[int, bool]:
    """Run yt-dlp, echoing its output to stderr. Returns (exit code, whether the site answered HTTP 567)."""
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    hit = False
    for raw in p.stdout:
        line = raw.decode("utf-8", "replace")
        hit = hit or "HTTP Error 567" in line
        sys.stderr.write(line)
    sys.stderr.flush()
    return p.wait(), hit


def _other_formats(out_dir: Path) -> tuple[list[dict], set[str]]:
    """Video formats yt-dlp saw, in the order worth trying when the chosen one is refused:
    720p and below from the highest down, then above 720p from the lowest up."""
    try:
        raw = json.loads((out_dir / "video.info.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], set()
    tried = set(str(raw.get("format_id") or "").split("+"))
    vids = [f for f in raw.get("formats") or []
            if f.get("vcodec") not in (None, "none") and f.get("height") and f.get("format_id") not in tried]
    best: dict[int, dict] = {}
    for f in vids:   # one format per height is enough
        best.setdefault(int(f["height"]), f)
    low = sorted((h for h in best if h <= 720), reverse=True)
    high = sorted(h for h in best if h > 720)
    return [best[h] for h in low + high], tried


def cookie_args(spec: str | None) -> list[str]:
    """yt-dlp sign-in arguments. spec is a browser name (firefox, chrome, edge, optionally
    "firefox:profile") or the path of a cookies.txt file exported from a browser."""
    spec = (spec or "").strip().strip('"')
    if not spec:
        return []
    if spec.lower().endswith(".txt") or Path(spec).expanduser().is_file():
        return ["--cookies", str(Path(spec).expanduser())]
    return ["--cookies-from-browser", spec]


def fetch_captions(url: str, out_dir: Path, cookies_from_browser: str | None = None) -> dict:
    """Fetch metadata and best available VTT captions without downloading video."""
    if shutil.which("yt-dlp") is None:
        raise SystemExit("yt-dlp is not installed. Install with: brew install yt-dlp")

    out_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(out_dir / "video.%(ext)s")
    cmd = ["yt-dlp"]
    cmd += cookie_args(cookies_from_browser)
    cmd += [
        "--skip-download",
        "--write-info-json",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", SUB_LANGS,
        "--sub-format", "vtt",
        "--convert-subs", "vtt",
        "--no-playlist",
        "--ignore-errors",
        "-o", output_template,
        "--",
        url,
    ]
    subprocess.run(cmd, stdout=sys.stderr, stderr=sys.stderr)
    subtitle = _pick_subtitle(out_dir)
    info = _read_info(out_dir / "video.info.json", url)
    return {
        "video_path": None,
        "subtitle_path": str(subtitle) if subtitle else None,
        "info": info or {"url": url},
        "downloaded": False,
    }


def _read_info(info_path: Path, url: str) -> dict:
    info: dict = {}
    if info_path.exists():
        try:
            raw = json.loads(info_path.read_text(encoding="utf-8"))
            info = {
                "title": raw.get("title"),
                "uploader": raw.get("uploader") or raw.get("channel"),
                "duration": raw.get("duration"),
                "url": raw.get("webpage_url") or url,
            }
        except Exception as exc:
            print(f"[watch] info.json parse failed: {exc}", file=sys.stderr)
            info = {"url": url}
    return info


def download_url(
    url: str,
    out_dir: Path,
    audio_only: bool = False,
    cookies_from_browser: str | None = None,
    concurrency: int = 8,
    should_stop=None,
) -> dict:
    if shutil.which("yt-dlp") is None:
        raise SystemExit("yt-dlp is not installed. Install with: brew install yt-dlp")

    out_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(out_dir / "video.%(ext)s")

    fmt = "ba/bestaudio" if audio_only else "bv*[height<=720]+ba/b[height<=720]/bv+ba/b"
    base = ["yt-dlp", *cookie_args(cookies_from_browser),
            "-N", str(concurrency), "--retries", "4", "--fragment-retries", "4", "--socket-timeout", "30",
            "--retry-sleep", "exp=1:8"]   # space retries out: some sites (Bilibili 567) refuse bursts
    cmd = base + [
        "-f", fmt,
        "--merge-output-format", "mp4",
        "--write-info-json",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", SUB_LANGS,
        "--sub-format", "vtt",
        "--convert-subs", "vtt",
        "--no-playlist",
        "--ignore-errors",
        "-o", output_template,
        "--",
        url,
    ]

    # yt-dlp may exit non-zero if a subtitle variant fails (e.g. 429) even when
    # the video itself downloaded fine. Treat "video file present" as success.
    code, limited = _run(cmd)
    video = _pick_video(out_dir, need_video=not audio_only)
    note = None
    if video is None and not audio_only:
        # Bilibili in particular refuses some quality streams outright (HTTP 567) while serving
        # others, so try the other video qualities before giving up.
        options, tried = _other_formats(out_dir)
        for f in options[:3]:
            if should_stop and should_stop():
                break
            print(f"[watch] the {'/'.join(sorted(tried))} stream was refused; trying {f['height']}p "
                  f"(format {f['format_id']})", file=sys.stderr, flush=True)
            _, hit = _run(base + ["--load-info-json", str(out_dir / "video.info.json"),
                                  "-f", f"{f['format_id']}+ba/{f['format_id']}",
                                  "--merge-output-format", "mp4", "-o", output_template])
            limited = limited or hit
            video = _pick_video(out_dir, need_video=True)
            if video:
                note = (f"The site refused the first video stream it offered, so the {f['height']}p "
                        "stream was used instead.")
                break
            tried.add(str(f["format_id"]))
    if video is None:
        got = _pick_video(out_dir)
        if limited:
            raise SystemExit(RATE_LIMITED)
        raise SystemExit(
            f"The site sent only the audio; every video stream it offered was refused (yt-dlp exit {code})."
            if got and not audio_only else f"yt-dlp did not produce a video file in {out_dir} (exit {code})"
        )

    subtitle = _pick_subtitle(out_dir)
    info = _read_info(out_dir / "video.info.json", url)

    return {
        "video_path": str(video),
        "subtitle_path": str(subtitle) if subtitle else None,
        "info": info or {"url": url},
        "downloaded": True,
        "note": note,
    }


def download(
    source: str,
    out_dir: Path,
    audio_only: bool = False,
    cookies_from_browser: str | None = None,
    concurrency: int = 8,
    should_stop=None,
) -> dict:
    if is_url(source):
        return download_url(source, out_dir, audio_only=audio_only, cookies_from_browser=cookies_from_browser,
                            concurrency=concurrency, should_stop=should_stop)
    return resolve_local(source)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: download.py <url-or-path> <out-dir>", file=sys.stderr)
        raise SystemExit(2)
    result = download(sys.argv[1], Path(sys.argv[2]))
    print(json.dumps(result, indent=2))
