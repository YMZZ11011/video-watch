"""Report languages: what the model is told, and the report's own headings and controls."""
from __future__ import annotations

LANGUAGES = {   # setting value -> (html lang, label in the app)
    "": ("en", "Same as the request"),
    "English": ("en", "English"),
    "Simplified Chinese": ("zh-Hans", "简体中文 (Simplified Chinese)"),
    "Traditional Chinese": ("zh-Hant", "繁體中文 (Traditional Chinese)"),
}


def code(s: dict) -> str:
    """The report's language code; a language the app has no headings for gets English ones."""
    return LANGUAGES.get(s.get("language") or "", ("en", ""))[0]


def prompt_rule(s: dict) -> str:
    lang = (s.get("language") or "").strip()
    if not lang:
        return ""
    if lang == "Simplified Chinese":
        return ("Write everything in Simplified Chinese (简体中文), whatever language the videos are in. The first time "
                "a technical term appears, give the English in brackets, e.g. 订单流 (order flow), 吸收 (absorption). "
                "Keep tickers, numbers, timestamps and quoted on-screen text exactly as shown. Lengths given in words "
                "mean English words: write about 1.6 Chinese characters for each word asked for.")
    if lang == "Traditional Chinese":
        return ("Write everything in Traditional Chinese (繁體中文), whatever language the videos are in. The first time "
                "a technical term appears, give the English in brackets, e.g. 訂單流 (order flow), 吸收 (absorption). "
                "Keep tickers, numbers, timestamps and quoted on-screen text exactly as shown. Lengths given in words "
                "mean English words: write about 1.6 Chinese characters for each word asked for.")
    if lang == "English":
        return ("Write everything in English, whatever language the videos are in. Translate quoted speech, and give "
                "the original wording in brackets where it matters.")
    return f"Write everything in {lang}."


def background_label(s: dict) -> str:
    return {"zh-Hans": "背景知识（非视频内容）：", "zh-Hant": "背景知識（非影片內容）："}.get(code(s), "Background, not from the videos:")


EN = {
    "item": "Item", "bundle": "Bundle of {n} videos", "combined": "Combined summary", "by_orch": "by the orchestrator",
    "glance": "The batch at a glance", "across": "Across these {n} items", "where": "Where each video is",
    "col_item": "Item", "col_video": "Video", "col_length": "Length", "col_category": "Category", "col_report": "Report",
    "col_id": "Id", "col_frames": "Frames", "col_transcript": "Transcript", "source": "source", "failed": "failed",
    "open": "open", "links_note": "The report links work from the reports folder and inside the app. Copies saved to "
    "your export folder have their own file names, so open those reports from there.", "items": "Items",
    "summary_failed": "The combined summary could not be written:", "no_ask": "No instructions given: general summary.",
    "unclean": "This item did not finish cleanly:", "sel_log": "Frame selection log",
    "sel_note": "The model chose these moments itself. Times are exactly what was extracted from the video.",
    "round": "Round {r}: asked for {a}, extracted {e}", "skipped": "skipped {n}", "col_frame": "Frame", "col_time": "Time",
    "col_why": "Why the model wanted it", "all_frames": "All frames examined ({n})", "frame_times": "Frame times examined ({n})",
    "transcript": "Transcript", "lines": "lines", "none": "none", "cited": "cited", "not_opened": "not opened",
    "per_stage": "Time per stage", "watched": "Watched", "engine": "Engine", "videos": "Videos", "frames": "Frames",
    "frame_width": "Frame width", "in_batch": "Videos in the batch", "watched_range": "watched {a} to {b} only",
    "chapters": "Chapters", "by_video": "Video by video", "depth": "Depth", "from": "from", "core": "core",
    "as_report": "depth as the report", "section_depth": "Depth of this section", "deeper": "Go deeper",
    "deeper_tag": "Deeper", "deeper_ph": "Optional: what to go deeper on, e.g. the maths of dealer hedging",
    "words_at": "about {n} words at this depth", "writing_more": "Writing more (usually one to three minutes)...",
    "added": "Added below. Saved in this report.", "deeper_fail": "Could not go deeper:", "run": "run",
    "default_title": "Video watch report", "overview": "overview", "overview_of": "Overview of {n} videos",
    "gist": "Gist", "summary": "Summary", "detailed": "Detailed", "deep": "Deep dive",
    "mode_interval": "Fixed interval", "mode_count": "Fixed count", "mode_scene": "Scene changes",
    "mode_keyframes": "Keyframes", "mode_dynamic": "Dynamic (model chooses)", "mode_transcript": "Transcript only",
}
ZH_HANS = {
    "item": "条目", "bundle": "{n} 个视频的合集", "combined": "综合摘要", "by_orch": "由统筹模型撰写",
    "glance": "整批概览", "across": "这 {n} 个条目的综合", "where": "各视频所在报告",
    "col_item": "条目", "col_video": "视频", "col_length": "时长", "col_category": "类别", "col_report": "报告",
    "col_id": "编号", "col_frames": "画面帧", "col_transcript": "字幕文本", "source": "原视频", "failed": "失败",
    "open": "打开", "links_note": "报告之间的链接在报告文件夹和应用内有效。导出文件夹中的副本使用各自的文件名，请从那里打开。",
    "items": "条目", "summary_failed": "综合摘要未能生成：", "no_ask": "未提供要求：通用摘要。",
    "unclean": "此条目未能顺利完成：", "sel_log": "选帧记录", "sel_note": "以下时刻由模型自行选择，时间为实际截取的时间。",
    "round": "第 {r} 轮：请求 {a} 帧，截取 {e} 帧", "skipped": "跳过 {n}", "col_frame": "帧", "col_time": "时间",
    "col_why": "模型选择的原因", "all_frames": "全部查看过的画面（{n}）", "frame_times": "查看过的画面时间（{n}）",
    "transcript": "字幕文本", "lines": "行", "none": "无", "cited": "已引用", "not_opened": "未打开",
    "per_stage": "各阶段用时", "watched": "观看方式", "engine": "模型", "videos": "视频", "frames": "画面帧",
    "frame_width": "画面宽度", "in_batch": "本批视频", "watched_range": "仅观看 {a} 至 {b}",
    "chapters": "章节", "by_video": "逐个视频", "depth": "深度", "from": "来源", "core": "核心",
    "as_report": "与全文一致", "section_depth": "本节深度", "deeper": "深入展开", "deeper_tag": "深入",
    "deeper_ph": "可选：想深入的方向，例如做市商对冲的数学原理", "words_at": "此深度约 {n} 字",
    "writing_more": "正在撰写（通常需要一到三分钟）……", "added": "已添加在下方，并保存到本报告。", "deeper_fail": "无法深入展开：",
    "run": "运行", "default_title": "视频观看报告", "overview": "概览", "overview_of": "{n} 个视频概览",
    "gist": "要点", "summary": "摘要", "detailed": "详细", "deep": "深度解析",
    "mode_interval": "固定间隔", "mode_count": "固定数量", "mode_scene": "场景切换", "mode_keyframes": "关键帧",
    "mode_dynamic": "动态（模型选择）", "mode_transcript": "仅字幕",
}
ZH_HANT = {
    "item": "條目", "bundle": "{n} 部影片的合集", "combined": "綜合摘要", "by_orch": "由統籌模型撰寫",
    "glance": "整批概覽", "across": "這 {n} 個條目的綜合", "where": "各影片所在報告",
    "col_item": "條目", "col_video": "影片", "col_length": "長度", "col_category": "類別", "col_report": "報告",
    "col_id": "編號", "col_frames": "畫面", "col_transcript": "字幕文字", "source": "原影片", "failed": "失敗",
    "open": "開啟", "links_note": "報告之間的連結在報告資料夾和應用程式內有效。匯出資料夾中的副本使用各自的檔名，請從那裡開啟。",
    "items": "條目", "summary_failed": "綜合摘要未能產生：", "no_ask": "未提供要求：一般摘要。",
    "unclean": "此條目未能順利完成：", "sel_log": "選幀記錄", "sel_note": "以下時刻由模型自行選擇，時間為實際擷取的時間。",
    "round": "第 {r} 輪：請求 {a} 幀，擷取 {e} 幀", "skipped": "略過 {n}", "col_frame": "幀", "col_time": "時間",
    "col_why": "模型選擇的原因", "all_frames": "全部檢視過的畫面（{n}）", "frame_times": "檢視過的畫面時間（{n}）",
    "transcript": "字幕文字", "lines": "行", "none": "無", "cited": "已引用", "not_opened": "未開啟",
    "per_stage": "各階段用時", "watched": "觀看方式", "engine": "模型", "videos": "影片", "frames": "畫面",
    "frame_width": "畫面寬度", "in_batch": "本批影片", "watched_range": "僅觀看 {a} 至 {b}",
    "chapters": "章節", "by_video": "逐部影片", "depth": "深度", "from": "來源", "core": "核心",
    "as_report": "與全文一致", "section_depth": "本節深度", "deeper": "深入展開", "deeper_tag": "深入",
    "deeper_ph": "可選：想深入的方向，例如造市商避險的數學原理", "words_at": "此深度約 {n} 字",
    "writing_more": "正在撰寫（通常需要一到三分鐘）……", "added": "已加在下方，並儲存到本報告。", "deeper_fail": "無法深入展開：",
    "run": "執行", "default_title": "影片觀看報告", "overview": "概覽", "overview_of": "{n} 部影片概覽",
    "gist": "要點", "summary": "摘要", "detailed": "詳細", "deep": "深度解析",
    "mode_interval": "固定間隔", "mode_count": "固定數量", "mode_scene": "場景切換", "mode_keyframes": "關鍵幀",
    "mode_dynamic": "動態（模型選擇）", "mode_transcript": "僅字幕",
}
TABLES = {"en": EN, "zh-Hans": ZH_HANS, "zh-Hant": ZH_HANT}


def strings(s: dict) -> dict:
    return TABLES.get(code(s), EN)
