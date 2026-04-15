#!/usr/bin/env python3
"""Generate a custom automated performance evaluation card."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple


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


def github_get_json(url: str, token: str | None, accept: str = "application/vnd.github+json") -> object:
    headers = {
        "Accept": accept,
        "User-Agent": "profile-evaluation-generator",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {err.code}: {detail}") from err
    except urllib.error.URLError as err:
        raise RuntimeError(f"Network error while calling GitHub API: {err}") from err


def fetch_repositories(username: str, token: str | None) -> List[dict]:
    repos: List[dict] = []
    page = 1
    while True:
        query = urllib.parse.urlencode(
            {"per_page": 100, "page": page, "type": "owner", "sort": "updated"}
        )
        url = f"https://api.github.com/users/{username}/repos?{query}"
        batch = github_get_json(url, token)
        if not isinstance(batch, list) or not batch:
            break
        repos.extend(batch)
        page += 1
    return repos


def fetch_search_total(kind: str, query: str, token: str | None, accept: str = "application/vnd.github+json") -> int:
    encoded_q = urllib.parse.quote_plus(query)
    url = f"https://api.github.com/search/{kind}?q={encoded_q}&per_page=1"
    payload = github_get_json(url, token, accept=accept)
    if isinstance(payload, dict):
        return int(payload.get("total_count", 0))
    return 0


def collect_metrics(username: str, token: str | None) -> Dict[str, float]:
    user_payload = github_get_json(f"https://api.github.com/users/{username}", token)
    if not isinstance(user_payload, dict):
        raise RuntimeError("Unexpected payload when loading user profile.")

    repos = fetch_repositories(username, token)
    own_repos = [repo for repo in repos if not repo.get("fork")]

    stars_total = sum(int(repo.get("stargazers_count", 0)) for repo in own_repos)
    repos_total = int(user_payload.get("public_repos", 0))
    followers_total = int(user_payload.get("followers", 0))
    prs_total = fetch_search_total("issues", f"author:{username} type:pr", token)
    commits_total = fetch_search_total("commits", f"author:{username}", token)

    return {
        "stars": float(stars_total),
        "commits": float(commits_total),
        "followers": float(followers_total),
        "repos": float(repos_total),
        "pull_requests": float(prs_total),
    }


def metric_grade(value: float, target: float) -> Tuple[str, float]:
    ratio = 0.0 if target <= 0 else value / target
    for min_ratio, grade in GRADE_STEPS:
        if ratio >= min_ratio:
            return grade, min(ratio, 1.0)
    return "D", min(ratio, 1.0)


def format_metric_value(value: float) -> str:
    if value >= 1000:
        return f"{value/1000:.1f}k"
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

    for idx, (key, label, target) in enumerate(METRIC_TARGETS):
        value = metrics.get(key, 0.0)
        grade, progress = metric_grade(value, target)
        color = grade_color(grade)
        x = card_x0 + idx * (card_w + gap)
        cx = x + card_w / 2
        cy = card_y + 90
        ring_fill = progress * ring_circ

        cards.append(
            f"""
  <g transform="translate({x}, {card_y})">
    <rect width="{card_w}" height="{card_h}" rx="10" fill="#110B16" stroke="#1A0010" />
    <text x="{card_w/2:.1f}" y="26" text-anchor="middle" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="14" fill="#00CFFF">{label}</text>

    <g transform="translate({card_w/2:.1f}, 90)">
      <circle cx="0" cy="0" r="{ring_radius}" fill="none" stroke="#350015" stroke-width="8" />
      <circle cx="0" cy="0" r="{ring_radius}" fill="none" stroke="{color}" stroke-width="8"
        stroke-linecap="round" transform="rotate(-90)"
        stroke-dasharray="{ring_fill:.2f} {ring_circ:.2f}" />
      <text x="0" y="8" text-anchor="middle" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="34" font-weight="700" fill="#00CFFF">{grade}</text>
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
    metrics = collect_metrics(args.username, token)
    svg = render_svg(args.username, metrics)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    print(f"Generated {output_path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

