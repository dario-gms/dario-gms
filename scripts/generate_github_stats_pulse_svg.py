#!/usr/bin/env python3
"""Generate an animated GitHub stats card."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Dict, List, Tuple

from github_metrics import collect_core_metrics


CARD_WIDTH = 350
CARD_HEIGHT = 170

RANK_STEPS: List[Tuple[float, str]] = [
    (1.45, "S*"),
    (1.30, "S+"),
    (1.15, "S"),
    (1.02, "S-"),
    (0.90, "A+"),
    (0.78, "A"),
    (0.66, "A-"),
    (0.56, "B+"),
    (0.47, "B"),
    (0.39, "B-"),
    (0.32, "C+"),
    (0.25, "C"),
    (0.19, "C-"),
    (0.00, "D"),
]

RANK_TARGETS = {
    "stars": 170.0,
    "commits": 1100.0,
    "pull_requests": 130.0,
    "followers": 380.0,
    "repos": 34.0,
}


def format_metric_value(value: float) -> str:
    if value >= 1000:
        return f"{value / 1000:.1f}k".replace(".0k", "k")
    return str(int(round(value)))


def grade_color(grade: str) -> str:
    if grade.startswith("S"):
        return "#FF003C"
    if grade.startswith("A"):
        return "#FF6633"
    if grade.startswith("B"):
        return "#00CFFF"
    if grade.startswith("C"):
        return "#4AB1FF"
    return "#8A9AA7"


def overall_grade(metrics: Dict[str, float]) -> Tuple[str, float]:
    ratios: List[float] = []
    for key, target in RANK_TARGETS.items():
        value = metrics.get(key, 0.0)
        ratio = 0.0 if target <= 0 else value / target
        ratios.append(ratio)

    score = 0.0 if not ratios else sum(ratios) / len(ratios)
    progress = min(score, 1.0)
    for minimum, rank in RANK_STEPS:
        if score >= minimum:
            return rank, progress
    return "D", progress


def render_svg(username: str, metrics: Dict[str, float]) -> str:
    commits_year = int(metrics.get("commits_year", 0))
    rank, progress = overall_grade(metrics)
    rank_color = grade_color(rank)

    ring_radius = 32
    ring_circ = 2 * 3.141592653589793 * ring_radius
    ring_fill = progress * ring_circ

    entries = [
        ("Total Stars", format_metric_value(metrics.get("stars", 0.0))),
        (f"Total Commits ({commits_year})", format_metric_value(metrics.get("commits", 0.0))),
        ("Total PRs", format_metric_value(metrics.get("pull_requests", 0.0))),
        ("Followers", format_metric_value(metrics.get("followers", 0.0))),
        ("Repositories", format_metric_value(metrics.get("repos", 0.0))),
    ]

    rows: List[str] = []
    row_y = 46
    for idx, (label, value) in enumerate(entries):
        y = row_y + idx * 22
        delay = 0.25 + idx * 0.10
        rows.append(
            f"""
  <g transform="translate(18, {y})">
    <circle cx="0" cy="-4" r="2.4" fill="#FF6633">
      <animate attributeName="opacity" values="0.5;1;0.5" dur="1.2s" begin="{delay:.2f}s" repeatCount="indefinite" />
    </circle>
    <text x="9" y="0" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="12.5" fill="#00CFFF">{label}:</text>
    <text x="166" y="0" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="12.5" fill="#00CFFF">{value}</text>
  </g>
"""
        )

    return f"""<svg width="{CARD_WIDTH}" height="{CARD_HEIGHT}" viewBox="0 0 {CARD_WIDTH} {CARD_HEIGHT}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bgGradient" x1="0" y1="0" x2="{CARD_WIDTH}" y2="{CARD_HEIGHT}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#0D0D0D" />
      <stop offset="1" stop-color="#140914" />
    </linearGradient>
    <filter id="titleGlow" x="-20%" y="-50%" width="150%" height="200%">
      <feDropShadow dx="0" dy="0" stdDeviation="1.8" flood-color="#00CFFF" flood-opacity="0.45" />
    </filter>
  </defs>

  <rect x="0.5" y="0.5" width="{CARD_WIDTH - 1}" height="{CARD_HEIGHT - 1}" rx="8" fill="url(#bgGradient)" stroke="#1A0010">
    <animate attributeName="stroke-opacity" values="0.6;1;0.6" dur="2.2s" repeatCount="indefinite" />
  </rect>

  <text x="18" y="26" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="16" font-weight="700" fill="#FF003C" filter="url(#titleGlow)">
    Dario's GitHub Stats
  </text>

  {"".join(rows)}

  <g transform="translate(296, 86)">
    <path id="rankOrbit" d="M 0 -{ring_radius} A {ring_radius} {ring_radius} 0 1 1 0 {ring_radius} A {ring_radius} {ring_radius} 0 1 1 0 -{ring_radius}" fill="none" />
    <circle cx="0" cy="0" r="{ring_radius}" fill="none" stroke="#350015" stroke-width="6" />
    <circle cx="0" cy="0" r="{ring_radius}" fill="none" stroke="{rank_color}" stroke-width="6"
      stroke-linecap="round" transform="rotate(-90)" stroke-dasharray="0 {ring_circ:.2f}">
      <animate attributeName="stroke-dasharray" from="0 {ring_circ:.2f}" to="{ring_fill:.2f} {ring_circ:.2f}" dur="1.05s" begin="0.32s" fill="freeze" />
      <animate attributeName="stroke-width" values="6;7.6;6" dur="1.6s" repeatCount="indefinite" />
    </circle>
    <circle r="2.6" fill="{rank_color}">
      <animateMotion dur="3.1s" repeatCount="indefinite" rotate="auto">
        <mpath href="#rankOrbit" />
      </animateMotion>
      <animate attributeName="opacity" values="0.45;1;0.45" dur="1.1s" repeatCount="indefinite" />
    </circle>
    <text x="0" y="7" text-anchor="middle" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="23" font-weight="700" fill="#00CFFF">{rank}
      <animate attributeName="fill-opacity" values="0.85;1;0.85" dur="1.45s" repeatCount="indefinite" />
    </text>
  </g>

  <text x="296" y="137" text-anchor="middle" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="11" fill="{rank_color}">RANK</text>
  <text x="{CARD_WIDTH - 12}" y="{CARD_HEIGHT - 8}" text-anchor="end" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="9" fill="#5CA1B8">{username}</text>
</svg>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate animated GitHub stats SVG.")
    parser.add_argument("--username", required=True, help="GitHub username")
    parser.add_argument(
        "--output",
        default="assets/github-stats.svg",
        help="Output SVG path",
    )
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN")
    metrics = collect_core_metrics(args.username, token)
    svg = render_svg(args.username, metrics)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    print(f"Generated {output_path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
