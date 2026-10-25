from __future__ import annotations

import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup


TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "mod",
    "cmpid",
    "ocid",
    "ref",
    "referrer",
    "source",
}


def clean_html(value: str | None) -> str:
    if not value:
        return ""
    text = BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def canonicalize_url(value: str) -> str:
    parts = urlsplit(value.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    if port and not (
        (scheme == "http" and port == 80)
        or (scheme == "https" and port == 443)
    ):
        host = f"{host}:{port}"

    filtered_query: list[tuple[str, str]] = []
    for key, item_value in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered.startswith("utm_") or lowered in TRACKING_QUERY_KEYS:
            continue
        filtered_query.append((key, item_value))
    filtered_query.sort()

    path = re.sub(r"/{2,}", "/", parts.path)
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit((scheme, host, path, urlencode(filtered_query), ""))


def title_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[\W_]+", "", normalized, flags=re.UNICODE)


def title_tokens(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    words = set(re.findall(r"[a-z0-9][a-z0-9.+-]{1,}", normalized))
    cjk = "".join(re.findall(r"[\u3400-\u9fff]", normalized))
    if len(cjk) >= 8:
        words.update(cjk[index : index + 3] for index in range(len(cjk) - 2))
    return words


def title_similarity(left: str, right: str) -> float:
    left_key = title_key(left)
    right_key = title_key(right)
    if not left_key or not right_key:
        return 0.0
    if left_key == right_key:
        return 1.0
    left_tokens = title_tokens(left)
    right_tokens = title_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)

