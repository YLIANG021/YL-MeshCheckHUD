import bpy

from . import (
    de_DE,
    en_US,
    es_ES,
    fr_FR,
    it_IT,
    ja_jp,
    ko_KR,
    pl_PL,
    pt_BR,
    ru_RU,
    vi_VN,
    zh_CN,
    zh_TW,
    zh_hans,
    zh_hant,
)


TRANSLATIONS = {
    "de": de_DE.TRANSLATIONS,
    "de_DE": de_DE.TRANSLATIONS,
    "en_US": en_US.TRANSLATIONS,
    "es": es_ES.TRANSLATIONS,
    "es_ES": es_ES.TRANSLATIONS,
    "fr": fr_FR.TRANSLATIONS,
    "fr_FR": fr_FR.TRANSLATIONS,
    "it": it_IT.TRANSLATIONS,
    "it_IT": it_IT.TRANSLATIONS,
    "ja": ja_jp.TRANSLATIONS,
    "ja_JP": ja_jp.TRANSLATIONS,
    "ja_jp": ja_jp.TRANSLATIONS,
    "ko": ko_KR.TRANSLATIONS,
    "ko_KR": ko_KR.TRANSLATIONS,
    "pl": pl_PL.TRANSLATIONS,
    "pl_PL": pl_PL.TRANSLATIONS,
    "pt": pt_BR.TRANSLATIONS,
    "pt_BR": pt_BR.TRANSLATIONS,
    "ru": ru_RU.TRANSLATIONS,
    "ru_RU": ru_RU.TRANSLATIONS,
    "vi": vi_VN.TRANSLATIONS,
    "vi_VN": vi_VN.TRANSLATIONS,
    "zh_CN": zh_CN.TRANSLATIONS,
    "zh_TW": zh_TW.TRANSLATIONS,
    "zh_HANS": zh_hans.TRANSLATIONS,
    "zh_HANT": zh_hant.TRANSLATIONS,
    "zh_hans": zh_hans.TRANSLATIONS,
    "zh_hant": zh_hant.TRANSLATIONS,
}


def pgettext(message):
    """Return the add-on's translated string for the active locale."""
    locale = getattr(bpy.app.translations, "locale", "") or ""

    candidates = []
    if locale:
        candidates.append(locale)
        if "_" in locale:
            candidates.append(locale.split("_", 1)[0])

    language = ""
    try:
        language = bpy.context.preferences.view.language or ""
    except AttributeError:
        language = ""

    if language:
        candidates.append(language)
        if "_" in language:
            candidates.append(language.split("_", 1)[0])

    candidates.extend(("en_US",))

    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        translations = TRANSLATIONS.get(candidate)
        if translations is None:
            continue
        return translations.get(("*", message), message)

    return message


def register():
    bpy.app.translations.register(__package__, TRANSLATIONS)


def unregister():
    bpy.app.translations.unregister(__package__)
