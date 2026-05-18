#!/usr/bin/env python3
"""Generate a custom Top Languages SVG card.

This script fetches public repositories from the GitHub API and computes
language percentages by code size in bytes (top N languages). It then writes
an SVG card using the project's profile visual style.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from html import escape
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


CARD_WIDTH = 350
CARD_HEIGHT = 170
BAR_X = 25
BAR_Y = 55
BAR_WIDTH = 300
BAR_HEIGHT = 8

LANGUAGE_COLORS: Dict[str, str] = {
    "Dart": "#00E5FF",
    "HTML": "#FF6B35",
    "Python": "#2F6BFF",
    "C#": "#FF315A",
    "JavaScript": "#FFB347",
}
PREFERRED_ORDER = ["Dart", "HTML", "Python", "C#", "JavaScript"]
PREFERRED_INDEX = {name: idx for idx, name in enumerate(PREFERRED_ORDER)}

FALLBACK_COLORS = [
    "#00E5FF",
    "#FF6B35",
    "#2F6BFF",
    "#FF315A",
    "#FFB347",
    "#44D07D",
    "#B276FF",
]


def fetch_repositories(username: str, token: str | None) -> List[dict]:
    repos: List[dict] = []
    page = 1

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-top-langs-generator",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    while True:
        query = urllib.parse.urlencode(
            {"per_page": 100, "page": page, "type": "owner", "sort": "updated"}
        )
        url = f"https://api.github.com/users/{username}/repos?{query}"
        request = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = response.read().decode("utf-8")
                batch = json.loads(payload)
        except urllib.error.HTTPError as err:
            details = err.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"GitHub API error {err.code} while fetching repos: {details}"
            ) from err
        except urllib.error.URLError as err:
            raise RuntimeError(f"Network error while fetching repos: {err}") from err

        if not batch:
            break

        repos.extend(batch)
        page += 1

    return repos


def fetch_repo_languages(languages_url: str, token: str | None) -> Dict[str, int]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-top-langs-generator",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(languages_url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read().decode("utf-8")
            data = json.loads(payload)
    except urllib.error.HTTPError as err:
        details = err.read().decode("utf-8", errors="replace")
        if err.code == 403 and "rate limit exceeded" in details.lower():
            return {}
        raise RuntimeError(
            f"GitHub API error {err.code} while fetching repo languages: {details}"
        ) from err
    except urllib.error.URLError as err:
        raise RuntimeError(f"Network error while fetching repo languages: {err}") from err

    if not isinstance(data, dict):
        return {}

    languages: Dict[str, int] = {}
    for name, bytes_count in data.items():
        try:
            languages[str(name)] = int(bytes_count)
        except (TypeError, ValueError):
            continue
    return languages


def select_top_languages(
    repos: Iterable[dict], top_n: int, include_forks: bool, token: str | None
) -> List[Tuple[str, int]]:
    counts: Counter[str] = Counter()
    primary_counts: Counter[str] = Counter()
    for repo in repos:
        if not include_forks and repo.get("fork"):
            continue

        primary_language = repo.get("language")
        if primary_language:
            primary_counts[str(primary_language)] += 1

        languages_url = repo.get("languages_url")
        if not languages_url:
            continue
        repo_languages = fetch_repo_languages(str(languages_url), token)
        for language, bytes_count in repo_languages.items():
            counts[language] += bytes_count

    # Fallback for unauthenticated local runs when the rate limit is reached.
    if not counts and primary_counts:
        counts = primary_counts

    # Deterministic ordering for ties, favoring the intended visual order.
    def rank(item: Tuple[str, int]) -> Tuple[int, int, str]:
        language, count = item
        preferred = PREFERRED_INDEX.get(language)
        if preferred is not None:
            return (-count, preferred, language.lower())
        return (-count, len(PREFERRED_ORDER) + 1, language.lower())

    ranked = sorted(counts.items(), key=rank)
    return ranked[:top_n]


def color_for_language(language: str, index: int) -> str:
    if language in LANGUAGE_COLORS:
        return LANGUAGE_COLORS[language]
    return FALLBACK_COLORS[index % len(FALLBACK_COLORS)]


def build_svg(top_langs: List[Tuple[str, int]], username: str) -> str:
    total = sum(count for _, count in top_langs)
    if total <= 0:
        # Minimal empty state card.
        return f"""<svg width="{CARD_WIDTH}" height="{CARD_HEIGHT}" viewBox="0 0 {CARD_WIDTH} {CARD_HEIGHT}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect x="0.5" y="0.5" width="{CARD_WIDTH-1}" height="{CARD_HEIGHT-1}" rx="6" fill="#090D15" stroke="#1A0010" />
  <text x="25" y="35" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="21" font-weight="600" fill="#FF315A">Top Languages</text>
  <text x="25" y="92" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="13" fill="#00CFFF">No public language data yet for {escape(username)}.</text>
</svg>
"""

    percentages = [(lang, count, (count * 100.0) / total) for lang, count in top_langs]

    parts: List[str] = []
    legend: List[str] = []
    cursor_x = float(BAR_X)

    for idx, (language, _, pct) in enumerate(percentages):
        color = color_for_language(language, idx)
        if idx == len(percentages) - 1:
            width = BAR_X + BAR_WIDTH - cursor_x
        else:
            width = (pct / 100.0) * BAR_WIDTH
        delay = 0.15 + (idx * 0.12)
        parts.append(
            f"""    <rect x="{cursor_x:.4f}" y="{BAR_Y}" width="0" height="{BAR_HEIGHT}" fill="{color}">
      <animate attributeName="width" from="0" to="{width:.4f}" dur="0.75s" begin="{delay:.2f}s" fill="freeze" />
      <animate attributeName="opacity" values="0.82;1;0.82" dur="1.8s" begin="{delay:.2f}s" repeatCount="indefinite" />
    </rect>"""
        )
        cursor_x += width

    for idx, (language, _, pct) in enumerate(percentages):
        col = idx % 2
        row = idx // 2
        cx = 30 if col == 0 else 180
        cy = 86 + (row * 25)
        color = color_for_language(language, idx)
        delay = 0.3 + (idx * 0.12)
        legend.append(
            f"""    <circle cx="{cx}" cy="{cy}" r="5" fill="{color}">
      <animate attributeName="r" values="4.2;5.4;4.2" dur="1.4s" begin="{delay:.2f}s" repeatCount="indefinite" />
      <animate attributeName="opacity" values="0.7;1;0.7" dur="1.4s" begin="{delay:.2f}s" repeatCount="indefinite" />
    </circle>"""
        )
        legend.append(
            f'    <text x="{cx + 10}" y="{cy + 4}">{escape(language)} {pct:.2f}%</text>'
        )

    bar_segments = "\n".join(parts)
    legend_rows = "\n".join(legend)

    return f"""<svg width="{CARD_WIDTH}" height="{CARD_HEIGHT}" viewBox="0 0 {CARD_WIDTH} {CARD_HEIGHT}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bgGradient" x1="0" y1="0" x2="{CARD_WIDTH}" y2="{CARD_HEIGHT}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#090D15" />
      <stop offset="1" stop-color="#140914" />
    </linearGradient>
    <filter id="softGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="0" stdDeviation="1.4" flood-color="#00CFFF" flood-opacity="0.25" />
    </filter>
    <clipPath id="progressClip">
      <rect x="{BAR_X}" y="{BAR_Y}" width="{BAR_WIDTH}" height="{BAR_HEIGHT}" rx="5" />
    </clipPath>
    <linearGradient id="scanGradient" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#00CFFF" stop-opacity="0" />
      <stop offset="0.5" stop-color="#00CFFF" stop-opacity="0.75" />
      <stop offset="1" stop-color="#00CFFF" stop-opacity="0" />
    </linearGradient>
  </defs>

  <rect x="0.5" y="0.5" width="{CARD_WIDTH-1}" height="{CARD_HEIGHT-1}" rx="6" fill="url(#bgGradient)" stroke="#1A0010" />
  <text x="25" y="35" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="21" font-weight="600" fill="#FF315A">Top Languages
    <animate attributeName="fill-opacity" values="0.85;1;0.85" dur="1.6s" repeatCount="indefinite" />
  </text>

  <rect x="{BAR_X}" y="{BAR_Y}" width="{BAR_WIDTH}" height="{BAR_HEIGHT}" rx="5" fill="#0A0F18" />
  <g clip-path="url(#progressClip)" filter="url(#softGlow)">
{bar_segments}
    <rect x="{BAR_X - 34}" y="{BAR_Y - 1}" width="34" height="{BAR_HEIGHT + 2}" fill="url(#scanGradient)" opacity="0">
      <animate attributeName="x" values="{BAR_X - 34};{BAR_X + BAR_WIDTH};{BAR_X + BAR_WIDTH}" dur="2.4s" repeatCount="indefinite" />
      <animate attributeName="opacity" values="0;0.7;0" dur="2.4s" repeatCount="indefinite" />
    </rect>
  </g>

  <g font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="12" fill="#00CFFF">
{legend_rows}
  </g>
</svg>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate top languages SVG card.")
    parser.add_argument("--username", required=True, help="GitHub username")
    parser.add_argument(
        "--output",
        default="assets/top-langs.svg",
        help="Output SVG path",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=6,
        help="How many languages to render (default: 6)",
    )
    parser.add_argument(
        "--include-forks",
        action="store_true",
        help="Include forked repositories",
    )
    args = parser.parse_args()

    if args.top < 1:
        print("--top must be >= 1", file=sys.stderr)
        return 2

    token = os.getenv("GITHUB_TOKEN")
    repos = fetch_repositories(args.username, token)
    top_langs = select_top_languages(
        repos,
        top_n=args.top,
        include_forks=args.include_forks,
        token=token,
    )
    svg = build_svg(top_langs, username=args.username)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    print(
        f"Generated {output_path} with {len(top_langs)} languages from {len(repos)} repos."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
