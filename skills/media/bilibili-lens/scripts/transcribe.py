#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["mlx-whisper>=0.4,<0.5"]
# ///
"""Download a Bilibili video's audio and transcribe it on this Mac with Whisper.

Usage: uv run transcribe.py --bvid BV1xxxxxxxxx [--part N] [--model medium]
                            [--language zh] [--refresh] [--audio-file PATH]

No login is used. The transcript is written to a cache file and only the header
and the file's path are printed, so a long video never overflows the terminal
output. Asking for the same video, part, model and language again reuses the
file instead of repeating a multi-minute transcription (--refresh forces a new
run). A transcript made from --audio-file is kept apart from the video's own.

The Whisper prompt is built here from the video's title, tags and chapter
titles. Whisper uses it as spelling context, which fixes terms that appear in
the title (measured: a title word written as a homophone in every mention was
right in all of them with the prompt). It does nothing for terms that are not in
it. The description is left out on purpose: it is full of boilerplate ("please
like and follow"), and over music or silence Whisper copies the prompt into the
transcript. The prompt text is never taken from the command line.
"""
import argparse
import datetime
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time

from bili_info import BV_RE, BiliError, canonical_url, fetch_video

MODEL_REPOS = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
}
DOWNLOAD_TIMEOUT_SECONDS = 900
CACHE_MAX_AGE_DAYS = 30
# Whisper keeps only the last ~223 tokens of a prompt; stay well under that so
# the opening of the prompt is not the part that gets cut.
PROMPT_MAX_CHARS = 160


def cache_dir():
    base = pathlib.Path(os.environ.get("XDG_CACHE_HOME") or pathlib.Path.home() / ".cache")
    path = base / "bilibili-lens" / "transcripts"
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def purge_old(directory):
    """Delete our own transcript files (and abandoned .partial files) older than CACHE_MAX_AGE_DAYS."""
    cutoff = time.time() - CACHE_MAX_AGE_DAYS * 86400
    for f in [*directory.glob("BV*.txt"), *directory.glob("BV*.partial")]:
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass


def cache_file(directory, bvid, part, model, language="", from_file=False):
    """One file per (video, part, model, language). A transcript of a local audio
    file never shares a name with the video's own: asking for another language, or
    handing in someone's clip, must not come back as the cached original."""
    suffix = f"-p{part}" if part else ""
    lang = f".lang-{language}" if language else ""
    source = ".file" if from_file else ""
    return directory / f"{bvid}{suffix}.{model}{lang}{source}.txt"


def build_prompt(info):
    """Spelling context for Whisper from the creator's own words (no description)."""
    title = (info.get("title") or "").strip()
    # Multi-part titles read "<series> p03 <part name>": the marker is noise.
    title = re.sub(r"\s+p\d{1,3}\s+", " ", title)
    chapters = "、".join((c.get("title") or "") for c in (info.get("chapters") or [])[:6])
    tags = "、".join((info.get("tags") or [])[:6])
    body = "。".join(p for p in (title, tags, chapters) if p)
    # No "this is Mandarin" cue: measured on the same audio it changed nothing
    # (the title alone gave identical results), and a Chinese cue in front of
    # Japanese or English speech is a language mismatch.
    return body[:PROMPT_MAX_CHARS]


# Whisper sometimes loops over music or silence and writes one short phrase
# dozens of times ("参加 参加 参加 ..."). Flagged only when a unit of 2 to 8
# characters, made of at least two different characters, repeats 8 or more times:
# laughter ("哈哈哈哈…"), "no no no no", digits and "bye bye bye" stay unflagged.
REPEAT_RE = re.compile(r"(.{2,8}?)(?:[\s,，。、!！?？]*\1){7,}")
REPEAT_MARK = "  ⟨疑似幻觉：同一内容连续重复⟩"
_NOT_A_LETTER = re.compile(r"[\s,，。、!！?？.]")


def flag_repetition(text):
    """Return (text, flagged). The text is kept; a marker is appended when it loops."""
    for m in REPEAT_RE.finditer(text):
        if len(set(_NOT_A_LETTER.sub("", m.group(1)))) >= 2:
            return text + REPEAT_MARK, True
    return text, False


# Other tell-tales of the same failure, across segments instead of inside one:
# the same line again and again (seen: "我就是在想" 14 times after the video's
# last words), and lines that start after the video has already ended.
LOOP_MIN_RUN = 4
BEYOND_MARK = "  ⟨疑似幻觉：时间已超出视频时长⟩"


def flag_segments(segments, duration=0):
    """segments: [(start, text)]. Returns ([(start, text-with-marker)], number flagged).

    Text is never removed, only marked, so a wrong flag costs a note, not content.
    """
    in_run = [False] * len(segments)
    i = 0
    while i < len(segments):
        j = i
        while j + 1 < len(segments) and segments[j + 1][1] == segments[i][1]:
            j += 1
        if j - i + 1 >= LOOP_MIN_RUN:
            in_run[i:j + 1] = [True] * (j - i + 1)
        i = j + 1

    out, flagged = [], 0
    for (start, text), run in zip(segments, in_run):
        text, marked = flag_repetition(text)
        if run and not marked:
            text, marked = text + REPEAT_MARK, True
        if not marked and duration and start >= duration:
            text, marked = text + BEYOND_MARK, True
        flagged += marked
        out.append((start, text))
    return out, flagged


def format_timestamp(seconds):
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"[{h}:{m:02d}:{s:02d}]" if h else f"[{m}:{s:02d}]"


def pick_audio_file(tmp_dir):
    """Largest complete file yt-dlp left behind (not a leftover .part)."""
    files = [f for f in pathlib.Path(tmp_dir).iterdir() if f.is_file() and f.suffix != ".part"]
    return str(max(files, key=lambda f: f.stat().st_size)) if files else None


def download_audio(url, tmp_dir):
    try:
        result = subprocess.run(
            ["yt-dlp", "-f", "bestaudio[ext=m4a]/bestaudio", "--no-playlist",
             "--no-cookies", "--no-cookies-from-browser",  # never logged in, whatever the user's config says
             "--socket-timeout", "30", "-o", f"{tmp_dir}/audio.%(ext)s", "--", url],
            capture_output=True, text=True, timeout=DOWNLOAD_TIMEOUT_SECONDS)
    except FileNotFoundError:
        raise BiliError("AUDIO_DOWNLOAD_FAILED", "yt-dlp is not installed — brew install yt-dlp")
    except subprocess.TimeoutExpired:
        raise BiliError("AUDIO_DOWNLOAD_FAILED", f"download timed out after {DOWNLOAD_TIMEOUT_SECONDS}s")
    if result.returncode != 0:
        lines = [l for l in result.stderr.strip().splitlines() if l.strip()]
        raise BiliError("AUDIO_DOWNLOAD_FAILED", lines[-1][:300] if lines else "no error output")
    path = pick_audio_file(tmp_dir)
    if path is None:
        raise BiliError("AUDIO_DOWNLOAD_FAILED", "yt-dlp exited 0 but produced no file")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bvid", required=True)
    parser.add_argument("--part", type=int, default=0)
    parser.add_argument("--model", default="medium")
    parser.add_argument("--language", default="")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--audio-file", default="",
                        help="transcribe this local file instead of downloading (the video is still looked up for its title)")
    args = parser.parse_args()

    if not BV_RE.fullmatch(args.bvid):
        print("ERROR:INVALID_INPUT: --bvid must look like BV1xxxxxxxxx")
        sys.exit(1)
    if args.model not in MODEL_REPOS:
        print(f"ERROR:INVALID_INPUT: unknown model {args.model!r} — use one of: {', '.join(MODEL_REPOS)}")
        sys.exit(1)
    if args.part < 0 or args.part > 9999:
        print("ERROR:INVALID_INPUT: --part must be a positive number")
        sys.exit(1)
    lang = (args.language or "").split("-")[0].lower().strip()
    if lang and not re.fullmatch(r"[a-z]{2,3}", lang):
        print("ERROR:INVALID_INPUT: --language must be a code like zh, en, ja")
        sys.exit(1)
    supplied = args.audio_file.strip()

    directory = cache_dir()
    purge_old(directory)
    target = cache_file(directory, args.bvid, args.part, args.model, lang, bool(supplied))

    if target.exists() and not args.refresh and not supplied:
        header = [l.rstrip("\n") for l in target.read_text(encoding="utf-8").splitlines() if not l.startswith("[")]
        print("CACHED: yes")
        print("\n".join(header))
        print(f"SEGMENTS: {sum(1 for l in target.read_text(encoding='utf-8').splitlines() if l.startswith('['))}")
        print(f"TRANSCRIPT_FILE: {target}")
        return

    try:
        import mlx_whisper
    except ImportError:
        print("ERROR:WHISPER_MISSING: mlx-whisper is not importable — run this script with `uv run` "
              "(not `python3`) so its declared dependencies are provided (Apple Silicon only)")
        sys.exit(1)
    if shutil.which("ffmpeg") is None:
        print("ERROR:FFMPEG_MISSING: brew install ffmpeg")
        sys.exit(1)

    try:
        info, part, count = fetch_video(args.bvid, args.part or None)
    except BiliError as e:
        print(f"ERROR:{e.code}: {e.message}")
        sys.exit(1)
    prompt = build_prompt(info)
    url = canonical_url(args.bvid, part if count > 1 else None)

    if supplied and not pathlib.Path(supplied).expanduser().is_file():
        print(f"ERROR:INVALID_INPUT: audio file not found: {supplied}")
        sys.exit(1)

    tmp_dir = None if supplied else tempfile.mkdtemp(prefix="bilibili-lens-audio-")
    try:
        try:
            audio_path = str(pathlib.Path(supplied).expanduser()) if supplied else download_audio(url, tmp_dir)
        except BiliError as e:
            print(f"ERROR:{e.code}: {e.message}")
            sys.exit(1)
        try:
            result = mlx_whisper.transcribe(
                audio_path,
                path_or_hf_repo=MODEL_REPOS[args.model],
                language=lang or None,
                condition_on_previous_text=False,
                initial_prompt=prompt or None,
                verbose=False,
            )
        except Exception as e:
            print(f"ERROR:TRANSCRIBE_FAILED: {type(e).__name__}: {e}")
            sys.exit(1)
    finally:
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    raw = [(seg["start"], seg["text"].strip()) for seg in (result.get("segments") or []) if seg["text"].strip()]
    segments, flagged = flag_segments(raw, info.get("duration") or 0)
    header = [
        f"BVID: {args.bvid}",
        f"PART: {part}",
        f"TITLE: {' '.join(str(info.get('title') or '').split())}",
        f"DURATION_SECONDS: {round(info.get('duration') or 0)}",
        f"LANG: {result.get('language') or lang}",
        f"SOURCE: whisper-{args.model}-local",
        f"PROMPT: {' '.join(prompt.split()) if prompt else '(none)'}",
        f"GENERATED: {datetime.date.today().isoformat()}",
        f"FLAGGED_SEGMENTS: {flagged}",
    ]
    body = "\n".join(f"{format_timestamp(start)} {text}" for start, text in segments)

    # Write to a temp name first so an interrupted run never leaves a half file
    # that a later call would take for a finished transcript.
    partial = target.with_name(f"{target.stem}.{os.getpid()}.partial")
    partial.write_text("\n".join(header) + "\n" + body + "\n", encoding="utf-8")
    partial.replace(target)

    print("CACHED: no")
    print("\n".join(header))
    print(f"SEGMENTS: {len(segments)}")
    print(f"TRANSCRIPT_FILE: {target}")


if __name__ == "__main__":
    main()
