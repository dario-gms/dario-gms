#!/usr/bin/env python3
"""Shared GitHub metrics helpers for profile card generators."""

from __future__ import annotations

import datetime as dt
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional


DEFAULT_STATS_ENDPOINT = "https://github-readme-stats-sigma-five.vercel.app/api"


def github_get_json(
    url: str,
    token: str | None,
    accept: str = "application/vnd.github+json",
) -> object:
    headers = {
        "Accept": accept,
        "User-Agent": "profile-cards-generator",
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


def github_post_graphql(query: str, variables: Dict[str, object], token: str | None) -> object | None:
    if not token:
        return None

    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "profile-cards-generator",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError:
        return None
    except urllib.error.URLError:
        return None


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


def fetch_search_total(
    kind: str,
    query: str,
    token: str | None,
    accept: str = "application/vnd.github+json",
) -> int:
    encoded_q = urllib.parse.quote_plus(query)
    url = f"https://api.github.com/search/{kind}?q={encoded_q}&per_page=1"
    payload = github_get_json(url, token, accept=accept)
    if isinstance(payload, dict):
        return int(payload.get("total_count", 0))
    return 0


def parse_compact_number(text: str) -> Optional[int]:
    cleaned = text.strip().lower().replace(",", "").replace(" ", "")
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([kmb])?", cleaned)
    if not match:
        return None

    base = float(match.group(1))
    unit = match.group(2)
    if unit == "k":
        base *= 1000
    elif unit == "m":
        base *= 1_000_000
    elif unit == "b":
        base *= 1_000_000_000
    return int(round(base))


def fetch_commits_from_readme_stats(
    username: str,
    endpoint: str = DEFAULT_STATS_ENDPOINT,
) -> Optional[int]:
    url = (
        f"{endpoint}?username={urllib.parse.quote(username)}&show_icons=true"
        "&count_private=true"
    )
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "image/svg+xml,text/plain;q=0.9,*/*;q=0.8",
            "User-Agent": "profile-cards-generator",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            svg_text = response.read().decode("utf-8", errors="replace")
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None

    match = re.search(r'data-testid="commits"\s*>\s*([^<]+)\s*</text>', svg_text)
    if not match:
        return None

    return parse_compact_number(match.group(1))


def fetch_current_year_commits(
    username: str,
    token: str | None,
    year: int | None = None,
    stats_endpoint: str = DEFAULT_STATS_ENDPOINT,
) -> int:
    active_year = year if year is not None else dt.date.today().year
    start_time = f"{active_year}-01-01T00:00:00Z"

    query = """
    query UserCommits($login: String!, $startTime: DateTime!) {
      user(login: $login) {
        commits: contributionsCollection(from: $startTime) {
          totalCommitContributions
        }
      }
    }
    """

    gql_payload = github_post_graphql(query, {"login": username, "startTime": start_time}, token)
    if isinstance(gql_payload, dict):
        user = (
            gql_payload.get("data", {})
            .get("user", {})
        )
        commits = (
            user.get("commits", {})
            .get("totalCommitContributions")
        )
        if isinstance(commits, int):
            return commits

    stats_commits = fetch_commits_from_readme_stats(username, endpoint=stats_endpoint)
    if isinstance(stats_commits, int):
        return stats_commits

    return fetch_search_total(
        "commits",
        f"author:{username}",
        token,
        accept="application/vnd.github.cloak-preview+json",
    )


def fetch_repositories_contributed_to(username: str, token: str | None) -> int:
    query = """
    query UserContribRepos($login: String!) {
      user(login: $login) {
        repositoriesContributedTo(
          first: 1,
          contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]
        ) {
          totalCount
        }
      }
    }
    """
    payload = github_post_graphql(query, {"login": username}, token)
    if not isinstance(payload, dict):
        return 0

    return int(
        payload.get("data", {})
        .get("user", {})
        .get("repositoriesContributedTo", {})
        .get("totalCount", 0)
    )


def collect_core_metrics(
    username: str,
    token: str | None,
    year: int | None = None,
    stats_endpoint: str = DEFAULT_STATS_ENDPOINT,
) -> Dict[str, float]:
    user_payload = github_get_json(f"https://api.github.com/users/{username}", token)
    if not isinstance(user_payload, dict):
        raise RuntimeError("Unexpected payload when loading user profile.")

    repos = fetch_repositories(username, token)
    own_repos = [repo for repo in repos if not repo.get("fork")]

    stars_total = sum(int(repo.get("stargazers_count", 0)) for repo in own_repos)
    repos_total = int(user_payload.get("public_repos", 0))
    followers_total = int(user_payload.get("followers", 0))
    prs_total = fetch_search_total("issues", f"author:{username} type:pr", token)
    commits_total = fetch_current_year_commits(
        username,
        token,
        year=year,
        stats_endpoint=stats_endpoint,
    )
    contributed_to_total = fetch_repositories_contributed_to(username, token)

    active_year = year if year is not None else dt.date.today().year
    return {
        "stars": float(stars_total),
        "commits": float(commits_total),
        "followers": float(followers_total),
        "repos": float(repos_total),
        "pull_requests": float(prs_total),
        "contributed_to": float(contributed_to_total),
        "commits_year": float(active_year),
    }
