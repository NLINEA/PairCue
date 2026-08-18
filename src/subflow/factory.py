from __future__ import annotations

from subflow.config import SubFlowSettings
from subflow.runtime import CoreRuntime, JobCoordinator
from subflow.services.downloader import SubliminalDownloader
from subflow.services.glossary import GlossaryStore
from subflow.services.media_tools import EmbeddedSubtitleExtractor, SubtitleSynchronizer
from subflow.services.pipeline import SubtitlePipeline
from subflow.services.plex import PlexClient
from subflow.services.state import StateStore
from subflow.services.translator import (
    CompleteTranslator,
    OpenAICompatibleProvider,
    ProviderConfig,
)


def build_runtime(settings: SubFlowSettings) -> CoreRuntime:
    state = StateStore(settings.state_dir / "subflow.sqlite3")
    downloader = SubliminalDownloader(settings.provider_names, settings.state_dir / "tmp")
    glossary = GlossaryStore(settings.state_dir / "glossaries")
    synchronizer = SubtitleSynchronizer() if settings.sync_enabled else None

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
    )
    plex = PlexClient(
        base_url=settings.plex_url,
        token=settings.plex_token.get_secret_value(),
        plex_path_prefix=settings.plex_path_prefix,
        media_root=settings.media_root,
    )
    coordinator = JobCoordinator(pipeline, max_size=settings.worker_queue_size)
    return CoreRuntime(plex, coordinator, settings.scan_interval_seconds)
