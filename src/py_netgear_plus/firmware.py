"""Firmware release lookup helpers for Netgear Plus switches."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any
from xml.etree import ElementTree

import requests

KB_SITEMAP_URL = "https://kb.netgear.com/sitemap"
HTTP_TIMEOUT = 30
SITEMAP_NAMESPACE = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
FIRMWARE_VERSION_MARKER = "-FIRMWARE-VERSION-"


def _version_key(version: str | None) -> tuple[int, ...]:
    """Convert a version string into a comparable tuple of integers."""
    if not version:
        return ()
    return tuple(int(part) for part in re.findall(r"\d+", version))


def _normalize_version(version: str | None) -> str | None:
    """Return a dotted numeric version string."""
    version_key = _version_key(version)
    if not version_key:
        return None
    return ".".join(str(part) for part in version_key)


def _format_version_from_slug(slug_version: str) -> str:
    """Convert a KB article slug version to a dotted version."""
    return slug_version.replace("-", ".")


def _select_latest_release(model_name: str, sitemap_text: str) -> dict[str, str] | None:
    """Return the latest KB firmware article for a model from the sitemap XML."""
    root = ElementTree.fromstring(sitemap_text)
    latest_release = None
    latest_version_key = ()
    model_name_upper = model_name.upper()

    for url_elem in root.findall("sm:url", SITEMAP_NAMESPACE):
        loc_elem = url_elem.find("sm:loc", SITEMAP_NAMESPACE)
        lastmod_elem = url_elem.find("sm:lastmod", SITEMAP_NAMESPACE)
        if loc_elem is None or not loc_elem.text:
            continue

        slug = loc_elem.text.rstrip("/").rsplit("/", maxsplit=1)[-1]
        slug_upper = slug.upper()
        marker_index = slug_upper.rfind(FIRMWARE_VERSION_MARKER)
        if marker_index == -1:
            continue

        model_section = slug_upper[:marker_index]
        if model_name_upper not in model_section.split("-"):
            continue

        version = _format_version_from_slug(
            slug[marker_index + len(FIRMWARE_VERSION_MARKER) :]
        )
        version_key = _version_key(version)
        if version_key <= latest_version_key:
            continue

        latest_version_key = version_key
        latest_release = {
            "release_url": loc_elem.text,
            "latest_version": version,
            "release_date": lastmod_elem.text if lastmod_elem is not None else None,
        }

    return latest_release


def _strip_tags(text: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    without_tags = re.sub(r"<[^>]+>", " ", text)
    return " ".join(without_tags.split())


def _parse_release_article(article_text: str) -> dict[str, str | None]:
    """Parse download URL and title from a firmware KB article."""
    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", article_text, re.I | re.S)
    download_match = re.search(
        r"Download Link:\s*.*?(https://www\.downloads\.netgear\.com[^\"< ]+)",
        article_text,
        re.I | re.S,
    )
    security_match = re.search(
        r"(Security Fixes:.*?)(?:Download Link:|Firmware Update Instructions:|Last Updated:)",
        article_text,
        re.I | re.S,
    )

    release_summary = None
    if security_match:
        release_summary = _strip_tags(security_match.group(1))

    return {
        "release_title": _strip_tags(title_match.group(1)) if title_match else None,
        "download_url": download_match.group(1) if download_match else None,
        "release_summary": release_summary,
    }


def is_update_available(installed_version: str | None, latest_version: str | None) -> bool:
    """Return whether a newer firmware version is available."""
    if not installed_version or not latest_version:
        return False
    return _version_key(latest_version) > _version_key(installed_version)


def get_latest_firmware_info(
    model_name: str,
    installed_version: str | None = None,
) -> dict[str, Any]:
    """Return latest firmware information for a switch model."""
    normalized_installed_version = _normalize_version(installed_version)
    sitemap_response = requests.get(KB_SITEMAP_URL, timeout=HTTP_TIMEOUT)
    sitemap_response.raise_for_status()
    release = _select_latest_release(model_name, sitemap_response.text)

    result: dict[str, Any] = {
        "model_name": model_name,
        "installed_version": normalized_installed_version,
        "installed_version_raw": installed_version,
        "latest_version": None,
        "update_available": False,
        "release_url": None,
        "download_url": None,
        "release_date": None,
        "release_title": None,
        "release_summary": None,
    }
    if release is None:
        return result

    result.update(release)

    article_response = requests.get(result["release_url"], timeout=HTTP_TIMEOUT)
    article_response.raise_for_status()
    result.update(_parse_release_article(article_response.text))
    result["update_available"] = is_update_available(
        normalized_installed_version, result["latest_version"]
    )

    release_date = result["release_date"]
    if release_date:
        result["release_date"] = datetime.fromisoformat(release_date).date().isoformat()

    return result
