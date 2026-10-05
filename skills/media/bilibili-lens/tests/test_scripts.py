"""Behaviour of the pure parts of bili_info.py and transcribe.py (no network, no Whisper)."""
import os
import sys
import time
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import bili_info  # noqa: E402
import transcribe  # noqa: E402
from bili_info import BiliError, parse_reference  # noqa: E402


# ---------- what people paste ----------

@pytest.mark.parametrize("raw, expected", [
    ("BV1S3411g7Gh", ("BV1S3411g7Gh", None)),
    ("av170001", ("av170001", None)),
    ("AV170001", ("av170001", None)),
    ("https://www.bilibili.com/video/BV1S3411g7Gh/", ("BV1S3411g7Gh", None)),
    ("https://www.bilibili.com/video/BV1S3411g7Gh/?spm_id_from=333.1007&p=3", ("BV1S3411g7Gh", 3)),
    ("https://m.bilibili.com/video/BV1S3411g7Gh?p=2", ("BV1S3411g7Gh", 2)),
    ("www.bilibili.com/video/BV1S3411g7Gh", ("BV1S3411g7Gh", None)),
    ("https://www.bilibili.com/video/bv1S3411g7Gh", ("BV1S3411g7Gh", None)),
    ("https://www.bilibili.com/video/av170001?p=1", ("av170001", 1)),
])
def test_accepted_references(raw, expected):
    assert parse_reference(raw) == expected


@pytest.mark.parametrize("raw", [
    "",
    "BV1S3411g7G",                                        # one character short
    "https://evil.example/video/BV1S3411g7Gh",            # not Bilibili
    "https://bilibili.com.evil.example/video/BV1S3411g7Gh",  # look-alike host
    "https://www.bilibili.com/video/BV1S3411g7Gh?p=0",
    "https://www.bilibili.com/video/BV1S3411g7Gh?p=abc",
    "https://www.bilibili.com/",
])
def test_rejected_references(raw):
    with pytest.raises(BiliError) as e:
        parse_reference(raw)
    assert e.value.code == "INVALID_INPUT"


def test_non_video_pages_are_reported_as_unsupported():
    with pytest.raises(BiliError) as e:
        parse_reference("https://www.bilibili.com/bangumi/play/ep12345")
    assert e.value.code == "UNSUPPORTED_URL"


def test_short_link_is_followed_then_parsed(monkeypatch):
    monkeypatch.setattr(bili_info, "_resolve_short_link",
                        lambda url: "https://www.bilibili.com/video/BV1S3411g7Gh/?p=4&share_source=copy_web")
    assert parse_reference("https://b23.tv/AbCdEf") == ("BV1S3411g7Gh", 4)


def test_short_link_cannot_redirect_off_bilibili():
    handler = bili_info._HostCheckedRedirect()
    with pytest.raises(urllib.error.URLError):
        handler.redirect_request(None, None, 302, "Found", {}, "https://evil.example/x")






@pytest.mark.parametrize("raw, expected", [
    # What the Bilibili app puts on the clipboard when sharing: a title, then the link.
    ("【关于利率你需要知道的那些事-哔哩哔哩】 https://www.bilibili.com/video/BV1S3411g7Gh", ("BV1S3411g7Gh", None)),
    ("看这个 BV1S3411g7Gh?p=2 很好", ("BV1S3411g7Gh", 2)),
    ("BV1S3411g7Gh?p=2", ("BV1S3411g7Gh", 2)),
    ("bv1S3411g7Gh", ("BV1S3411g7Gh", None)),
    ("https://www.bilibili.com/list/watchlater?bvid=BV1S3411g7Gh", ("BV1S3411g7Gh", None)),
    ("https://www.bilibili.com/medialist/play/watchlater/BV1S3411g7Gh", ("BV1S3411g7Gh", None)),
    ("https://player.bilibili.com/player.html?bvid=BV1S3411g7Gh&page=2", ("BV1S3411g7Gh", 2)),
    # A title with a quote in it must not matter once the link is cut out.
    ("【it's a title】 https://www.bilibili.com/video/BV1S3411g7Gh/", ("BV1S3411g7Gh", None)),
])
def test_links_are_cut_out_of_what_people_paste(raw, expected):
    assert parse_reference(raw) == expected


def test_a_non_bilibili_link_is_refused_even_if_it_contains_a_bv_id():
    with pytest.raises(BiliError) as e:
        parse_reference("看这个 https://evil.example/video/BV1S3411g7Gh")
    assert e.value.code == "INVALID_INPUT"


def test_a_malformed_url_is_an_input_error_not_a_crash():
    with pytest.raises(BiliError) as e:
        parse_reference("http://[www.bilibili.com/")
    assert e.value.code == "INVALID_INPUT"


# The sentences below are yt-dlp's own (extractor/bilibili.py), prefixed the way
# it prefixes them with the video id.
@pytest.mark.parametrize("stderr, code", [
    ("ERROR: [BiliBili] BV1S3411g7Gh: Request is blocked by server (412), please wait and try later.", "RISK_CONTROL"),
    ("ERROR: [BiliBili] BV1S3411g7Gh: Request is rejected by server (352)", "RISK_CONTROL"),
    ("ERROR: [BiliBili] BV1S3411g7Gh: You have exceeded the rate limit. Try again later", "RISK_CONTROL"),
    ("ERROR: Unable to download JSON metadata: HTTP Error 412: Precondition Failed", "RISK_CONTROL"),
    ("ERROR: [BiliBili] BV1S3411g7Gh: This video is only available for registered users. Use --cookies-from-browser", "LOGIN_REQUIRED"),
    ("ERROR: [BiliBili] BV1S3411g7Gh: This is a supporter-only video: 充电专属", "LOGIN_REQUIRED"),
    ("ERROR: [BiliBili] BV1S3411g7Gh: This video is for premium members only", "LOGIN_REQUIRED"),
    ("ERROR: [BiliBili] BV1aaaaaaaaa: This video may be deleted or geo-restricted. You might want to try a VPN", "VIDEO_UNAVAILABLE"),
    ("ERROR: [BiliBili] BV1S3411g7Gh: This video is restricted", "VIDEO_UNAVAILABLE"),
    ("ERROR: Unable to download webpage: <urlopen error [Errno 8] nodename nor servname provided, or not known>", "NETWORK_ERROR"),
    ("ERROR: something nobody has seen before", "EXTRACT_FAILED"),
])
def test_failures_are_classified_from_ytdlps_real_messages(stderr, code):
    assert bili_info._classify_failure(stderr) == code


def test_a_video_id_that_contains_412_does_not_look_like_risk_control():
    # Ids are mixed letters and digits; the classifier must read the sentence, not the id.
    assert bili_info._classify_failure("ERROR: [BiliBili] BV1x412abcde: Unable to extract initial state") == "EXTRACT_FAILED"


# ---------- the Whisper prompt ----------

def test_prompt_uses_title_and_tags_but_not_the_description():
    prompt = transcribe.build_prompt({
        "title": "【干货】关于利率，你需要知道的那些事儿",
        "tags": ["利率", "经济"],
        "description": "求点赞投币收藏 微博@小Lin说",
    })
    assert prompt == "【干货】关于利率，你需要知道的那些事儿。利率、经济"
    # Whisper copies prompt text into the transcript over music or silence.
    assert "点赞" not in prompt and "微博" not in prompt


def test_prompt_drops_the_part_marker_of_multi_part_titles():
    prompt = transcribe.build_prompt({"title": "物语中的人物是如何吐槽自己的OP的 p02 帰り道"})
    assert " p02 " not in prompt and "帰り道" in prompt


def test_prompt_has_no_language_cue_so_it_suits_any_audio():
    assert transcribe.build_prompt({"title": "Never Gonna Give You Up"}) == "Never Gonna Give You Up"
    assert "普通话" not in transcribe.build_prompt({"title": "关于利率"})


def test_prompt_is_capped_to_stay_inside_whispers_prompt_window():
    assert len(transcribe.build_prompt({"title": "很长的标题" * 80})) <= transcribe.PROMPT_MAX_CHARS


# ---------- cache ----------

def test_asking_for_another_language_does_not_return_the_cached_original(tmp_path):
    original = transcribe.cache_file(tmp_path, "BV1S3411g7Gh", 1, "medium")
    english = transcribe.cache_file(tmp_path, "BV1S3411g7Gh", 1, "medium", "en")
    assert original != english


def test_a_transcript_of_a_local_audio_file_never_takes_the_videos_own_cache_name(tmp_path):
    own = transcribe.cache_file(tmp_path, "BV1S3411g7Gh", 1, "medium")
    from_file = transcribe.cache_file(tmp_path, "BV1S3411g7Gh", 1, "medium", "", True)
    assert own != from_file


def test_parts_and_models_are_cached_separately(tmp_path):
    names = {transcribe.cache_file(tmp_path, "BV1S3411g7Gh", part, model).name
             for part in (0, 2) for model in ("medium", "large-v3")}
    assert len(names) == 4


def test_purge_removes_old_transcripts_and_abandoned_partials_but_nothing_else(tmp_path):
    old = tmp_path / "BV1AAAAAAAAA.medium.txt"
    old_partial = tmp_path / "BV1AAAAAAAAA.medium.123.partial"
    fresh = tmp_path / "BV1BBBBBBBBB.medium.txt"
    stranger = tmp_path / "notes.txt"
    for f in (old, old_partial, fresh, stranger):
        f.write_text("x")
    long_ago = time.time() - (transcribe.CACHE_MAX_AGE_DAYS + 1) * 86400
    for f in (old, old_partial, stranger):
        os.utime(f, (long_ago, long_ago))
    transcribe.purge_old(tmp_path)
    assert not old.exists() and not old_partial.exists()
    assert fresh.exists() and stranger.exists()


def test_timestamps_switch_to_hours_only_when_needed():
    assert transcribe.format_timestamp(75) == "[1:15]"
    assert transcribe.format_timestamp(3725) == "[1:02:05]"


# ---------- Whisper loops ----------

def test_a_phrase_repeated_dozens_of_times_is_flagged_but_kept():
    text, flagged = transcribe.flag_repetition("DVD版OP " + "参加 " * 30)
    assert flagged and text.startswith("DVD版OP 参加") and "疑似幻觉" in text


@pytest.mark.parametrize("text", [
    "但是你有想过吗？利率它为什么那么重要？",
    "哈" * 12,                              # laughter
    "no no no no no no",                    # emphasis
    "bye bye bye bye bye bye",
    "1000000000000",                        # a number, not a loop
    "谢谢，" * 6,
    "对对对，就是这样，就是这样",
])
def test_ordinary_speech_is_not_flagged(text):
    assert transcribe.flag_repetition(text) == (text, False)


def _segs(*pairs):
    return [(start, text) for start, text in pairs]


def test_the_same_line_over_and_over_is_flagged_but_kept():
    segments = _segs((0, "大家好"), *[(10 + 2 * n, "我就是在想") for n in range(6)], (30, "再见"))
    out, flagged = transcribe.flag_segments(segments)
    assert flagged == 6
    assert [t for _, t in out if "疑似幻觉" in t] == ["我就是在想" + transcribe.REPEAT_MARK] * 6
    assert out[0][1] == "大家好" and out[-1][1] == "再见"


def test_three_identical_lines_in_a_row_are_ordinary_speech():
    _, flagged = transcribe.flag_segments(_segs((0, "对"), (1, "对"), (2, "对"), (3, "好")))
    assert flagged == 0


def test_lines_that_start_after_the_video_has_ended_are_flagged():
    out, flagged = transcribe.flag_segments(_segs((540, "下次见"), (560, "多出来的一句")), duration=554)
    assert flagged == 1
    assert out[0][1] == "下次见" and "超出视频时长" in out[1][1]


def test_an_unknown_duration_flags_nothing_by_time():
    _, flagged = transcribe.flag_segments(_segs((9999, "很晚的一句")), duration=0)
    assert flagged == 0
