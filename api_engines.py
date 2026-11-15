"""Watch with an API key instead of a CLI login: the Claude API (Anthropic SDK), or any provider
with an OpenAI-compatible Chat Completions endpoint (OpenAI, Gemini, OpenRouter, DeepSeek, Qwen,
Kimi, GLM, Grok, Mistral, Groq, a local Ollama or LM Studio, or one you name). Frames go in as
attached images, like Codex.

Keys are typed into the app once and stored encrypted for this Windows user (DPAPI) in
keys.json next to the settings, one per provider; a key in the provider's usual environment
variable is used when none is saved. The page only ever sees the last four characters.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

PROVIDERS = {"claude_api": "anthropic", "openai_api": "openai"}   # engine -> provider (openai_api: see PRESETS)

# Providers reached through the OpenAI-compatible engine. images: most images one request may carry
# (0 = the model cannot see images); max_tokens: reply limit to ask for (0 = leave to the provider).
# The limits are cautious defaults as of late 2026: they change with each model, and every one can be
# overridden in the app.
PRESETS = {
    "openai": {"name": "OpenAI", "base": "https://api.openai.com/v1", "env": "OPENAI_API_KEY",
               "site": "platform.openai.com (API keys)", "images": 100, "max_tokens": 0,
               "limits": "All current GPT models see images. Billed per token to your OpenAI API account, which "
                         "is separate from a ChatGPT subscription."},
    "gemini": {"name": "Google Gemini", "base": "https://generativelanguage.googleapis.com/v1beta/openai",
               "env": "GEMINI_API_KEY", "site": "aistudio.google.com (Get API key)", "images": 100, "max_tokens": 32000,
               "limits": "Uses Google's OpenAI-compatible endpoint, which supports fewer options than Gemini's own "
                         "API. Free-tier keys allow only a few requests per minute: set Sub-agents at once to 1 or 2."},
    "openrouter": {"name": "OpenRouter", "base": "https://openrouter.ai/api/v1", "env": "OPENROUTER_API_KEY",
                   "site": "openrouter.ai/keys", "images": 50, "max_tokens": 16000,
                   "limits": "One key for hundreds of models from many companies. Only models that list image input "
                             "can see frames, and the image limit and price depend on the model you pick."},
    "deepseek": {"name": "DeepSeek", "base": "https://api.deepseek.com/v1", "env": "DEEPSEEK_API_KEY",
                 "site": "platform.deepseek.com (API keys)", "images": 20, "max_tokens": 8192,
                 "limits": "Only DeepSeek's vision-capable flash model sees images (added August 2026); its other "
                           "models read text only, so set 'Can see images' to No for them. Replies stop at about "
                           "8,000 tokens, so deep dives come out shorter."},
    "qwen": {"name": "Alibaba Qwen (DashScope)", "base": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
             "env": "DASHSCOPE_API_KEY", "site": "Alibaba Cloud Model Studio (API keys)", "images": 20, "max_tokens": 8192,
             "limits": "Only the VL models (names with vl, such as qwen-vl-max) see images. Accounts in mainland "
                       "China use https://dashscope.aliyuncs.com/compatible-mode/v1 as the address."},
    "moonshot": {"name": "Moonshot Kimi", "base": "https://api.moonshot.ai/v1", "env": "MOONSHOT_API_KEY",
                 "site": "platform.moonshot.ai (API keys)", "images": 20, "max_tokens": 8192,
                 "limits": "Only vision models see images. Mainland China accounts use https://api.moonshot.cn/v1. "
                           "Older models have short context windows, so long transcripts are cut."},
    "zhipu": {"name": "Zhipu GLM", "base": "https://open.bigmodel.cn/api/paas/v4", "env": "ZHIPUAI_API_KEY",
              "site": "open.bigmodel.cn (API keys)", "images": 5, "max_tokens": 8192,
              "limits": "Only the GLM-V models (names with v, such as glm-4.5v) see images, and they take few "
                        "images per request, so a long video needs many calls. Not tested with this app."},
    "xai": {"name": "xAI Grok", "base": "https://api.x.ai/v1", "env": "XAI_API_KEY", "site": "console.x.ai",
            "images": 10, "max_tokens": 16000,
            "limits": "Only Grok models with image input see frames. Not tested with this app."},
    "mistral": {"name": "Mistral", "base": "https://api.mistral.ai/v1", "env": "MISTRAL_API_KEY",
                "site": "console.mistral.ai (API keys)", "images": 8, "max_tokens": 16000,
                "limits": "Pixtral and the newer Medium and Small models see images. Mistral sets no fixed image "
                          "limit (it depends on the model's token budget), so 8 per request is a cautious default."},
    "groq": {"name": "Groq", "base": "https://api.groq.com/openai/v1", "env": "GROQ_API_KEY",
             "site": "console.groq.com/keys", "images": 3, "max_tokens": 8192,
             "limits": "Very fast, but its vision models take only 3 to 5 images per request, so a long video "
                       "becomes many small calls, and free-tier rate limits are low."},
    "ollama": {"name": "Ollama (on this computer)", "base": "http://localhost:11434/v1", "env": "", "keyless": True,
               "site": "", "images": 8, "max_tokens": 0,
               "limits": "Free and private: runs on your own computer. Pull a vision model first (for example "
                         "ollama pull qwen2.5vl). Ollama's default context is small, so set OLLAMA_CONTEXT_LENGTH to "
                         "32768 or more, or long prompts are cut without warning. Much slower than cloud models, "
                         "and small local models write much thinner reports."},
    "lmstudio": {"name": "LM Studio (on this computer)", "base": "http://localhost:1234/v1", "env": "", "keyless": True,
                 "site": "", "images": 8, "max_tokens": 0,
                 "limits": "Free and private. Load a vision model and start LM Studio's local server; set a large "
                           "context length when loading it. Slow, and small models write thin reports."},
    "custom": {"name": "Another OpenAI-compatible service", "base": "", "env": "", "site": "", "images": 10,
               "max_tokens": 8192,
               "limits": "Any service with an OpenAI Chat Completions endpoint that accepts base64 images (for "
                         "example Together, Fireworks, a company gateway or a self-hosted vLLM). Enter its address, "
                         "and set whether the model sees images and how many it takes per request."},
}
NOT_SUPPORTED = ("Not supported: Azure OpenAI (it needs a deployment-specific address and an api-key header), "
                 "Amazon Bedrock, Google Vertex AI, and providers without an OpenAI-compatible endpoint.")
ENV_VARS = {"anthropic": "ANTHROPIC_API_KEY", **{k: p["env"] for k, p in PRESETS.items()}}
NAMES = {"anthropic": "Claude API", **{k: p["name"] for k, p in PRESETS.items()}}


def provider(engine: str, s: dict) -> str:
    """The key and preset an engine uses: "anthropic", or the chosen OpenAI-compatible provider."""
    if engine == "claude_api":
        return "anthropic"
    p = (s.get("openai_api_provider") or "openai").strip()
    return p if p in PRESETS else "openai"


def preset(s: dict) -> dict:
    return PRESETS[provider("openai_api", s)]


def sees_images(engine: str, s: dict) -> bool:
    if engine != "openai_api":
        return True
    v = (s.get("openai_api_vision") or "").strip()
    return v == "yes" if v in ("yes", "no") else preset(s)["images"] > 0


def image_limit(engine: str, s: dict) -> int | None:
    """Most images one request may carry; None means no limit the app has to respect."""
    if engine == "claude_api":
        return MAX_IMAGES
    if engine == "openai_api":
        n = int(s.get("openai_api_images") or 0) or preset(s)["images"] or MAX_IMAGES
        return max(1, min(n, MAX_IMAGES))
    return None
KEYS_FILE: Path = Path.home() / ".video-watch-keys.json"   # the app points this inside its data folder
MAX_IMAGES = 100   # images per request the APIs accept; larger batches are split across sub-agents
CLAUDE_DEFAULT = "claude-opus-5-5"
CLAUDE_MODELS = [
    {"id": "claude-opus-5-5", "name": "Claude Opus 5.5"},
    {"id": "claude-fable-5-2", "name": "Claude Fable 5.2 (most capable, costliest)"},
    {"id": "claude-sonnet-5-5", "name": "Claude Sonnet 5.5"},
    {"id": "claude-haiku-5-5", "name": "Claude Haiku 5.5 (cheapest)"},
]
# US$ per million input / output tokens, for the cost line in the report (cache discounts ignored)
PRICES = {"claude-fable-5-2": (8, 40), "claude-fable-5-1": (10, 50), "claude-fable-5": (10, 50),
          "claude-opus-5-5": (4, 20), "claude-opus-5": (5, 25), "claude-opus-4-8": (5, 25),
          "claude-sonnet-5-5": (2, 10), "claude-sonnet-5": (2, 10), "claude-haiku-5-5": (0.10, 0.50),
          "claude-haiku-4-5": (1, 5)}
# Models that take server-side refusal fallbacks ("default" routes by refusal category)
FALLBACK_MODELS = ("claude-fable-5-2", "claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5")

_sessions: dict[str, dict] = {}   # session id -> {"provider", "messages"}: the APIs keep no state


class Cancelled(Exception):
    pass


# ---------- key storage ----------

def _dpapi(data: bytes, protect: bool) -> bytes:
    if os.name != "nt":
        return data
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    inp, out = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), Blob()
    crypt = ctypes.windll.crypt32
    ok = (crypt.CryptProtectData(ctypes.byref(inp), ctypes.c_wchar_p("Video Watch"), None, None, None, 1, ctypes.byref(out))
          if protect else crypt.CryptUnprotectData(ctypes.byref(inp), None, None, None, None, 1, ctypes.byref(out)))
    if not ok:
        raise OSError("Windows could not " + ("encrypt" if protect else "decrypt") + " the key")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def _load() -> dict:
    try:
        return json.loads(KEYS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_key(provider: str, key: str) -> None:
    key = key.strip()
    if provider not in ENV_VARS or len(key) < 8 or any(c.isspace() for c in key):
        raise ValueError("That does not look like an API key.")
    keys = _load()
    keys[provider] = base64.b64encode(_dpapi(key.encode("utf-8"), True)).decode("ascii")
    KEYS_FILE.write_text(json.dumps(keys), encoding="utf-8")


def delete_key(provider: str) -> None:
    keys = _load()
    if keys.pop(provider, None) is not None:
        KEYS_FILE.write_text(json.dumps(keys), encoding="utf-8")


def get_key(provider: str) -> tuple[str, str]:
    """(key, where it came from): "saved", "environment", or ("", "")."""
    blob = _load().get(provider)
    if blob:
        try:
            return _dpapi(base64.b64decode(blob), False).decode("utf-8"), "saved"
        except (OSError, ValueError):
            pass
    env = os.environ.get(ENV_VARS.get(provider, ""), "").strip()
    return (env, "environment") if env else ("", "")


def key_status() -> dict:
    out = {}
    for p in ENV_VARS:
        key, src = get_key(p)
        out[p] = {"set": bool(key), "source": src, "hint": ("…" + key[-4:]) if key else "", "env": ENV_VARS[p],
                  "keyless": bool(PRESETS.get(p, {}).get("keyless"))}
    return out


def presets_public() -> dict:
    return {"presets": PRESETS, "not_supported": NOT_SUPPORTED}


# ---------- helpers ----------

def _b64(path: str) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


def _anthropic(key: str, timeout: float, retries: int):
    """The SDK client, on the system's own TLS settings (Windows certificate store); this also avoids a
    clash with packages such as pip-system-certs that patch the ssl module."""
    import ssl
    import anthropic
    return anthropic.Anthropic(api_key=key, max_retries=retries, timeout=timeout,
                               http_client=anthropic.DefaultHttpxClient(verify=ssl.create_default_context()))


def cost(model: str, tokens_in: int, tokens_out: int) -> float:
    for name, (pi, po) in sorted(PRICES.items(), key=lambda kv: -len(kv[0])):
        if model.startswith(name):
            return (tokens_in * pi + tokens_out * po) / 1_000_000
    return 0.0


def _fail(session, msg) -> dict:
    return {"text": "", "session": session, "cost": 0.0, "turns": 0, "tokens": 0, "error": msg, "opened": []}


# ---------- Claude API ----------

def _claude(prompt: str, images: list[str], s: dict, session: str | None, on_activity, cancel) -> dict:
    import anthropic
    key, _ = get_key("anthropic")
    if not key:
        return _fail(session, "No Claude API key is set. Add one in Video Watch under Model, Claude API "
                              "(create a key at console.anthropic.com, API keys).")
    model = (s.get("claude_api_model") or "").strip() or CLAUDE_DEFAULT
    effort = (s.get("claude_api_effort") or "").strip()
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _b64(p)}} for p in images]
    content.append({"type": "text", "text": prompt})
    state = _sessions.get(session or "") or {"provider": "anthropic", "messages": []}
    messages = state["messages"] + [{"role": "user", "content": content}]
    kwargs = {"model": model, "max_tokens": 32000, "messages": messages}
    if effort:
        kwargs["output_config"] = {"effort": effort}
    if model.startswith(FALLBACK_MODELS):   # a declined request is re-run on a fallback model, not lost
        kwargs.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    client = _anthropic(key, 60 * float(s.get("timeout_min") or 30), 3)
    if on_activity:
        on_activity("sending frames to the Claude API")
    try:
        with client.beta.messages.stream(**kwargs) as stream:
            last = 0.0
            for ev in stream:
                if cancel is not None and cancel.is_set():
                    raise Cancelled()
                if on_activity and ev.type == "content_block_delta" and time.time() - last > 1:
                    last = time.time()
                    on_activity("writing")
            msg = stream.get_final_message()
    except anthropic.AuthenticationError:
        return _fail(session, "The Claude API rejected the key (401). Check or replace it under Model, Claude API.")
    except anthropic.PermissionDeniedError as e:
        return _fail(session, f"This API key may not use {model} (403): {e.message}")
    except anthropic.NotFoundError:
        return _fail(session, f'The Claude API does not know the model "{model}" (404). Pick another model.')
    except anthropic.RateLimitError as e:
        return _fail(session, f"The Claude API rate limit or spending limit was reached (429): {e.message}")
    except anthropic.BadRequestError as e:
        return _fail(session, f"The Claude API refused the request (400): {e.message}")
    except anthropic.APIStatusError as e:
        return _fail(session, f"Claude API error {e.status_code}: {e.message}")
    except anthropic.APIConnectionError:
        return _fail(session, "Could not reach the Claude API. Check the internet connection.")
    text = "".join(b.text for b in msg.content if b.type == "text")
    u = msg.usage
    t_in = (u.input_tokens or 0) + (getattr(u, "cache_read_input_tokens", 0) or 0) + (getattr(u, "cache_creation_input_tokens", 0) or 0)
    out = {"text": text, "cost": cost(msg.model or model, t_in, u.output_tokens or 0), "turns": 1,
           "tokens": t_in + (u.output_tokens or 0), "error": None, "opened": [], "model": msg.model or model}
    if msg.stop_reason == "refusal":
        d = getattr(msg, "stop_details", None)
        out["error"] = f"The model declined this request (refusal{': ' + str(d.category) if d and d.category else ''})."
    elif msg.stop_reason == "max_tokens":
        out["error"] = "The reply was cut off at the output limit."
    sid = session or "api-" + uuid.uuid4().hex
    state["messages"] = messages + [{"role": "assistant", "content": [b.to_dict() for b in msg.content]}]
    _sessions[sid] = state
    out["session"] = sid
    return out


# ---------- OpenAI-compatible API ----------

def _openai_base(s: dict) -> str:
    return (s.get("openai_api_base") or "").strip().rstrip("/") or preset(s)["base"]


def _openai_key(s: dict) -> tuple[str, str]:
    pid = provider("openai_api", s)
    if PRESETS[pid].get("keyless"):
        return get_key(pid)[0] or "local", "none needed"
    return get_key(pid)


def _http(method: str, url: str, key: str, body: dict | None, timeout: float) -> dict:
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode("utf-8") if body is not None else None,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _http_error(e: urllib.error.HTTPError, model: str) -> str:
    try:
        detail = json.loads(e.read().decode("utf-8", "replace")).get("error", {}).get("message", "")
    except (ValueError, AttributeError, OSError):
        detail = ""
    return {401: "The provider rejected the key (401). Check or replace it under Model, Other APIs.",
            403: f"This API key may not use {model} (403). {detail}",
            404: f'The API does not know the model "{model}" (404). Pick another model. {detail}',
            429: f"The provider's rate limit or quota was reached (429). Lower 'Sub-agents at once' or wait. {detail}"}.get(
        e.code, f"API error {e.code}: {detail or e.reason}").strip()


def _openai(prompt: str, images: list[str], s: dict, session: str | None, on_activity, cancel) -> dict:
    p = preset(s)
    key, _ = _openai_key(s)
    if not key:
        return _fail(session, f"No {p['name']} key is set. Add one in Video Watch under Model, Other APIs"
                              + (f" (create a key at {p['site']})." if p["site"] else "."))
    if not _openai_base(s):
        return _fail(session, "Enter the service's address under Model, Other APIs.")
    model = (s.get("openai_api_model") or "").strip()
    if not model:
        return _fail(session, "Choose a model under Model, Other APIs (\"load my models\" lists what your key can use).")
    content = [{"type": "text", "text": prompt}] + [
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + _b64(p)}} for p in images]
    state = _sessions.get(session or "") or {"provider": "openai", "messages": []}
    messages = state["messages"] + [{"role": "user", "content": content}]
    body = {"model": model, "messages": messages}
    limit = int(s.get("openai_api_max_tokens") or 0) or p["max_tokens"]
    if limit:
        body["max_tokens"] = limit
    if (s.get("openai_api_effort") or "").strip():
        body["reasoning_effort"] = s["openai_api_effort"].strip()
    timeout = 60 * float(s.get("timeout_min") or 30)
    box: dict = {}

    def call() -> None:
        for attempt in range(3):
            try:
                box["r"] = _http("POST", _openai_base(s) + "/chat/completions", key, body, timeout)
                return
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(5 * (attempt + 1) ** 2)
                    continue
                box["e"] = _http_error(e, model)
                return
            except (OSError, ValueError) as e:
                if attempt < 2:
                    time.sleep(5)
                    continue
                box["e"] = f"Could not reach {_openai_base(s)}: {e}"
                return

    if on_activity:
        on_activity("waiting for the OpenAI API")
    t = threading.Thread(target=call, daemon=True)
    t.start()
    while t.is_alive():
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        t.join(0.5)
    if "e" in box:
        return _fail(session, box["e"])
    r = box.get("r") or {}
    choice = (r.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    text = msg.get("content") or ""
    if isinstance(text, list):
        text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
    u = r.get("usage") or {}
    out = {"text": text, "cost": 0.0, "turns": 1, "error": None, "opened": [], "model": r.get("model") or model,
           "tokens": int(u.get("prompt_tokens") or 0) + int(u.get("completion_tokens") or 0)}
    if not text:
        out["error"] = "The API returned an empty reply" + (f" ({choice.get('finish_reason')})" if choice.get("finish_reason") else "") + "."
    elif choice.get("finish_reason") == "length":
        out["truncated"] = True
    sid = session or "api-" + uuid.uuid4().hex
    state["messages"] = messages + [{"role": "assistant", "content": text}]
    _sessions[sid] = state
    out["session"] = sid
    return out


def run(engine: str, prompt: str, s: dict, images: list[str] | None = None, session: str | None = None,
        on_activity=None, cancel=None) -> dict:
    images = images or []
    cap = image_limit(engine, s) or MAX_IMAGES
    if len(images) > cap:
        return _fail(session, f"{len(images)} images in one request; this provider is set to take at most {cap}.")
    try:
        if engine == "claude_api":
            return _claude(prompt, images, s, session, on_activity, cancel)
        return _openai(prompt, images, s, session, on_activity, cancel)
    except Cancelled:
        raise
    except Exception as exc:  # noqa: BLE001  (report, never crash the run)
        print(f"[api] {engine} failed: {exc!r}", file=sys.stderr)
        return _fail(session, f"{NAMES[provider(engine, s)]} call failed: {exc}")


# ---------- checks from the settings page ----------

def test(engine: str, s: dict) -> dict:
    """Check the key (and the chosen model) without spending anything."""
    pid = provider(engine, s)
    key, src = get_key(pid) if pid == "anthropic" else _openai_key(s)
    if not key:
        return {"ok": False, "message": "No key is set yet."}
    try:
        if pid == "anthropic":
            model = (s.get("claude_api_model") or "").strip() or CLAUDE_DEFAULT
            m = _anthropic(key, 30, 1).models.retrieve(model)
            return {"ok": True, "message": f"The key works ({src}); {m.display_name} is available to it."}
        ids = [m.get("id") for m in _http("GET", _openai_base(s) + "/models", key, None, 30).get("data", [])]
        model = (s.get("openai_api_model") or "").strip()
        if model and model not in ids:
            return {"ok": False, "message": f'The key works ({src}), but "{model}" is not among the {len(ids)} models it can use.'}
        return {"ok": True, "message": f"The key works ({src}); {len(ids)} models available" + (f", including {model}." if model else ".")}
    except urllib.error.HTTPError as e:
        return {"ok": False, "message": _http_error(e, s.get("openai_api_model") or "")}
    except Exception as exc:  # noqa: BLE001
        name = type(exc).__name__
        if name == "AuthenticationError":
            return {"ok": False, "message": "The key was rejected (401)."}
        if name == "NotFoundError":
            return {"ok": False, "message": "The key works, but that model name is unknown (404)."}
        return {"ok": False, "message": f"Check failed: {exc}"}


def list_models(engine: str, s: dict) -> list[dict]:
    pid = provider(engine, s)
    key, _ = get_key(pid) if pid == "anthropic" else _openai_key(s)
    if not key:
        raise OSError("No key is set yet.")
    if pid == "anthropic":
        page = _anthropic(key, 30, 1).models.list(limit=100)
        return [{"id": m.id, "name": m.display_name or m.id} for m in page.data]
    data = _http("GET", _openai_base(s) + "/models", key, None, 30).get("data", [])
    skip = ("embedding", "tts", "whisper", "dall-e", "transcribe", "moderation", "audio", "realtime", "image", "search", "davinci", "babbage")
    ids = sorted({m["id"] for m in data if m.get("id") and not any(k in m["id"] for k in skip)}, reverse=True)
    return [{"id": i, "name": i} for i in ids]
