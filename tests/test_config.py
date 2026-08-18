import pytest
from pydantic import ValidationError

from paircue.config import DownloadStationSettings, PairCueSettings

TOKEN = "a" * 32
SERVER_TOKEN = "s" * 16
LEGACY_TOKEN = "l" * 16


def test_exposed_core_requires_a_strong_token() -> None:
    with pytest.raises(ValidationError, match="at least 32"):
        PairCueSettings(api_host="0.0.0.0", api_token="short")


def test_translation_requires_a_key() -> None:
    with pytest.raises(ValidationError, match="TRANSLATION_API_KEY"):
        PairCueSettings(translation_enabled=True, translation_api_key="")


def test_openai_transcription_requires_a_key_but_local_endpoint_does_not() -> None:
    with pytest.raises(ValidationError, match="TRANSCRIPTION_API_KEY"):
        PairCueSettings(transcription_enabled=True)

    settings = PairCueSettings(
        transcription_enabled=True,
        transcription_base_url="http://whisper:9000/v1",
    )

    assert settings.transcription_model == "whisper-1"


def test_opensubtitles_credentials_require_api_key_and_complete_pair() -> None:
    with pytest.raises(ValidationError, match="configured together"):
        PairCueSettings(opensubtitles_username="user")
    with pytest.raises(ValidationError, match="OPENSUBTITLES_API_KEY"):
        PairCueSettings(opensubtitles_username="user", opensubtitles_password="password")

    settings = PairCueSettings(
        opensubtitles_api_key="key",
        opensubtitles_username="user",
        opensubtitles_password="password",
    )

    assert settings.opensubtitles_username == "user"


def test_glm_thinking_is_disabled_by_default() -> None:
    settings = PairCueSettings()

    assert settings.translation_disable_thinking is True
    assert settings.fallback_disable_thinking is False


def test_target_language_is_canonicalized_and_named() -> None:
    settings = PairCueSettings(target_language="ZH-hk")

    assert settings.target_language == "zh-HK"
    assert settings.effective_target_language_name == "Traditional Chinese (Hong Kong)"


def test_english_can_be_the_target_for_a_different_source_language() -> None:
    settings = PairCueSettings(source_language="JA", target_language="en")

    assert settings.source_language == "ja"
    assert settings.effective_source_language_name == "Japanese"
    assert settings.target_language == "en"
    assert settings.effective_target_language_name == "English"


def test_custom_target_language_name_is_supported() -> None:
    settings = PairCueSettings(target_language="gd", target_language_name="Scottish Gaelic")

    assert settings.effective_target_language_name == "Scottish Gaelic"


@pytest.mark.parametrize("language", ["../../ja", "not_a_language"])
def test_invalid_language_tag_is_rejected(language: str) -> None:
    with pytest.raises(ValidationError, match="valid BCP-47"):
        PairCueSettings(target_language=language)


def test_source_and_target_languages_must_differ() -> None:
    with pytest.raises(ValidationError, match="must differ"):
        PairCueSettings(source_language="en", target_language="EN")


def test_empty_target_language_style_is_rejected() -> None:
    with pytest.raises(ValidationError, match="style must not be empty"):
        PairCueSettings(target_language_style="   ")


def test_jellyfin_requires_generic_server_settings() -> None:
    with pytest.raises(ValidationError, match="SERVER_URL"):
        PairCueSettings(platform="jellyfin")

    settings = PairCueSettings(
        platform="jellyfin",
        server_url="http://jellyfin:8096",
        server_token=SERVER_TOKEN,
        server_user_id="0123456789abcdef",
        server_path_prefix="/media",
    )

    assert settings.effective_server_url == "http://jellyfin:8096"
    assert settings.effective_server_token == SERVER_TOKEN
    assert settings.effective_server_path_prefix == "/media"


def test_filesystem_mode_parses_and_deduplicates_extensions() -> None:
    settings = PairCueSettings(
        platform="filesystem",
        filesystem_extensions="mkv, .MP4,mkv",
    )

    assert settings.media_extensions == (".mkv", ".mp4")


def test_legacy_plex_settings_remain_supported() -> None:
    settings = PairCueSettings(
        plex_url="http://plex:32400",
        plex_token=LEGACY_TOKEN,
        plex_path_prefix="/volume1/Media",
    )

    assert settings.effective_server_url == "http://plex:32400"
    assert settings.effective_server_token == LEGACY_TOKEN
    assert settings.effective_server_path_prefix == "/volume1/Media"


def test_download_service_has_separate_required_credentials() -> None:
    settings = DownloadStationSettings(
        username="download-user",
        password="password",
        api_token=TOKEN,
    )

    assert settings.username == "download-user"
    assert settings.api_token.get_secret_value() == TOKEN


def test_credentials_cannot_be_embedded_in_urls() -> None:
    with pytest.raises(ValidationError, match="must not be embedded"):
        DownloadStationSettings(
            url="http://user:password@nas:5000",
            username="download-user",
            password="password",
            api_token=TOKEN,
        )
