"""Simple backend i18n using locale JSON files."""

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=32)
def _load_translations(locale: str) -> dict:
    i18n_dir = Path(__file__).resolve().parent
    path = i18n_dir / f"{locale}.json"
    if not path.exists():
        path = i18n_dir / "en.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def translate(key: str, locale: str = "en", **kwargs: str) -> str:
    """Resolve a dot-separated key in the locale JSON and interpolate {placeholders}."""
    translations = _load_translations(locale)
    parts = key.split(".")
    value: object = translations
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part, "")
        else:
            value = ""
    if not isinstance(value, str):
        value = ""
    if kwargs:
        value = value.format(**kwargs)
    return value
