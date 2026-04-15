#!/usr/bin/env python3
"""Generate a custom automated trophy grid SVG for a GitHub profile."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List


CARD_WIDTH = 1000
CARD_HEIGHT = 360
MARGIN_X = 30
GRID_TOP = 92
GRID_COLS = 4
GRID_ROWS = 2
GRID_GAP_X = 16
GRID_GAP_Y = 14
TILE_W = int((CARD_WIDTH - (2 * MARGIN_X) - (GRID_GAP_X * (GRID_COLS - 1))) / GRID_COLS)
TILE_H = 108


def github_get_json(url: str, token: str | None) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-trophies-generator",
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


def format_number(value: float) -> str:
    if value >= 1000:
        return f"{int(value):,}"
    if value == int(value):
        return str(int(value))
    return f"{value:.1f}"


def build_trophies(user: dict, repos: List[dict]) -> List[dict]:
    own_repos = [repo for repo in repos if not repo.get("fork")]
    now = dt.datetime.now(dt.UTC)

    stars_total = sum(int(repo.get("stargazers_count", 0)) for repo in own_repos)
    forks_total = sum(int(repo.get("forks_count", 0)) for repo in own_repos)
    max_repo_stars = max((int(repo.get("stargazers_count", 0)) for repo in own_repos), default=0)
    languages = sorted(
        {repo.get("language") for repo in own_repos if repo.get("language")}
    )
    active_90_days = 0
    for repo in own_repos:
        pushed_raw = repo.get("pushed_at")
        if not pushed_raw:
            continue
        pushed_at = dt.datetime.fromisoformat(pushed_raw.replace("Z", "+00:00"))
        if (now - pushed_at).days <= 90:
            active_90_days += 1

    followers = int(user.get("followers", 0))
    public_repos = int(user.get("public_repos", 0))
    created_at = dt.datetime.fromisoformat(str(user.get("created_at")).replace("Z", "+00:00"))
    profile_years = max(0.0, (now - created_at).days / 365.25)

    return [
        {
            "title": "STAR COLLECTOR",
            "value": float(stars_total),
            "target": 300.0,
            "display": format_number(stars_total),
            "hint": "total stars",
        },
        {
            "title": "REPO SHIPYARD",
            "value": float(public_repos),
            "target": 40.0,
            "display": format_number(public_repos),
            "hint": "public repos",
        },
        {
            "title": "POLYGLOT MATRIX",
            "value": float(len(languages)),
            "target": 10.0,
            "display": format_number(len(languages)),
            "hint": "languages",
        },
        {
            "title": "NETWORK SIGNAL",
            "value": float(followers),
            "target": 200.0,
            "display": format_number(followers),
            "hint": "followers",
        },
        {
            "title": "ACTIVE PULSE",
            "value": float(active_90_days),
            "target": 10.0,
            "display": format_number(active_90_days),
            "hint": "repos in 90d",
        },
        {
            "title": "FORK IMPACT",
            "value": float(forks_total),
            "target": 100.0,
            "display": format_number(forks_total),
            "hint": "total forks",
        },
        {
            "title": "FLAGSHIP REPO",
            "value": float(max_repo_stars),
            "target": 100.0,
            "display": format_number(max_repo_stars),
            "hint": "max repo stars",
        },
        {
            "title": "PROFILE VETERAN",
            "value": profile_years,
            "target": 6.0,
            "display": format_number(profile_years),
            "hint": "years on GitHub",
        },
    ]


def trophy_state(ratio: float) -> tuple[str, str]:
    if ratio >= 1.0:
        return ("UNLOCKED", "#FF003C")
    if ratio >= 0.67:
        return ("ADVANCING", "#FF6633")
    return ("BUILDING", "#00CFFF")


def render_svg(username: str, trophies: List[dict]) -> str:
    tiles = trophies[:8]
    tile_markup: List[str] = []

    for idx, trophy in enumerate(tiles):
        col = idx % GRID_COLS
        row = idx // GRID_COLS
        x = MARGIN_X + (col * (TILE_W + GRID_GAP_X))
        y = GRID_TOP + (row * (TILE_H + GRID_GAP_Y))

        ratio = 0.0 if trophy["target"] <= 0 else min(trophy["value"] / trophy["target"], 1.0)
        state_label, state_color = trophy_state(ratio)
        progress_w = max(2.0, (TILE_W - 24) * ratio)

        tile_markup.append(
            f"""
  <g transform="translate({x},{y})">
    <rect width="{TILE_W}" height="{TILE_H}" rx="10" fill="#110B16" stroke="#1A0010" />
    <circle cx="18" cy="18" r="8" fill="{state_color}" />
    <text x="34" y="23" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="13" fill="#FF315A">{trophy["title"]}</text>
    <text x="14" y="50" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="26" fill="#00CFFF">{trophy["display"]}</text>
    <text x="14" y="68" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="11" fill="#5CA1B8">{trophy["hint"]}</text>
    <rect x="12" y="79" width="{TILE_W - 24}" height="8" rx="4" fill="#0A0F18" />
    <rect x="12" y="79" width="{progress_w:.2f}" height="8" rx="4" fill="{state_color}" />
    <text x="{TILE_W - 14}" y="95" text-anchor="end" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="11" fill="{state_color}">{state_label}</text>
  </g>"""
        )

    progress_total = 0.0
    for trophy in tiles:
        if trophy["target"] > 0:
            progress_total += min(trophy["value"] / trophy["target"], 1.0)
    completion_pct = int(round((progress_total / len(tiles)) * 100))

    return f"""<svg width="{CARD_WIDTH}" height="{CARD_HEIGHT}" viewBox="0 0 {CARD_WIDTH} {CARD_HEIGHT}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bgGradient" x1="0" y1="0" x2="{CARD_WIDTH}" y2="{CARD_HEIGHT}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#0B111A" />
      <stop offset="1" stop-color="#140914" />
    </linearGradient>
    <filter id="titleGlow" x="-20%" y="-40%" width="150%" height="200%">
      <feDropShadow dx="0" dy="0" stdDeviation="2" flood-color="#00CFFF" flood-opacity="0.35" />
    </filter>
  </defs>

  <rect x="0.5" y="0.5" width="{CARD_WIDTH - 1}" height="{CARD_HEIGHT - 1}" rx="12" fill="url(#bgGradient)" stroke="#1A2C3D" />
  <text x="30" y="42" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="30" font-weight="700" fill="#00CFFF" filter="url(#titleGlow)">
    CUSTOM TROPHY GRID
  </text>
  <text x="{CARD_WIDTH - 30}" y="42" text-anchor="end" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="13" fill="#FF6633">
    PROFILE COMPLETION: {completion_pct}%
  </text>
  <text x="30" y="66" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="12" fill="#5CA1B8">
    AUTO-GENERATED // USER: {username}
  </text>

  {"".join(tile_markup)}
</svg>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate custom profile trophies SVG.")
    parser.add_argument("--username", required=True, help="GitHub username")
    parser.add_argument(
        "--output",
        default="assets/trophies-cyberpunk.svg",
        help="Output SVG path",
    )
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN")
    user = github_get_json(f"https://api.github.com/users/{args.username}", token)
    repos = fetch_repositories(args.username, token)

    if not isinstance(user, dict):
        raise RuntimeError("Unexpected GitHub user payload.")

    trophies = build_trophies(user, repos)
    svg = render_svg(args.username, trophies)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(svg, encoding="utf-8")
    print(f"Generated {output} with {len(trophies)} custom trophies.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
