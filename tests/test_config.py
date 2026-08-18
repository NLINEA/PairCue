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
