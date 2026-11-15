// Interface language. Fixed text anywhere on the page (including text added later) is swapped
// through ZH by exact match, or through ZH_RE when it carries numbers or names. Sentences that are
// assembled from several pieces use L(english, chinese) in the main script instead.
const UI_LANG = (() => {
  try { const v = localStorage.getItem('vw-ui'); if (v) return v; } catch (_) {}
  return /^zh/i.test(navigator.language || '') ? 'zh' : 'en';
})();
const L = (en, zh) => UI_LANG === 'zh' ? zh : en;

const ZH = {
  'checking tools…': '正在检查工具…', 'Quit': '退出', 'What to watch': '要看的视频', 'Report title (optional)': '报告标题（可选）',
  'e.g. Fed press conference review': '例如：美联储发布会回顾', '+ Add another item': '+ 添加条目', 'Report in': '报告语言',
  "the request's language": '与要求相同', 'English': '英语', 'Watch': '开始观看', 'Progress': '进度', 'Stop': '停止',
  'The whole report is written in this language, whatever language the videos are in, including its headings and buttons. In Chinese, technical terms keep the English in brackets the first time they appear.':
    '整份报告（包括标题和按钮）都用这种语言撰写，无论视频是什么语言。中文报告中，专业术语第一次出现时会在括号里保留英文。',
  'Past reports': '历史报告', 'None yet.': '暂无。', 'open reports folder': '打开报告文件夹', 'delete working files': '删除工作文件',
  'delete all reports': '删除全部报告', 'Library': '资料库', 'by date': '按日期', 'by category': '按类别',
  'Model': '模型', 'Other APIs': '其他 API', 'Claude model': 'Claude 模型', 'Effort': '推理强度', 'CLI default': 'CLI 默认',
  'low': '低', 'medium': '中', 'high': '高', 'xhigh': '超高', 'max': '最高', 'minimal': '最低',
  'Codex model': 'Codex 模型', 'Reasoning effort': '推理强度', 'Model default': '模型默认', 'Provider': '服务商',
  'Address, image and length limits': '地址、图片和长度限制', 'API address': 'API 地址', 'Model can see images': '模型能否看图片',
  'Provider default': '服务商默认', 'Yes': '能', 'No, text only': '不能，仅文本', 'Images per request': '每次请求的图片数',
  'Max output tokens': '最大输出 token 数',
  "0 or empty means the provider's default shown in the box. A model that cannot see images can still write the report: add a model that can under Agents, Sub-agent settings, Who the sub-agents are, and it describes the frames first. Fewer images per request means more, smaller calls. Raise max output tokens if reports stop mid-sentence and the provider allows more.":
    '0 或留空表示使用框中显示的服务商默认值。不能看图片的模型仍可撰写报告：在“智能体 → 子智能体设置 → 子智能体使用的模型”中添加一个能看图片的模型，由它先描述画面。每次请求的图片越少，调用就越多、越小。如果报告在句子中间中断且服务商允许，请调高最大输出 token 数。',
  'Each item can also override the model in its own card. Claude Code and Codex run on your own CLI sign-in; the APIs use a key and are billed per use by the provider.':
    '每个条目也可以在自己的卡片中单独指定模型。Claude Code 和 Codex 使用你自己的 CLI 登录；API 使用密钥，由服务商按用量计费。',
  'Agents': '智能体', 'Automatic': '自动', 'One agent does everything': '一个智能体完成全部', 'Always split the frames across sub-agents': '始终把画面分给多个子智能体',
  'Sub-agent settings': '子智能体设置', 'Frames per sub-agent': '每个子智能体的画面数', 'Sub-agents at once': '同时运行的子智能体',
  'Who the sub-agents are': '子智能体使用的模型', '+ add a sub-agent type': '+ 添加子智能体类型',
  'Sub-agents each open one slice of the frames at the same time and write notes; the main model then writes the report from the notes and the transcript. Not used in Dynamic mode.':
    '各子智能体同时查看一部分画面并做笔记；主模型再根据笔记和字幕撰写报告。动态模式不使用。',
  'How the video is watched': '观看方式', 'Dynamic': '动态',
  'The model reads the transcript and a few overview frames, then asks for the exact moments it wants. Every time it picks is recorded in the report.':
    '模型先读字幕和几张概览画面，再请求它想看的具体时刻。每个选中的时间都记录在报告中。',
  'Fixed interval': '固定间隔', 'One frame every N seconds or minutes.': '每隔 N 秒或 N 分钟取一帧。', 'Fixed count': '固定数量',
  'N frames spread evenly across the video.': '在整个视频中平均取 N 帧。', 'Scene changes': '场景切换',
  'A frame at each visual cut; falls back to even sampling on static video. Slowest to extract.': '每次画面切换取一帧；画面静止时改为平均取帧。提取最慢。',
  'Keyframes': '关键帧', "The encoder's own keyframes. Fast, lands near cuts.": '使用编码器自带的关键帧。速度快，通常落在切换处附近。',
  'Transcript only': '仅字幕', 'No frames. Skips the video download when captions exist.': '不取画面。有字幕时跳过视频下载。',
  'One frame every': '每隔多久取一帧', 'Unit': '单位', 'seconds': '秒', 'minutes': '分钟', 'Frames per video': '每个视频的画面数',
  'Overview frames': '概览画面', 'Frames it may request': '可请求的画面数', 'Request rounds': '请求轮数',
  'Overview frames are evenly spaced and shown up front, which matters most when there is no transcript. Set to 0 to let the model start from the transcript alone.':
    '概览画面平均分布并预先提供，没有字幕时最重要。设为 0 则让模型只从字幕开始。',
  'Frame cap per video (0 = automatic)': '每个视频的画面上限（0 = 自动）', 'Frame width (px)': '画面宽度（像素）', 'Safety limit (frames)': '安全上限（画面数）',
  'Make the model open every frame (Claude Code)': '要求模型打开每一帧（Claude Code）',
  'Claude tends to open only a few frames when given many. With this on, the app checks which frames were opened and sends it back for the rest, up to three times. Slower and costlier, but the frames are actually looked at. Codex always receives every frame.':
    '画面很多时，Claude 往往只打开其中几张。开启后，应用会检查哪些画面已打开，并让它回去看剩下的，最多三次。更慢、更贵，但画面确实都被看过。Codex 总会收到全部画面。',
  "512px is enough for most footage; use 1024 when on-screen text has to be read. The safety limit is the most frames any video can get, whatever the other settings say (up to":
    '大多数视频 512 像素就够了；需要看清屏幕上的文字时用 1024。安全上限是任何视频最多能取的画面数，不受其他设置影响（最多',
  'Drop near-identical frames (held slides, static screens)': '去掉几乎相同的画面（停留的幻灯片、静止的屏幕）',
  'Transcript': '字幕', "Use the platform's captions when available": '有平台字幕时使用', 'Transcribe the audio when there are no captions': '没有字幕时转写音频',
  'Transcription service': '转写服务', 'Sign-in for video sites': '视频网站登录', 'Use my login from': '使用此浏览器的登录',
  'none (public videos only)': '无（仅公开视频）',
  "For videos that need an account (Bilibili above 480p or members-only, age-restricted YouTube, private playlists): log in to the site in that browser, then name the browser here. Firefox is the most reliable; Chrome and Edge often lock their cookies while open. Otherwise export a cookies.txt file from your browser and put its full path here. The app never sees your password, only the browser's saved session.":
    '需要账号的视频（B 站 480p 以上或会员视频、有年龄限制的 YouTube、私有播放列表）：先在该浏览器中登录网站，再在这里填写浏览器名称。Firefox 最可靠；Chrome 和 Edge 打开时常会锁定 cookie。也可以从浏览器导出 cookies.txt 文件，在这里填写它的完整路径。应用不会看到你的密码，只使用浏览器保存的登录状态。',
  'Check a video': '检查一个视频', 'paste a URL from the site': '粘贴该网站的视频链接', 'Check access': '检查访问',
  'Report and run': '报告与运行', 'Default instructions (used when an item has none)': '默认要求（条目未填写时使用）',
  'Leave empty for a general summary': '留空则生成一般摘要', 'When a run has several videos': '一次运行包含多个视频时',
  'Automatic: the model groups related videos into reports': '自动：由模型把相关视频归入同一报告', 'One report per video': '每个视频一份报告',
  'One report for everything': '全部放在一份报告', 'Custom: group by my rule': '自定义：按我的规则分组',
  'e.g. One report per channel. Or: trading videos together, everything else separate.': '例如：每个频道一份报告。或：交易类视频放一起，其余分开。',
  'Report style': '报告样式', 'Layered: chapters with a depth slider, from gist to deep dive': '分层：按章节组织，可用滑块从要点切换到深度解析',
  'Standard: one written analysis': '标准：一篇分析', 'Reports open at': '报告默认打开深度',
  'Gist': '要点', 'Summary': '摘要', 'Detailed': '详细', 'Deep dive': '深度解析',
  'Explain the theory the videos assume, from the model\'s own knowledge (marked "Background, not from the videos")': '解释视频默认你已懂的理论，来自模型自身知识（标注为“背景知识，非视频内容”）',
  'Combined summary for a batch: the main model reads every analysis and writes an overview that comes first': '批量综合摘要：主模型阅读所有分析，先写一份总览',
  'A report holding several videos opens with it. When a run is split into several reports, an extra overview report covers the whole batch and links to the others.':
    '包含多个视频的报告会以它开头。一次运行拆成多份报告时，会另外生成一份总览报告，涵盖整批视频并链接到其他报告。',
  'Include every frame examined in the report': '在报告中附上所有看过的画面', 'Include the transcript': '附上字幕全文',
  'Keep downloaded video files after the run': '运行结束后保留下载的视频文件', 'Advanced': '高级', 'Items at once': '同时处理的条目',
  'Timeout per turn (min)': '每轮超时（分钟）', 'Max turns (Claude)': '最大轮数（Claude）', 'Storage': '存储',
  'Delete working files (frames, audio) once the report is written': '报告写完后删除工作文件（画面、音频）',
  'The report already has its images built in, so nothing is lost. Ignored while "Keep downloaded video files" is on.': '报告已内嵌图片，所以不会丢失任何内容。勾选“保留下载的视频文件”时不生效。',
  'Compress the frame gallery images in the report': '压缩报告中画面图库的图片', 'Gallery image width (px)': '图库图片宽度（像素）', 'Quality (10 to 100)': '质量（10 到 100）',
  'Runs after the analysis, so the model always sees full-size frames. Frames the report cites in its text stay full size; only the "every frame examined" gallery shrinks.':
    '在分析之后进行，所以模型看到的始终是原尺寸画面。报告正文引用的画面保持原尺寸，只缩小“所有看过的画面”图库。',
  'Keep only the newest reports (0 = keep all)': '只保留最新的报告（0 = 全部保留）',
  'Older reports are deleted from this computer after each run. Copies saved to the folder below are never deleted.': '每次运行后会从本机删除较旧的报告。保存到下方文件夹的副本永远不会删除。',
  'Also save a copy of each report to this folder': '同时把每份报告复制到这个文件夹', 'e.g. G:\\My Drive\\Video Watch (empty = off)': '例如 G:\\My Drive\\Video Watch（留空 = 关闭）',
  'Folder and file layout': '文件夹和文件名格式', 'All in one folder': '全部放一个文件夹', 'A folder per month': '每月一个文件夹', 'Year, then month': '先按年再按月',
  'A folder per title': '每个标题一个文件夹', 'A folder per category': '每个类别一个文件夹', 'Save a folder per report with run.json and run.log too': '每份报告单独一个文件夹，并附上 run.json 和 run.log',
  // item cards
  'Remove': '移除', 'Video URLs or local file paths, one per line (paste a whole list)': '视频链接或本机文件路径，每行一个（可粘贴整份列表）',
  'https://www.youtube.com/watch?v=… (or drop video files onto this card)': 'https://www.youtube.com/watch?v=…（也可以把视频文件拖到这张卡片上）',
  '+ add video files from this computer': '+ 从本机添加视频文件', 'Instructions (optional)': '要求（可选）', 'What should be looked for or answered?': '要关注什么，或要回答什么问题？',
  'Watch these together as one bundle (one combined analysis). Unticked, each URL is analysed on its own with the same instructions.': '把这些视频作为一组一起看（一份合并分析）。不勾选时，每个链接按相同要求单独分析。',
  'Range and model for this item': '此条目的时间范围和模型', 'Start': '开始', 'End': '结束', 'end': '结尾', 'Same as settings': '与设置相同', 'Other API (as set in Model)': '其他 API（按模型设置）',
  // model card
  'check again': '重新检查', 'Check again': '重新检查', 'checking…': '检查中…', 'Open a terminal to sign in': '打开终端登录', 'signed in': '已登录',
  'Runs on this computer: no key needed.': '在本机运行：无需密钥。', 'No key yet: add one below.': '尚无密钥：请在下方添加。',
  'API key': 'API 密钥', 'Save key': '保存密钥', 'check the key': '检查密钥', 'load my models': '加载我的模型', 'remove the key': '删除密钥', 'check the connection': '检查连接',
  'No key needed: it runs on this computer. Start it before watching.': '无需密钥：在本机运行。观看前请先启动它。',
  'paste your API key': '粘贴你的 API 密钥', 'paste a new key to replace it': '粘贴新密钥以替换', 'Saved in this app, encrypted for your Windows account:': '已保存在本应用中，按你的 Windows 账户加密：',
  'Saving…': '保存中…', 'Saved. Checking it…': '已保存，正在检查…', 'Checking…': '检查中…', 'Asking for the list…': '正在获取列表…',
  'Remove the saved key from this app?': '从本应用删除已保存的密钥？', 'Settings saved.': '设置已保存。',
  'Choose a model…': '选择模型…', 'Other… (type a model name)': '其他…（输入模型名称）', 'Other…': '其他…', "that CLI's default model": '该 CLI 的默认模型', 'remove': '移除',
  'Model name, exactly as the CLI accepts it:': '模型名称（与 CLI 接受的写法完全一致）：', 'model default': '模型默认', 'provider default': '服务商默认',
  'The slices are dealt out to these in turn: slice 1 to the first, slice 2 to the second, and so on. The main model above still writes the report.': '画面切片依次分配给它们：第 1 片给第一个，第 2 片给第二个，依此类推。报告仍由上方的主模型撰写。',
  'Every sub-agent uses this. The main model above still writes the report.': '所有子智能体都用它。报告仍由上方的主模型撰写。',
  'Empty: the sub-agents use the same engine and model as above. Add types to use a cheaper model, or to mix Claude Code and Codex.': '留空：子智能体使用与上方相同的引擎和模型。可添加类型来使用更便宜的模型，或混用 Claude Code 和 Codex。',
  'One model call opens every frame itself. Simplest, but slow when there are many frames.': '由一次模型调用自己打开所有画面。最简单，但画面多时较慢。',
  'Each video is written up on its own at four depths, sized to how much it holds, with its key frames re-captured sharp. A bundle of videos also gets chapters organised around your question, each drawing on every video that covers it. In the report, slide the whole report between gist and deep dive, set one section\'s depth on its own, or press Go deeper on a section for more (when the report is opened from this app). Costs about one extra model call per video and per chapter.':
    '每个视频单独按四种深度撰写，篇幅取决于视频内容的多少，关键画面会重新高清截取。一组视频还会按你的问题组织成章节，每章综合所有相关视频。在报告中，可以用滑块在要点和深度解析之间切换整份报告，单独设置某一节的深度，或在某一节点击“深入展开”获取更多内容（需从本应用打开报告）。每个视频和每个章节大约多花一次模型调用。',
  'One model reply per item: quicker and cheaper, but a long video or a bundle gets compressed.': '每个条目一次模型回复：更快、更便宜，但长视频或一组视频会被压缩。',
  'No transcription key is configured in ~/.config/watch/.env, so videos without captions will be frames only.': '~/.config/watch/.env 中没有配置转写密钥，没有字幕的视频只能看画面。',
  'Off. Point this at a folder inside Google Drive (or OneDrive, Dropbox) and every report syncs there.': '已关闭。指向 Google Drive（或 OneDrive、Dropbox）中的文件夹，每份报告都会同步到那里。',
  'Delete this report from this computer? This cannot be undone. A copy saved to your export folder is not touched.': '从本机删除这份报告？此操作无法撤销。保存到导出文件夹的副本不受影响。',
  'Delete the working files (frames, audio, kept videos) of every run? The reports themselves stay.': '删除所有运行的工作文件（画面、音频、保留的视频）？报告本身会保留。',
  'Delete ALL reports from this computer? This cannot be undone. Copies saved to your export folder are not touched.': '从本机删除全部报告？此操作无法撤销。保存到导出文件夹的副本不受影响。',
  'Category for this video:': '这个视频的类别：', 'Video Watch has stopped. You can close this window.': 'Video Watch 已停止，可以关闭此窗口。',
  'asking the model…': '正在询问模型…', 'let the model categorise them': '让模型分类', 'Uncategorised': '未分类', 'Untitled run': '未命名运行', 'Untitled': '未命名',
  'folder': '文件夹', 'open folder': '打开文件夹', 'save copy': '保存副本', 'delete': '删除', 'source': '原视频', 'failed': '失败', 'copy saved': '已保存副本',
  'queued': '排队中', 'running': '进行中', 'done': '完成', 'error': '出错', 'cancelled': '已停止', 'starting': '开始中', 'writing': '撰写中',
  'interval': '固定间隔', 'count': '固定数量', 'scene': '场景切换', 'keyframes': '关键帧', 'dynamic': '动态', 'transcript': '仅字幕',
  'taking longer than estimated': '比预计耗时更长', 'the app did not answer': '应用没有响应',
  'Add at least one video URL or file path.': '请至少添加一个视频链接或文件路径。', 'A run is already in progress.': '已有运行在进行中。',
  'Progress log': '进度日志', 'dismiss': '关闭',
  'Retry a failed download automatically when the cause is temporary': '下载失败且原因是暂时性时自动重试',
  'The app reads why a download failed. When the site is limiting downloads or the network dropped, it tries again after a pause (30 s and 90 s for a rate limit). A members-only, private, removed or region-blocked video fails the same way every time, so it is not retried. Either way, a failed link is listed on the run\'s card with the reason and what to do, and the rest of the run carries on.':
    '应用会读取下载失败的原因。如果是网站在限制下载或网络中断，会在暂停后重试（遇到限流时分别等 30 秒和 90 秒）。会员专属、私有、已删除或地区受限的视频每次都会以同样的方式失败，因此不会重试。无论哪种情况，失败的链接都会列在该运行的卡片上，附上原因和处理方法，其余部分照常进行。', 'Pause': '暂停', 'Resume': '继续', 'paused': '已暂停', '+ New topic': '+ 新主题', 'Watch all topics': '全部主题开始观看',
  'Each topic has its own report title and items, and becomes its own run: watch the topic you are on, or all topics at once. Runs go on at the same time and can be stopped one by one.':
    '每个主题有自己的报告标题和条目，并作为单独的一次运行：可以只看当前主题，也可以一次看全部主题。多个运行同时进行，可以逐个停止。',
  'Give each run its own title to tell them apart. Runs go on at the same time and can be stopped one by one.': '为每次运行起一个不同的标题以便区分。多个运行可以同时进行，并且可以逐个停止。',
};

Object.assign(ZH, {'Another OpenAI-compatible service': '其他 OpenAI 兼容服务', 'Interface language / 界面语言': '界面语言 / Interface language'});
const STAGES ={captions: '字幕', download: '下载', frames: '取帧', transcribe: '转写', model: '模型'};
const ZH_RE = [
  [/^CLI default \((.+)\)$/, (m, a) => `CLI 默认（${a}）`],
  [/^Default \((.+)\)$/, (m, a) => `默认（${a}）`],
  [/^(.+) \(on this computer\)$/, (m, a) => `${a}（本机运行）`],
  [/^(.+) \(latest\)( · .+)?$/, (m, a, b) => `${a}（最新）${b || ''}`],
  [/^(.+) \(most capable, costliest\)( · .+)?$/, (m, a, b) => `${a}（最强、最贵）${b || ''}`],
  [/^(.+) \(cheapest\)( · .+)?$/, (m, a, b) => `${a}（最便宜）${b || ''}`],
  [/^Item (\d+)$/, (m, a) => `条目 ${a}`],
  [/^A run titled "(.+)" is already watching\. Give this one another title, or wait for it to finish\.$/, (m, a) => `标题为“${a}”的运行正在进行。请给这次运行换一个标题，或等它完成。`],
  [/^(\d+) videos?$/, (m, a) => `${a} 个视频`],
  [/^(\d+) analys(?:is|es) with (.+)$/, (m, a, b) => `${a} 项分析，使用 ${b}`],
  [/^Using key (.+)$/, (m, a) => `使用密钥 ${a}`],
  [/^Using (.+)$/, (m, a) => `使用 ${a}`],
  [/^(.+) was not found on this computer\.$/, (m, a) => `此电脑上未找到 ${a}。`],
  [/^(.+) missing$/, (m, a) => `${a} 未安装`],
  [/^(.+) not signed in$/, (m, a) => `${a} 未登录`],
  [/^(.+) key ✓$/, (m, a) => `${tr(a)} 密钥 ✓`],
  [/^Taken from the (\S+) environment variable:$/, (m, a) => `来自环境变量 ${a}：`],
  [/^✓ (\d+) models listed in the model menu above\.$/, (m, a) => `✓ 已在上方模型菜单中列出 ${a} 个模型。`],
  [/^Could not save settings: (.+)$/, (m, a) => `无法保存设置：${a}`],
  [/^Configured: (.+) \(keys from ~\/\.config\/watch\/\.env\)\.$/, (m, a) => `已配置：${a}（密钥来自 ~/.config/watch/.env）。`],
  [/^Saved to (.+)$/, (m, a) => `已保存到 ${a}`],
  [/^Freed (.+)\.$/, (m, a) => `释放了 ${a}。`],
  [/^(\d+) min$/, (m, a) => `${a} 分钟`], [/^(\d+) sec$/, (m, a) => `${a} 秒`],
  [/^([\d:]+) elapsed$/, (m, a) => `已用 ${a}`], [/^about (.+) left$/, (m, a) => `预计还需 ${tr(a)}`],
  [/^about (.+) once started$/, (m, a) => `开始后约需 ${tr(a)}`], [/^took ([\d:]+)$/, (m, a) => `用时 ${a}`],
  [/^preparing video (\d+) of (\d+)$/, (m, a, b) => `准备第 ${a}/${b} 个视频`],
  [/^(.+): sub-agents (\d+) of (\d+) finished$/, (m, a, b, c) => `${a}：子智能体完成 ${b}/${c}`],
  [/^(.+): (\d+) sub-agents viewing frames$/, (m, a, b) => `${a}：${b} 个子智能体正在看画面`],
  [/^(.+): video write-ups (\d+) of (\d+)$/, (m, a, b, c) => `${a}：视频撰写 ${b}/${c}`],
  [/^(.+): writing up each video$/, (m, a) => `${a}：正在逐个撰写视频`],
  [/^(.+): planning the chapters$/, (m, a) => `${a}：正在规划章节`],
  [/^(.+): writing (\d+) chapters$/, (m, a, b) => `${a}：正在撰写 ${b} 个章节`],
  [/^(.+): chapters (\d+) of (\d+)$/, (m, a, b, c) => `${a}：章节 ${b}/${c}`],
  [/^(.+): viewing frames \((\d+) opened\)$/, (m, a, b) => `${a}：正在看画面（已打开 ${b}）`],
  [/^(.+): (starting|writing)$/, (m, a, b) => `${a}：${ZH[b]}`],
  [/^(.+): working \((.+)\)$/, (m, a) => `${a}：处理中`],
  [/^(.+): (sending frames to the Claude API|waiting for the OpenAI API|waiting for the API)$/, (m, a) => `${a}：等待 API 响应`],
  [/^v(\d+) (captions|download|frames|transcribe|model)(.*)$/, (m, a, b, c) => `v${a} ${STAGES[b]}${c}`],
  [/^(captions|download|frames|transcribe|model)(.*)$/, (m, a, b) => `${STAGES[a]}${b}`],
];

function tr(s) {
  if (UI_LANG !== 'zh' || !s || !/[A-Za-z]/.test(s)) return s;
  const key = s.replace(/\s+/g, ' ').trim();
  if (!key) return s;
  const lead = s.match(/^\s*/)[0], trail = s.match(/\s*$/)[0];
  if (ZH[key] !== undefined) return lead + ZH[key] + trail;
  for (const [re, f] of ZH_RE) if (re.test(key)) return lead + key.replace(re, f) + trail;
  if (key.includes(' · ')) { const parts = key.split(' · ').map(p => tr(p)); if (parts.join(' · ') !== key) return lead + parts.join(' · ') + trail; }
  if (key.includes(' → ')) { const parts = key.split(' → ').map(p => tr(p)); if (parts.join(' → ') !== key) return lead + parts.join(' → ') + trail; }
  return s;
}
function trNode(n) {
  if (n.nodeType === 3) {
    const p = n.parentNode;
    if (!p || /^(SCRIPT|STYLE|TEXTAREA|PRE)$/.test(p.nodeName) || p.closest?.('[data-notr]')) return;
    const v = tr(n.nodeValue);
    if (v !== n.nodeValue) n.nodeValue = v;
  } else if (n.nodeType === 1) {
    if (n.closest('[data-notr]') || /^(SCRIPT|STYLE)$/.test(n.nodeName)) return;
    for (const a of ['placeholder', 'title']) if (n.hasAttribute?.(a)) { const v = tr(n.getAttribute(a)); if (v !== n.getAttribute(a)) n.setAttribute(a, v); }
    if (/^(TEXTAREA|PRE)$/.test(n.nodeName)) return;
    for (const c of n.childNodes) trNode(c);
  }
}
if (UI_LANG === 'zh') {
  document.documentElement.lang = 'zh-Hans';
  const native = {alert: window.alert, confirm: window.confirm, prompt: window.prompt};
  window.alert = m => native.alert.call(window, tr(String(m)));
  window.confirm = m => native.confirm.call(window, tr(String(m)));
  window.prompt = (m, d) => native.prompt.call(window, tr(String(m)), d);
  new MutationObserver(recs => {
    for (const r of recs) {
      if (r.type === 'characterData') trNode(r.target);
      else if (r.type === 'attributes') trNode(r.target);
      else r.addedNodes.forEach(trNode);
    }
  }).observe(document.documentElement, {subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['placeholder', 'title']});
  document.addEventListener('DOMContentLoaded', () => trNode(document.body));
}
