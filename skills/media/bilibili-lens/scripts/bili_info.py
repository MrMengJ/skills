#!/usr/bin/env python3
"""Resolve a Bilibili video reference and print its metadata. Needs no login.

Usage: python3 bili_info.py "<video URL | BV id | av id | b23.tv short link>"

Accepts what people paste: https://www.bilibili.com/video/BV1xxxxxxxxx/?p=3,
a bare BV or av id, m.bilibili.com links, b23.tv short links, and the text the
Bilibili app produces when sharing ("【title-哔哩哔哩】 https://b23.tv/xxxx"): the
Bilibili part is cut out of surrounding words. Only ordinary videos are
supported (not bangumi, live, articles or dynamics).

Prints `KEY: value` lines on stdout. On failure prints `ERROR:CODE: message`
and exits 1. The raw text the user gave is never passed to yt-dlp: the id and
part number are extracted first and a canonical URL is rebuilt from them.
"""
import argparse
import datetime
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"
ALLOWED_HOSTS = ("bilibili.com", "b23.tv")
BV_RE = re.compile(r"BV[0-9A-Za-z]{10}")
AV_RE = re.compile(r"av(\d{1,12})", re.I)
# Where an id can sit in a Bilibili URL: /video/<id>, a bare /<BV id> segment
# (watch-later playlists), or a bvid= parameter (embedded player, watch-later).
VIDEO_PATH_RE = re.compile(r"/video/(BV[0-9A-Za-z]{10}|av\d{1,12})(?![0-9A-Za-z])", re.I)
BV_SEGMENT_RE = re.compile(r"/(BV[0-9A-Za-z]{10})(?![0-9A-Za-z])", re.I)
NOT_A_VIDEO_PREFIXES = ("/bangumi/", "/cheese/", "/read/", "/opus/", "/festival/")
URL_IN_TEXT_RE = re.compile(r"https?://[^\s<>\"'「」【】（）()，。！？]+", re.I)
ID_IN_TEXT_RE = re.compile(r"(?<![0-9A-Za-z])(BV[0-9A-Za-z]{10}|av\d{1,12})(?![0-9A-Za-z])", re.I)
BARE_REF_RE = re.compile(r"(BV[0-9A-Za-z]{10}|av\d{1,12})(?:\?p=(\d{1,4}))?", re.I)
MAX_PART = 9999
DESCRIPTION_LIMIT = 2000


class BiliError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def _host_allowed(url):
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return parsed.scheme in ("http", "https") and any(
        host == d or host.endswith("." + d) for d in ALLOWED_HOSTS)


class _HostCheckedRedirect(urllib.request.HTTPRedirectHandler):
    """Follow short-link redirects, but only to Bilibili hosts."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _host_allowed(newurl):
            raise urllib.error.URLError(
                f"redirected to an unexpected host: {urllib.parse.urlparse(newurl).hostname}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _resolve_short_link(url):
    opener = urllib.request.build_opener(_HostCheckedRedirect)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with opener.open(req, timeout=10) as response:
            return response.geturl()
    except (urllib.error.URLError, OSError) as e:
        raise BiliError("NETWORK_ERROR", f"could not follow the short link: {e}")


def extract_reference(text):
    """Cut the Bilibili link or id out of whatever the user pasted.

    The app's share text is "【title-哔哩哔哩】 https://b23.tv/xxxx": a title, a
    space, then the link. Taking the first Bilibili URL (or, failing that, the
    first BV/av id) means the surrounding words never reach the parser.
    """
    text = (text or "").strip()
    urls = URL_IN_TEXT_RE.findall(text)
    for url in urls:
        if _host_allowed(url):
            return url
    if urls:
        # Links are present but none is Bilibili's: refuse rather than dig a BV id
        # out of someone else's URL.
        return text
    m = ID_IN_TEXT_RE.search(text)
    if m:
        tail = re.match(r"[?&]p=(\d{1,4})", text[m.end():])
        return m.group(1) + (f"?p={tail.group(1)}" if tail else "")
    return text


def _normalise_id(raw_id):
    return ("BV" + raw_id[2:]) if raw_id[:2].lower() == "bv" else ("av" + raw_id[2:])


def _part_from(value):
    if not re.fullmatch(r"\d{1,4}", value or "") or not 1 <= int(value) <= MAX_PART:
        raise BiliError("INVALID_INPUT", f"bad part number: {value!r}")
    return int(value)


def parse_reference(raw):
    """User input → (video id, part number or None). Raises BiliError on bad input."""
    raw = extract_reference(raw)

    bare = BARE_REF_RE.fullmatch(raw)
    if bare:
        return _normalise_id(bare.group(1)), (_part_from(bare.group(2)) if bare.group(2) else None)

    candidate = raw if re.match(r"https?://", raw, re.I) else "https://" + raw
    if not _host_allowed(candidate) or any(c.isspace() for c in raw):
        raise BiliError("INVALID_INPUT",
                        "not a Bilibili video link, BV id or av id — expected something like "
                        "https://www.bilibili.com/video/BV1xxxxxxxxx")

    if (urllib.parse.urlparse(candidate).hostname or "").lower().endswith("b23.tv"):
        candidate = _resolve_short_link(candidate)
        if not _host_allowed(candidate):
            raise BiliError("INVALID_INPUT", "the short link does not lead to Bilibili")

    parsed = urllib.parse.urlparse(candidate)
    if parsed.path.lower().startswith(NOT_A_VIDEO_PREFIXES):
        raise BiliError("UNSUPPORTED_URL",
                        "only ordinary Bilibili videos are supported, not bangumi, courses, articles or lists")
    query = urllib.parse.parse_qs(parsed.query)
    match = VIDEO_PATH_RE.search(parsed.path) or BV_SEGMENT_RE.search(parsed.path)
    if match:
        vid = _normalise_id(match.group(1))
    elif query.get("bvid") and BV_RE.fullmatch("BV" + query["bvid"][0][2:]) and query["bvid"][0][:2].lower() == "bv":
        vid = _normalise_id(query["bvid"][0])
    else:
        raise BiliError("INVALID_INPUT", "no BV or av id found in the link")

    part_value = (query.get("p") or query.get("page") or [None])[0]  # the embedded player says page=
    part = _part_from(part_value) if part_value else None
    return vid, part


def canonical_url(video_id, part=None):
    url = f"https://www.bilibili.com/video/{video_id}"
    return f"{url}?p={part}" if part else url


# Phrases are taken from yt-dlp's Bilibili extractor, not bare numbers: the
# error text carries the video id, and an id can contain "412" or "404".
_RISK_CONTROL = re.compile(
    r"blocked by server|rejected by server|rate limit|HTTP Error (412|401|403)|\(412\)|\(352\)|Precondition Failed", re.I)
_LOGIN_REQUIRED = re.compile(
    r"registered users|premium member|supporter-only|--cookies|need to log ?in|requires? (a )?login|purchase the course", re.I)
_UNAVAILABLE = re.compile(
    r"deleted|geo-?restricted|is restricted|HTTP Error 404|not found|does not exist|no longer available|unavailable", re.I)
_NETWORK = re.compile(
    r"timed out|timeout|connection|network is unreachable|nodename nor servname|name or service not known|"
    r"getaddrinfo|temporary failure in name resolution", re.I)


def _classify_failure(stderr):
    for pattern, code in ((_RISK_CONTROL, "RISK_CONTROL"), (_LOGIN_REQUIRED, "LOGIN_REQUIRED"),
                          (_UNAVAILABLE, "VIDEO_UNAVAILABLE"), (_NETWORK, "NETWORK_ERROR")):
        if pattern.search(stderr):
            return code
    return "EXTRACT_FAILED"


def ytdlp_json(args, timeout=90):
    try:
        result = subprocess.run(
            # No cookies, whatever the user's own yt-dlp config says: this skill is
            # meant to run without a Bilibili login.
            ["yt-dlp", "--no-warnings", "--skip-download", "--no-cookies", "--no-cookies-from-browser",
             "-J", *args],
            capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise BiliError("YTDLP_MISSING", "yt-dlp is not installed — brew install yt-dlp")
    except subprocess.TimeoutExpired:
        raise BiliError("NETWORK_ERROR", f"yt-dlp did not answer within {timeout}s")
    if result.returncode != 0 or not result.stdout.strip():
        lines = [l for l in result.stderr.strip().splitlines() if l.strip()]
        detail = lines[-1][:300] if lines else "no error output"
        raise BiliError(_classify_failure(result.stderr), detail)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise BiliError("EXTRACT_FAILED", "yt-dlp returned something that is not JSON")


def fetch_video(video_id, part):
    """Metadata for the requested part. Returns (info dict, resolved part, part count)."""
    first = ytdlp_json(["--flat-playlist", "--", canonical_url(video_id)])
    if first.get("_type") != "playlist":
        if part not in (None, 1):
            raise BiliError("PART_OUT_OF_RANGE", f"this video has a single part, but part {part} was requested")
        return first, 1, 1

    count = len(first.get("entries") or []) or int(first.get("playlist_count") or 1)
    chosen = part or 1
    if chosen > count:
        raise BiliError("PART_OUT_OF_RANGE", f"this video has {count} parts, but part {chosen} was requested")
    info = ytdlp_json(["--no-playlist", "--", canonical_url(video_id, chosen)])
    return info, chosen, count


def _bvid_of(info, fallback):
    found = BV_RE.search(str(info.get("id") or "")) or BV_RE.search(str(info.get("webpage_url") or ""))
    return found.group(0) if found else fallback


def _date(info):
    raw = str(info.get("upload_date") or "")
    if re.fullmatch(r"\d{8}", raw):
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    ts = info.get("timestamp")
    if isinstance(ts, (int, float)):
        return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d")
    return ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("reference")
    args = parser.parse_args()
    try:
        video_id, part = parse_reference(args.reference)
        info, chosen, count = fetch_video(video_id, part)
    except BiliError as e:
        print(f"ERROR:{e.code}: {e.message}")
        sys.exit(1)

    bvid = _bvid_of(info, video_id)
    multi = count > 1
    description = (info.get("description") or "").strip()
    chapters = [{"start_time": c.get("start_time"), "title": c.get("title")}
                for c in (info.get("chapters") or [])]

    print(f"BVID: {bvid}")
    print(f"PART: {chosen}")
    print(f"PART_COUNT: {count}")
    if multi and part is None:
        print("PART_DEFAULTED: yes")
    print(f"URL: {canonical_url(bvid, chosen if multi else None)}")
    print(f"TITLE: {info.get('title') or ''}")
    print(f"UPLOADER: {info.get('uploader') or info.get('channel') or ''}")
    print(f"PUBLISHED: {_date(info)}")
    print(f"DURATION_SECONDS: {round(info.get('duration') or 0)}")
    print(f"VIEWS: {info.get('view_count') if info.get('view_count') is not None else ''}")
    print(f"TAGS: {json.dumps((info.get('tags') or [])[:15], ensure_ascii=False)}")
    print(f"CHAPTERS: {json.dumps(chapters, ensure_ascii=False)}")
    print(f"DESCRIPTION: {json.dumps(description[:DESCRIPTION_LIMIT], ensure_ascii=False)}")


if __name__ == "__main__":
    main()
