from __future__ import annotations

from paircue.config import PairCueSettings
from paircue.runtime import CoreRuntime, JobCoordinator
from paircue.services.downloader import (
    DisabledSubtitleDownloader,
    OpenSubtitlesDownloader,
    SubtitleDownloader,
)
from paircue.services.filesystem import FilesystemSource
from paircue.services.glossary import GlossaryStore
from paircue.services.media_browser import EmbyClient, JellyfinClient
from paircue.services.media_source import MediaSource
from paircue.services.media_tools import EmbeddedSubtitleExtractor, SubtitleSynchronizer
from paircue.services.pipeline import SubtitlePipeline
from paircue.services.plex import PlexClient
from paircue.services.state import StateStore
from paircue.services.translator import (
    CompleteTranslator,
    OpenAICompatibleProvider,
    ProviderConfig,
)


def build_runtime(settings: PairCueSettings) -> CoreRuntime:
    state = StateStore(settings.state_dir / "paircue.sqlite3")
    opensubtitles_key = settings.opensubtitles_api_key.get_secret_value()
    downloader: SubtitleDownloader
    if settings.subtitle_download_enabled and opensubtitles_key:
        downloader = OpenSubtitlesDownloader(
            api_key=opensubtitles_key,
            username=settings.opensubtitles_username,
            password=settings.opensubtitles_password.get_secret_value(),
            timeout_seconds=settings.subtitle_download_timeout_seconds,
        )
    else:
        downloader = DisabledSubtitleDownloader()
    glossary = GlossaryStore(settings.state_dir / "glossaries")
    synchronizer = (
        SubtitleSynchronizer(
            max_offset_seconds=settings.sync_max_offset_seconds,
            min_confidence=settings.sync_min_confidence,
        )
        if settings.sync_enabled
        else None
    )

    translator: CompleteTranslator | None = None
    if settings.translation_enabled:
        primary = OpenAICompatibleProvider(
            ProviderConfig(
                name="primary",
                base_url=settings.translation_base_url,
                api_key=settings.translation_api_key.get_secret_value(),
                model=settings.translation_model,
                timeout_seconds=settings.translation_timeout_seconds,
                max_attempts=settings.translation_max_attempts,
                disable_thinking=settings.translation_disable_thinking,
            )
        )
        fallback = None
        if settings.fallback_base_url and settings.fallback_model:
            fallback_key = settings.fallback_api_key.get_secret_value()
            if fallback_key:
                fallback = OpenAICompatibleProvider(
                    ProviderConfig(
                        name="fallback",
                        base_url=settings.fallback_base_url,
                        api_key=fallback_key,
                        model=settings.fallback_model,
                        timeout_seconds=settings.translation_timeout_seconds,
                        max_attempts=settings.translation_max_attempts,
                        disable_thinking=settings.fallback_disable_thinking,
                    )
                )
        translator = CompleteTranslator(
            primary,
            fallback=fallback,
            batch_size=settings.translation_batch_size,
            source_language=settings.source_language,
            source_language_name=settings.effective_source_language_name,
            target_language=settings.target_language,
            target_language_name=settings.effective_target_language_name,
            target_language_style=settings.target_language_style,
        )

    pipeline = SubtitlePipeline(
        media_root=settings.media_root,
        state=state,
        downloader=downloader,
        extractor=EmbeddedSubtitleExtractor(),
        synchronizer=synchronizer,
        translator=translator,
        glossary=glossary,
        clean_source_output=settings.clean_source_output,
        source_language=settings.source_language,
        target_language=settings.target_language,
        bilingual_order=settings.bilingual_order,
        bilingual_merge_tolerance_ms=settings.bilingual_merge_tolerance_ms,
        bilingual_merge_min_match_ratio=settings.bilingual_merge_min_match_ratio,
    )
    media_source = build_media_source(settings)
    coordinator = JobCoordinator(pipeline, max_size=settings.worker_queue_size)
    return CoreRuntime(media_source, coordinator, settings.scan_interval_seconds)


def build_media_source(settings: PairCueSettings) -> MediaSource:
    if settings.platform == "filesystem":
        return FilesystemSource(
            media_root=settings.media_root,
            extensions=settings.media_extensions,
        )
    if settings.platform == "plex":
        return PlexClient(
            base_url=settings.effective_server_url,
            token=settings.effective_server_token,
            plex_path_prefix=settings.effective_server_path_prefix,
            media_root=settings.media_root,
        )
    client_type = JellyfinClient if settings.platform == "jellyfin" else EmbyClient
    media_source: MediaSource = client_type(
        base_url=settings.effective_server_url,
        token=settings.effective_server_token,
        user_id=settings.server_user_id,
        server_path_prefix=settings.effective_server_path_prefix,
        media_root=settings.media_root,
    )
    return media_source
