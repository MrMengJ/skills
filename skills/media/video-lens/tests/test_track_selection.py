"""Caption-track selection: the spoken-language track must win over translations."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from fetch_transcript import _match_track, _pick_original_track  # noqa: E402


def _tracks(*specs):
    """specs like 'ar', 'en', 'en*' — a trailing * marks an auto-generated track."""
    return [SimpleNamespace(language_code=s.rstrip("*"), is_generated=s.endswith("*")) for s in specs]


def _pick(*specs):
    track, ambiguous = _pick_original_track(_tracks(*specs))
    return track.language_code, track.is_generated, ambiguous


def test_manual_original_beats_earlier_translations():
    # Real case: an English video whose first listed manual track is Arabic.
    assert _pick("ar", "zh", "en", "fr", "en*") == ("en", False, False)


def test_auto_generated_original_beats_manual_translation():
    assert _pick("en", "ja*") == ("ja", True, False)


def test_regional_manual_track_counts_as_original():
    assert _pick("fr", "pt-BR", "pt*") == ("pt-BR", False, False)


def test_only_auto_generated():
    assert _pick("en*") == ("en", True, False)


def test_manual_variants_of_one_language_are_not_ambiguous():
    assert _pick("zh-Hans", "zh-Hant") == ("zh-Hans", False, False)


def test_manual_tracks_in_several_languages_without_auto_is_ambiguous():
    assert _pick("zh-Hans", "zh-Hant", "en") == ("zh-Hans", False, True)


def test_dubbed_video_with_several_auto_languages_is_ambiguous():
    assert _pick("en*", "fr-FR*", "de-DE*")[2] is True


def _match(specs, lang):
    track, exact = _match_track(_tracks(*specs), lang)
    return (track.language_code if track else None), exact


def test_explicit_language_exact_match_ignores_case():
    # preflight lowercases user input; YouTube reports mixed-case codes.
    assert _match(("zh-CN", "zh-TW", "en*"), "zh-tw") == ("zh-TW", True)
    assert _match(("pt", "pt-BR"), "pt-br") == ("pt-BR", True)


def test_bare_language_matches_a_regional_track():
    assert _match(("zh", "zh-TW", "fr-FR*"), "fr") == ("fr-FR", True)


def test_other_variant_of_requested_language_is_flagged_inexact():
    # Asked for Traditional, only Simplified exists: usable, but must be reported.
    assert _match(("zh-CN", "en*"), "zh-tw") == ("zh-CN", False)


def test_explicit_language_absent():
    assert _match(("zh", "en*"), "ko") == (None, False)


def test_error_codes_for_blocks_at_fetch_time():
    import xml.etree.ElementTree as ET

    import requests
    from youtube_transcript_api import IpBlocked, RequestBlocked

    from fetch_transcript import _error_code

    assert _error_code(IpBlocked("vid")) == "ERROR:IP_BLOCKED"
    assert _error_code(RequestBlocked("vid")) == "ERROR:REQUEST_BLOCKED"
    # Throttled requests can come back as an empty body the XML parser rejects.
    assert _error_code(ET.ParseError("no element found")) == "ERROR:REQUEST_BLOCKED"
    assert _error_code(requests.exceptions.ConnectionError("reset")) == "ERROR:NETWORK_ERROR"
    assert _error_code(ValueError("boom")) == "ERROR:TRANSCRIPT_FETCH_FAILED"
