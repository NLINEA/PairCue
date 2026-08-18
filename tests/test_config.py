import pytest
from pydantic import ValidationError

from subflow.config import DownloadStationSettings, SubFlowSettings

TOKEN = "a" * 32


def test_exposed_core_requires_a_strong_token() -> None:
    with pytest.raises(ValidationError, match="at least 32"):
        SubFlowSettings(api_host="0.0.0.0", api_token="short")


def test_translation_requires_a_key() -> None:
    with pytest.raises(ValidationError, match="TRANSLATION_API_KEY"):
        SubFlowSettings(translation_enabled=True, translation_api_key="")


def test_glm_thinking_is_disabled_by_default() -> None:
    settings = SubFlowSettings()

    assert settings.translation_disable_thinking is True
    assert settings.fallback_disable_thinking is False


def test_target_language_is_canonicalized_and_named() -> None:
    settings = SubFlowSettings(target_language="ZH-hk")

    assert settings.target_language == "zh-HK"
    assert settings.effective_target_language_name == "Traditional Chinese (Hong Kong)"


def test_custom_target_language_name_is_supported() -> None:
    settings = SubFlowSettings(target_language="gd", target_language_name="Scottish Gaelic")

    assert settings.effective_target_language_name == "Scottish Gaelic"


@pytest.mark.parametrize("language", ["../../ja", "en", "en-GB"])
def test_invalid_or_english_target_language_is_rejected(language: str) -> None:
    with pytest.raises(ValidationError, match="target language"):
        SubFlowSettings(target_language=language)


def test_empty_target_language_style_is_rejected() -> None:
    with pytest.raises(ValidationError, match="style must not be empty"):
        SubFlowSettings(target_language_style="   ")


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
