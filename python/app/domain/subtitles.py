from concurrent.futures import ThreadPoolExecutor
import json
import logging
from pathlib import Path
import re
import time
from typing import Callable, List, Optional, Tuple
import requests

from app.i18n import LRE, LRM, PDF, RLE, RLM, tp

logger = logging.getLogger(__name__)

RTL_LANG_PREFIXES = ("ar", "fa", "ur", "he", "yi", "ps", "sd", "ug", "ckb")
TIMECODE_RE = re.compile(
    r"(\d{1,2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{3})"
)
VTT_SHORT_TIMECODE_RE = re.compile(
    r"(\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}[,\.]\d{3})"
)
HTML_TAG_RE = re.compile(r"<[^>]+>")
ARABIC_CHARS_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")


class SubtitlePauseRequested(Exception):
    pass


class SubtitleCancelRequested(Exception):
    pass


def tc_to_ms(tc: str) -> int:
    """Converts HH:MM:SS,mmm or MM:SS,mmm into exact integer milliseconds."""
    clean = tc.strip().replace(".", ",")
    if "," in clean:
        main_part, ms_part = clean.split(",", 1)
        ms = int((ms_part + "000")[:3])
    else:
        main_part = clean
        ms = 0
    parts = [int(p) for p in main_part.split(":")]
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h, m, s = 0, parts[0], parts[1]
    else:
        h, m, s = 0, 0, parts[0]
    return ((h * 3600) + (m * 60) + s) * 1000 + ms


def ms_to_srt_tc(ms: int) -> str:
    """Formats integer milliseconds as strict SRT timestamp HH:MM:SS,mmm."""
    ms = max(0, int(ms))
    h = ms // 3600000
    rem = ms % 3600000
    m = rem // 60000
    rem = rem % 60000
    s = rem // 1000
    millis = rem % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{millis:03d}"


class SubtitleCue:
    def __init__(self, index: int, start_tc: str, end_tc: str, text: str) -> None:
        self.index = index
        self.start_ms = tc_to_ms(start_tc)
        self.end_ms = max(self.start_ms + 180, tc_to_ms(end_tc))
        self.text = text.strip()

    @property
    def start_tc(self) -> str:
        return ms_to_srt_tc(self.start_ms)

    @property
    def end_tc(self) -> str:
        return ms_to_srt_tc(self.end_ms)


def is_rtl_language(lang_code: str) -> bool:
    code = (lang_code or "").strip().lower()
    return any(code == p or code.startswith(f"{p}-") or code.startswith(f"{p}_") for p in RTL_LANG_PREFIXES)


def format_bidi_line(line: str, target_is_rtl: bool, tv_safe: bool = True) -> str:
    """
    Formats a subtitle line for proper RTL/LTR punctuation, bracket, and mixed-script rendering.
    - When `tv_safe=True` (default): uses zero-width directional marks (`RLM` / `LRM`) at line boundaries
      and around trailing punctuation without raw `RLE`/`LRE`/`PDF` (`U+202A..U+202C`), preventing
      Smart TVs and hardware players from rendering missing-glyph boxes (`□`) while keeping brackets
      and periods on the correct side in VLC, MPC-HC, MPV, PotPlayer, and TVs!
    - When `tv_safe=False`: wraps with full `RLE`/`LRE` + `PDF` embedding controls.
    """
    clean = line.strip()
    if not clean:
        return ""
    for ch in (LRM, RLM, LRE, RLE, PDF, "\u2066", "\u2067", "\u2068", "\u2069"):
        clean = clean.replace(ch, "")
    clean = clean.strip()
    if not clean:
        return ""

    if tv_safe:
        if target_is_rtl or ARABIC_CHARS_RE.search(clean):
            return f"{RLM}{clean}{RLM}"
        return f"{LRM}{clean}{LRM}"

    if target_is_rtl:
        return f"{RLM}{RLE}{clean}{PDF}{RLM}"
    return f"{LRM}{LRE}{clean}{PDF}{LRM}"


def wrap_subtitle_lines_cleanly(text: str, max_line_chars: int = 52) -> List[str]:
    """
    Wraps a subtitle cue into at most 2 balanced lines (or 1 clean line if <= max_line_chars)
    so media players never stack 3-4 lines or wrap awkwardly.
    """
    single = " ".join(text.split()).strip()
    if not single:
        return []
    if len(single) <= max_line_chars:
        return [single]

    words = single.split(" ")
    if len(words) <= 2:
        return [single]

    mid_char = len(single) // 2
    best_split = 1
    best_dist = 9999
    running = 0
    for i in range(1, len(words)):
        running += len(words[i - 1]) + (1 if i > 1 else 0)
        dist = abs(running - mid_char)
        if dist < best_dist:
            best_dist = dist
            best_split = i

    line1 = " ".join(words[:best_split]).strip()
    line2 = " ".join(words[best_split:]).strip()
    return [line1, line2] if (line1 and line2) else [single]


def apply_bidi_to_block(
    text: str,
    target_lang: str,
    enforce_bidi: bool = True,
    tv_safe: bool = True,
) -> str:
    wrapped_lines = wrap_subtitle_lines_cleanly(text, max_line_chars=54)
    if not wrapped_lines:
        return ""
    if not enforce_bidi:
        return "\n".join(wrapped_lines)
    target_rtl = is_rtl_language(target_lang)
    return "\n".join(format_bidi_line(ln, target_rtl, tv_safe=tv_safe) for ln in wrapped_lines if ln.strip())


def _normalize_tc(tc: str) -> str:
    tc = tc.strip().replace(".", ",")
    parts = tc.split(":")
    if len(parts) == 2:
        return f"00:{parts[0]}:{parts[1]}"
    if len(parts) == 3 and len(parts[0]) == 1:
        return f"0{parts[0]}:{parts[1]}:{parts[2]}"
    return tc


def _remove_rolling_overlap(prev_text: str, curr_text: str, overlapped_in_time: bool = True) -> str:
    """
    YouTube VTT/SRV3 auto-captions often repeat the tail of Cue N at the start of Cue N+1.
    Strips the rolling prefix ONLY when cues overlapped/touched in time or share a multi-word rolling prefix,
    preserving legitimate repeated short utterances like "No." followed by "No.".
    """
    p_clean = " ".join(prev_text.split()).strip()
    c_clean = " ".join(curr_text.split()).strip()
    if not p_clean or not c_clean:
        return c_clean

    if c_clean == p_clean:
        # Only collapse identical lines if they actually overlapped in time (rolling VTT snapshot)
        # or are multi-word sentences; never erase distinct short utterances like "No." -> "No."
        if overlapped_in_time or len(p_clean.split()) >= 3:
            return ""
        return c_clean

    if c_clean.startswith(p_clean) and (overlapped_in_time or len(p_clean.split()) >= 2):
        return c_clean[len(p_clean) :].strip()

    p_words = p_clean.split(" ")
    c_words = c_clean.split(" ")
    max_k = min(len(p_words), len(c_words))
    # Require at least 2 words of suffix->prefix overlap (or overlapped_in_time)
    min_k = 1 if overlapped_in_time else 2
    for k in range(max_k, min_k - 1, -1):
        if p_words[-k:] == c_words[:k]:
            rem = " ".join(c_words[k:]).strip()
            return rem
    return c_clean


def _has_heavy_rolling_overlap(cues: List[SubtitleCue]) -> bool:
    """Detects whether a parsed cue list exhibits YouTube VTT auto-caption rolling timestamp overlap."""
    if len(cues) < 2:
        return False
    overlap_count = 0
    for i in range(len(cues) - 1):
        if cues[i].end_ms > cues[i + 1].start_ms:
            overlap_count += 1
        else:
            p_txt = " ".join(cues[i].text.split()).strip()
            c_txt = " ".join(cues[i + 1].text.split()).strip()
            if p_txt and c_txt.startswith(p_txt) and len(p_txt.split()) >= 2:
                overlap_count += 1
    return overlap_count >= 1 and (overlap_count / float(len(cues) - 1)) >= 0.25


def reconstruct_and_clamp_cues(
    raw_cues: List[SubtitleCue],
    is_auto_generated: Optional[bool] = None,
) -> List[SubtitleCue]:
    """
    1. If `is_auto_generated` is False (manual human subtitles) and the file does not have
       heavy VTT rolling overlap:
       - Preserves the human translator's exact cue boundaries and intentional repeated lines (e.g. "No." / "No.").
       - Strictly clamps any overlapping timestamps (`cue[i].end_ms <= cue[i+1].start_ms - 40`) so two lines never stack vertically.
    2. If `is_auto_generated` is True (or the VTT file has rolling auto-caption overlaps):
       - Filters micro-transition cues (< 130ms), removes rolling word overlaps, coalesces fragmented
         auto-caption phrases into complete sentences, and clamps timestamps (`- 45ms`).
    """
    if not raw_cues:
        return []

    sorted_cues = sorted(raw_cues, key=lambda c: (c.start_ms, c.end_ms))

    if is_auto_generated is None:
        use_auto_coalesce = _has_heavy_rolling_overlap(sorted_cues)
    else:
        use_auto_coalesce = bool(is_auto_generated)

    if not use_auto_coalesce:
        # Manual / Human Subtitles: preserve exact cues & short repeated lines, only clamp overlaps!
        manual_final: List[SubtitleCue] = []
        for idx, c in enumerate(sorted_cues, start=1):
            txt = " ".join(c.text.split()).strip()
            if not txt:
                continue
            item = SubtitleCue(len(manual_final) + 1, ms_to_srt_tc(c.start_ms), ms_to_srt_tc(c.end_ms), txt)
            manual_final.append(item)

        for i in range(len(manual_final) - 1):
            nxt_start = manual_final[i + 1].start_ms
            if manual_final[i].end_ms > nxt_start - 40:
                manual_final[i].end_ms = max(manual_final[i].start_ms + 140, nxt_start - 40)
            manual_final[i].index = i + 1
        if manual_final:
            manual_final[-1].index = len(manual_final)
        return manual_final

    # Auto-Generated Subtitles: de-roll, coalesce fragments, and clamp!
    deduped: List[SubtitleCue] = []
    for c in sorted_cues:
        txt = " ".join(c.text.split()).strip()
        if not txt:
            continue
        if (c.end_ms - c.start_ms) < 130 and deduped:
            continue

        if deduped:
            prev = deduped[-1]
            overlapped = prev.end_ms >= c.start_ms - 50
            cleaned = _remove_rolling_overlap(prev.text, txt, overlapped_in_time=overlapped)
            if not cleaned:
                prev.end_ms = max(prev.end_ms, c.end_ms)
                continue
            txt = cleaned

        item = SubtitleCue(len(deduped) + 1, ms_to_srt_tc(c.start_ms), ms_to_srt_tc(c.end_ms), txt)
        deduped.append(item)

    if not deduped:
        return []

    for i in range(len(deduped) - 1):
        nxt_start = deduped[i + 1].start_ms
        if deduped[i].end_ms >= nxt_start:
            deduped[i].end_ms = max(deduped[i].start_ms + 180, nxt_start - 40)

    coalesced: List[SubtitleCue] = []
    for c in deduped:
        if not coalesced:
            coalesced.append(c)
            continue

        prev = coalesced[-1]
        gap_ms = c.start_ms - prev.end_ms
        combined_len = len(prev.text) + 1 + len(c.text)
        combined_dur = c.end_ms - prev.start_ms
        ends_sentence = prev.text.endswith((".", "!", "?", "؟", "।", ":", ";"))

        if (
            not ends_sentence
            and gap_ms <= 450
            and combined_len <= 82
            and combined_dur <= 5800
            and (len(prev.text.split()) <= 6 or len(c.text.split()) <= 4)
        ):
            prev.text = f"{prev.text} {c.text}".strip()
            prev.end_ms = c.end_ms
        else:
            coalesced.append(c)

    final_cues: List[SubtitleCue] = []
    for idx, c in enumerate(coalesced, start=1):
        if idx < len(coalesced):
            next_c = coalesced[idx]
            if c.end_ms > next_c.start_ms - 45:
                c.end_ms = max(c.start_ms + 150, next_c.start_ms - 45)
        c.index = idx
        final_cues.append(c)

    return final_cues


def _parse_json3_subtitles(raw_json: str, is_auto_generated: Optional[bool] = True) -> List[SubtitleCue]:
    cues: List[SubtitleCue] = []
    try:
        data = json.loads(raw_json)
        events = data.get("events") or []
        idx = 1
        for ev in events:
            segs = ev.get("segs")
            if not segs:
                continue
            text = "".join(s.get("utf8", "") for s in segs).strip()
            text = re.sub(r"\s+", " ", text).strip()
            if not text:
                continue
            start_ms = int(ev.get("tStartMs") or 0)
            dur_ms = int(ev.get("dDurationMs") or 2500)
            start_tc = ms_to_srt_tc(start_ms)
            end_tc = ms_to_srt_tc(start_ms + dur_ms)
            cues.append(SubtitleCue(idx, start_tc, end_tc, text))
            idx += 1
    except Exception as exc:
        logger.debug("json3 parse error: %s", exc)
    return reconstruct_and_clamp_cues(cues, is_auto_generated=is_auto_generated)


def parse_subtitle_file(path: Path, is_auto_generated: Optional[bool] = None) -> List[SubtitleCue]:
    """
    Parses .srt, .vtt, and .json3 subtitle files.
    - Coalesces fragmented cues ONLY if `is_auto_generated` is True (or if a VTT/json3 file has rolling overlaps).
    - Always clamps overlapping cue timestamps so two subtitle lines never stack on screen.
    """
    raw = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    if raw.strip().startswith("{") and '"events"' in raw:
        return _parse_json3_subtitles(raw, is_auto_generated=True if is_auto_generated is None else is_auto_generated)

    raw = raw.replace("\r\n", "\n").replace("\r", "\n")

    blocks = re.split(r"\n\s*\n", raw)
    raw_cues: List[SubtitleCue] = []
    idx_counter = 1

    for block in blocks:
        lines = [ln.strip() for ln in block.strip().split("\n") if ln.strip()]
        if not lines:
            continue
        if (
            lines[0].upper().startswith("WEBVTT")
            or lines[0].startswith("NOTE")
            or lines[0].startswith("Kind:")
            or lines[0].startswith("Language:")
        ):
            continue

        tc_line_idx = -1
        start_tc, end_tc = "", ""
        for i, ln in enumerate(lines):
            m = TIMECODE_RE.search(ln)
            if not m:
                m = VTT_SHORT_TIMECODE_RE.search(ln)
            if m:
                tc_line_idx = i
                start_tc = _normalize_tc(m.group(1))
                end_tc = _normalize_tc(m.group(2))
                break

        if tc_line_idx == -1:
            continue

        payload_lines = lines[tc_line_idx + 1 :]
        cleaned_lines: List[str] = []
        for pl in payload_lines:
            no_tags = HTML_TAG_RE.sub("", pl).strip()
            for ch in (LRM, RLM, LRE, RLE, PDF):
                no_tags = no_tags.replace(ch, "")
            no_tags = no_tags.strip()
            if no_tags and (not cleaned_lines or cleaned_lines[-1] != no_tags):
                cleaned_lines.append(no_tags)

        text_body = " ".join(cleaned_lines).strip()
        if not text_body:
            continue

        raw_cues.append(SubtitleCue(idx_counter, start_tc, end_tc, text_body))
        idx_counter += 1

    return reconstruct_and_clamp_cues(raw_cues, is_auto_generated=is_auto_generated)


def write_srt_file(
    cues: List[SubtitleCue],
    out_path: Path,
    lang_code: str,
    enforce_bidi: bool = True,
    tv_safe: bool = True,
) -> Path:
    out_lines: List[str] = []
    out_idx = 1
    for cue in cues:
        formatted_text = apply_bidi_to_block(
            cue.text,
            lang_code,
            enforce_bidi=enforce_bidi,
            tv_safe=tv_safe,
        )
        if not formatted_text:
            continue
        out_lines.append(f"{out_idx}")
        out_lines.append(f"{cue.start_tc} --> {cue.end_tc}")
        out_lines.append(formatted_text)
        out_lines.append("")
        out_idx += 1

    srt_path = out_path.with_suffix(".srt")
    srt_path.write_text("\ufeff" + "\n".join(out_lines), encoding="utf-8")
    return srt_path


def _translate_with_retry_and_fallback(
    session: requests.Session,
    text: str,
    src: str,
    tgt: str,
    max_retries: int = 3,
) -> Tuple[str, bool]:
    """
    Multi-provider translation with exponential backoff:
    1. Primary: Google GTX (`translate.googleapis.com`) with exponential backoff retries.
    2. Secondary: Google Clients5 (`clients5.google.com`).
    3. Tertiary Fallback: MyMemory REST API (`api.mymemory.translated.net`) for resilient fallback.
    Returns `(translated_text, success_bool)`. Never silently pretends failure is success!
    """
    if not text.strip():
        return text, True

    # 1. Try Primary & Secondary Google endpoints with exponential backoff
    for attempt in range(max_retries):
        if attempt > 0:
            time.sleep(0.35 * (2 ** (attempt - 1)))
        try:
            resp = session.get(
                "https://translate.googleapis.com/translate_a/single",
                params={
                    "client": "gtx",
                    "sl": src,
                    "tl": tgt,
                    "dt": "t",
                    "q": text,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data and isinstance(data[0], list):
                    pieces = [seg[0] for seg in data[0] if isinstance(seg, list) and seg and seg[0]]
                    joined = "".join(pieces).strip()
                    if joined:
                        return joined, True
        except Exception as exc:
            logger.debug("GTX primary attempt %d error: %s", attempt + 1, exc)

        try:
            resp2 = session.get(
                "https://clients5.google.com/translate_a/t",
                params={
                    "client": "dict-chrome-ex",
                    "sl": src,
                    "tl": tgt,
                    "q": text,
                },
                timeout=10,
            )
            if resp2.status_code == 200:
                data2 = resp2.json()
                if isinstance(data2, list) and data2:
                    if isinstance(data2[0], str) and data2[0].strip():
                        return data2[0].strip(), True
                    if isinstance(data2[0], list) and data2[0] and str(data2[0][0]).strip():
                        return str(data2[0][0]).strip(), True
        except Exception as exc:
            logger.debug("GTX secondary attempt %d error: %s", attempt + 1, exc)

    # 2. Tertiary Fallback Provider: MyMemory REST API (for single cues or short batches <= 500 chars)
    if len(text) <= 500:
        try:
            src_mm = "en" if src == "auto" else src
            resp3 = session.get(
                "https://api.mymemory.translated.net/get",
                params={"q": text, "langpair": f"{src_mm}|{tgt}"},
                timeout=10,
            )
            if resp3.status_code == 200:
                data3 = resp3.json()
                tr_mm = str((data3.get("responseData") or {}).get("translatedText") or "").strip()
                if tr_mm and "MYMEMORY WARNING" not in tr_mm.upper():
                    return tr_mm, True
        except Exception as exc:
            logger.debug("MyMemory fallback provider error: %s", exc)

    return text, False


def _check_control_state(
    cancel_check: Optional[Callable[[], bool]],
    state_check: Optional[Callable[[], str]],
) -> None:
    if state_check is not None:
        st = state_check()
        if st == "pause":
            raise SubtitlePauseRequested("Subtitle translation paused by user")
        if st == "cancel":
            raise SubtitleCancelRequested("Subtitle translation canceled by user")
    if cancel_check is not None and cancel_check():
        raise SubtitleCancelRequested("Subtitle translation canceled by user")


def translate_cues_batch(
    cues: List[SubtitleCue],
    source_lang: str,
    target_lang: str,
    progress_cb: Optional[Callable[[float], None]] = None,
    cue_progress_cb: Optional[Callable[[int, int, float], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    state_check: Optional[Callable[[], str]] = None,
) -> Tuple[List[SubtitleCue], int]:
    """
    Context-Aware Batch Subtitle Translator with Retry, Backoff, Fallback Provider, and Failure Tracking.
    Returns `(translated_cues, failed_cue_count)`.
    """
    if not cues or not target_lang:
        return cues, 0

    src = "auto" if not source_lang or source_lang == "auto" else source_lang.split("-")[0].lower()
    tgt = target_lang if target_lang in ("zh-CN", "zh-TW") else target_lang.split("-")[0].lower()

    if src == tgt and src != "auto":
        return cues, 0

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            )
        }
    )

    translated_cues: List[SubtitleCue] = []
    failed_count = 0
    batch_size = 16
    total = len(cues)

    if cue_progress_cb:
        cue_progress_cb(0, total, 0.0)

    try:
        for start_i in range(0, total, batch_size):
            _check_control_state(cancel_check, state_check)
            chunk = cues[start_i : start_i + batch_size]

            clean_source_lines = [" ".join(c.text.splitlines()).strip() for c in chunk]
            batch_payload = "\n".join(clean_source_lines)

            translated_blob, ok_batch = _translate_with_retry_and_fallback(session, batch_payload, src, tgt)
            out_lines = [ln.strip() for ln in translated_blob.split("\n") if ln.strip()]

            if ok_batch and len(out_lines) == len(chunk):
                for c, tr_text in zip(chunk, out_lines):
                    translated_cues.append(
                        SubtitleCue(c.index, c.start_tc, c.end_tc, tr_text or c.text)
                    )
            else:
                def _tr_one(cue_item: SubtitleCue) -> Tuple[SubtitleCue, bool]:
                    if cancel_check and cancel_check():
                        return cue_item, False
                    if state_check and state_check() != "run":
                        return cue_item, False
                    single_src = " ".join(cue_item.text.splitlines()).strip()
                    tr_val, ok_single = _translate_with_retry_and_fallback(session, single_src, src, tgt)
                    return (
                        SubtitleCue(cue_item.index, cue_item.start_tc, cue_item.end_tc, tr_val or cue_item.text),
                        ok_single,
                    )

                with ThreadPoolExecutor(max_workers=4) as pool:
                    chunk_results = list(pool.map(_tr_one, chunk))

                for res_cue, ok_flag in chunk_results:
                    translated_cues.append(res_cue)
                    if not ok_flag:
                        failed_count += 1

            _check_control_state(cancel_check, state_check)
            done_n = min(total, start_i + len(chunk))
            pct = min(100.0, (done_n / float(total)) * 100.0)
            if progress_cb:
                progress_cb(pct)
            if cue_progress_cb:
                cue_progress_cb(done_n, total, pct)
    finally:
        session.close()

    return translated_cues, failed_count


def process_and_sync_subtitle(
    raw_sub_path: Path,
    source_lang: str,
    target_lang: str,
    do_translate: bool,
    enforce_bidi: bool,
    is_auto_generated: Optional[bool] = None,
    tv_safe_bidi: bool = True,
    progress_cb: Optional[Callable[[float], None]] = None,
    cue_progress_cb: Optional[Callable[[int, int, float], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    state_check: Optional[Callable[[], str]] = None,
) -> Tuple[Path, int, int]:
    """
    Parses, optionally translates with retry/fallback, applies BiDi formatting, and saves `.srt`.
    Returns `(written_srt_path, total_cues, failed_translation_cues)`.
    Raises RuntimeError if translation was requested (`do_translate=True`) and 100% of cues failed!
    """
    _check_control_state(cancel_check, state_check)
    cues = parse_subtitle_file(raw_sub_path, is_auto_generated=is_auto_generated)
    if not cues:
        raise ValueError(f"Could not parse any subtitle cues from {raw_sub_path.name}")

    total = len(cues)
    failed_cues = 0
    if cue_progress_cb:
        cue_progress_cb(0, total, 2.0)

    final_lang = target_lang if (do_translate and target_lang) else (source_lang if source_lang != "auto" else "ar")

    src_base = (source_lang or "auto").split("-")[0].lower()
    tgt_base = (target_lang or "").split("-")[0].lower()

    if do_translate and tgt_base and (src_base == "auto" or tgt_base != src_base):
        cues, failed_cues = translate_cues_batch(
            cues,
            source_lang=source_lang,
            target_lang=target_lang,
            progress_cb=progress_cb,
            cue_progress_cb=cue_progress_cb,
            cancel_check=cancel_check,
            state_check=state_check,
        )
        if failed_cues >= total and total > 0:
            raise RuntimeError(
                tp(
                    "تعذّر الاتصال بخدمات الترجمة بعد عدة محاولات — يرجى التحقق من اتصال الإنترنت وإعادة المحاولة.",
                    "Subtitle translation failed across all providers after multiple retries — please check your internet connection.",
                )
            )
    else:
        if cue_progress_cb:
            cue_progress_cb(total, total, 100.0)

    stem_base = raw_sub_path.stem
    for ext_candidate in (f".{source_lang}", f".{target_lang}", ".orig", ".live_chat"):
        if ext_candidate != "." and stem_base.endswith(ext_candidate):
            stem_base = stem_base[: -len(ext_candidate)]

    out_srt = raw_sub_path.parent / f"{stem_base}.{final_lang}.srt"
    written = write_srt_file(cues, out_srt, final_lang, enforce_bidi=enforce_bidi, tv_safe=tv_safe_bidi)
    return written, len(cues), failed_cues
