"""Turn one video source into frames + transcript, according to the watch settings.

Built on the /watch skill's scripts (vendored in watchlib/): yt-dlp download and
captions, ffmpeg frame extraction, Whisper/Gemini transcription fallback.
"""
from __future__ import annotations

import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

LIB = Path(__file__).parent / "watchlib"
sys.path.insert(0, str(LIB))

import frames as F  # noqa: E402
from download import download, fetch_captions, has_video, is_url  # noqa: E402
from transcribe import filter_range, format_transcript, parse_vtt  # noqa: E402
from whisper import load_api_keys, transcribe_video  # noqa: E402

# No model reads more than a few hundred images usefully in one sitting.
HARD_CAP = 400     # default safety limit on frames per video (the "frame_limit" setting)
MAX_LIMIT = 5000   # the highest that limit can be set
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def fmt(t: float) -> str:
    return F.format_time(t)


def never() -> bool:
    return False


def grab_frames(video: str, out_dir: Path, times: list[float], resolution: int, tag: str,
                cancelled=never) -> list[tuple[float, str | None]]:
    """One exact frame per timestamp. Returns (time, path-or-None) in input order.
    cancelled: the run's Stop flag (each run has its own, so stopping one leaves the others)."""
    out_dir.mkdir(parents=True, exist_ok=True)

    def one(item: tuple[int, float]) -> tuple[float, str | None]:
        i, t = item
        if cancelled():
            return (t, None)
        path = out_dir / f"{tag}_{i:04d}.jpg"
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{t:.3f}", "-i", str(video),
            "-frames:v", "1", "-vf", F._scale_filter(resolution), "-q:v", "4", str(path),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW)
        ok = r.returncode == 0 and path.exists() and path.stat().st_size > 0
        return (t, str(path) if ok else None)

    with ThreadPoolExecutor(4) as ex:
        return list(ex.map(one, enumerate(times)))


def compress_frames(frames: list[dict], width: int, quality: int, cancelled=never) -> tuple[int, int]:
    """Smaller copies of frames for the report gallery (sets f["small"]). Returns bytes (before, after).
    quality is 10..100; a copy that does not come out smaller is dropped."""
    q = str(max(2, min(31, round(31 - quality / 100 * 29))))

    def one(f: dict) -> tuple[int, int]:
        if cancelled():
            return (0, 0)
        src = Path(f["path"])
        dst = src.with_name(src.stem + "_small.jpg")
        try:
            before = src.stat().st_size
        except OSError:
            return (0, 0)
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
               "-vf", f"scale='min({int(width)},iw)':-2", "-q:v", q, str(dst)]
        r = subprocess.run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW)
        if r.returncode == 0 and dst.exists() and 0 < dst.stat().st_size < before:
            f["small"] = str(dst)
            return (before, dst.stat().st_size)
        return (before, before)

    with ThreadPoolExecutor(4) as ex:
        sizes = list(ex.map(one, frames))
    return (sum(a for a, _ in sizes), sum(b for _, b in sizes))


def label_frames(frames: list[dict], out_dir: Path) -> dict[str, str]:
    """Copies of frames with an id/time strip burnt in, for engines that receive
    images as unlabelled attachments. Returns {frame id: labelled path}; a frame
    that fails to label maps to its original."""
    out_dir.mkdir(parents=True, exist_ok=True)

    def one(f: dict) -> tuple[str, str]:
        t = int(round(f["t"]))
        h, rem = divmod(t, 3600)
        stamp = (f"{h}h" if h else "") + f"{rem // 60:02d}m{rem % 60:02d}s"
        out = out_dir / f"{f['id']}.jpg"
        vf = (
            "pad=iw:ih+26:0:26:black,"
            "drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':"
            f"text='{f['id']}  {stamp}':fontcolor=white:fontsize=17:x=6:y=5"
        )
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", f["path"], "-vf", vf, "-q:v", "4", str(out)],
            capture_output=True, text=True, creationflags=NO_WINDOW,
        )
        return f["id"], (str(out) if r.returncode == 0 and out.exists() else f["path"])

    with ThreadPoolExecutor(4) as ex:
        return dict(ex.map(one, frames))


def _parse_subs(dl: dict, log) -> tuple[list[dict], str | None]:
    if not dl.get("subtitle_path"):
        return [], None
    try:
        return parse_vtt(dl["subtitle_path"]), "captions"
    except Exception as exc:  # noqa: BLE001
        log(f"caption parse failed: {exc}")
        return [], None


def prepare_video(source: str, vdir: Path, s: dict, start: str | None, end: str | None, log, stage=None,
                  cancelled=never) -> dict:
    stage = stage or (lambda name: None)
    mode = s["mode"]
    cookies = s.get("cookies_browser") or None
    url = is_url(source)
    notes: list[str] = []
    dl: dict = {"subtitle_path": None, "info": {}}
    segs: list[dict] = []
    tsrc: str | None = None

    if url and s["use_captions"]:
        stage("captions")
        log("checking metadata and captions")
        dl = fetch_captions(source, vdir / "download", cookies_from_browser=cookies)
        segs, tsrc = _parse_subs(dl, log)

    need_video = mode != "transcript"
    video_path: str | None = None
    if need_video or (not segs and s["whisper"]):
        if url:
            stage("download")
            log("downloading " + ("video" if need_video else "audio"))
            # Sites sometimes refuse a download for a while (Bilibili answers HTTP 567 to bursts),
            # so try again more gently before giving up.
            limited = False
            for attempt, (wait, streams) in enumerate(((0, 8), (8, 1), (25, 1)), 1):
                if wait:
                    wait *= 4 if limited else 1   # a rate limit needs a longer pause than a hiccup
                    log(f"download failed; trying again in {wait}s with a single connection (attempt {attempt} of 3)")
                    for _ in range(wait * 2):
                        if cancelled():
                            raise SystemExit("cancelled")
                        time.sleep(0.5)
                try:
                    dl2 = download(source, vdir / "download", audio_only=not need_video,
                                   cookies_from_browser=cookies, concurrency=streams, should_stop=cancelled)
                    if dl2.get("note"):
                        notes.append(dl2["note"])
                        log(dl2["note"])
                    break
                except SystemExit as exc:
                    if cancelled():
                        raise SystemExit("cancelled") from None
                    limited = "HTTP 567" in str(exc)
                    if attempt == 3:
                        raise SystemExit(
                            f"{exc} It refused three tries over about two minutes. Wait 15 to 30 minutes and "
                            "watch this video again; fewer Bilibili videos in one run also helps." if limited else
                            f"{exc} The site refused the download three times; it may be blocking this connection "
                            "for now, or the video may need a login (see Sign-in for video sites).") from None
        else:
            dl2 = download(source, vdir / "download")
            if need_video and not has_video(Path(dl2["video_path"])):
                notes.append("This file has no picture (audio only), so there are no frames; "
                             "the analysis uses the transcript.")
                need_video = False
        video_path = dl2["video_path"]
        info = dl2.get("info") or {}
        dl = {**dl2, "info": {**(dl.get("info") or {}), **{k: v for k, v in info.items() if v}}}
        if not segs and s["use_captions"]:
            segs, tsrc = _parse_subs(dl, log)

    info = dl.get("info") or {}
    meta = F.get_metadata(video_path) if video_path else {
        "duration_seconds": float(info.get("duration") or 0), "width": None, "height": None, "has_audio": False,
    }
    duration = meta["duration_seconds"]

    start_sec = F.parse_time(start)
    end_sec = F.parse_time(end)
    if end_sec is not None and duration and end_sec > duration:
        end_sec = None
    if start_sec is not None and duration and start_sec >= duration:
        raise SystemExit(f"start {start} is past the end of the video ({fmt(duration)})")
    if start_sec is not None and end_sec is not None and end_sec <= start_sec:
        raise SystemExit("range end must be after range start")
    focused = start_sec is not None or end_sec is not None
    lo = start_sec or 0.0
    hi = end_sec if end_sec is not None else duration
    span = max(0.0, hi - lo)

    limit = int(s.get("frame_limit") or HARD_CAP)
    auto = not int(s.get("max_frames") or 0)   # cap 0 = automatic: as many frames as the mode asks for
    cap = limit if auto else min(int(s["max_frames"]), limit)
    res = int(s["resolution"])
    fdir = vdir / "frames"
    frames: list[dict] = []
    frame_note = ""

    def timed(times: list[float], reason: str, origin: str, tag: str) -> list[dict]:
        times = [min(t, max(0.0, duration - 0.25)) for t in times]
        got = grab_frames(video_path, fdir, times, res, tag, cancelled)
        missed = sum(1 for _, p in got if p is None)
        if missed:
            notes.append(f"{missed} frame(s) could not be extracted")
        return [{"t": round(t, 2), "path": p, "reason": reason, "origin": origin} for t, p in got if p]

    if video_path and need_video and span > 0:
        stage("frames")
        if mode == "interval":
            unit = s["interval_unit"]
            step = max(0.1, float(s["interval_value"]) * (60 if unit == "minutes" else 1))
            times = [lo + i * step for i in range(int(span // step) + 1) if lo + i * step < hi]
            asked = len(times)
            every = f"every {s['interval_value']:g} {unit}"
            if asked > cap:  # say so everywhere: the frames are no longer at the interval asked for
                times = [times[i] for i in F._even_indices(asked, cap)]
                actual = span / cap
                which = "safety limit" if auto or cap == limit else "frame cap"
                every = f"about every {actual:.0f}s (asked {s['interval_value']:g} {unit}, {which} {cap} frames)"
                notes.append(
                    f"One frame every {s['interval_value']:g} {unit} would be {asked} frames; the {which} "
                    f"is {cap}, so they were thinned to about one every {actual:.0f} seconds. "
                    + (f"Raise 'Safety limit' to {asked} or more to get the full interval." if which == "safety limit"
                       else f"Raise 'Frame cap per video' to {asked} or more, or set it to 0 (automatic).")
                )
                log(f"{which} {cap} is below the {asked} frames asked for: thinning to about one every {actual:.0f}s")
            log(f"extracting {len(times)} frames, one {every}")
            frames = timed(times, every, "interval", "iv")
            frame_note = f"{len(frames)} frames, one {every}"
        elif mode == "count":
            n = max(1, min(int(s["count"]), cap))
            log(f"extracting {n} evenly spaced frames")
            frames = timed([lo + (i + 0.5) * span / n for i in range(n)], "evenly spaced", "count", "ct")
            frame_note = f"{len(frames)} evenly spaced frames"
        elif mode in ("scene", "keyframes"):
            log("extracting " + ("scene-change frames" if mode == "scene" else "keyframes"))
            if mode == "scene":
                fps, target = (F.auto_fps_focus if focused else F.auto_fps)(span, max_frames=cap)
                raw, fm = F.extract_scene_or_uniform(
                    video_path, fdir, fps=fps, target_frames=target, resolution=res, max_frames=cap,
                    start_seconds=start_sec, end_seconds=end_sec, dedup=bool(s["dedup"]),
                )
            else:
                raw, fm = F.extract_keyframes(
                    video_path, fdir, resolution=res, max_frames=cap,
                    start_seconds=start_sec, end_seconds=end_sec, dedup=bool(s["dedup"]),
                )
            frames = [
                {"t": f["timestamp_seconds"], "path": f["path"], "reason": f.get("reason", "selected"), "origin": mode}
                for f in raw
            ]
            frame_note = (
                f"{fm.get('selected_count', len(frames))} selected from {fm.get('candidate_count', len(frames))} "
                f"candidates ({fm.get('engine')}{', uniform fallback' if fm.get('fallback') else ''}"
                f"{', %d near-duplicates dropped' % fm['deduped_count'] if fm.get('deduped_count') else ''})"
            )
        elif mode == "dynamic":
            n = max(0, min(int(s["dynamic_overview"]), cap))
            if n:
                log(f"extracting {n} overview frames")
                frames = timed([lo + (i + 0.5) * span / n for i in range(n)], "overview", "overview", "ov")
            frame_note = "chosen by the model (see frame selection log)"

    if video_path and need_video and span > 0 and not frames and mode != "dynamic":
        notes.append("No frames could be extracted from this video, so the analysis rests on the transcript alone.")
        log("warning: no frames could be extracted")

    # Transcription fallback when the platform had no captions.
    if not segs and s["whisper"] and video_path and meta.get("has_audio"):
        backends = load_api_keys(s.get("whisper_backend") or None)
        if not backends:
            notes.append("No captions and no transcription API key configured, so there is no transcript.")
        for backend, key in backends:
            stage("transcribe")
            try:
                log(f"transcribing audio via {backend}")
                segs, used = transcribe_video(video_path, vdir / "audio.mp3", backend=backend, api_key=key)
                tsrc = "gemini" if used == "gemini" else f"whisper ({used})"
                break
            except (SystemExit, Exception) as exc:  # noqa: BLE001
                log(f"{backend} transcription failed: {exc}")
    if focused and segs:
        segs = filter_range(segs, start_sec, end_sec)

    return {
        "source": source,
        "url": info.get("url") if url else None,
        "title": info.get("title") or source,
        "uploader": info.get("uploader"),
        "duration": duration,
        "width": meta.get("width"),
        "height": meta.get("height"),
        "video_path": video_path if need_video else None,
        "downloaded": url,
        "range": [lo, hi] if focused else None,
        "span": [lo, hi],
        "transcript": segs,
        "transcript_text": format_transcript(segs) if segs else "",
        "transcript_source": tsrc,
        "frames": frames,
        "frame_note": frame_note,
        "notes": notes,
    }
