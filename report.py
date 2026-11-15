"""Render a finished run as one self-contained HTML report (images embedded)."""
from __future__ import annotations

import base64
import html
import json
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import i18n
from pipeline import fmt

T = dict(i18n.EN)   # the report's own words; build() switches them to the run's language

esc = html.escape
ALLOWED = {"h3", "h4", "p", "ul", "ol", "li", "strong", "em", "b", "i", "code", "pre", "blockquote",
           "table", "thead", "tbody", "tr", "th", "td", "br", "hr", "a"}
VOID = {"br", "hr"}
RENAME = {"h1": "h3", "h2": "h3", "h5": "h4", "h6": "h4"}
DROP_CONTENT = {"script", "style", "iframe", "object", "svg"}
_REF = r"(?:v\d+\s+)?\d{1,2}(?::\d{2}){1,2}(?:\s*[–—-]\s*\d{1,2}(?::\d{2}){1,2})?"
# {{frame:v1f003}}, or a bracketed citation: [04:15], [v2 04:15], [v2 00:31–01:06; v1 03:15]
TOKEN_RE = re.compile(r"\{\{\s*frame:\s*(v\d+f\d+)\s*\}\}|\[(" + _REF + r"(?:\s*[;,]\s*" + _REF + r")*)\]")
PART_RE = re.compile(r"(?:(v\d+)\s+)?(\d{1,2}(?::\d{2}){1,2})")

ENGINE_NAMES = {"claude": "Claude Code", "codex": "Codex", "claude_api": "Claude API", "openai_api": "OpenAI API"}
MODE_NAMES = {
    "interval": "Fixed interval", "count": "Fixed count", "scene": "Scene changes", "keyframes": "Keyframes",
    "dynamic": "Dynamic (model chooses)", "transcript": "Transcript only",
}


def data_uri(path: str) -> str:
    try:
        return "data:image/jpeg;base64," + base64.b64encode(Path(path).read_bytes()).decode("ascii")
    except OSError:
        return ""


def time_link(url: str | None, seconds: float) -> str | None:
    if not url:
        return None
    u = urlparse(url)
    host = u.netloc.lower()
    if not any(h in host for h in ("youtube.com", "youtu.be", "bilibili.com")):
        return None
    q = dict(parse_qsl(u.query))
    q["t"] = f"{int(seconds)}s" if "youtu" in host else str(int(seconds))
    return urlunparse(u._replace(query=urlencode(q)))


def _seconds(stamp: str) -> int:
    total = 0
    for part in stamp.split(":"):
        total = total * 60 + int(part)
    return total


class Sanitizer(HTMLParser):
    """Allowlist the model's HTML fragment and expand frame tokens / timestamps."""

    def __init__(self, videos: list[dict], images: dict | None = None):
        super().__init__(convert_charrefs=True)
        self.images = images   # when given, frames are embedded once per report (see build) instead of inline
        self.out: list[str] = []
        self.skip = 0
        self.videos = {v["id"]: v for v in videos}
        self.frames = {f["id"]: (f, v) for v in videos for f in v["frames"]}
        self.used: set[str] = set()

    def handle_starttag(self, tag, attrs):
        if tag in DROP_CONTENT:
            self.skip += 1
            return
        tag = RENAME.get(tag, tag)
        if self.skip or tag not in ALLOWED:
            return
        keep = ""
        for k, v in attrs:
            if tag == "a" and k == "href" and v and re.match(r"https?://", v):
                keep += f' href="{esc(v)}" target="_blank" rel="noopener noreferrer"'
            elif tag in ("td", "th") and k in ("colspan", "rowspan") and v and v.isdigit():
                keep += f' {k}="{v}"'
            elif tag == "blockquote" and k == "class" and v == "bg":
                keep += ' class="bg"'
        self.out.append(f"<{tag}{keep}>")

    def handle_endtag(self, tag):
        if tag in DROP_CONTENT:
            self.skip = max(0, self.skip - 1)
            return
        tag = RENAME.get(tag, tag)
        if not self.skip and tag in ALLOWED and tag not in VOID:
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(TOKEN_RE.sub(self._token, esc(data, quote=False)))

    def _token(self, m: re.Match) -> str:
        if m.group(1):
            hit = self.frames.get(m.group(1))
            if not hit:
                return ""
            f, v = hit
            self.used.add(f["id"])
            path = f.get("hd") or f["path"]
            if self.images is not None:
                self.images.setdefault(f["id"], data_uri(path))
                img = f'<img data-f="{esc(f["id"])}" alt="Frame at {fmt(f["t"])}">'
            else:
                img = f'<img src="{data_uri(path)}" alt="Frame at {fmt(f["t"])}">'
            return (f'<figure class="shot">{img}'
                    f'<figcaption><b>{fmt(f["t"])}</b> · {esc(f["id"])} · {esc(f["reason"])}</figcaption></figure>')
        out, vid = [], next(iter(self.videos)) if len(self.videos) == 1 else None
        for part in re.split(r"\s*[;,]\s*", m.group(2)):   # each moment its own chip; a range links to its start
            pm = PART_RE.match(part)
            vid = (pm.group(1) if pm and pm.group(1) else vid)
            link = time_link((self.videos.get(vid) or {}).get("url"), _seconds(pm.group(2))) if pm and vid else None
            out.append(f'<a class="ts" href="{esc(link)}" target="_blank" rel="noopener noreferrer">{part}</a>' if link
                       else f'<span class="ts">{part}</span>')
        return " ".join(out)


CSS = """
:root{--bg:#f6f5f1;--card:#fff;--ink:#1d1c1a;--mute:#6b6a65;--line:#e3e1da;--accent:#a5481f;--soft:#f1ede4;--bad:#a3281c}
@media (prefers-color-scheme:dark){:root{--bg:#161614;--card:#1f1f1c;--ink:#ebe9e3;--mute:#a09e97;--line:#34332f;--accent:#e58a5c;--soft:#2a2925;--bad:#ef8f84}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 "Segoe UI",system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:32px 20px 80px}
h1{font-size:28px;line-height:1.2;margin:0 0 6px}h2{font-size:21px;margin:0 0 4px;line-height:1.3}
h3{font-size:17px;margin:26px 0 8px}h4{font-size:15px;margin:18px 0 6px}
.sub{color:var(--mute);font-size:14px}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:24px;margin-top:22px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0 0}.chip{background:var(--soft);border-radius:999px;padding:2px 10px;font-size:13px;color:var(--mute)}
.chip b{color:var(--ink);font-weight:600}
table{border-collapse:collapse;width:100%;font-size:14px;margin:10px 0}th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mute);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.meta td:first-child{color:var(--mute);width:130px;white-space:nowrap}
a{color:var(--accent)}.ts{font-variant-numeric:tabular-nums;font-size:.9em;background:var(--soft);border-radius:5px;padding:1px 6px;text-decoration:none;white-space:nowrap}
.ask{border-left:3px solid var(--accent);background:var(--soft);padding:10px 14px;border-radius:0 8px 8px 0;margin:14px 0;white-space:pre-wrap;font-size:15px}
.analysis{margin-top:8px}.analysis p{margin:0 0 12px}.analysis pre{background:var(--soft);padding:12px;border-radius:8px;overflow:auto;font-size:13px}
.analysis code{background:var(--soft);padding:1px 5px;border-radius:4px;font-size:.9em}.analysis blockquote{margin:12px 0;padding-left:14px;border-left:3px solid var(--line);color:var(--mute)}
figure.shot{margin:16px 0;max-width:560px}figure.shot img,.grid img{width:100%;display:block;border-radius:8px;border:1px solid var(--line);cursor:zoom-in}
figcaption{font-size:13px;color:var(--mute);margin-top:5px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:12px;margin-top:12px}
.grid figure{margin:0}.grid figcaption{line-height:1.35}.tag{display:inline-block;font-size:11px;border:1px solid var(--line);border-radius:4px;padding:0 5px;margin-left:4px}
.tag.used{border-color:var(--accent);color:var(--accent)}
details{margin-top:18px;border-top:1px solid var(--line);padding-top:12px}summary{cursor:pointer;font-weight:600}
.transcript{white-space:pre-wrap;font:13px/1.55 Consolas,monospace;max-height:420px;overflow:auto;background:var(--soft);padding:12px;border-radius:8px;margin-top:10px}
.err{color:var(--bad);border:1px solid var(--bad);border-radius:8px;padding:10px 14px;margin:14px 0}.note{color:var(--mute);font-size:14px;margin:6px 0}
.summary{border-color:var(--accent);border-width:2px}
.depthbar{position:sticky;top:0;z-index:5;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 16px;margin:18px 0 0;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.depthbar input{flex:1;min-width:180px;accent-color:var(--accent)}.depthbar .stops{display:flex;gap:14px;font-size:13px;color:var(--mute)}
.depthbar .stops span{cursor:pointer}.depthbar .stops span.on{color:var(--ink);font-weight:600}
.toc{background:var(--soft);border-radius:8px;padding:12px 18px;margin:16px 0}.toc ol{margin:6px 0 0;padding-left:22px}.toc a{text-decoration:none}
.blk{border-top:1px solid var(--line);padding-top:14px;margin-top:22px}.bh{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.bh h3{margin:0;flex:1;min-width:240px}.bmeta{font-size:13px;color:var(--mute)}.local{font:inherit;font-size:12px;color:var(--mute);background:var(--card);border:1px solid var(--line);border-radius:6px;padding:1px 4px}
.lv{display:none}.lv.on{display:block}.lv p{margin:0 0 12px}.lvtag{font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--mute);margin:8px 0 4px}
blockquote.bg{border-left:3px solid #c9a227;background:rgba(201,162,39,.09);color:var(--ink);padding:8px 14px;border-radius:0 8px 8px 0;margin:14px 0}
.more{border-left:3px solid var(--accent);padding-left:14px;margin-top:14px}.more .lvtag{color:var(--accent)}
.dp{display:none;margin-top:12px;gap:8px;align-items:center;flex-wrap:wrap}.live .dp{display:flex}
.dp input{flex:1;min-width:220px;font:inherit;font-size:13px;padding:5px 9px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--ink)}
.dp button{font:inherit;font-size:13px;padding:5px 12px;border-radius:6px;border:1px solid var(--accent);background:var(--card);color:var(--accent);cursor:pointer}
h3.part{margin-top:34px;font-size:19px}
.wrap{overflow-x:auto}img.zoom{position:fixed;inset:0;margin:auto;max-width:96vw;max-height:96vh;width:auto;z-index:9;cursor:zoom-out;box-shadow:0 0 0 100vmax rgba(0,0,0,.8)}
"""


def _clean(text: str, videos: list[dict], images: dict | None, used: set) -> str:
    san = Sanitizer(videos, images)
    san.feed(text or "")
    san.close()
    used |= san.used
    return "".join(san.out)


CJK_RE = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯豈-﫿]")


def words(html_text: str) -> int:
    """Words, counting each Chinese, Japanese or Korean character as one (as word counts there do)."""
    text = re.sub(r"<[^>]+>|\{\{[^}]*\}\}", " ", html_text or "")
    return len(CJK_RE.findall(text)) + len(CJK_RE.sub(" ", text).split())


def _block(i: int, key: str, title: str, meta: str, b: dict, videos: list[dict], images: dict, used: set,
           default: str) -> str:
    """One section of a layered report: the same content at four depths, plus anything added later."""
    from deep import LEVELS
    opts = "".join(f'<option value="{lv}">{T[lv]}</option>' for lv in LEVELS)
    o = [f'<div class="blk" id="b{i}-{esc(key)}" data-unit="{i - 1}" data-key="{esc(key)}">',
         f'<div class="bh"><h3>{esc(title)}</h3><span class="bmeta">{meta}</span>'
         f'<select class="local" title="{T["section_depth"]}"><option value="">{T["as_report"]}</option>{opts}</select></div>']
    for lv in LEVELS:
        o.append(f'<div class="lv{" on" if lv == default else ""}" data-l="{lv}" data-w="{words(b.get(lv))}">'
                 f'{_clean(b.get(lv) or "", videos, images, used)}</div>')
    o.append('<div class="ext">')
    for x in b.get("extra") or []:
        o.append(f'<div class="more"><div class="lvtag">{T["deeper_tag"]}{": " + esc(x["focus"]) if x.get("focus") else ""}</div>{x["html"]}</div>')
    o.append(f'<!--ext:{i - 1}:{key}--></div>')
    o.append(f'<div class="dp"><input class="focus" placeholder="{esc(T["deeper_ph"])}">'
             f'<button class="deeper">{T["deeper"]}</button><span class="bmeta dpst"></span></div></div>')
    return "\n".join(o)


def _layered(i: int, u: dict, s: dict, images: dict, used: set) -> str:
    d = u["deep"]
    videos = u["videos"]
    default = d.get("default") or "detailed"
    o = []
    if d.get("intro"):
        o.append(f'<p class="note">{esc(d["intro"])}</p>')
    secs = {x["video"]: x for x in d.get("videos") or []}
    if d.get("chapters"):
        o.append(f'<nav class="toc"><b>{T["chapters"]}</b><ol>' + "".join(
            f'<li><a href="#b{i}-c{k}">{esc(c["title"])}</a></li>' for k, c in enumerate(d["chapters"], 1))
            + f'<li><a href="#b{i}-videos">{T["by_video"]}</a></li></ol></nav>')
        for k, c in enumerate(d["chapters"], 1):
            meta = f'{T["from"]} ' + ", ".join(c.get("videos") or []) + (f' · {T["core"]}' if c.get("weight") == "heavy" else "")
            o.append(_block(i, f"c{k}", f'{k}. {c["title"]}', meta, c, videos, images, used, default))
        o.append(f'<h3 class="part" id="b{i}-videos">{T["by_video"]}</h3>')
    for v in videos:
        sec = secs.get(v["id"])
        if sec:
            o.append(_block(i, v["id"], f'{v["id"]}: {v["title"]}' if len(videos) > 1 else v["title"],
                            fmt(v["duration"]), sec, videos, images, used, default))
    return "\n".join(o)


def _unit_html(i: int, u: dict, s: dict, images: dict | None = None) -> str:
    videos = u["videos"]
    used: set = set()
    if u.get("deep"):
        analysis = _layered(i, u, s, images if images is not None else {}, used)
    else:
        analysis = _clean(u.get("analysis") or "", videos, None, used)
    title = u.get("label") or (videos[0]["title"] if len(videos) == 1 else T["bundle"].format(n=len(videos)))
    o = [f'<section class="card" id="item-{i}"><div class="sub">{T["item"]} {i}</div><h2>{esc(str(title))}</h2>']

    rows = []
    for v in videos:
        src = f'<a href="{esc(v["url"])}" target="_blank" rel="noopener noreferrer">{esc(v["source"])}</a>' if v.get("url") else esc(v["source"])
        bits = [fmt(v["duration"])]
        if v.get("width"):
            bits.append(f'{v["width"]}×{v["height"]}')
        if v.get("range"):
            bits.append(T["watched_range"].format(a=fmt(v["range"][0]), b=fmt(v["range"][1])))
        rows.append(
            f'<tr><td>{esc(v["id"])}</td><td><b>{esc(str(v["title"]))}</b>'
            + (f' · {esc(v["uploader"])}' if v.get("uploader") else "")
            + f'<br>{src}</td><td>{" · ".join(bits)}</td><td>{len(v["frames"])}<br><span class="sub">{esc(v["frame_note"])}</span></td>'
            f'<td>{len(v["transcript"])} {T["lines"]}<br><span class="sub">{esc(v["transcript_source"] or T["none"])}</span></td></tr>'
        )
    if rows:
        o.append(f'<div class="wrap"><table><thead><tr><th>{T["col_id"]}</th><th>{T["col_video"]}</th><th>{T["col_length"]}</th>'
                 f'<th>{T["col_frames"]}</th><th>{T["col_transcript"]}</th></tr></thead><tbody>'
                 + "".join(rows) + "</tbody></table></div>")
    for v in videos:
        for note in v.get("notes") or []:
            o.append(f'<p class="note">{esc(v["id"])}: {esc(note)}</p>')

    task = u.get("instructions") or s.get("default_instructions")
    o.append(f'<div class="ask">{esc(task)}</div>' if task else f'<p class="note">{T["no_ask"]}</p>')
    if u.get("error"):
        o.append(f'<div class="err"><b>{T["unclean"]}</b> {esc(u["error"])}</div>')
    if analysis.strip():
        o.append(f'<div class="analysis">{analysis}</div>')

    if u.get("rounds"):
        o.append(f'<h3>{T["sel_log"]}</h3><p class="note">{T["sel_note"]}</p>')
        frames = {f["id"]: (f, v) for v in videos for f in v["frames"]}
        for r in u["rounds"]:
            o.append('<h4>' + T["round"].format(r=r["round"], a=r["requested"], e=len(r["extracted"]))
                     + (', ' + T["skipped"].format(n=r["skipped"]) if r.get("skipped") else "") + "</h4>")
            o.append(f'<div class="wrap"><table><thead><tr><th>{T["col_frame"]}</th><th>{T["col_time"]}</th><th>{T["col_why"]}</th></tr></thead><tbody>')
            for fid in r["extracted"]:
                f, _ = frames[fid]
                o.append(f'<tr><td>{esc(fid)}</td><td><span class="ts">{fmt(f["t"])}</span> <span class="sub">{f["t"]:.2f}s</span></td><td>{esc(f["reason"])}</td></tr>')
            o.append("</tbody></table></div>")

    total = sum(len(v["frames"]) for v in videos)
    if total and s.get("report_gallery"):
        o.append(f'<details{" open" if total <= 24 else ""}><summary>{T["all_frames"].format(n=total)}</summary>')
        for v in videos:
            if len(videos) > 1:
                o.append(f'<h4>{esc(v["id"])}: {esc(str(v["title"]))}</h4>')
            o.append('<div class="grid">')
            for f in sorted(v["frames"], key=lambda f: f["t"]):
                origin = f"round {f['round']}" if f.get("round") else f["origin"]
                used_tag = f'<span class="tag used">{T["cited"]}</span>' if f["id"] in used else ""
                if f.get("viewed") is False:
                    used_tag += f'<span class="tag">{T["not_opened"]}</span>'
                o.append(f'<figure><img loading="lazy" src="{data_uri(f.get("small") or f["path"])}" alt="Frame at {fmt(f["t"])}">'
                         f'<figcaption><b>{fmt(f["t"])}</b> · {esc(f["id"])}<span class="tag">{esc(origin)}</span>{used_tag}<br>{esc(f["reason"])}</figcaption></figure>')
            o.append("</div>")
        o.append("</details>")
    elif total:
        times = ", ".join(fmt(f["t"]) for v in videos for f in sorted(v["frames"], key=lambda f: f["t"]))
        o.append(f'<details><summary>{T["frame_times"].format(n=total)}</summary><p class="note">{times}</p></details>')

    if s.get("report_transcript"):
        for v in videos:
            if v["transcript_text"]:
                o.append(f'<details><summary>{T["transcript"]}: {esc(v["id"])} ({esc(v["transcript_source"] or "")})</summary>'
                         f'<div class="transcript">{esc(v["transcript_text"])}</div></details>')

    m = u.get("llm") or {}
    foot = [f'{esc(ENGINE_NAMES.get(u["engine"], u["engine"]))} · {esc(str(m.get("model") or "CLI default"))}', f'{u.get("seconds", 0):.0f}s']
    if m.get("cost"):
        foot.append(f'${m["cost"]:.2f}')
    if m.get("tokens"):
        foot.append(f'{m["tokens"]:,} tokens')
    o.append(f'<p class="sub" style="margin:18px 0 0">{" · ".join(foot)}</p>')
    if u.get("stages"):
        o.append(f'<p class="sub" style="margin:2px 0 0">{T["per_stage"]}: ' + " · ".join(f'{esc(st["name"])} {st.get("seconds", 0):.0f}s' for st in u["stages"]) + "</p>")
    o.append("</section>")
    return "\n".join(o)


def _summary_html(run: dict) -> str:
    """The orchestrator's combined summary, and in an overview report the list of where each item went."""
    summ = run.get("summary") or {}
    over = run.get("overview")
    units = run["units"]
    if over:   # [v2 04:15] in an overview points at item 2 of the whole batch
        refs = [{"id": f"v{o['item']}", "url": o.get("url"), "frames": []} for o in over]
    else:
        refs = [{"id": f"v{i}", "url": (u["videos"][0].get("url") if len(u.get("videos") or []) == 1 else None), "frames": []}
                for i, u in enumerate(units, 1)]
    o = [f'<section class="card summary"><div class="sub">{T["combined"]}'
         + (f' · {T["by_orch"]}, {esc(ENGINE_NAMES.get(summ.get("engine"), summ.get("engine") or ""))}' if summ else "") + '</div>'
         f'<h2>{T["glance"] if over else T["across"].format(n=len(units))}</h2>']
    if summ.get("analysis"):
        san = Sanitizer(refs)
        san.feed(summ["analysis"])
        san.close()
        o.append(f'<div class="analysis">{"".join(san.out)}</div>')
    elif summ.get("error"):
        o.append(f'<div class="err"><b>{T["summary_failed"]}</b> {esc(summ["error"])}</div>')
    if over:
        o.append(f'<h3>{T["where"]}</h3><div class="wrap"><table><thead><tr><th>{T["col_item"]}</th><th>{T["col_video"]}</th>'
                 f'<th>{T["col_length"]}</th><th>{T["col_category"]}</th><th>{T["col_report"]}</th></tr></thead><tbody>')
        for it in over:
            src = f' · <a href="{esc(it["url"])}" target="_blank" rel="noopener noreferrer">{T["source"]}</a>' if it.get("url") else ""
            rep = (f'<a href="../{esc(it["report"])}/report.html">{esc(it["report_title"] or T["open"])}</a>' if it.get("report") else "")
            o.append(f'<tr><td>{it["item"]}</td><td><b>{esc(str(it["title"]))}</b>{src}'
                     + (f' <span class="tag">{T["failed"]}</span>' if it.get("error") else "")
                     + f'</td><td>{fmt(it.get("duration") or 0)}</td><td>{esc(it.get("category") or "")}</td><td>{rep}</td></tr>')
        o.append(f'</tbody></table></div><p class="note">{T["links_note"]}</p>')
    elif len(units) > 1:
        o.append(f'<p class="note">{T["items"]}: ' + " · ".join(
            f'<a href="#item-{i}">{i}. {esc(str(u["videos"][0]["title"] if len(u.get("videos") or []) == 1 else u.get("label") or "Bundle"))}</a>'
            for i, u in enumerate(units, 1)) + "</p>")
    if summ:
        foot = [esc(str(summ.get("model") or "")), f'{summ.get("seconds", 0):.0f}s']
        if summ.get("cost"):
            foot.append(f'${summ["cost"]:.2f}')
        o.append(f'<p class="sub" style="margin:14px 0 0">{" · ".join(x for x in foot if x)}</p>')
    o.append("</section>")
    return "\n".join(o)


LAYER_JS = """<script>
(function(){
var RUN=__RUN__,IMG=__IMAGES__,T=__T__,L=['gist','summary','detailed','deep'];
document.querySelectorAll('img[data-f]').forEach(function(im){var s=IMG[im.getAttribute('data-f')];if(s)im.src=s;});
var r=document.getElementById('depth'),g=L[r.value-1];
try{var k=localStorage.getItem('vw-depth-'+RUN);if(k&&L.indexOf(k)>=0){g=k;r.value=L.indexOf(k)+1;}}catch(e){}
function apply(){var total=0;document.querySelectorAll('.blk').forEach(function(b){var lv=b.querySelector('.local').value||g;
b.querySelectorAll('.lv').forEach(function(d){var on=d.getAttribute('data-l')===lv;d.classList.toggle('on',on);if(on)total+=+d.getAttribute('data-w');});
b.querySelector('.ext').style.display=lv==='deep'?'':'none';});
document.querySelectorAll('.stops span').forEach(function(x){x.classList.toggle('on',x.getAttribute('data-l')===g);});
document.getElementById('depthw').textContent=T.words_at.replace('{n}',total.toLocaleString());}
r.addEventListener('input',function(){g=L[r.value-1];try{localStorage.setItem('vw-depth-'+RUN,g);}catch(e){}apply();});
document.querySelectorAll('.stops span').forEach(function(x){x.onclick=function(){g=x.getAttribute('data-l');r.value=L.indexOf(g)+1;apply();};});
document.querySelectorAll('.local').forEach(function(x){x.onchange=apply;});
apply();
if(/^https?:/.test(location.protocol)){fetch('/api/ping').then(function(){document.body.classList.add('live');}).catch(function(){});}
document.querySelectorAll('.deeper').forEach(function(btn){btn.onclick=function(){
var b=btn.closest('.blk'),st=b.querySelector('.dpst'),f=b.querySelector('.focus');btn.disabled=true;st.textContent=T.writing_more;
fetch('/api/deeper',{method:'POST',headers:{'Content-Type':'application/json','X-Video-Watch':'1'},
body:JSON.stringify({run:RUN,unit:+b.getAttribute('data-unit'),key:b.getAttribute('data-key'),focus:f.value})})
.then(function(x){return x.json().then(function(j){if(!x.ok)throw new Error(j.error||x.statusText);return j;});})
.then(function(j){var d=document.createElement('div');d.className='more';d.innerHTML='<div class="lvtag">'+T.deeper_tag+(f.value?': '+f.value.replace(/[<>&]/g,''):'')+'</div>'+j.html;
b.querySelector('.ext').insertBefore(d,null);b.querySelector('.local').value='deep';apply();st.textContent=T.added;f.value='';d.scrollIntoView({behavior:'smooth'});})
.catch(function(e){st.textContent=T.deeper_fail+' '+e.message;}).finally(function(){btn.disabled=false;});};});
})();
</script>"""


def build(run: dict) -> str:
    s = run["settings"]
    units = run["units"]
    T.clear()
    T.update(i18n.strings(s))
    lang = i18n.code(s)
    mode = T.get("mode_" + s["mode"], MODE_NAMES.get(s["mode"], s["mode"]))
    detail = {
        "interval": f'every {s["interval_value"]:g} {s["interval_unit"]}',
        "count": f'{s["count"]} per video',
        "dynamic": f'{s["dynamic_overview"]} overview + up to {s["dynamic_budget"]} requested in {s["dynamic_rounds"]} rounds',
    }.get(s["mode"], "")
    if lang != "en":   # the detail line is plain settings; keep it short rather than half-translated
        detail = {"interval": f'{s["interval_value"]:g} {"秒" if s["interval_unit"] == "seconds" else "分钟" if lang == "zh-Hans" else "分鐘"}'}.get(s["mode"], "")
    chips = [(T["watched"], mode + (f" ({detail})" if detail else "")),
             (T["engine"], ", ".join(sorted({ENGINE_NAMES.get(u["engine"], u["engine"]) for u in units}))
              or ENGINE_NAMES.get(s["engine"], s["engine"]))]
    if run.get("overview"):
        chips.append((T["in_batch"], str(len(run["overview"]))))
    else:
        chips += [(T["items"], str(len(units))),
                  (T["videos"], str(sum(len(u["videos"]) for u in units))),
                  (T["frames"], str(sum(len(v["frames"]) for u in units for v in u["videos"])))]
    if s["mode"] not in ("transcript",):
        chips.append((T["frame_width"], f'{s["resolution"]}px'))
    title = run.get("title") or T["default_title"]
    when = datetime.fromisoformat(run["started"]).strftime("%d %b %Y, %H:%M")
    images: dict = {}
    body = "\n".join(([_summary_html(run)] if run.get("summary") or run.get("overview") else [])
                     + [_unit_html(i, u, s, images) for i, u in enumerate(units, 1)])
    layered = any(u.get("deep") for u in units)
    if layered:
        from deep import LEVELS
        default = next((u["deep"].get("default") for u in units if u.get("deep")), "detailed")
        bar = (f'<div class="depthbar"><b>{T["depth"]}</b><input type="range" id="depth" min="1" max="4" step="1" '
               f'value="{LEVELS.index(default) + 1}" aria-label="{T["depth"]}"><div class="stops">'
               + "".join(f'<span data-l="{lv}">{T[lv]}</span>' for lv in LEVELS)
               + '</div><span class="sub" id="depthw"></span></div>')
        body = bar + "\n" + body
    script = (LAYER_JS.replace("__RUN__", json.dumps(run["id"])).replace("__T__", json.dumps(T, ensure_ascii=False))
              .replace("__IMAGES__", json.dumps(images))) if layered else ""
    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><style>{CSS}</style></head><body><main>
<h1>{esc(title)}</h1><div class="sub">{when} · {T["run"]} {esc(run["id"])}</div>
<div class="chips">{"".join(f'<span class="chip">{k}: <b>{esc(v)}</b></span>' for k, v in chips)}</div>
{body}
</main>{script}<script>document.addEventListener('click',function(e){{var z=document.querySelector('img.zoom');if(z){{z.classList.remove('zoom');return}}if(e.target.matches('figure img'))e.target.classList.add('zoom')}})</script>
</body></html>"""
