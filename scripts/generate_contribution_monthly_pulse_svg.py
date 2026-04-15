#!/usr/bin/env python3
"""Generate a monthly contribution card with pulse animation."""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Tuple


CARD_WIDTH = 1000
CARD_HEIGHT = 260
CHART_X = 70
CHART_Y = 62
CHART_W = 860
CHART_H = 150


class ContributionsParser(HTMLParser):
    """Extract date and count from GitHub contributions HTML fragment."""

    def __init__(self) -> None:
        super().__init__()
        self.id_to_date: Dict[str, str] = {}
        self.id_to_count: Dict[str, int] = {}
        self._active_tooltip_for: str | None = None
        self._in_tooltip = False
        self._tooltip_chunks: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "td":
            klass = attr.get("class", "")
            date = attr.get("data-date")
            cell_id = attr.get("id")
            if klass and "ContributionCalendar-day" in klass and date and cell_id:
                self.id_to_date[cell_id] = date

        if tag == "tool-tip":
            self._in_tooltip = True
            self._active_tooltip_for = attr.get("for")
            self._tooltip_chunks = []

    def handle_data(self, data: str) -> None:
        if self._in_tooltip:
            self._tooltip_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "tool-tip":
            return

        text = " ".join(part.strip() for part in self._tooltip_chunks if part.strip())
        text = re.sub(r"\s+", " ", text)
        count = 0
        match = re.search(r"(\d+)\s+contribution", text)
        if match:
            count = int(match.group(1))

        if self._active_tooltip_for:
            self.id_to_count[self._active_tooltip_for] = count

        self._active_tooltip_for = None
        self._in_tooltip = False
        self._tooltip_chunks = []


def fetch_year_html(username: str, year: int) -> str:
    url = (
        f"https://github.com/users/{username}/contributions"
        f"?from={year}-01-01&to={year}-12-31"
    )
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "profile-contribution-monthly-generator",
            "Accept": "text/html",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub returned {err.code} for {url}: {detail[:300]}") from err
    except urllib.error.URLError as err:
        raise RuntimeError(f"Network error while fetching {url}: {err}") from err


def parse_daily_contributions(html_text: str) -> Dict[str, int]:
    parser = ContributionsParser()
    parser.feed(html_text)
    contributions: Dict[str, int] = {}
    for cell_id, date_str in parser.id_to_date.items():
        contributions[date_str] = parser.id_to_count.get(cell_id, 0)
    return contributions


def last_12_months(today: dt.date) -> List[Tuple[int, int]]:
    result: List[Tuple[int, int]] = []
    year = today.year
    month = today.month
    for offset in range(11, -1, -1):
        m = month - offset
        y = year
        while m <= 0:
            m += 12
            y -= 1
        result.append((y, m))
    return result


def monthly_series(daily: Dict[str, int], months: List[Tuple[int, int]]) -> List[Tuple[str, int]]:
    series: List[Tuple[str, int]] = []
    for year, month in months:
        prefix = f"{year:04d}-{month:02d}-"
        total = sum(value for date_str, value in daily.items() if date_str.startswith(prefix))
        label = calendar.month_abbr[month].upper()
        series.append((label, total))
    return series


def build_path(points: List[Tuple[float, float]]) -> str:
    first = points[0]
    segments = [f"M {first[0]:.2f} {first[1]:.2f}"]
    for x, y in points[1:]:
        segments.append(f"L {x:.2f} {y:.2f}")
    return " ".join(segments)


def render_svg(series: List[Tuple[str, int]], username: str, generated_at: dt.datetime) -> str:
    values = [value for _, value in series]
    max_value = max(values) if values else 0
    total_value = sum(values)
    peak_label = f"{max_value}"

    points: List[Tuple[float, float]] = []
    for idx, (_, value) in enumerate(series):
        x = CHART_X + (CHART_W * idx / max(1, len(series) - 1))
        if max_value <= 0:
            normalized = 0.0
        else:
            normalized = value / max_value
        y = CHART_Y + CHART_H - (normalized * CHART_H)
        points.append((x, y))

    line_path = build_path(points)
    area_path = (
        f"{line_path} "
        f"L {points[-1][0]:.2f} {CHART_Y + CHART_H:.2f} "
        f"L {points[0][0]:.2f} {CHART_Y + CHART_H:.2f} Z"
    )

    x_labels: List[str] = []
    for idx, (label, _) in enumerate(series):
        x = CHART_X + (CHART_W * idx / max(1, len(series) - 1))
        x_labels.append(
            f'<text x="{x:.2f}" y="{CHART_Y + CHART_H + 24}" '
            f'font-family="\'Share Tech Mono\', \'Segoe UI\', sans-serif" '
            f'font-size="11" fill="#00CFFF" text-anchor="middle">{label}</text>'
        )

    y_lines: List[str] = []
    for step in range(0, 5):
        y = CHART_Y + (CHART_H * step / 4)
        y_lines.append(
            f'<line x1="{CHART_X}" y1="{y:.2f}" x2="{CHART_X + CHART_W}" y2="{y:.2f}" '
            'stroke="#113446" stroke-width="1" stroke-dasharray="3 6" opacity="0.7" />'
        )

    pulse_dot = f"""
  <circle r="4.5" fill="#FF6633">
    <animateMotion dur="2.4s" repeatCount="indefinite" rotate="auto">
      <mpath href="#pulsePath" />
    </animateMotion>
  </circle>
"""

    labels = "\n  ".join(x_labels)
    grid = "\n  ".join(y_lines)
    generated_text = generated_at.strftime("%Y-%m-%d %H:%M UTC")

    return f"""<svg width="{CARD_WIDTH}" height="{CARD_HEIGHT}" viewBox="0 0 {CARD_WIDTH} {CARD_HEIGHT}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bgGradient" x1="0" y1="0" x2="{CARD_WIDTH}" y2="{CARD_HEIGHT}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#0A111B" />
      <stop offset="1" stop-color="#120A16" />
    </linearGradient>
    <linearGradient id="areaGradient" x1="0" y1="{CHART_Y}" x2="0" y2="{CHART_Y + CHART_H}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#FF003C" stop-opacity="0.45" />
      <stop offset="1" stop-color="#FF003C" stop-opacity="0.03" />
    </linearGradient>
    <filter id="neonGlow" x="-20%" y="-30%" width="140%" height="160%">
      <feDropShadow dx="0" dy="0" stdDeviation="2.2" flood-color="#FF003C" flood-opacity="0.75" />
      <feDropShadow dx="0" dy="0" stdDeviation="5.5" flood-color="#00CFFF" flood-opacity="0.2" />
    </filter>
  </defs>

  <rect x="0.5" y="0.5" width="{CARD_WIDTH - 1}" height="{CARD_HEIGHT - 1}" rx="10" fill="url(#bgGradient)" stroke="#1A2C3D" />

  <text x="32" y="36" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="22" font-weight="700" fill="#00CFFF">
    CONTRIBUTION GRID (MONTHLY)
  </text>
  <text x="{CARD_WIDTH - 32}" y="36" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="12" fill="#FF6633" text-anchor="end">
    12M TOTAL: {total_value}
  </text>

  {grid}

  <path d="{area_path}" fill="url(#areaGradient)" />

  <path id="pulsePath" d="{line_path}" fill="none" stroke="#FF003C" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round" filter="url(#neonGlow)">
    <animate attributeName="stroke-width" values="2.8;4.2;2.8" dur="1.15s" repeatCount="indefinite" />
    <animate attributeName="opacity" values="0.92;1;0.92" dur="1.15s" repeatCount="indefinite" />
  </path>

  <path d="{line_path}" fill="none" stroke="#00CFFF" stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round" opacity="0.55" />

  {pulse_dot}

  {labels}

  <text x="32" y="{CARD_HEIGHT - 14}" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="10" fill="#5CA1B8">
    PEAK MONTH: {peak_label} | USER: {username}
  </text>
  <text x="{CARD_WIDTH - 32}" y="{CARD_HEIGHT - 14}" font-family="'Share Tech Mono', 'Segoe UI', sans-serif" font-size="10" fill="#5CA1B8" text-anchor="end">
    UPDATED: {generated_text}
  </text>
</svg>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate monthly contribution pulse SVG.")
    parser.add_argument("--username", required=True, help="GitHub username")
    parser.add_argument(
        "--output",
        default="assets/contribution-monthly-pulse.svg",
        help="Output SVG path",
    )
    args = parser.parse_args()

    today = dt.date.today()
    years = {today.year, today.year - 1}
    daily: Dict[str, int] = {}
    for year in sorted(years):
        html_text = fetch_year_html(args.username, year)
        daily.update(parse_daily_contributions(html_text))

    months = last_12_months(today)
    series = monthly_series(daily, months)
    now_utc = dt.datetime.now(dt.UTC)
    svg = render_svg(series, username=args.username, generated_at=now_utc)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")
    print(f"Generated {out_path} for {args.username}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
