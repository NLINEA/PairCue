from datetime import timedelta

import pytest
import srt

from subflow.services.translator import (
    CompleteTranslator,
    OpenAICompatibleProvider,
    ProviderConfig,
    TranslationError,
)


class FakeProvider:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0
        self.languages: list[str] = []

    def translate(
        self,
        cues: dict[int, str],
        *,
        context: str,
        glossary: dict[str, str],
        source_language: str,
        source_language_name: str,
        target_language: str,
        target_language_name: str,
        target_language_style: str,
    ) -> dict[int, str]:
        self.calls += 1
        self.languages.append(f"{source_language}->{target_language}")
        if self.fail:
            raise TranslationError("failed")
        return {cue_id: f"中:{text}" for cue_id, text in cues.items()}


def _cues(count: int) -> list[srt.Subtitle]:
    return [
        srt.Subtitle(
            index + 1,
            timedelta(seconds=index),
            timedelta(seconds=index + 1),
            f"line {index}",
        )
        for index in range(count)
    ]


def test_fallback_is_used_only_after_primary_fails() -> None:
    primary = FakeProvider(fail=True)
    fallback = FakeProvider()
    translator = CompleteTranslator(
        primary,  # type: ignore[arg-type]
        fallback=fallback,  # type: ignore[arg-type]
        batch_size=2,
        source_language="ko",
        target_language="en",
    )

    result = translator.translate_all(_cues(3), context="Movie")

    assert set(result) == {0, 1, 2}
    assert primary.calls == 2
    assert fallback.calls == 2
    assert primary.languages == ["ko->en", "ko->en"]
    assert fallback.languages == ["ko->en", "ko->en"]


def test_incomplete_provider_output_is_rejected() -> None:
    class IncompleteProvider(FakeProvider):
        def translate(
            self,
            cues: dict[int, str],
            *,
            context: str,
            glossary: dict[str, str],
            source_language: str,
            source_language_name: str,
            target_language: str,
            target_language_name: str,
            target_language_style: str,
        ) -> dict[int, str]:
            return {min(cues): "only one"}

    translator = CompleteTranslator(IncompleteProvider(), batch_size=10)  # type: ignore[arg-type]

    with pytest.raises(TranslationError, match="missing"):
        translator.translate_all(_cues(2), context="Movie")


def test_only_chinese_targets_are_normalized_with_opencc() -> None:
    provider = OpenAICompatibleProvider(
        ProviderConfig("test", "https://example.com", "key", "model")
    )
    response = '{"translations":[{"id":0,"text":"软件"}]}'

    taiwan = provider._parse_response(response, target_language="zh-TW")
    hong_kong = provider._parse_response(response, target_language="zh-HK")
    japanese = provider._parse_response(response, target_language="ja")

    assert taiwan == {0: "軟體"}
    assert hong_kong == {0: "軟件"}
    assert japanese == {0: "软件"}
