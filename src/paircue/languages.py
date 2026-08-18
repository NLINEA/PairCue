from __future__ import annotations

import re

LANGUAGE_TAG = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")

LANGUAGE_NAMES = {
    "zh-TW": "Traditional Chinese (Taiwan)",
    "zh-HK": "Traditional Chinese (Hong Kong)",
    "zh-Hant": "Traditional Chinese",
    "zh-CN": "Simplified Chinese (Mainland China)",
    "zh-Hans": "Simplified Chinese",
    "en": "English",
    "en-US": "English (United States)",
    "en-GB": "English (United Kingdom)",
    "ja": "Japanese",
    "ko": "Korean",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "pt-BR": "Brazilian Portuguese",
    "id": "Indonesian",
    "th": "Thai",
    "vi": "Vietnamese",
    "ar": "Arabic",
}

OBSERVED_ALIASES = {
    "ara": "ar",
    "deu": "de",
    "dut": "nl",
    "eng": "en",
    "english": "en",
    "fre": "fr",
    "fra": "fr",
    "ger": "de",
    "ind": "id",
    "ita": "it",
    "jpn": "ja",
    "kor": "ko",
    "nld": "nl",
    "por": "pt",
    "spa": "es",
    "tha": "th",
    "vie": "vi",
    "zho": "zh",
    "cht": "zh-TW",
    "zht": "zh-TW",
    "traditional": "zh-TW",
    "chs": "zh-CN",
    "zhs": "zh-CN",
    "simplified": "zh-CN",
    "chi": "zh",
}

OPENCC_PROFILES = {
    "zh-TW": "s2twp",
    "zh-HK": "s2hk",
    "zh-Hant": "s2t",
    "zh-CN": "t2s",
    "zh-Hans": "t2s",
}


def canonicalize_language_tag(value: str) -> str:
    """Validate a safe BCP-47-shaped tag and normalize its common casing."""

    raw = value.strip()
    if not raw or not LANGUAGE_TAG.fullmatch(raw):
        raise ValueError("language must be a valid BCP-47 language tag")
    parts = raw.split("-")
    normalized = [parts[0].lower()]
    for part in parts[1:]:
        if len(part) == 4 and part.isalpha():
            normalized.append(part.title())
        elif len(part) == 2 and part.isalpha():
            normalized.append(part.upper())
        else:
            normalized.append(part.lower())
    return "-".join(normalized)


def language_name(tag: str) -> str:
    return LANGUAGE_NAMES.get(tag, tag)


def observed_language_tag(value: str) -> str | None:
    """Normalize common BCP-47 and media-container language tags."""

    raw = value.strip()
    alias = OBSERVED_ALIASES.get(raw.lower())
    if alias is not None:
        return alias
    try:
        return canonicalize_language_tag(raw)
    except ValueError:
        return None


def language_matches(observed: str, requested: str) -> bool:
    normalized = observed_language_tag(observed)
    return normalized is not None and normalized.casefold() == requested.casefold()


def opencc_profile(tag: str) -> str | None:
    return OPENCC_PROFILES.get(tag)
