# Video Watch

Watch videos with an AI model and get a written report you can actually study from.

Paste links (YouTube, Bilibili and most other video sites) or drop in video files, say what you want
to learn, and Video Watch downloads each video, takes frames from it, reads the transcript, and has an
AI model write a layered report: from a one-line gist to a deep-dive essay, with timestamps that jump
into the video and the frames that matter. A batch of videos becomes one report organised by topic
around your question, with a combined summary across all of them.

Windows 10/11. Free and open source (MIT). Runs on your computer; nothing is uploaded anywhere except
to the AI model you choose.

## Install

1. Download `VideoWatchSetup-<version>.exe` from the [latest release](../../releases/latest).
2. Run it. Windows SmartScreen may say "Windows protected your PC", because the installer is not
   code-signed: click "More info", then "Run anyway".
3. The installer explains what the app needs, lets you pick the install folder, checks for yt-dlp,
   FFmpeg, Claude Code and Codex, offers to install what is missing, and shows whether each AI tool is
   signed in (with a button that opens its sign-in). No administrator rights are needed for the app.

Uninstall from Windows Settings, Apps, Installed apps, Video Watch.

## What you need

- yt-dlp and FFmpeg (the installer can install both through winget).
- One AI model to watch with:

| Model | How you pay | Sign-in |
|---|---|---|
| Claude Code | your Claude Pro/Max plan or Anthropic Console account | `claude auth login` |
| Codex | your ChatGPT plan | `codex login` |
| Claude API | per use, with an Anthropic API key | key pasted in the app |
| Other APIs | per use, with that provider's key (or free, on your own computer) | key pasted in the app |

The app never signs in for you and never sees passwords. API keys are stored encrypted for your
Windows account and are sent only to the provider they belong to.

### Other API providers, and their limits

"Other APIs" talks to any service with an OpenAI-compatible Chat Completions endpoint. Presets:

| Provider | Default images per request | Limits to know |
|---|---|---|
| OpenAI | 100 | API billing is separate from a ChatGPT subscription. |
| Google Gemini | 100 | Through Google's OpenAI-compatible endpoint, which supports fewer options than Gemini's own API. Free-tier keys allow few requests per minute: use 1 or 2 sub-agents at once. |
| OpenRouter | 50 | Hundreds of models behind one key; only models with image input can see frames, and limits and prices depend on the model. |
| DeepSeek | 20 | Only its vision-capable flash model sees images; other DeepSeek models are text only. Replies stop around 8,000 tokens, so deep dives are shorter. |
| Alibaba Qwen (DashScope) | 20 | Only the VL models see images. Mainland China accounts use a different address. |
| Moonshot Kimi | 20 | Only vision models see images. Mainland China accounts use a different address. |
| Zhipu GLM | 5 | Only the GLM-V models see images, few per request. Not tested. |
| xAI Grok | 10 | Only Grok models with image input. Not tested. |
| Mistral | 8 | Pixtral and newer Medium/Small models see images; Mistral sets no fixed image limit, so 8 is cautious. |
| Groq | 3 | Very fast, but 3 to 5 images per request means many small calls; low free-tier rate limits. |
| Ollama, LM Studio | 8 | Free and private on your own computer, but slow, and small local models write thin reports. Ollama needs a larger context (`OLLAMA_CONTEXT_LENGTH=32768`) or long prompts are cut. |
| Anything else | 10 | Any OpenAI-compatible endpoint that accepts base64 images (Together, Fireworks, vLLM, a company gateway). |

Every default can be changed in the app (images per request, whether the model sees images, maximum
reply length), because limits change with each model; check the provider's own documentation.
A model that cannot see images can still write the report: add a model that can as a sub-agent, and
it describes the frames first. Not supported: Azure OpenAI, Amazon Bedrock, Google Vertex AI.
The Claude API and OpenAI presets were tested; the others are configured from their published
documentation and may need adjusting.

## Languages

Reports can be written in English, Simplified Chinese or Traditional Chinese, whatever language the
videos are in (Report panel, Report language). The report's own headings, depth names and buttons
follow the language; in Chinese, technical terms keep the English in brackets the first time.
The language picker sits next to the Watch button.

The app's own interface is available in English and Simplified Chinese: switch with the menu next
to Quit (it starts in Chinese when Windows is set to Chinese). Messages that come from the AI tools
themselves, the progress log and some error details stay in English.

## Run from source

Python 3.12 on Windows:

```
py -3.12 -m pip install anthropic
py -3.12 app.py
```

The app opens in its own window (Microsoft Edge in app mode); closing the window quits it.
`build.cmd` builds `dist\Video Watch.exe` and the installer `dist\Video Watch Setup.exe`, which carries
the app inside it (one-time setup: `py -3.12 -m venv .build\venv`, then
`.build\venv\Scripts\pip install pyinstaller anthropic`). The app keeps its settings, reports, logs and
saved keys in `%LOCALAPPDATA%\VideoWatch` (set `VIDEO_WATCH_HOME` to move it).
`Video Watch Setup.exe --silent --dir <folder>` installs without questions.

## Several topics at once

Press Watch again while a run is going to start another one: each run gets its own progress card,
named by its report title, with its own Stop button, log and estimates, and stopping one leaves the
others running. Give each run its own title; a second run with the same title as one still watching
is refused, so a double click cannot start it twice. Runs share the computer and your model's rate
limits, so many large runs at once each go slower.

## Progress, estimates and logs

While a run is going, each item shows its current stage, elapsed time, a progress bar and an
estimate of time left. Estimates are learned from your own past analyses (`history.json`);
before there is any history they are rough defaults. Every run writes `run.log` next to its
report, and the report lists the time spent per stage.

## Requirements

- Python 3.12, plus the `anthropic` package for the Claude API engine
- `yt-dlp`, `ffmpeg`, `ffprobe` on PATH (tools installed after the app started are picked up from
  the registry PATH)
- At least one model: `claude` and/or `codex` on PATH and signed in, or an API key. The app never
  signs in for you: when a CLI is not signed in it says so, explains `claude auth login` /
  `codex login`, and has a button that opens a terminal running that command.
- Optional: a transcription key in `~/.config/watch/.env` (`GEMINI_API_KEY`, `GROQ_API_KEY`
  or `OPENAI_API_KEY`), used only when a video has no captions. Same file the skill uses.

## Inputs

Each item is one or more URLs (or local file paths) plus optional instructions. Video files on
this computer can be dropped onto an item or picked with "add video files from this computer"; the
app keeps its own copy under `uploads\`, deleted after the run unless "Keep downloaded video files"
is on (and by "delete working files").

- One URL per item: its own instructions.
- Several URLs in one item, bundle unticked: each is analysed separately with the same instructions.
- Several URLs, bundle ticked: watched together in one analysis (comparisons, series).

An item can also carry a start/end range and its own model override.

## How the video is watched

| Mode | What it does |
|---|---|
| Dynamic | The model sees the transcript and a few overview frames, then requests the moments it wants over several rounds. Every extracted time and the model's reason is recorded in the report. |
| Fixed interval | One frame every N seconds or minutes. |
| Fixed count | N evenly spaced frames. |
| Scene changes | A frame per visual cut, uniform fallback on static video. |
| Keyframes | The encoder's keyframes; fastest. |
| Transcript only | No frames; skips the video download when captions exist. |

Two numbers bound the frames per video, both yours to set:

- Frame cap per video: 0 means automatic (as many frames as the mode asks for); any other number
  thins the frames evenly down to it, and the report says so.
- Safety limit: the most any video can get whatever else is set (default 400, up to 5000).

Claude Code opens frame files itself and, given many, tends to open only a few. With "Make the
model open every frame" on (the default), the app records which files were opened and sends the
model back for the rest, up to three times; any frame still unopened is marked in the report.

## Sub-agents

With Agents on Automatic (the default), up to 60 frames are handled by one model call. Above that the
frames are split into slices of about 40; sub-agents open the slices in parallel (4 at a time) and write
notes, and the main model writes the report from the notes and the transcript. On a 13-minute video at
one frame per 5 seconds (158 frames) this cut the model step from 258 s to 78 s. Slice size, parallelism
are settings. Dynamic mode always uses one agent.

Sub-agents can be a mix: under "Who the sub-agents are" add any number of engine and model pairs
(for example Claude Code haiku and Codex). Slices are dealt out to them in turn, and the main model
still writes the report. Left empty, sub-agents use the main engine and model.

## Combined summary for a batch

When a report holds several videos, the main model acts as orchestrator after they are watched: it
reads every analysis and writes a combined summary (themes across the videos, where they agree or
differ, one line per item, and the answer to the request across the batch) that opens the report,
before the individual analyses. When a run is split into several reports (for example one per video),
an extra overview report holds the combined summary for the whole batch and links to each report.
"Combined summary for a batch" in the Report panel turns it off.

## Layered reports: the depth slider

With Report style on Layered (the default), the report is written in stages instead of one reply:

1. Sub-agents write notes on every frame, in slices that never mix two videos.
2. Each video's key frames (the ones the notes say are worth showing) are re-captured at 1280px, so
   numbers on charts and slides are legible to the model and in the report.
3. Each video gets its own write-up at four depths: gist, summary, detailed and deep dive. The deep
   dive is sized to the video (about 130 words per minute, 900 to 4,500 words).
4. A bundle also gets chapters: the main model plans 4 to 10 chapters around your question (topics, not
   videos, in learning order, weighted by how central and well covered each is), then each chapter is
   written by its own call from every video that covers it. "Video by video" follows the chapters.

In the report, a slider at the top switches the whole report between the four depths; each section
also has its own depth menu. With "Explain the theory the videos assume" on, the model adds the
mechanisms the videos take for granted, always in a box marked "Background, not from the videos".
When the report is opened from the app, every section has Go deeper (with an optional "what to go
deeper on"): one more model call writes a further layer from the section and its videos' transcripts,
saved into the report and its exported copy. Standard style keeps the old single reply.

YouTube auto-captions repeat each line as they scroll; transcripts are de-duplicated, which halves
what the model has to read.

## API keys instead of a CLI

Claude API and Other APIs are engines like Claude Code and Codex: frames are sent as images, split
into as many requests as the provider's image limit needs. Paste the key in the Model panel: each
provider has its own key, stored encrypted for your Windows account (DPAPI) in `keys.json`, never
shown again (only its last four characters), and only sent to that provider. A key in the provider's
usual environment variable (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, ...) is used when
none is saved. "check the key" and "load my models" cost nothing. The Claude API engine uses the
Anthropic SDK with server-side refusal fallbacks; Other APIs speak OpenAI Chat Completions. Reports
show tokens and, for Claude, an estimated cost.

## Library

Below Past reports, the Library lists every video watched, grouped by date or by category. The model
assigns the category while it writes the report, reusing existing categories where they fit; click a
category to change it, and older reports can be filed with one click. `{category}` also works in the
export folder layout.

## Switching models

The Model panel picks the default engine (Claude Code or Codex), with a model and effort for each.
The model lists come from the CLIs' own files (Codex: `~/.codex/models_cache.json`; Claude: the
fable/opus/sonnet/haiku aliases), and "Other…" accepts any name the CLI takes. Any item can override the engine in its own card, so one run can mix both.

- Claude runs as `claude -p` with only the Read tool and opens the frame files itself.
- Codex runs as `codex exec` in a read-only sandbox; frames are attached as images, each
  with its id and time burnt into a strip so the model can tell them apart.

## Output

`runs/<timestamp>/report.html` (images embedded, safe to move or share) and `run.json`
(the same data, including every frame time). Frames stay in `runs/<timestamp>/work/`;
downloaded video is deleted unless "Keep downloaded video files" is on.

## Storage, deleting and Google Drive

The Storage panel keeps the reports from growing without limit:

- Working files (frames, audio) are deleted once the report is written; the report embeds its images.
- "Keep only the newest reports" deletes older ones from this computer after each run (0 = keep all).
- Gallery images in the report are re-compressed after the analysis (width and quality are settings);
  frames cited in the text stay full size, and the model always sees the full-size frames.
- Past reports shows the size of each run, with delete per report, "delete working files" and
  "delete all reports". The run in progress is never touched.
- "Also save a copy of each report to this folder" copies every report to a folder you choose,
  for example one inside Google Drive for desktop (`G:\My Drive\Video Watch`), which then syncs it.
  The layout template decides folders and file names: `{year} {month} {day} {date} {time} {title} {id}`,
  with `/` starting a subfolder. Copies are never deleted by the app, and never overwritten.

## Reports per run

"When a run has several videos" decides how they are divided into reports: Automatic (the selected
model looks at what each video was about and groups related ones), one report per video, one report
for everything, or Custom (the model follows a rule you write). A bundle watched together is never
split. Each report is its own entry in Past reports (`<run id>`, `<run id>-02`, ...).

## Sign-in for video sites

"Use my login from" takes a browser name (firefox is the most reliable) or the path of an exported
cookies.txt; yt-dlp then uses that browser's saved session. "Check access" asks yt-dlp what it can
see of one URL without downloading.

Bilibili refuses downloads it considers too frequent with HTTP 567, sometimes for one quality stream
only. When the chosen stream is refused, the app tries the next qualities (720p down, then higher)
before giving up, and never mistakes the audio-only part for the video. If every stream is refused,
the item retries twice, waiting longer each time, then fails with "wait 15 to 30 minutes" advice.

## Layout

- `app.py` server, settings, job runner
- `engine.py` prompts and the dynamic frame-request loop
- `llm.py` Claude Code and Codex runners, sign-in checks
- `api_engines.py` Claude API and OpenAI API runners, encrypted key storage
- `installer.py` the setup wizard and uninstaller
- `pipeline.py` download, transcript, frame extraction per mode
- `report.py` HTML report
- `ui/index.html` the interface
- `watchlib/` download, frame and transcription scripts from the `/watch` skill
  (github.com/bradautomates/claude-video, MIT)
