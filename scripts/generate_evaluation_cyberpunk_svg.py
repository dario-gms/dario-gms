#!/usr/bin/env python3
"""Generate a custom automated evaluation card based on GitHub metrics."""

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

METRIC_TARGETS: List[Tuple[str, str, float]] = [
    ("stars", "Stars", 250.0),
    ("commits", "Commits", 1200.0),
    ("followers", "Followers", 500.0),
    ("issues", "Issues", 25.0),
    ("repos", "Repositories", 40.0),
    ("pull_requests", "Pull Requests", 160.0),
]

GRADE_STEPS: List[Tuple[float, str, float]] = [
    (1.80, "S*", 5.0),
    (1.55, "S+", 4.8),
    (1.35, "S", 4.6),
    (1.20, "S-", 4.4),
    (1.05, "A+", 4.1),
    (0.90, "A", 3.8),
    (0.78, "A-", 3.6),
    (0.66, "B+", 3.3),
    (0.55, "B", 3.0),
    (0.46, "B-", 2.8),
    (0.38, "C+", 2.5),
    (0.30, "C", 2.2),
    (0.22, "C-", 2.0),
    (0.00, "D", 1.7),
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
    issues_total = fetch_search_total("issues", f"author:{username} type:issue", token)
    prs_total = fetch_search_total("issues", f"author:{username} type:pr", token)
    commits_total = fetch_search_total("commits", f"author:{username}", token)

    return {
        "stars": float(stars_total),
        "commits": float(commits_total),
        "followers": float(followers_total),
        "issues": float(issues_total),
        "repos": float(repos_total),
        "pull_requests": float(prs_total),
    }


def metric_grade(value: float, target: float) -> Tuple[str, float, float]:
    ratio = 0.0 if target <= 0 else value / target
    for min_ratio, grade, points in GRADE_STEPS:
        if ratio >= min_ratio:
            return grade, points, ratio
    return "D", 1.7, ratio


def format_metric_value(value: float) -> str:
    if value >= 1000:
        return f"{value/1000:.1f}k"
    return str(int(round(value)))


def overall_grade(avg_points: float) -> str:
    if avg_points >= 4.95:
        return "S*"
    if avg_points >= 4.7:
        return "S+"
    if avg_points >= 4.5:
        return "S"
    if avg_points >= 4.3:
        return "S-"
    if avg_points >= 4.0:
        return "A+"
    if avg_points >= 3.75:
        return "A"
    if avg_points >= 3.5:
        return "A-"
    if avg_points >= 3.2:
        return "B+"
    if avg_points >= 2.95:
        return "B"
    if avg_points >= 2.7:
        return "B-"
    if avg_points >= 2.4:
        return "C+"
    if avg_points >= 2.1:
        return "C"
    if avg_points >= 1.9:
        return "C-"
    return "D"


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
    row_markup: List[str] = []
    grade_points: List[float] = []
    progress_ratios: List[float] = []

    start_y = 84
    row_h = 30
    bar_w = 250

    for idx, (key, label, target) in enumerate(METRIC_TARGETS):
        value = metrics.get(key, 0.0)
        grade, points, ratio = metric_grade(value, target)
        grade_points.append(points)
        progress = min(ratio, 1.0)
        progress_ratios.append(progress)
        color = grade_color(grade)
        y = start_y + (idx * row_h)
        bar_fill = int(bar_w * progress)

        row_markup.append(
            f"""
  <text x="46" y="{y}" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="14" fill="#00CFFF">{label}:</text>
  <text x="210" y="{y}" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="14" fill="#00CFFF">{format_metric_value(value)}</text>
  <text x="300" y="{y}" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="14" fill="{color}">{grade}</text>
  <rect x="340" y="{y-10}" width="{bar_w}" height="8" rx="4" fill="#0A0F18" />
  <rect x="340" y="{y-10}" width="{bar_fill}" height="8" rx="4" fill="{color}" />
"""
        )

    avg_points = sum(grade_points) / len(grade_points)
    overall = overall_grade(avg_points)
    overall_color = grade_color(overall)
    progress_avg = sum(progress_ratios) / len(progress_ratios)

    ring_radius = 44
    ring_circ = 2 * 3.141592653589793 * ring_radius
    ring_fill = max(0.0, min(progress_avg, 1.0)) * ring_circ

    rows = "".join(row_markup)
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
    CUSTOM PERFORMANCE EVALUATION
  </text>
  <text x="30" y="66" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="12" fill="#5CA1B8">
    stars // commits // followers // issues // repositories // pull requests
  </text>

  {rows}

  <g transform="translate(810,145)">
    <circle cx="0" cy="0" r="{ring_radius}" fill="none" stroke="#350015" stroke-width="8" />
    <circle cx="0" cy="0" r="{ring_radius}" fill="none" stroke="{overall_color}" stroke-width="8"
      stroke-linecap="round" transform="rotate(-90)"
      stroke-dasharray="{ring_fill:.2f} {ring_circ:.2f}" />
    <text x="0" y="8" text-anchor="middle" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="36" font-weight="700" fill="#00CFFF">{overall}</text>
  </g>

  <text x="810" y="214" text-anchor="middle" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="13" fill="{overall_color}">OVERALL</text>
  <text x="{CARD_WIDTH - 24}" y="{CARD_HEIGHT - 16}" text-anchor="end" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="11" fill="#5CA1B8">{username}</text>
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
