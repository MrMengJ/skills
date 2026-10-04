#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["youtube-transcript-api>=1.2,<2", "requests>=2.32,<3"]
# ///
"""Fetch YouTube transcript and basic HTML metadata.

Usage: uv run fetch_transcript.py VIDEO_ID [LANG_PREF]

The block above declares the dependencies inline, so `uv run` provides them in
its own cached environment and nothing is installed into the system Python.
"""
import argparse
import datetime
import html as html_lib
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree


def _json_str(raw):
    """Decode a captured JSON string body; fall back to the raw text."""
    try:
        return json.loads(f'"{raw}"')
    except (ValueError, TypeError):
        return raw


def _fetch_html_metadata(video_id):
    try:
        req = urllib.request.Request(
            f"https://www.youtube.com/watch?v={video_id}",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", errors="ignore")

        m = re.search(r"<title>([^<]+)</title>", html)
        # The <title> element carries HTML entities ("Rock &amp; Roll"); the renderer
        # escapes again downstream, so decode here or the entity reaches the <h1> verbatim.
        title = html_lib.unescape(m.group(1)).replace(" - YouTube", "").strip() if m else ""

        # channelName is a JSON string literal: decode \u00e9-style escapes rather
        # than passing the raw source text through.
        channel = ""
        m_ch = re.search(r'"channelName"\s*:\s*"((?:[^"\\]|\\.)*)"', html)
        if m_ch:
            channel = _json_str(m_ch.group(1))

        published = ""
        m_pub = re.search(r'"publishDate"\s*:\s*"([^"]+)"', html)
        if m_pub:
            parts = m_pub.group(1)[:10].split("-")
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            published = f"{months[int(parts[1])-1]} {int(parts[2])} {parts[0]}"

        views = ""
        m_views = re.search(r'"viewCount"\s*:\s*"([0-9]+)"', html)
        if m_views:
            v = int(m_views.group(1))
            views = (f"{v/1e6:.1f}M views" if v >= 1e6
                     else f"{v/1e3:.0f}K views" if v >= 1e3
                     else f"{v} views")

        duration = ""
        m_dur = re.search(r'"lengthSeconds"\s*:\s*"([0-9]+)"', html)
        if m_dur:
            total_s = int(m_dur.group(1))
            h, rem = divmod(total_s, 3600)
            m2 = rem // 60
            duration = f"{h}h {m2}m" if h > 0 else f"{m2} min"

        return title, channel, published, views, duration
    except Exception:
        return "", "", "", "", ""


def _primary_lang(code):
    return (code or "").split("-")[0].split("_")[0].lower()


def _caption_type(track):
    return "auto-generated" if getattr(track, "is_generated", False) else "manual"


def _match_track(tracks, lang):
    """Track for an explicit language. Returns (track, exact); track is None if absent.

    Exact code first (case-insensitive: preflight lowercases what the user typed,
    YouTube reports zh-TW / pt-BR), then any track with the same primary subtag.
    `exact` is False when a regional or script variant was asked for (zh-TW) and
    only a different variant of that language exists (zh-CN) — the caller must
    say so rather than pass one off as the other.

    `tracks` keeps the API order (manual before auto-generated), so a manual
    track wins over an auto-generated one in the same language.
    """
    wanted = (lang or "").lower()
    for t in tracks:
        if (t.language_code or "").lower() == wanted:
            return t, True
    for t in tracks:
        if _primary_lang(t.language_code) == _primary_lang(wanted):
            return t, wanted == _primary_lang(wanted)
    return None, False


def _pick_original_track(tracks):
    """Pick the track in the video's spoken language. Returns (track, ambiguous).

    YouTube only auto-generates captions for the language actually spoken, so a
    single auto-generated language identifies the original. Prefer a manual
    track in that language (human-written beats speech recognition), then the
    auto-generated one. Manual tracks in other languages are translations.

    When that signal is missing (no auto-generated track) or unclear (dubbed
    videos carry one auto-generated track per audio language), fall back to the
    first track and flag the pick as ambiguous so the caller can verify it.
    """
    generated = [t for t in tracks if getattr(t, "is_generated", False)]
    manual = [t for t in tracks if not getattr(t, "is_generated", False)]
    gen_langs = {_primary_lang(t.language_code) for t in generated}

    if len(gen_langs) == 1:
        orig = generated[0].language_code
        same_lang = [t for t in manual if _primary_lang(t.language_code) == _primary_lang(orig)]
        for t in same_lang:
            if t.language_code == orig:
                return t, False
        return (same_lang[0] if same_lang else generated[0]), False

    if not generated and len({_primary_lang(t.language_code) for t in manual}) == 1:
        return manual[0], False

    return (manual or tracks)[0], True


def _error_code(e):
    """Typed error code for an exception raised while listing or fetching captions."""
    import youtube_transcript_api as yta

    # Order matters: IpBlocked subclasses RequestBlocked. Names missing from an
    # older library version are skipped.
    for name, code in (
        ("TranscriptsDisabled",  "ERROR:CAPTIONS_DISABLED"),
        ("AgeRestricted",        "ERROR:AGE_RESTRICTED"),
        ("VideoUnavailable",     "ERROR:VIDEO_UNAVAILABLE"),
        ("InvalidVideoId",       "ERROR:INVALID_VIDEO_ID"),
        ("IpBlocked",            "ERROR:IP_BLOCKED"),
        ("RequestBlocked",       "ERROR:REQUEST_BLOCKED"),
        ("PoTokenRequired",      "ERROR:PO_TOKEN_REQUIRED"),
        ("NoTranscriptFound",    "ERROR:NO_TRANSCRIPT"),
        ("YouTubeRequestFailed", "ERROR:NETWORK_ERROR"),
    ):
        cls = getattr(yta, name, None)
        if cls is not None and isinstance(e, cls):
            return code

    # Failures the library does not wrap. YouTube sometimes answers a throttled
    # caption request with an empty body, which surfaces as an XML ParseError.
    if isinstance(e, xml.etree.ElementTree.ParseError):
        return "ERROR:REQUEST_BLOCKED"
    try:
        import requests
        if isinstance(e, requests.exceptions.RequestException):
            return "ERROR:NETWORK_ERROR"
    except ImportError:
        pass
    return "ERROR:TRANSCRIPT_FETCH_FAILED"


def _fail(e):
    print(f"{_error_code(e)}: {type(e).__name__}: {e}")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video_id")
    parser.add_argument("lang_pref", nargs="?", default="")
    args = parser.parse_args()

    video_id = args.video_id
    lang_pref = args.lang_pref

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        print("ERROR:LIBRARY_MISSING: youtube-transcript-api is not importable — run this script "
              "with `uv run` (not `python3`) so its declared dependencies are provided")
        sys.exit(1)

    title, channel, published, views, duration = _fetch_html_metadata(video_id)
    if not title:
        title = f"YouTube video {video_id}"

    try:
        try:
            tlist = YouTubeTranscriptApi().list(video_id)
        except (AttributeError, TypeError):
            tlist = YouTubeTranscriptApi.list_transcripts(video_id)
    except Exception as e:
        _fail(e)

    tracks = list(tlist)
    if not tracks:
        print("ERROR:NO_TRANSCRIPT: the video lists no caption tracks")
        sys.exit(1)

    ambiguous = False
    if lang_pref:
        transcript_obj, exact = _match_track(tracks, lang_pref)
        if transcript_obj is None:
            transcript_obj, ambiguous = _pick_original_track(tracks)
            print(f'LANG_WARN: Requested language "{lang_pref}" not available; using {transcript_obj.language_code}')
        elif not exact:
            print(f'LANG_WARN: Requested language "{lang_pref}" not available; '
                  f'using {transcript_obj.language_code} (same language, different variant)')
    else:
        transcript_obj, ambiguous = _pick_original_track(tracks)

    try:
        transcript = transcript_obj.fetch()
    except Exception as e:
        # Blocks often hit here rather than at list(): map them to the same typed
        # codes so the caller can offer the local-transcription fallback.
        _fail(e)
    lang = transcript_obj.language_code

    # Detect entry type once before the loop
    use_dict = isinstance(transcript[0], dict) if transcript else False

    lines = [
        f"TITLE: {title}",
        f"CHANNEL: {channel}",
        f"PUBLISHED: {published}",
        f"VIEWS: {views}",
        f"DURATION: {duration}",
        f"DATE: {datetime.date.today().isoformat()}",
        f"LANG: {lang}",
        f"CAPTION_TYPE: {_caption_type(transcript_obj)}",
        "TRACKS: " + ", ".join(f"{t.language_code} ({_caption_type(t)})" for t in tracks),
    ]
    if ambiguous:
        lines.append(
            f"TRACK_AMBIGUOUS: could not tell the spoken language from the caption tracks; picked {lang}"
        )

    for s in transcript:
        text = s["text"] if use_dict else s.text
        start = s["start"] if use_dict else s.start
        total_s = int(start)
        h, rem = divmod(total_s, 3600)
        m2, s2 = divmod(rem, 60)
        if h > 0:
            lines.append(f"[{h}:{m2:02d}:{s2:02d}] {text}")
        else:
            lines.append(f"[{m2}:{s2:02d}] {text}")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
