from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from subflow.languages import canonicalize_language_tag, language_name


def _secret_value(secret: SecretStr) -> str:
    return secret.get_secret_value()


class SubFlowSettings(BaseSettings):
    """Settings for the subtitle service only.

    Download Station has a separate settings class so it never inherits media-server,
    translation, or media-library credentials.
    """

    model_config = SettingsConfigDict(
        env_prefix="SUBFLOW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    platform: Literal["plex", "jellyfin", "emby", "filesystem"] = "plex"
    server_url: str = ""
    server_token: SecretStr = SecretStr("")
    server_user_id: str = ""
    server_path_prefix: str = ""
    filesystem_extensions: str = ".mkv,.mp4,.avi,.m4v,.mov,.ts,.webm"

    # Deprecated Plex-specific aliases retained for existing installations.
    plex_url: str = "http://127.0.0.1:32400"
    plex_token: SecretStr = SecretStr("")
    plex_path_prefix: str = "/volume1/MediaForPlex"
    media_root: Path = Path("/media")
    state_dir: Path = Path("/state")

    scan_interval_seconds: int = Field(default=1800, ge=60, le=86400)
    worker_queue_size: int = Field(default=1000, ge=1, le=10000)
    providers: str = "gestdown,tvsubtitles,opensubtitles"
    sync_enabled: bool = True
    clean_source_output: bool = True

    source_language: str = "en"
    source_language_name: str = Field(default="", max_length=80)
    target_language: str = "zh-TW"
    target_language_name: str = Field(default="", max_length=80)
    target_language_style: str = Field(
        default="natural, concise dialogue suitable for subtitles",
        min_length=1,
        max_length=200,
    )
    bilingual_order: Literal["target-first", "source-first"] = "target-first"
    bilingual_merge_tolerance_ms: int = Field(default=350, ge=0, le=2000)
    bilingual_merge_min_match_ratio: float = Field(default=0.7, ge=0.5, le=1)

    translation_enabled: bool = False
    translation_base_url: str = "https://api.z.ai/api/coding/paas/v4"
    translation_api_key: SecretStr = SecretStr("")
    translation_model: str = "glm-5-turbo"
    translation_disable_thinking: bool = True
    translation_batch_size: int = Field(default=30, ge=1, le=50)
    translation_timeout_seconds: float = Field(default=120, ge=5, le=600)
    translation_max_attempts: int = Field(default=3, ge=1, le=6)
    fallback_base_url: str = ""
    fallback_api_key: SecretStr = SecretStr("")
    fallback_model: str = ""
    fallback_disable_thinking: bool = False

    webhook_enabled: bool = False
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=9292, ge=1, le=65535)
    api_token: SecretStr = SecretStr("")
    api_docs_enabled: bool = False
    trusted_hosts: str = "localhost,127.0.0.1"
    max_webhook_bytes: int = Field(default=131072, ge=1024, le=1048576)

    @field_validator("server_url", "plex_url", "translation_base_url", "fallback_base_url")
    @classmethod
    def validate_service_urls(cls, value: str) -> str:
        if not value:
            return value
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("service URLs must use http or https and include a host")
        if parsed.username or parsed.password:
            raise ValueError("credentials must not be embedded in service URLs")
        return value.rstrip("/")

    @field_validator("source_language", "target_language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        return canonicalize_language_tag(value)

    @field_validator("source_language_name", "target_language_name", "target_language_style")
    @classmethod
    def validate_translation_prompt_setting(cls, value: str, info: ValidationInfo) -> str:
        value = value.strip()
        if info.field_name == "target_language_style" and not value:
            raise ValueError("target language style must not be empty")
        if any(ord(character) < 32 for character in value):
            raise ValueError("translation language settings must be a single line")
        return value

    @model_validator(mode="after")
    def validate_secure_runtime(self) -> SubFlowSettings:
        token = _secret_value(self.api_token)
        exposed = self.api_host not in {"127.0.0.1", "::1", "localhost"}
        if (self.webhook_enabled or exposed) and len(token) < 32:
            raise ValueError("SUBFLOW_API_TOKEN must contain at least 32 characters")
        if self.translation_enabled and not _secret_value(self.translation_api_key):
            raise ValueError("translation is enabled but SUBFLOW_TRANSLATION_API_KEY is empty")
        if self.source_language.casefold() == self.target_language.casefold():
            raise ValueError("source and target languages must differ")
        if self.platform in {"jellyfin", "emby"}:
            if not self.server_url:
                raise ValueError("SUBFLOW_SERVER_URL is required for Jellyfin and Emby")
            if not _secret_value(self.server_token):
                raise ValueError("SUBFLOW_SERVER_TOKEN is required for Jellyfin and Emby")
            if not self.server_user_id:
                raise ValueError("SUBFLOW_SERVER_USER_ID is required for Jellyfin and Emby")
            if not self.server_path_prefix:
                raise ValueError("SUBFLOW_SERVER_PATH_PREFIX is required for Jellyfin and Emby")
        return self

    @property
    def provider_names(self) -> tuple[str, ...]:
        return tuple(name.strip() for name in self.providers.split(",") if name.strip())

    @property
    def allowed_hosts(self) -> list[str]:
        hosts = [host.strip() for host in self.trusted_hosts.split(",") if host.strip()]
        return hosts or ["localhost", "127.0.0.1"]

    @property
    def effective_server_url(self) -> str:
        return self.server_url or self.plex_url

    @property
    def effective_server_token(self) -> str:
        return _secret_value(self.server_token) or _secret_value(self.plex_token)

    @property
    def effective_server_path_prefix(self) -> str:
        return self.server_path_prefix or self.plex_path_prefix

    @property
    def media_extensions(self) -> tuple[str, ...]:
        output: list[str] = []
        for raw in self.filesystem_extensions.split(","):
            extension = raw.strip().casefold()
            if not extension:
                continue
            if not extension.startswith("."):
                extension = f".{extension}"
            if len(extension) > 9 or not extension[1:].isalnum():
                raise ValueError("SUBFLOW_FILESYSTEM_EXTENSIONS contains an invalid extension")
            output.append(extension)
        if not output:
            raise ValueError("SUBFLOW_FILESYSTEM_EXTENSIONS must not be empty")
        return tuple(dict.fromkeys(output))

    @property
    def effective_target_language_name(self) -> str:
        return self.target_language_name or language_name(self.target_language)

    @property
    def effective_source_language_name(self) -> str:
        return self.source_language_name or language_name(self.source_language)


class DownloadStationSettings(BaseSettings):
    """Credentials and paths available only to the optional download service."""

    model_config = SettingsConfigDict(
        env_prefix="SUBFLOW_DS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    url: str = "http://127.0.0.1:5000"
    username: str = ""
    password: SecretStr = SecretStr("")
    destination: str = "MediaForPlex/Download"
    watch_dir: Path = Path("/torrents")
    host: str = "127.0.0.1"
    port: int = Field(default=9293, ge=1, le=65535)
    api_token: SecretStr = SecretStr("")
    trusted_hosts: str = "localhost,127.0.0.1"
    max_torrent_bytes: int = Field(default=4 * 1024 * 1024, ge=1024, le=16 * 1024 * 1024)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("SUBFLOW_DS_URL must use http or https and include a host")
        if parsed.username or parsed.password:
            raise ValueError("Download Station credentials must not be embedded in its URL")
        return value.rstrip("/")

    @model_validator(mode="after")
    def validate_credentials(self) -> DownloadStationSettings:
        if len(_secret_value(self.api_token)) < 32:
            raise ValueError("SUBFLOW_DS_API_TOKEN must contain at least 32 characters")
        if not self.username or not _secret_value(self.password):
            raise ValueError("Download Station username and password are required")
        return self

    @property
    def allowed_hosts(self) -> list[str]:
        hosts = [host.strip() for host in self.trusted_hosts.split(",") if host.strip()]
        return hosts or ["localhost", "127.0.0.1"]
