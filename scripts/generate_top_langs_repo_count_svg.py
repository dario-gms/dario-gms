#!/usr/bin/env python3
"""Generate a full-width Top Languages card by repository count."""

from __future__ import annotations

import argparse
import math
import os
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from github_metrics import fetch_repositories


CARD_WIDTH = 1000
MIN_CARD_HEIGHT = 290
COLUMN_COUNT = 3

LANGUAGE_COLORS: Dict[str, str] = {
    "C#": "#FF315A",
    "Dart": "#00E5FF",
    "HTML": "#FF6B35",
    "Python": "#2F6BFF",
    "JavaScript": "#FFB347",
    "PHP": "#FFB347",
    "C": "#44D07D",
}

PREFERRED_ORDER = ["C#", "Dart", "HTML", "Python", "JavaScript", "PHP", "C"]
PREFERRED_INDEX = {name: idx for idx, name in enumerate(PREFERRED_ORDER)}

FALLBACK_COLORS = [
    "#00E5FF",
    "#FF6B35",
    "#2F6BFF",
    "#FF315A",
    "#FFB347",
    "#44D07D",
    "#9B6DFF",
    "#00D68F",
]


def color_for_language(language: str, index: int) -> str:
    if language in LANGUAGE_COLORS:
        return LANGUAGE_COLORS[language]
    return FALLBACK_COLORS[index % len(FALLBACK_COLORS)]


def select_repo_language_counts(
    repos: Iterable[dict], include_forks: bool
) -> Tuple[List[Tuple[str, int]], int]:
    counts: Counter[str] = Counter()
    repos_with_language = 0
    for repo in repos:
        if not include_forks and repo.get("fork"):
            continue
        language = repo.get("language")
        if not language:
            continue
        counts[str(language)] += 1
        repos_with_language += 1

    def rank(item: Tuple[str, int]) -> Tuple[int, int, str]:
        language, count = item
        preferred = PREFERRED_INDEX.get(language)
        if preferred is not None:
            return (-count, preferred, language.lower())
        return (-count, len(PREFERRED_ORDER) + 1, language.lower())

    ranked = sorted(counts.items(), key=rank)
    return ranked, repos_with_language


def compute_card_height(language_count: int) -> int:
    rows = max(1, math.ceil(language_count / COLUMN_COUNT))
    dynamic = 140 + (rows * 38) + 34
    return max(MIN_CARD_HEIGHT, dynamic)


def build_svg(
    username: str,
    language_counts: List[Tuple[str, int]],
    repos_analyzed: int,
    repos_with_language: int,
) -> str:
    card_height = compute_card_height(len(language_counts))
    if repos_with_language <= 0 or not language_counts:
        return f"""<svg width="{CARD_WIDTH}" height="{card_height}" viewBox="0 0 {CARD_WIDTH} {card_height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bgGradient" x1="0" y1="0" x2="{CARD_WIDTH}" y2="{card_height}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#0B111A" />
      <stop offset="1" stop-color="#140914" />
    </linearGradient>
  </defs>
  <rect x="0.5" y="0.5" width="{CARD_WIDTH-1}" height="{card_height-1}" rx="12" fill="url(#bgGradient)" stroke="#1A2C3D" />
  <text x="30" y="44" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="30" font-weight="700" fill="#00CFFF">LANGUAGES BY REPO COUNT</text>
  <text x="30" y="94" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="17" fill="#FF6633">No public primary-language data available yet.</text>
  <text x="{CARD_WIDTH - 20}" y="{card_height - 16}" text-anchor="end" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="11" fill="#5CA1B8">{username}</text>
</svg>
"""

    total = sum(count for _, count in language_counts)
    max_count = max(count for _, count in language_counts)
    percentages = [(lang, count, (count * 100.0) / total) for lang, count in language_counts]

    bar_parts: List[str] = []
    row_parts: List[str] = []

    bar_x = 30.0
    bar_y = 79.0
    bar_width = 940.0
    bar_height = 10.0
    cursor_x = bar_x

    for idx, (language, _, pct) in enumerate(percentages):
        color = color_for_language(language, idx)
        width = bar_x + bar_width - cursor_x if idx == len(percentages) - 1 else (pct / 100.0) * bar_width
        delay = 0.18 + (idx * 0.08)
        bar_parts.append(
            f"""    <rect x="{cursor_x:.4f}" y="{bar_y:.2f}" width="0" height="{bar_height:.2f}" fill="{color}">
      <animate attributeName="width" from="0" to="{width:.4f}" dur="0.7s" begin="{delay:.2f}s" fill="freeze" />
      <animate attributeName="opacity" values="0.80;1;0.80" dur="1.7s" begin="{delay:.2f}s" repeatCount="indefinite" />
    </rect>"""
        )
        cursor_x += width

    rows = math.ceil(len(percentages) / COLUMN_COUNT)
    row_start_y = 118
    row_height = 38
    col_gap = 22.0
    col_width = (CARD_WIDTH - 60.0 - ((COLUMN_COUNT - 1) * col_gap)) / COLUMN_COUNT

    for idx, (language, count, pct) in enumerate(percentages):
        col = idx % COLUMN_COUNT
        row = idx // COLUMN_COUNT
        color = color_for_language(language, idx)
        x = 30.0 + col * (col_width + col_gap)
        y = row_start_y + row * row_height
        progress_width = (count / max_count) * (col_width - 22.0)
        delay = 0.25 + (idx * 0.06)
        row_parts.append(
            f"""
  <g transform="translate({x:.2f}, {y:.2f})">
    <circle cx="6" cy="8" r="5" fill="{color}">
      <animate attributeName="r" values="4.2;5.5;4.2" dur="1.5s" begin="{delay:.2f}s" repeatCount="indefinite" />
      <animate attributeName="opacity" values="0.72;1;0.72" dur="1.5s" begin="{delay:.2f}s" repeatCount="indefinite" />
    </circle>
    <text x="18" y="12" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="14.5" fill="#00CFFF">{language}</text>
    <text x="{col_width - 4:.2f}" y="12" text-anchor="end" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="14.5" fill="#FF6633">{count} repos • {pct:.2f}%</text>
    <rect x="18" y="19" width="{col_width - 22:.2f}" height="6" rx="4" fill="#0F1824" />
    <rect x="18" y="19" width="0" height="6" rx="4" fill="{color}">
      <animate attributeName="width" from="0" to="{progress_width:.2f}" dur="0.68s" begin="{delay:.2f}s" fill="freeze" />
      <animate attributeName="opacity" values="0.8;1;0.8" dur="1.6s" begin="{delay:.2f}s" repeatCount="indefinite" />
    </rect>
  </g>"""
        )

    legend_height = row_start_y + (rows * row_height) + 8
    footer_y = max(card_height - 16, legend_height + 20)

    return f"""<svg width="{CARD_WIDTH}" height="{card_height}" viewBox="0 0 {CARD_WIDTH} {card_height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bgGradient" x1="0" y1="0" x2="{CARD_WIDTH}" y2="{card_height}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#0B111A" />
      <stop offset="1" stop-color="#140914" />
    </linearGradient>
    <filter id="titleGlow" x="-20%" y="-40%" width="150%" height="200%">
      <feDropShadow dx="0" dy="0" stdDeviation="2.0" flood-color="#00CFFF" flood-opacity="0.35" />
    </filter>
    <clipPath id="progressClip">
      <rect x="{bar_x:.2f}" y="{bar_y:.2f}" width="{bar_width:.2f}" height="{bar_height:.2f}" rx="5" />
    </clipPath>
  </defs>

  <rect x="0.5" y="0.5" width="{CARD_WIDTH - 1}" height="{card_height - 1}" rx="12" fill="url(#bgGradient)" stroke="#1A2C3D" />
  <text x="30" y="44" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="30" font-weight="700" fill="#00CFFF" filter="url(#titleGlow)">
    LANGUAGES BY REPO COUNT
  </text>
  <text x="30" y="64" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="13.5" fill="#5CA1B8">
    primary language per repository • repos analyzed: {repos_analyzed} • languages: {len(language_counts)}
  </text>

  <rect x="{bar_x:.2f}" y="{bar_y:.2f}" width="{bar_width:.2f}" height="{bar_height:.2f}" rx="5" fill="#0A0F18" />
  <g clip-path="url(#progressClip)">
{"".join(bar_parts)}
  </g>

{"".join(row_parts)}

  <text x="{CARD_WIDTH - 20}" y="{footer_y}" text-anchor="end" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="11" fill="#5CA1B8">{username}</text>
</svg>
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate full-width language distribution card by repo count."
    )
    parser.add_argument("--username", required=True, help="GitHub username")
    parser.add_argument(
        "--output",
        default="assets/top-langs-repo-count.svg",
        help="Output SVG path",
    )
    parser.add_argument(
        "--include-forks",
        action="store_true",
        help="Include forked repositories",
    )
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN")
    repos = fetch_repositories(args.username, token)
    language_counts, repos_with_language = select_repo_language_counts(
        repos,
        include_forks=args.include_forks,
    )
    svg = build_svg(
        username=args.username,
        language_counts=language_counts,
        repos_analyzed=len(repos),
        repos_with_language=repos_with_language,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    print(
        f"Generated {output_path} with {len(language_counts)} languages from {repos_with_language} repositories."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
