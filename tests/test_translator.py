from datetime import timedelta

import pytest
import srt

from subflow.services.translator import CompleteTranslator, TranslationError


class FakeProvider:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def translate(
        self, cues: dict[int, str], *, context: str, glossary: dict[str, str]
    ) -> dict[int, str]:
        self.calls += 1
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
    translator = CompleteTranslator(primary, fallback=fallback, batch_size=2)  # type: ignore[arg-type]

    result = translator.translate_all(_cues(3), context="Movie")

    assert set(result) == {0, 1, 2}
    assert primary.calls == 2
    assert fallback.calls == 2


def test_incomplete_provider_output_is_rejected() -> None:
    class IncompleteProvider(FakeProvider):
        def translate(
            self, cues: dict[int, str], *, context: str, glossary: dict[str, str]
        ) -> dict[int, str]:
            return {min(cues): "only one"}

    translator = CompleteTranslator(IncompleteProvider(), batch_size=10)  # type: ignore[arg-type]

    with pytest.raises(TranslationError, match="missing"):
        translator.translate_all(_cues(2), context="Movie")
