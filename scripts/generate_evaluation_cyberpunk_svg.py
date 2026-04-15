#!/usr/bin/env python3
"""Generate a custom automated performance evaluation card."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Dict, List, Tuple

from github_metrics import collect_core_metrics


CARD_WIDTH = 1000
CARD_HEIGHT = 290

# Relaxed targets for a more permissive grading scale.
METRIC_TARGETS: List[Tuple[str, str, float]] = [
    ("stars", "Stars", 170.0),
    ("commits", "Commits", 1100.0),
    ("followers", "Followers", 380.0),
    ("repos", "Repositories", 34.0),
    ("pull_requests", "Pull Requests", 130.0),
]

# Grade scale requested by user: S(*,+,-), A(+,-), ... down to D.
GRADE_STEPS: List[Tuple[float, str]] = [
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


def metric_grade(value: float, target: float) -> Tuple[str, float]:
    ratio = 0.0 if target <= 0 else value / target
    for min_ratio, grade in GRADE_STEPS:
        if ratio >= min_ratio:
            return grade, min(ratio, 1.0)
    return "D", min(ratio, 1.0)


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


def render_svg(username: str, metrics: Dict[str, float]) -> str:
    # Layout: 5 cards in one row.
    card_x0 = 25
    card_y = 72
    card_w = 178
    card_h = 198
    gap = 15
    ring_radius = 44  # same size as old overall ring
    ring_circ = 2 * 3.141592653589793 * ring_radius

    cards: List[str] = []

    commits_year = int(metrics.get("commits_year", 0))

    for idx, (key, label, target) in enumerate(METRIC_TARGETS):
        value = metrics.get(key, 0.0)
        grade, progress = metric_grade(value, target)
        color = grade_color(grade)
        x = card_x0 + idx * (card_w + gap)
        label_text = f"Commits ({commits_year})" if key == "commits" and commits_year else label
        delay = 0.15 + (idx * 0.12)
        ring_fill = progress * ring_circ

        cards.append(
            f"""
  <g transform="translate({x}, {card_y})">
    <rect width="{card_w}" height="{card_h}" rx="10" fill="#110B16" stroke="#1A0010">
      <animate attributeName="stroke-opacity" values="0.55;1;0.55" dur="2.2s" begin="{delay:.2f}s" repeatCount="indefinite" />
    </rect>
    <text x="{card_w/2:.1f}" y="26" text-anchor="middle" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="14" fill="#00CFFF">{label_text}</text>

    <g transform="translate({card_w/2:.1f}, 90)">
      <path id="orbit{idx}" d="M 0 -{ring_radius} A {ring_radius} {ring_radius} 0 1 1 0 {ring_radius} A {ring_radius} {ring_radius} 0 1 1 0 -{ring_radius}" fill="none" />
      <circle cx="0" cy="0" r="{ring_radius}" fill="none" stroke="#350015" stroke-width="8" />
      <circle cx="0" cy="0" r="{ring_radius}" fill="none" stroke="{color}" stroke-width="8"
        stroke-linecap="round" transform="rotate(-90)"
        stroke-dasharray="0 {ring_circ:.2f}">
        <animate attributeName="stroke-dasharray" from="0 {ring_circ:.2f}" to="{ring_fill:.2f} {ring_circ:.2f}" dur="1.1s" begin="{delay:.2f}s" fill="freeze" />
        <animate attributeName="stroke-width" values="8;9.4;8" dur="1.6s" begin="{delay:.2f}s" repeatCount="indefinite" />
      </circle>
      <circle r="3.4" fill="{color}">
        <animateMotion dur="{3.2 + (idx * 0.2):.1f}s" repeatCount="indefinite" rotate="auto">
          <mpath href="#orbit{idx}" />
        </animateMotion>
        <animate attributeName="opacity" values="0.5;1;0.5" dur="1.1s" begin="{delay:.2f}s" repeatCount="indefinite" />
      </circle>
      <text x="0" y="8" text-anchor="middle" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="34" font-weight="700" fill="#00CFFF">{grade}
        <animate attributeName="fill-opacity" values="0.8;1;0.8" dur="1.6s" begin="{delay:.2f}s" repeatCount="indefinite" />
      </text>
    </g>

    <text x="{card_w/2:.1f}" y="170" text-anchor="middle" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="16" fill="#FF6633">{format_metric_value(value)}</text>
  </g>
"""
        )

    return f"""<svg width="{CARD_WIDTH}" height="{CARD_HEIGHT}" viewBox="0 0 {CARD_WIDTH} {CARD_HEIGHT}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bgGradient" x1="0" y1="0" x2="{CARD_WIDTH}" y2="{CARD_HEIGHT}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#0B111A" />
      <stop offset="1" stop-color="#140914" />
    </linearGradient>
    <filter id="titleGlow" x="-20%" y="-40%" width="150%" height="200%">
      <feDropShadow dx="0" dy="0" stdDeviation="2.0" flood-color="#00CFFF" flood-opacity="0.35" />
    </filter>
  </defs>

  <rect x="0.5" y="0.5" width="{CARD_WIDTH - 1}" height="{CARD_HEIGHT - 1}" rx="12" fill="url(#bgGradient)" stroke="#1A2C3D" />
  <text x="30" y="44" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="30" font-weight="700" fill="#00CFFF" filter="url(#titleGlow)">
    PERFORMANCE EVALUATION
  </text>

  {"".join(cards)}

  <text x="{CARD_WIDTH - 20}" y="{CARD_HEIGHT - 16}" text-anchor="end" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="11" fill="#5CA1B8">{username}</text>
</svg>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate custom GitHub evaluation SVG.")
    parser.add_argument("--username", required=True, help="GitHub username")
    parser.add_argument(
        "--output",
        default="assets/evaluation-cyberpunk.svg",
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

