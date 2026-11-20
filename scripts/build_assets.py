#!/usr/bin/env python3
"""Generate the profile README artwork from live GitHub data.

    GITHUB_TOKEN=$(gh auth token) python3 scripts/build_assets.py

Writes every image twice (-dark.svg and -light.svg) into assets/. The daily
workflow in .github/workflows/update.yml runs this and commits what changed.
Colors are the bahrul.me tokens: warm near-black and off-white, the site red
for activity, green for the availability dot. Standard library only.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import urllib.request
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

LOGIN = os.environ.get("PROFILE_LOGIN", "bahrulbangsawan")
OUT = Path(__file__).resolve().parent.parent / "assets"

SANS = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
MONO = "'Geist Mono', ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Monaco, Consolas, 'Liberation Mono', monospace"

THEMES = {
    "dark": {
        "bg": "#121212",
        "panel": "#1e1e1d",
        "cell": "#262624",
        "border": "#2e2e2d",
        "text": "#faf9f6",
        "muted": "#b4b4b2",
        "faint": "#8e8e8c",
        "red": "#ff6467",
        "green": "#22c55e",
    },
    "light": {
        "bg": "#faf9f6",
        "panel": "#ffffff",
        "cell": "#e9e8e4",
        "border": "#dedcd8",
        "text": "#1e1e1d",
        "muted": "#5e5d5a",
        "faint": "#6f6e6b",
        "red": "#c10007",
        "green": "#15803d",
    },
}

CARDS = [
    {
        "file": "card-sawit",
        "kind": "RUST · MACOS APP",
        "title": "Sawit",
        "lines": ["Postgres, an editor and a terminal in one native", "macOS app, without Docker."],
        "repo": "sawit.dev",
    },
    {
        "file": "card-claude-pool",
        "kind": "SWIFT · MENU BAR APP",
        "title": "Claude Pool",
        "lines": ["Switch between Claude Code accounts and see", "every account's usage limits at a glance."],
        "repo": "claude-pool",
    },
    {
        "file": "card-content-studio",
        "kind": "CLAUDE CODE SKILL",
        "title": "Content Studio",
        "lines": ["A Claude skill and CLI that builds educational", "Instagram carousels and Reels."],
        "repo": "content-studio",
    },
    {
        "file": "card-manujujaya-mcp",
        "kind": "CLOUDFLARE WORKERS · MCP",
        "title": "Manuju Jaya MCP",
        "lines": ["A remote MCP server that gives AI assistants", "read-only access to live Qasir POS data."],
        "repo": "manujujaya-mcp",
    },
]

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel weekday } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes { languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } } }
    }
  }
}
"""

LEVELS = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}
LEVEL_ALPHA = [0, 0.30, 0.50, 0.75, 1.0]  # the ramp bahrul.me uses on its red


# ---------------------------------------------------------------- data


def fetch() -> dict:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("Set GITHUB_TOKEN (locally: GITHUB_TOKEN=$(gh auth token)).")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-readme"},
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        body = json.load(res)
    if body.get("errors"):
        raise SystemExit(f"GitHub API error: {body['errors']}")
    return body["data"]["user"]


def summarize(user: dict) -> dict:
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = [
        [
            {
                "date": dt.date.fromisoformat(d["date"]),
                "count": d["contributionCount"],
                "level": LEVELS[d["contributionLevel"]],
                "weekday": d["weekday"],
            }
            for d in w["contributionDays"]
        ]
        for w in cal["weeks"]
    ]
    days = [d for w in weeks for d in w]

    longest = run = 0
    for d in days:
        run = run + 1 if d["count"] else 0
        longest = max(longest, run)
    # A day that has not seen a commit yet does not break the streak.
    tail = days[:-1] if days and not days[-1]["count"] else days
    current = 0
    for d in reversed(tail):
        if not d["count"]:
            break
        current += 1

    langs: Counter = Counter()
    for repo in user["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            langs[edge["node"]["name"]] += edge["size"]
    total_bytes = sum(langs.values()) or 1
    top = [(name, size / total_bytes * 100) for name, size in langs.most_common(5)]
    other = 100 - sum(p for _, p in top)
    if other >= 0.05:
        top.append(("Other", other))

    return {
        "total": cal["totalContributions"],
        "weeks": weeks,
        "days": days,
        "current": current,
        "longest": longest,
        "active": sum(1 for d in days if d["count"]),
        "best": max(days, key=lambda d: d["count"]),
        "languages": top,
        "public_repos": user["repositories"]["totalCount"],
    }


# ---------------------------------------------------------------- helpers


def mix(base: str, top: str, alpha: float) -> str:
    b = [int(base[i : i + 2], 16) for i in (1, 3, 5)]
    t = [int(top[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(b[i] + (t[i] - b[i]) * alpha):02x}" for i in range(3))


def num(n: int) -> str:
    return f"{n:,}"


def svg(w: int, h: int, title: str, desc: str, body: str, extra_css: str = "") -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-labelledby="t d">
  <title id="t">{escape(title)}</title>
  <desc id="d">{escape(desc)}</desc>
  <style>
    .sans {{ font-family: {SANS}; }}
    .mono {{ font-family: {MONO}; }}
    .num {{ font-variant-numeric: tabular-nums; }}
    .fu {{ animation: fu .7s cubic-bezier(.2,.7,.2,1) both; }}
    .pulse {{ animation: pulse 2.4s ease-in-out infinite; }}
    @keyframes fu {{ from {{ opacity: 0; transform: translateY(10px); }} }}
    @keyframes pulse {{ 50% {{ opacity: .35; }} }}
    {extra_css}
    @media (prefers-reduced-motion: reduce) {{
      * {{ animation: none !important; }}
      .cover {{ display: none; }}
    }}
  </style>
{body}
</svg>
"""


def frame(t: dict, w: int, h: int, r: int = 18) -> str:
    return (
        f'  <rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="{r}" '
        f'fill="{t["bg"]}" stroke="{t["border"]}"/>'
    )


def eyebrow(t: dict, x: int, y: int, label: str, size: int = 14) -> str:
    return (
        f'  <circle class="pulse" cx="{x + 4}" cy="{y - size * 0.34:.1f}" r="4" fill="{t["red"]}"/>\n'
        f'  <text x="{x + 18}" y="{y}" class="mono" font-size="{size}" font-weight="600" '
        f'letter-spacing="{size * 0.16:.1f}" fill="{t["red"]}">{escape(label)}</text>'
    )


# ---------------------------------------------------------------- hero


def hero(t: dict) -> str:
    w, h = 1280, 420
    tx, ty, tw, th = 772, 84, 444, 244
    lx = tx + 26
    char = 10.25
    rows = [
        ("cmd", "whoami"),
        ("out", "bahrul, gtm engineer"),
        ("cmd", "ls building/"),
        ("out", "sawit  claude-pool  content-studio"),
        ("cmd", "open bahrul.me"),
    ]
    css, lines, covers = [], [], []
    clock = 0.9
    y = ty + 84
    for i, (kind, text) in enumerate(rows):
        if kind == "cmd":
            lines.append(
                f'    <text x="{lx}" y="{y}" class="mono" font-size="17">'
                f'<tspan fill="{t["red"]}">$</tspan><tspan fill="{t["text"]}" dx="10">{escape(text)}</tspan></text>'
            )
            dist = len(text) * char + 14
            dur = len(text) * 0.055
            css.append(
                f".c{i} {{ animation: t{i} {dur:.2f}s steps({len(text)}) {clock:.2f}s both, "
                f"gone .01s linear {clock + dur:.2f}s forwards; }}"
                f" @keyframes t{i} {{ to {{ transform: translateX({dist:.0f}px); }} }}"
            )
            # The prompt itself appears just before its command is typed.
            css.append(f".p{i} {{ animation: gone .01s linear {clock - 0.25:.2f}s forwards; }}")
            covers.append(f'    <rect class="cover p{i}" x="{lx - 4}" y="{y - 19}" width="24" height="27" fill="{t["panel"]}"/>')
            covers.append(
                f'    <rect class="cover c{i}" x="{lx + 18}" y="{y - 19}" width="{tw - 46}" height="27" fill="{t["panel"]}"/>'
            )
            clock += dur + 0.3
            cursor_x = lx + 20.5 + len(text) * char + 7
            cursor_y = y - 15
        else:
            lines.append(f'    <text x="{lx}" y="{y}" class="mono" font-size="17" fill="{t["muted"]}">{escape(text)}</text>')
            css.append(f".c{i} {{ animation: gone .01s linear {clock:.2f}s forwards; }}")
            covers.append(f'    <rect class="cover c{i}" x="{lx - 4}" y="{y - 19}" width="{tw - 24}" height="27" fill="{t["panel"]}"/>')
            clock += 0.45
        y += 32
    css.append("@keyframes gone { to { opacity: 0; } }")
    css.append(f".cursor {{ opacity: 0; animation: blink 1.1s steps(1) {clock - 0.3:.2f}s infinite; }}")
    css.append("@keyframes blink { 0% { opacity: 1; } 50% { opacity: 0; } }")
    css.append("@media (prefers-reduced-motion: reduce) { .cursor { opacity: 1; } }")

    body = f"""{frame(t, w, h, 20)}
{eyebrow(t, 64, 96, "BAHRUL.ME", 15)}
  <text x="61" y="206" class="sans fu" style="animation-delay:.05s" font-size="74" font-weight="700" letter-spacing="-2.6" fill="{t["text"]}">Bahrul Bangsawan</text>
  <text x="64" y="258" class="sans fu" style="animation-delay:.18s" font-size="27" font-weight="500" letter-spacing="-0.4" fill="{t["text"]}">I help businesses get more customers.</text>
  <text x="64" y="294" class="sans fu" style="animation-delay:.28s" font-size="21" fill="{t["muted"]}">Websites, marketing automation, and data that shows</text>
  <text x="64" y="322" class="sans fu" style="animation-delay:.28s" font-size="21" fill="{t["muted"]}">what works.</text>
  <line x1="64" y1="356" x2="{w - 64}" y2="356" stroke="{t["border"]}"/>
  <circle class="pulse" cx="70" cy="383" r="5" fill="{t["green"]}"/>
  <text x="86" y="388" class="sans" font-size="16" fill="{t["muted"]}">Available for new work</text>
  <text x="{w - 64}" y="388" class="sans" font-size="16" text-anchor="end" fill="{t["faint"]}">GTM Engineer · Indonesia</text>

  <rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="12" fill="{t["panel"]}" stroke="{t["border"]}"/>
  <circle cx="{tx + 24}" cy="{ty + 24}" r="5.5" fill="{t["border"]}"/>
  <circle cx="{tx + 44}" cy="{ty + 24}" r="5.5" fill="{t["border"]}"/>
  <circle cx="{tx + 64}" cy="{ty + 24}" r="5.5" fill="{t["border"]}"/>
  <text x="{tx + tw / 2}" y="{ty + 29}" class="mono" font-size="13" text-anchor="middle" fill="{t["faint"]}">~/bahrul</text>
  <line x1="{tx}" y1="{ty + 48}" x2="{tx + tw}" y2="{ty + 48}" stroke="{t["border"]}"/>
  <g>
{chr(10).join(lines)}
{chr(10).join(covers)}
    <rect class="cursor" x="{cursor_x:.1f}" y="{cursor_y}" width="9" height="19" fill="{t["red"]}"/>
  </g>"""
    return svg(
        w,
        h,
        "Bahrul Bangsawan, GTM Engineer",
        "I help businesses get more customers: websites, marketing automation, and data that shows what works. Available for new work.",
        body,
        "\n    ".join(css),
    )


# ---------------------------------------------------------------- stats


def stats(t: dict, s: dict) -> str:
    w, h, gap = 1280, 176, 16
    tile_w = (w - gap * 3) / 4
    best = s["best"]
    tiles = [
        ("CONTRIBUTIONS", num(s["total"]), "in the last 12 months"),
        ("CURRENT STREAK", num(s["current"]), "days in a row" if s["current"] != 1 else "day"),
        ("LONGEST STREAK", num(s["longest"]), "days in a row" if s["longest"] != 1 else "day"),
        ("BUSIEST DAY", num(best["count"]), f'on {best["date"].strftime("%b")} {best["date"].day}, {best["date"].year}'),
    ]
    parts = []
    for i, (label, value, sub) in enumerate(tiles):
        x = i * (tile_w + gap)
        parts.append(
            f"""  <g class="fu" style="animation-delay:{i * 0.09:.2f}s">
    <rect x="{x + 0.5:.1f}" y="0.5" width="{tile_w - 1:.1f}" height="{h - 1}" rx="16" fill="{t["bg"]}" stroke="{t["border"]}"/>
    <text x="{x + 28:.1f}" y="46" class="mono" font-size="13" font-weight="600" letter-spacing="2.1" fill="{t["faint"]}">{label}</text>
    <text x="{x + 26:.1f}" y="112" class="sans num" font-size="58" font-weight="700" letter-spacing="-2" fill="{t["text"]}">{value}</text>
    <text x="{x + 28:.1f}" y="146" class="sans" font-size="17" fill="{t["muted"]}">{escape(sub)}</text>
  </g>"""
        )
    desc = "; ".join(f"{label.title()}: {value} {sub}" for label, value, sub in tiles)
    return svg(w, h, "GitHub activity in numbers", desc, "\n".join(parts))


# ---------------------------------------------------------------- heatmap


def heatmap(t: dict, s: dict) -> str:
    w, h = 1280, 330
    cell, pitch = 17, 21
    weeks = s["weeks"]
    gx = (w - (46 + len(weeks) * pitch - (pitch - cell))) / 2 + 46
    gy = 118
    fills = [mix(t["cell"], t["red"], a) for a in LEVEL_ALPHA]

    cols, months, last_label = [], [], -9
    prev_month = None
    for i, week in enumerate(weeks):
        x = gx + i * pitch
        month = week[0]["date"].month
        if month != prev_month and i - last_label >= 3 and i <= len(weeks) - 2:
            if prev_month is not None or week[0]["date"].day <= 7:
                months.append(
                    f'  <text x="{x:.1f}" y="{gy - 12}" class="sans" font-size="14" fill="{t["faint"]}">'
                    f'{week[0]["date"].strftime("%b")}</text>'
                )
                last_label = i
        prev_month = month
        rects = "".join(
            f'<rect x="{x:.1f}" y="{gy + d["weekday"] * pitch}" width="{cell}" height="{cell}" rx="4" fill="{fills[d["level"]]}"/>'
            for d in week
        )
        cols.append(f'  <g class="wk" style="animation-delay:{0.15 + i * 0.016:.3f}s">{rects}</g>')

    day_labels = "\n".join(
        f'  <text x="{gx - 12:.1f}" y="{gy + row * pitch + 13}" class="sans" font-size="13" text-anchor="end" fill="{t["faint"]}">{name}</text>'
        for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri"))
    )
    right = gx + len(weeks) * pitch - (pitch - cell)
    ly = gy + 7 * pitch + 22
    more_w = 44
    start = right - more_w - 5 * 22
    legend = [f'  <text x="{start - 8:.1f}" y="{ly + 13}" class="sans" font-size="13" text-anchor="end" fill="{t["faint"]}">Less</text>']
    for i, fill in enumerate(fills):
        legend.append(f'  <rect x="{start + i * 22:.1f}" y="{ly}" width="{cell}" height="{cell}" rx="4" fill="{fill}"/>')
    legend.append(f'  <text x="{right:.1f}" y="{ly + 13}" class="sans" font-size="13" text-anchor="end" fill="{t["faint"]}">More</text>')

    left = gx - 46
    body = f"""{frame(t, w, h)}
{eyebrow(t, round(left), 62, "CONTRIBUTIONS")}
  <text x="{right:.1f}" y="62" class="sans num" font-size="17" text-anchor="end" fill="{t["muted"]}"><tspan font-weight="700" fill="{t["text"]}">{num(s["total"])}</tspan> in the last year · <tspan font-weight="700" fill="{t["text"]}">{num(s["active"])}</tspan> active days</text>
{chr(10).join(months)}
{day_labels}
{chr(10).join(cols)}
  <text x="{left:.1f}" y="{ly + 13}" class="sans" font-size="13" fill="{t["faint"]}">Public and private work, updated daily</text>
{chr(10).join(legend)}"""
    css = ".wk { animation: wk .5s cubic-bezier(.2,.7,.2,1) both; } @keyframes wk { from { opacity: 0; transform: translateY(6px); } }"
    return svg(
        w,
        h,
        "GitHub contribution calendar",
        f'{num(s["total"])} contributions in the last year across {num(s["active"])} active days.',
        body,
        css,
    )


# ---------------------------------------------------------------- weekly line


def weekly(t: dict, s: dict) -> str:
    w, h = 620, 320
    totals = [sum(d["count"] for d in wk) for wk in s["weeks"]]
    x0, x1, y0, y1 = 36, w - 36, 118, 250
    top = max(totals) or 1
    pts = [
        (x0 + i * (x1 - x0) / (len(totals) - 1), y1 - v / top * (y1 - y0))
        for i, v in enumerate(totals)
    ]
    line = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{line} L{x1},{y1} L{x0},{y1} Z"
    pi = totals.index(top)
    px, py = pts[pi]
    anchor = "end" if px > w - 150 else "start" if px < 150 else "middle"
    lx = px - 12 if anchor == "end" else px + 12 if anchor == "start" else px
    label_y = py - 14 if anchor == "middle" else py + 5
    wk_start = s["weeks"][pi][0]["date"]
    avg = round(sum(totals) / len(totals))
    first, last = s["days"][0]["date"], s["days"][-1]["date"]
    body = f"""{frame(t, w, h, 16)}
  <defs>
    <linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{t["red"]}" stop-opacity=".30"/>
      <stop offset="1" stop-color="{t["red"]}" stop-opacity="0"/>
    </linearGradient>
  </defs>
{eyebrow(t, 36, 54, "WEEKLY ACTIVITY", 13)}
  <text x="{w - 36}" y="54" class="sans num" font-size="15" text-anchor="end" fill="{t["muted"]}"><tspan font-weight="700" fill="{t["text"]}">{num(avg)}</tspan> a week on average</text>
  <path class="area" d="{area}" fill="url(#fade)"/>
  <line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="{t["border"]}"/>
  <path class="line" d="{line}" pathLength="1" fill="none" stroke="{t["red"]}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
  <g class="peak">
    <circle cx="{px:.1f}" cy="{py:.1f}" r="6.5" fill="{t["bg"]}"/>
    <circle cx="{px:.1f}" cy="{py:.1f}" r="4.5" fill="{t["red"]}"/>
    <text x="{lx:.1f}" y="{label_y:.1f}" class="sans num" font-size="14" text-anchor="{anchor}" fill="{t["muted"]}"><tspan font-weight="700" fill="{t["text"]}">{num(top)}</tspan> in the week of {wk_start.strftime("%b")} {wk_start.day}</text>
  </g>
  <text x="{x0}" y="{y1 + 26}" class="sans" font-size="13" fill="{t["faint"]}">{first.strftime("%b %Y")}</text>
  <text x="{x1}" y="{y1 + 26}" class="sans" font-size="13" text-anchor="end" fill="{t["faint"]}">{last.strftime("%b %Y")}</text>"""
    css = (
        ".line { stroke-dasharray: 1; stroke-dashoffset: 1; animation: draw 1.8s cubic-bezier(.4,0,.2,1) .2s forwards; }"
        " .area { animation: show .9s ease 1.3s both; } .peak { animation: show .5s ease 1.9s both; }"
        " @keyframes draw { to { stroke-dashoffset: 0; } } @keyframes show { from { opacity: 0; } }"
        " @media (prefers-reduced-motion: reduce) { .line { stroke-dashoffset: 0; } }"
    )
    return svg(
        w,
        h,
        "Contributions per week over the last year",
        f'{num(avg)} contributions a week on average; the busiest week had {num(top)}, starting {wk_start.strftime("%b")} {wk_start.day}, {wk_start.year}.',
        body,
        css,
    )


# ---------------------------------------------------------------- languages


def languages(t: dict, s: dict) -> str:
    w, h = 620, 320
    langs = s["languages"]
    bx, bmax = 168, 330
    widest = max(p for _, p in langs) or 1
    rows = []
    for i, (name, pct) in enumerate(langs):
        y = 104 + i * 33
        bw = max(6, pct / widest * bmax)
        shown = f"{pct:.1f}%" if pct >= 0.1 else "<0.1%"
        fill = t["faint"] if name == "Other" else t["text"]
        rows.append(
            f"""  <text x="36" y="{y + 5}" class="sans" font-size="16" fill="{t["text"]}">{escape(name)}</text>
  <rect class="bar" style="animation-delay:{0.2 + i * 0.08:.2f}s" x="{bx}" y="{y - 5}" width="{bw:.1f}" height="10" rx="5" fill="{fill}"/>
  <text x="{w - 36}" y="{y + 5}" class="sans num" font-size="15" text-anchor="end" fill="{t["muted"]}">{shown}</text>"""
        )
    repos = s["public_repos"]
    body = f"""{frame(t, w, h, 16)}
{eyebrow(t, 36, 54, "LANGUAGES", 13)}
  <text x="{w - 36}" y="54" class="sans num" font-size="15" text-anchor="end" fill="{t["muted"]}">by code size in <tspan font-weight="700" fill="{t["text"]}">{repos}</tspan> public repos</text>
{chr(10).join(rows)}"""
    css = (
        ".bar { transform-box: fill-box; transform-origin: left center; animation: grow .9s cubic-bezier(.2,.7,.2,1) both; }"
        " @keyframes grow { from { transform: scaleX(0); } }"
    )
    desc = ", ".join(f"{name} {pct:.1f}%" for name, pct in langs)
    return svg(w, h, "Languages across public repositories", desc, body, css)


# ---------------------------------------------------------------- cards


def card(t: dict, c: dict) -> str:
    w, h = 620, 256
    desc = "\n".join(
        f'  <text x="36" y="{146 + i * 28}" class="sans" font-size="19" fill="{t["muted"]}">{escape(line)}</text>'
        for i, line in enumerate(c["lines"])
    )
    body = f"""{frame(t, w, h, 16)}
{eyebrow(t, 36, 54, c["kind"], 13)}
  <text x="35" y="108" class="sans" font-size="36" font-weight="700" letter-spacing="-1.1" fill="{t["text"]}">{escape(c["title"])}</text>
{desc}
  <line x1="36" y1="204" x2="{w - 36}" y2="204" stroke="{t["border"]}"/>
  <text x="36" y="231" class="mono" font-size="13" fill="{t["faint"]}">{LOGIN}/{escape(c["repo"])}</text>
  <text x="{w - 36}" y="231" class="sans" font-size="14" font-weight="600" text-anchor="end" fill="{t["text"]}">View repo →</text>"""
    return svg(w, h, c["title"], " ".join(c["lines"]), body)


# ---------------------------------------------------------------- main


def main() -> None:
    s = summarize(fetch())
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.svg"):
        stale.unlink(missing_ok=True)
    count = 0
    for name, t in THEMES.items():
        files = {
            "hero": hero(t),
            "stats": stats(t, s),
            "contributions": heatmap(t, s),
            "weekly": weekly(t, s),
            "languages": languages(t, s),
            **{c["file"]: card(t, c) for c in CARDS},
        }
        for stem, content in files.items():
            (OUT / f"{stem}-{name}.svg").write_text(content, encoding="utf-8")
            count += 1
    print(
        f"Wrote {count} files. {num(s['total'])} contributions, streak {s['current']} "
        f"(longest {s['longest']}), {s['active']} active days."
    )


if __name__ == "__main__":
    main()
