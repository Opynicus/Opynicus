#!/usr/bin/env python3
"""Generate a public card from WakaTime's private daily summaries."""

import base64
from collections import defaultdict
from datetime import datetime, timedelta
from html import escape
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


OUTPUT = Path(__file__).resolve().parents[1] / "assets" / "wakatime.svg"
HIDDEN = {"yaml", "starlark", "vhdl", "html", "css"}


def duration(seconds):
    minutes = int(seconds) // 60
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours} hr{'s' if hours != 1 else ''} {minutes} min{'s' if minutes != 1 else ''}"
    return f"{minutes} min{'s' if minutes != 1 else ''}"


def fetch():
    token = os.environ.get("WAKATIME_TOKEN")
    if not token:
        raise ValueError("WAKATIME_TOKEN is required")
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    query = urlencode({"start": (today - timedelta(days=6)).isoformat(), "end": today.isoformat(),
                       "timezone": "Asia/Shanghai"})
    authorization = base64.b64encode(token.encode()).decode("ascii")
    request = Request("https://wakatime.com/api/v1/users/current/summaries?" + query,
                      headers={"Authorization": "Basic " + authorization, "User-Agent": "Opynicus-profile-stats"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def render(summary):
    total = summary["cumulative_total"]["seconds"]
    if not isinstance(total, (int, float)) or total < 0:
        raise ValueError("Invalid total")
    languages = defaultdict(float)
    days = summary["data"]
    if len(days) != 7:
        raise ValueError("Expected seven daily summaries")
    for day in days:
        for language in day["languages"]:
            seconds = language["total_seconds"]
            if not isinstance(seconds, (int, float)) or seconds < 0:
                raise ValueError("Invalid language duration")
            languages[language["name"]] += seconds
    visible = sorted(((name, seconds) for name, seconds in languages.items()
                      if name.casefold() not in HIDDEN and seconds > 0),
                     key=lambda item: (-item[1], item[0]))[:5]
    height = 90 + max(len(visible), 1) * 28
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="495" height="{height}" viewBox="0 0 495 {height}" role="img" aria-labelledby="title">',
             '<title id="title">WakaTime activity over the last 7 days</title>',
             f'<rect width="495" height="{height}" rx="5" fill="#2e3440"/>',
             '<g font-family="Arial, sans-serif" font-size="14" fill="#d8dee9">',
             '<text x="25" y="31" font-size="17" font-weight="bold" fill="#88a8c6">WakaTime Stats (last 7 days)</text>',
             f'<text x="25" y="57">Total: {duration(total)}</text>',
             f'<text x="250" y="57" font-size="11">{escape(days[0]["range"]["date"])} – {escape(days[-1]["range"]["date"])}</text>']
    for i, (name, seconds) in enumerate(visible):
        y = 85 + i * 28
        width = min(200, max(0, 200 * seconds / total)) if total else 0
        parts.extend([f'<text x="25" y="{y}">{escape(name)}</text>',
                      f'<rect x="145" y="{y - 9}" width="200" height="8" rx="4" fill="#4c566a"/>',
                      f'<rect x="145" y="{y - 9}" width="{width:.2f}" height="8" rx="4" fill="#88a8c6"/>',
                      f'<text x="360" y="{y}">{duration(seconds)}</text>'])
    if not visible:
        parts.append('<text x="25" y="85">No activity recorded</text>')
    parts.append('</g></svg>')
    return "\n".join(parts) + "\n"


def main():
    try:
        summary = fetch()
        card = render(summary)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(card, encoding="utf-8")
    except HTTPError as exc:
        print(f"Could not update WakaTime card: HTTP {exc.code}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Could not update WakaTime card: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
