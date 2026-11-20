#!/usr/bin/env python3
"""Generate the profile README artwork from live data.

    GITHUB_TOKEN=$(gh auth token) python3 scripts/build_assets.py

Every number comes from an API at build time:
  * GitHub GraphQL: contributions, streaks, languages, stars.
  * bahrul.me/api/v1: projects, clients, case studies, experience, tech stack,
    availability. The last good answer is kept in scripts/site-cache.json and
    used when the site cannot be reached.

Each image is written twice (-dark.svg and -light.svg) into assets/. The
workflow in .github/workflows/update.yml runs this daily and commits changes.
Colors are the bahrul.me tokens. Standard library only.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import urllib.request
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

LOGIN = os.environ.get("PROFILE_LOGIN", "bahrulbangsawan")
SITE = "https://bahrul.me"
ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "assets"
CACHE = ROOT / "site-cache.json"
HISTORY = ROOT / "history.json"
ICONS: dict[str, str] = json.loads((ROOT / "icons.json").read_text())

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

# Link buttons under the banner: (file, label, icon, primary)
LINKS = [
    ("link-site", "bahrul.me", "globe", False),
    ("link-book", "Book a call", "calendar", True),
    ("link-email", "Email", "mail", False),
    ("link-linkedin", "LinkedIn", "linkedin", False),
    ("link-x", "X", "x", False),
    ("link-instagram", "Instagram", "instagram", False),
    ("link-threads", "Threads", "threads", False),
]

# Names that do not reduce to their Simple Icons slug by stripping punctuation.
ICON_ALIASES = {
    "next.js": "nextdotjs",
    "node.js": "nodedotjs",
    "html": "html5",
    "shell": "gnubash",
    "c++": "cplusplus",
    "vue": "vuedotjs",
}

# Hand-drawn 24px stroke icons for the links that are not brands.
STROKE_ICONS = {
    "globe": '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
    "calendar": '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="m3.5 7.5 8.5 6 8.5-6"/>',
}

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
      nodes {
        name
        stargazerCount
        primaryLanguage { name }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } }
      }
    }
  }
}
"""

PRIOR_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}
"""

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
LEVEL_ALPHA = [0, 0.30, 0.50, 0.75, 1.0]  # the ramp bahrul.me uses on its red
LOOP = 20  # seconds; charts replay their entrance on this period


# ---------------------------------------------------------------- data


def get_json(url: str, payload: dict | None = None, token: str | None = None):
    headers = {"User-Agent": "profile-readme", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"bearer {token}"
    data = json.dumps(payload).encode() if payload else None
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=30) as res:
        return json.load(res)


def fetch_github() -> dict:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("Set GITHUB_TOKEN (locally: GITHUB_TOKEN=$(gh auth token)).")
    body = get_json("https://api.github.com/graphql", {"query": QUERY, "variables": {"login": LOGIN}}, token)
    if body.get("errors"):
        raise SystemExit(f"GitHub API error: {body['errors']}")
    user = body["data"]["user"]
    # The 365 days before the current calendar, for the trend markers.
    first = dt.date.fromisoformat(user["contributionsCollection"]["contributionCalendar"]["weeks"][0]["contributionDays"][0]["date"])
    span = {
        "login": LOGIN,
        "from": f"{first - dt.timedelta(days=365)}T00:00:00Z",
        "to": f"{first - dt.timedelta(days=1)}T23:59:59Z",
    }
    prior = get_json("https://api.github.com/graphql", {"query": PRIOR_QUERY, "variables": span}, token)
    if prior.get("errors"):
        raise SystemExit(f"GitHub API error: {prior['errors']}")
    weeks = prior["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    user["priorDays"] = [
        d["contributionCount"]
        for w in weeks
        for d in w["contributionDays"]
        if span["from"][:10] <= d["date"] <= span["to"][:10]
    ]
    return user


def fetch_site() -> dict:
    try:
        profile = get_json(f"{SITE}/api/v1/profile")
        site = {
            "profile": profile,
            "projects": get_json(f"{SITE}/api/v1/projects")["count"],
            "cases": get_json(f"{SITE}/api/v1/cases")["count"],
            "articles": get_json(f"{SITE}/api/v1/articles")["count"],
        }
        CACHE.write_text(json.dumps(site, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        return {**site, "fresh": True}
    except Exception as err:  # the site being down must not break the profile
        print(f"bahrul.me unreachable ({err}); using scripts/site-cache.json")
        return json.loads(CACHE.read_text(encoding="utf-8"))


WORK_KEYS = ("projects", "clients", "cases", "articles")
BASELINE_DAYS = 30  # compare with the log entry about this old
MIN_BASELINE_DAYS = 7  # and show no trend until the log reaches back this far


def work_baseline(s: dict, fresh: bool) -> dict | None:
    """Record today's work numbers in the running log and return the entry to compare against.

    bahrul.me's API has no history, so the daily build keeps its own: one row per day in
    scripts/history.json. Rows are only written from a live answer, never from the cache.
    """
    log = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []
    today = s["today"].isoformat()
    if fresh:
        log = [row for row in log if row["date"] != today]
        log.append({"date": today, **{k: s[k] for k in WORK_KEYS}})
        log = sorted(log, key=lambda row: row["date"])[-400:]
        HISTORY.write_text(json.dumps(log, indent=0) + "\n", encoding="utf-8")
    old = [row for row in log if (s["today"] - dt.date.fromisoformat(row["date"])).days >= MIN_BASELINE_DAYS]
    if not old:
        return None
    return min(old, key=lambda row: abs((s["today"] - dt.date.fromisoformat(row["date"])).days - BASELINE_DAYS))


def parse_month(text: str, today: dt.date) -> dt.date | None:
    text = text.strip()
    if text.lower() in ("present", "now", "current"):
        return today
    try:
        return dt.datetime.strptime(text, "%b %Y").date()
    except ValueError:
        return None


def summarize(user: dict, site: dict) -> dict:
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
    today = days[-1]["date"]

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

    def longest_run(counts: list[int]) -> int:
        best = cur = 0
        for c in counts:
            cur = cur + 1 if c else 0
            best = max(best, cur)
        return best

    prior = user.get("priorDays") or []
    # The streak before the current one: walk back past it and the gap that ended the earlier one.
    history = prior + [d["count"] for d in tail]
    i = len(history) - 1 - current
    while i >= 0 and not history[i]:
        i -= 1
    previous_streak = 0
    while i >= 0 and history[i]:
        previous_streak += 1
        i -= 1

    by_weekday = [0] * 7  # Monday first
    months: dict[tuple[int, int], int] = {}
    for d in days:
        by_weekday[(d["weekday"] + 6) % 7] += d["count"]
        key = (d["date"].year, d["date"].month)
        months[key] = months.get(key, 0) + d["count"]

    langs: Counter = Counter()
    repos = {}
    for repo in user["repositories"]["nodes"]:
        repos[repo["name"]] = {
            "stars": repo["stargazerCount"],
            "language": (repo["primaryLanguage"] or {}).get("name"),
        }
        for edge in repo["languages"]["edges"]:
            langs[edge["node"]["name"]] += edge["size"]
    total_bytes = sum(langs.values()) or 1
    top = [(name, size / total_bytes * 100) for name, size in langs.most_common(5)]
    other = 100 - sum(p for _, p in top)
    if other >= 0.05:
        top.append(("Other", other))

    profile = site["profile"]
    roles = []
    for e in profile.get("experience", []):
        parts = re.split(r"\s+[–—-]\s+", e.get("period", ""))
        if len(parts) != 2:
            continue
        start, end = parse_month(parts[0], today), parse_month(parts[1], today)
        if not start or not end:
            continue
        roles.append(
            {
                "company": e["company"],
                "start": start,
                "end": end,
                "current": parts[1].strip().lower() in ("present", "now", "current"),
                "since": parts[0].strip(),
            }
        )
    roles.sort(key=lambda r: (not r["current"], -r["start"].toordinal()))

    stack: dict[str, list[str]] = {}
    for tool in profile.get("techStack", []):
        stack.setdefault(tool.get("category") or "Other", []).append(tool["name"])

    loc = profile.get("location") or {}
    return {
        "today": today,
        "total": cal["totalContributions"],
        "weeks": weeks,
        "days": days,
        "current": current,
        "longest": longest,
        "active": sum(1 for d in days if d["count"]),
        "best": max(days, key=lambda d: d["count"]),
        "last365": sum(d["count"] for d in days[-365:]),
        "prior_total": sum(prior),
        "prior_longest": longest_run(prior),
        "prior_best": max(prior, default=0),
        "previous_streak": previous_streak,
        "has_prior": bool(prior),
        "by_weekday": by_weekday,
        "months": months,
        "languages": top,
        "public_repos": user["repositories"]["totalCount"],
        "repos": repos,
        "roles": roles,
        "stack": stack,
        "tools": sum(len(v) for v in stack.values()),
        "projects": site["projects"],
        "cases": site["cases"],
        "articles": site["articles"],
        "clients": len(profile.get("clients", [])),
        "available": bool(profile.get("availableForHire")),
        "title": profile.get("title") or "GTM Engineer",
        "place": ", ".join(x for x in (loc.get("city"), loc.get("country")) if x) or "Indonesia",
    }


# ---------------------------------------------------------------- helpers


def mix(base: str, top: str, alpha: float) -> str:
    b = [int(base[i : i + 2], 16) for i in (1, 3, 5)]
    t = [int(top[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(b[i] + (t[i] - b[i]) * alpha):02x}" for i in range(3))


def num(n: int) -> str:
    return f"{n:,}"


def slug_for(name: str) -> str:
    key = name.strip().lower()
    return ICON_ALIASES.get(key) or re.sub(r"[^a-z0-9]", "", key)


def logo(t: dict, name: str, x: float, y: float, size: float, fill: str | None = None) -> str:
    """A brand logo by name, or a letter tile when we have no logo for it."""
    path = ICONS.get(slug_for(name))
    fill = fill or t["text"]
    if path:
        return f'<path transform="translate({x:.1f} {y:.1f}) scale({size / 24:.4f})" fill="{fill}" d="{path}"/>'
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{size}" height="{size}" rx="{size * 0.25:.1f}" fill="none" stroke="{fill}" stroke-width="1.4"/>'
        f'<text x="{x + size / 2:.1f}" y="{y + size * 0.72:.1f}" class="sans" font-size="{size * 0.6:.1f}" font-weight="700" text-anchor="middle" fill="{fill}">{escape(name[:1].upper())}</text>'
    )


BASE_CSS = f"""
    .sans {{ font-family: {SANS}; }}
    .mono {{ font-family: {MONO}; }}
    .num {{ font-variant-numeric: tabular-nums; }}
    .fu {{ animation: fu .7s cubic-bezier(.2,.7,.2,1) both; }}
    .pulse {{ animation: pulse 2.4s ease-in-out infinite; }}
    .growx, .growy {{ transform-box: fill-box; animation: {LOOP}s cubic-bezier(.2,.7,.2,1) infinite both; }}
    .growx {{ transform-origin: left center; animation-name: growx; }}
    .growy {{ transform-origin: center bottom; animation-name: growy; }}
    @keyframes fu {{ from {{ opacity: 0; transform: translateY(10px); }} }}
    @keyframes pulse {{ 50% {{ opacity: .35; }} }}
    @keyframes growx {{ 0% {{ transform: scaleX(0); opacity: 0; }} 1% {{ opacity: 1; }} 7% {{ transform: scaleX(1); }} 95% {{ transform: scaleX(1); opacity: 1; }} 100% {{ transform: scaleX(1); opacity: 0; }} }}
    @keyframes growy {{ 0% {{ transform: scaleY(0); opacity: 0; }} 1% {{ opacity: 1; }} 7% {{ transform: scaleY(1); }} 95% {{ transform: scaleY(1); opacity: 1; }} 100% {{ transform: scaleY(1); opacity: 0; }} }}
"""


def svg(w: float, h: float, title: str, desc: str, body: str, extra_css: str = "") -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:g} {h:g}" width="{w:g}" height="{h:g}" role="img" aria-labelledby="t d">
  <title id="t">{escape(title)}</title>
  <desc id="d">{escape(desc)}</desc>
  <style>{BASE_CSS}    {extra_css}
    @media (prefers-reduced-motion: reduce) {{
      * {{ animation: none !important; }}
      .cover {{ display: none; }}
    }}
  </style>
{body}
</svg>
"""


def frame(t: dict, w: float, h: float, r: int = 18) -> str:
    return f'  <rect x="0.5" y="0.5" width="{w - 1:g}" height="{h - 1:g}" rx="{r}" fill="{t["bg"]}" stroke="{t["border"]}"/>'


def eyebrow(t: dict, x: float, y: float, label: str, size: int = 14) -> str:
    return (
        f'  <circle class="pulse" cx="{x + 4:.1f}" cy="{y - size * 0.34:.1f}" r="4" fill="{t["red"]}"/>\n'
        f'  <text x="{x + 18:.1f}" y="{y}" class="mono" font-size="{size}" font-weight="600" '
        f'letter-spacing="{size * 0.16:.1f}" fill="{t["red"]}">{escape(label)}</text>'
    )


def note(t: dict, x: float, y: float, parts: list[tuple[str, bool]], size: int = 15, anchor: str = "end") -> str:
    """Header note: plain words in muted ink, the numbers in bold primary ink."""
    spans = "".join(
        f'<tspan font-weight="700" fill="{t["text"]}">{escape(s)}</tspan>' if bold else escape(s) for s, bold in parts
    )
    return f'  <text x="{x:.1f}" y="{y}" class="sans num" font-size="{size}" text-anchor="{anchor}" fill="{t["muted"]}">{spans}</text>'


# ---------------------------------------------------------------- hero


def hero(t: dict, s: dict) -> str:
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
    cursor_x = cursor_y = 0.0
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

    if s["available"]:
        status = (
            f'  <circle class="pulse" cx="70" cy="383" r="5" fill="{t["green"]}"/>\n'
            f'  <text x="86" y="388" class="sans" font-size="16" fill="{t["muted"]}">Available for new work</text>'
        )
    else:
        status = (
            f'  <circle cx="70" cy="383" r="5" fill="{t["faint"]}"/>\n'
            f'  <text x="86" y="388" class="sans" font-size="16" fill="{t["muted"]}">Fully booked right now</text>'
        )

    body = f"""{frame(t, w, h, 20)}
  <defs><clipPath id="term"><rect x="{tx + 1}" y="{ty + 49}" width="{tw - 2}" height="{th - 50}"/></clipPath></defs>
{eyebrow(t, 64, 96, "BAHRUL.ME", 15)}
  <text x="61" y="206" class="sans fu" style="animation-delay:.05s" font-size="74" font-weight="700" letter-spacing="-2.6" fill="{t["text"]}">Bahrul Bangsawan</text>
  <text x="64" y="258" class="sans fu" style="animation-delay:.18s" font-size="27" font-weight="500" letter-spacing="-0.4" fill="{t["text"]}">I help businesses get more customers.</text>
  <text x="64" y="294" class="sans fu" style="animation-delay:.28s" font-size="21" fill="{t["muted"]}">Websites, marketing automation, and data that shows</text>
  <text x="64" y="322" class="sans fu" style="animation-delay:.28s" font-size="21" fill="{t["muted"]}">what works.</text>
  <line x1="64" y1="356" x2="{w - 64}" y2="356" stroke="{t["border"]}"/>
{status}
  <text x="{w - 64}" y="388" class="sans" font-size="16" text-anchor="end" fill="{t["faint"]}">{escape(s["title"])} · {escape(s["place"])}</text>

  <rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="12" fill="{t["panel"]}" stroke="{t["border"]}"/>
  <circle cx="{tx + 24}" cy="{ty + 24}" r="5.5" fill="{t["border"]}"/>
  <circle cx="{tx + 44}" cy="{ty + 24}" r="5.5" fill="{t["border"]}"/>
  <circle cx="{tx + 64}" cy="{ty + 24}" r="5.5" fill="{t["border"]}"/>
  <text x="{tx + tw / 2}" y="{ty + 29}" class="mono" font-size="13" text-anchor="middle" fill="{t["faint"]}">~/bahrul</text>
  <line x1="{tx}" y1="{ty + 48}" x2="{tx + tw}" y2="{ty + 48}" stroke="{t["border"]}"/>
  <g clip-path="url(#term)">
{chr(10).join(lines)}
{chr(10).join(covers)}
    <rect class="cursor" x="{cursor_x:.1f}" y="{cursor_y}" width="9" height="19" fill="{t["red"]}"/>
  </g>"""
    return svg(
        w,
        h,
        "Bahrul Bangsawan, GTM Engineer",
        "I help businesses get more customers: websites, marketing automation, and data that shows what works.",
        body,
        "\n    ".join(css),
    )


# ---------------------------------------------------------------- link buttons


def link_button(t: dict, label: str, icon: str, primary: bool) -> str:
    h = 44
    w = round(16 + 20 + 10 + len(label) * 9.2 + 18)
    fill, ink, stroke = (t["text"], t["bg"], t["text"]) if primary else (t["panel"], t["text"], t["border"])
    if icon in STROKE_ICONS:
        glyph = (
            f'<g transform="translate(16 12) scale({20 / 24:.4f})" fill="none" stroke="{ink}" stroke-width="1.9" '
            f'stroke-linecap="round" stroke-linejoin="round">{STROKE_ICONS[icon]}</g>'
        )
    else:
        glyph = logo(t, icon, 17, 13, 18, ink)
    body = f"""  <rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="10" fill="{fill}" stroke="{stroke}"/>
  {glyph}
  <text x="46" y="27.5" class="sans" font-size="16" font-weight="600" fill="{ink}">{escape(label)}</text>"""
    return svg(w, h, label, label, body)


# ---------------------------------------------------------------- stat tiles

FLAME = (
    "M12 2C12 6 17 8.5 17 14A5 5 0 0 1 7 14C7 11.8 8 10.2 9.2 9C9.4 10.6 10 11.6 11 12C10.6 8.5 11 5 12 2Z",
    "M12 12.5C12 14.5 14.2 15.2 14.2 17.2A2.2 2.2 0 0 1 9.8 17.2C9.8 15.4 11.4 14.6 12 12.5Z",
)
FLAME_COLORS = {"#121212": ("#f97316", "#fbbf24"), "#faf9f6": ("#c2410c", "#f59e0b")}  # the site's chart orange
TREND_ICONS = {
    "up": "M3 17l6-6 4 4 8-8M15 7h6v6",
    "down": "M3 7l6 6 4-4 8 8M15 17h6v-6",
    "flat": "M4 12h16",
}


def trend(now: float, before: float, unit: str = "%") -> tuple[str, str] | None:
    """(direction, label) against an earlier value; None when there is nothing to compare."""
    if before is None or (unit == "%" and not before):
        return None
    if unit == "%":
        change = round((now - before) / before * 100)
        # Past +1,000% a percentage stops meaning much; say how many times bigger instead.
        label = f"{round(now / before):,}\u00d7" if change >= 1000 else f"{change:+d}%"
    else:
        change = round(now - before)
        label = f"{change:+d} {unit if abs(change) != 1 else unit.rstrip('s')}".strip()
    if change == 0:
        return ("flat", "no change")
    return ("up" if change > 0 else "down", label.replace("-", "\u2212"))


def tiles(t: dict, title: str, items: list[dict]) -> str:
    w, h, gap = 1280, 176, 16
    tile_w = (w - gap * (len(items) - 1)) / len(items)
    digit_w, comma_w, row_h, base = 36, 15, 64, 112
    parts, css, lengths = [], [], set()
    for i, item in enumerate(items):
        x = i * (tile_w + gap)
        out = [
            f'    <rect x="{x + 0.5:.1f}" y="0.5" width="{tile_w - 1:.1f}" height="{h - 1}" rx="16" fill="{t["bg"]}" stroke="{t["border"]}"/>',
            f'    <text x="{x + 28:.1f}" y="46" class="mono" font-size="13" font-weight="600" letter-spacing="2.1" fill="{t["faint"]}">{escape(item["label"])}</text>',
        ]
        # The number: one clipped column per digit, rolling up from 0 to its value.
        cx = x + 26
        text = num(item["value"])
        for j, ch in enumerate(text):
            if ch == ",":
                out.append(
                    f'    <text x="{cx + comma_w / 2 - 1:.1f}" y="{base}" class="sans" font-size="58" font-weight="700" text-anchor="middle" fill="{t["text"]}">,</text>'
                )
                cx += comma_w
                continue
            d = int(ch)
            strip = list(range(d, -1, -1)) + list(range(9, -1, -1))  # shown last to first: 0..9, 0..d
            lengths.add(len(strip))
            cid = f"c{i}_{j}"
            digits = "".join(
                f'<text x="{cx + digit_w / 2:.1f}" y="{base + k * row_h}" text-anchor="middle">{v}</text>' for k, v in enumerate(strip)
            )
            out.append(
                f'    <clipPath id="{cid}"><rect x="{cx:.1f}" y="{base - 52}" width="{digit_w}" height="{row_h}"/></clipPath>'
                f'<g clip-path="url(#{cid})"><g class="sans roll r{len(strip)}" style="animation-delay:{j * 0.09:.2f}s" '
                f'font-size="58" font-weight="700" fill="{t["text"]}">{digits}</g></g>'
            )
            cx += digit_w
        if item.get("flame"):
            outer, inner = FLAME_COLORS[t["bg"]]
            out.append(
                f'    <g transform="translate({cx + 8:.1f} 66) scale(1.9)"><g class="flame">'
                f'<path d="{FLAME[0]}" fill="{outer}"/><path class="core" d="{FLAME[1]}" fill="{inner}"/></g></g>'
            )
        tr = item.get("trend")
        if tr:
            direction, label = tr
            color = {"up": t["green"], "down": t["red"], "flat": t["faint"]}[direction]
            right = x + tile_w - 26
            icon_x = right - len(label) * 8.3 - 32
            out.append(
                f'    <path transform="translate({icon_x:.1f} 31) scale(0.8)" d="{TREND_ICONS[direction]}" fill="none" stroke="{color}" '
                f'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
                f'<text x="{right:.1f}" y="46" class="sans num" font-size="15" font-weight="700" text-anchor="end" fill="{t["text"]}">{escape(label)}</text>'
            )
        out.append(f'    <text x="{x + 28:.1f}" y="146" class="sans num" font-size="16" fill="{t["muted"]}">{escape(item["sub"])}</text>')
        parts.append(f'  <g class="fu" style="animation-delay:{i * 0.09:.2f}s">\n' + "\n".join(out) + "\n  </g>")
    for n in sorted(lengths):
        css.append(
            f".r{n} {{ animation-name: r{n}; }} @keyframes r{n} {{ 0% {{ transform: translateY(-{(n - 1) * row_h}px); opacity: 0; }} "
            f"1.5% {{ opacity: 1; }} 10% {{ transform: translateY(0); }} 95% {{ transform: translateY(0); opacity: 1; }} "
            f"100% {{ transform: translateY(0); opacity: 0; }} }}"
        )
    css.append(f".roll {{ animation: {LOOP}s cubic-bezier(.16,.84,.3,1) infinite both; }}")
    css.append(
        ".flame { transform-box: fill-box; transform-origin: center bottom; animation: flick 1.3s ease-in-out infinite; }"
        " .core { transform-box: fill-box; transform-origin: center bottom; animation: flick .9s ease-in-out infinite reverse; }"
        " @keyframes flick { 0%, 100% { transform: scale(1, 1) rotate(0); } 30% { transform: scale(.94, 1.07) rotate(-2deg); }"
        " 65% { transform: scale(1.05, .95) rotate(2deg); } }"
    )

    def spoken(item: dict) -> str:
        words = f'{item["label"].title()}: {num(item["value"])}, {item["sub"]}'
        return words + (f' ({item["trend"][1]})' if item.get("trend") else "")

    return svg(w, h, title, "; ".join(spoken(i) for i in items), "\n".join(parts), "\n    ".join(css))


def github_tiles(t: dict, s: dict) -> str:
    best = s["best"]
    day = f'{best["date"].strftime("%b")} {best["date"].day}'
    cmp = s["has_prior"]
    return tiles(
        t,
        "GitHub activity in numbers, compared with the year before",
        [
            {
                "label": "CONTRIBUTIONS",
                "value": s["total"],
                "sub": f'{num(s["prior_total"])} the year before' if cmp else "in the last 12 months",
                "trend": trend(s["last365"], s["prior_total"]) if cmp else None,
            },
            {
                "label": "CURRENT STREAK",
                "value": s["current"],
                "flame": s["current"] > 0,
                "sub": f'days in a row · {num(s["previous_streak"])} last time',
                "trend": trend(s["current"], s["previous_streak"], "days"),
            },
            {
                "label": "LONGEST STREAK",
                "value": s["longest"],
                "flame": True,
                "sub": f'days · {num(s["prior_longest"])} the year before' if cmp else "days in a row",
                "trend": trend(s["longest"], s["prior_longest"], "days") if cmp else None,
            },
            {
                "label": "BUSIEST DAY",
                "value": best["count"],
                "sub": f'{day} · {num(s["prior_best"])} the year before' if cmp else f"on {day}, {best['date'].year}",
                "trend": trend(best["count"], s["prior_best"]) if cmp else None,
            },
        ],
    )


def work_tiles(t: dict, s: dict) -> str:
    first = min((r["start"] for r in s["roles"]), default=s["today"])
    years = s["today"].year - first.year - ((s["today"].month, s["today"].day) < (first.month, first.day))
    base = s.get("work_baseline")
    if base:
        then = dt.date.fromisoformat(base["date"])
        when = f'on {then.strftime("%b")} {then.day}'

    def tile(label: str, key: str, sub: str) -> dict:
        if not base or key not in base:
            return {"label": label, "value": s[key], "sub": sub}
        return {"label": label, "value": s[key], "sub": f"{num(base[key])} {when}", "trend": trend(s[key], base[key], "")}

    return tiles(
        t,
        "Work in numbers, from bahrul.me",
        [
            tile("PROJECTS SHIPPED", "projects", "live on bahrul.me"),
            tile("CLIENTS", "clients", "businesses worked with"),
            tile("CASE STUDIES", "cases", "written up in detail"),
            {"label": "YEARS IN THE FIELD", "value": years, "sub": f"since {first.year}"},
        ],
    )


# ---------------------------------------------------------------- heatmap


def heatmap(t: dict, s: dict) -> str:
    w, h = 1280, 330
    cell, pitch = 17, 21
    weeks = s["weeks"]
    gx = (w - (46 + len(weeks) * pitch - (pitch - cell))) / 2 + 46
    gy = 118
    fills = [mix(t["cell"], t["red"], a) for a in LEVEL_ALPHA]

    steps = len(weeks) * 7
    step = 0.09  # seconds the snake spends on each cell
    loop = steps * step

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
        rects = []
        for d in week:
            y = gy + d["weekday"] * pitch
            rects.append(f'<rect x="{x:.1f}" y="{y}" width="{cell}" height="{cell}" rx="4" fill="{fills[0]}"/>')
            if d["level"]:
                # The snake reaches this cell at step k, eats it, and it grows back later.
                k = 7 * i + (d["weekday"] if i % 2 == 0 else 6 - d["weekday"])
                rects.append(
                    f'<rect class="eat" style="animation-delay:{k * step - loop:.2f}s" x="{x:.1f}" y="{y}" '
                    f'width="{cell}" height="{cell}" rx="4" fill="{fills[d["level"]]}"/>'
                )
        cols.append(f'  <g class="wk" style="animation-delay:{0.15 + i * 0.016:.3f}s">{"".join(rects)}</g>')

    # The snake walks the grid column by column, down one and up the next, one cell per step.
    frames = []
    for i in range(len(weeks)):
        x = gx + i * pitch
        ys = (gy, gy + 6 * pitch) if i % 2 == 0 else (gy + 6 * pitch, gy)
        frames.append(f"{7 * i / steps * 100:.4f}% {{ transform: translate({x:.1f}px, {ys[0]}px); animation-timing-function: steps(6, end); }}")
        frames.append(f"{(7 * i + 6) / steps * 100:.4f}% {{ transform: translate({x:.1f}px, {ys[1]}px); animation-timing-function: steps(1, end); }}")
    frames.append(f"100% {{ transform: translate({gx:.1f}px, {gy}px); }}")
    snake = "\n".join(
        f'    <rect class="seg" style="animation-delay:{j * step:.2f}s" width="{cell}" height="{cell}" rx="3" '
        f'fill="{t["text"]}" opacity="{o}"/>'
        for j, o in reversed(list(enumerate((1, 0.82, 0.64, 0.48, 0.34, 0.22))))
    )

    day_labels = "\n".join(
        f'  <text x="{gx - 12:.1f}" y="{gy + row * pitch + 13}" class="sans" font-size="13" text-anchor="end" fill="{t["faint"]}">{name}</text>'
        for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri"))
    )
    right = gx + len(weeks) * pitch - (pitch - cell)
    ly = gy + 7 * pitch + 22
    start = right - 44 - 5 * 22
    legend = [f'  <text x="{start - 8:.1f}" y="{ly + 13}" class="sans" font-size="13" text-anchor="end" fill="{t["faint"]}">Less</text>']
    for i, fill in enumerate(fills):
        legend.append(f'  <rect x="{start + i * 22:.1f}" y="{ly}" width="{cell}" height="{cell}" rx="4" fill="{fill}"/>')
    legend.append(f'  <text x="{right:.1f}" y="{ly + 13}" class="sans" font-size="13" text-anchor="end" fill="{t["faint"]}">More</text>')

    left = gx - 46
    updated = f'{s["today"].strftime("%b")} {s["today"].day}, {s["today"].year}'
    body = f"""{frame(t, w, h)}
{eyebrow(t, round(left), 62, "CONTRIBUTIONS")}
{note(t, right, 62, [(num(s["total"]), True), (" in the last year · ", False), (num(s["active"]), True), (" active days", False)], 17)}
{chr(10).join(months)}
{day_labels}
{chr(10).join(cols)}
  <g class="snake">
{snake}
  </g>
  <text x="{left:.1f}" y="{ly + 13}" class="sans" font-size="13" fill="{t["faint"]}">Public and private work · updated {updated}</text>
{chr(10).join(legend)}"""
    css = (
        ".wk { animation: wk .5s cubic-bezier(.2,.7,.2,1) both; }"
        f" .eat {{ animation: eat {loop:.2f}s linear infinite; }}"
        f" .seg {{ animation: crawl {loop:.2f}s infinite both; }}"
        " @keyframes wk { from { opacity: 0; transform: translateY(6px); } }"
        " @keyframes eat { 0%, 11% { opacity: 0; } 17%, 100% { opacity: 1; } }"
        " @keyframes crawl { " + " ".join(frames) + " }"
        " @media (prefers-reduced-motion: reduce) { .snake { display: none; } }"
    )
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
    pts = [(x0 + i * (x1 - x0) / (len(totals) - 1), y1 - v / top * (y1 - y0)) for i, v in enumerate(totals)]
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
{note(t, w - 36, 54, [(num(avg), True), (" a week on average", False)])}
  <path class="area" d="{area}" fill="url(#fade)"/>
  <line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="{t["border"]}"/>
  <path class="line" d="{line}" pathLength="1" fill="none" stroke="{t["red"]}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
  <g class="peak">
    <circle cx="{px:.1f}" cy="{py:.1f}" r="6.5" fill="{t["bg"]}"/>
    <circle cx="{px:.1f}" cy="{py:.1f}" r="4.5" fill="{t["red"]}"/>
    {note(t, lx, round(label_y, 1), [(num(top), True), (f" in the week of {wk_start.strftime('%b')} {wk_start.day}", False)], 14, anchor).strip()}
  </g>
  <text x="{x0}" y="{y1 + 26}" class="sans" font-size="13" fill="{t["faint"]}">{first.strftime("%b %Y")}</text>
  <text x="{x1}" y="{y1 + 26}" class="sans" font-size="13" text-anchor="end" fill="{t["faint"]}">{last.strftime("%b %Y")}</text>"""
    css = (
        f".line {{ stroke-dasharray: 1; animation: draw {LOOP}s cubic-bezier(.4,0,.2,1) infinite both; }}"
        f" .area {{ animation: area {LOOP}s ease infinite both; }} .peak {{ animation: peak {LOOP}s ease infinite both; }}"
        " @keyframes draw { 0% { stroke-dashoffset: 1; opacity: 1; } 11% { stroke-dashoffset: 0; } 95% { stroke-dashoffset: 0; opacity: 1; } 100% { stroke-dashoffset: 0; opacity: 0; } }"
        " @keyframes area { 0%, 8% { opacity: 0; } 14%, 95% { opacity: 1; } 100% { opacity: 0; } }"
        " @keyframes peak { 0%, 11% { opacity: 0; } 14%, 95% { opacity: 1; } 100% { opacity: 0; } }"
    )
    return svg(
        w,
        h,
        "Contributions per week over the last year",
        f'{num(avg)} contributions a week on average; the busiest week had {num(top)}, starting {wk_start.strftime("%b")} {wk_start.day}, {wk_start.year}.',
        body,
        css,
    )


# ---------------------------------------------------------------- column charts


def columns(t: dict, title: str, label: str, head: list[tuple[str, bool]], data: list[tuple[str, int]], desc: str) -> str:
    """Vertical bars on one shared baseline; only the tallest carries its value."""
    w, h = 620, 320
    x0, x1, y0, y1 = 36, w - 36, 112, 250
    top = max(v for _, v in data) or 1
    pitch = (x1 - x0) / len(data)
    bar_w = min(44, pitch - max(6, pitch * 0.28))
    peak = max(range(len(data)), key=lambda i: data[i][1])
    bars = []
    for i, (name, value) in enumerate(data):
        cx = x0 + pitch * (i + 0.5)
        bh = max(3, value / top * (y1 - y0))
        r = min(4, bar_w / 2, bh)
        x, y = cx - bar_w / 2, y1 - bh
        # Rounded at the data end, square on the baseline.
        d = (
            f"M{x:.1f},{y1} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} H{x + bar_w - r:.1f} "
            f"Q{x + bar_w:.1f},{y:.1f} {x + bar_w:.1f},{y + r:.1f} V{y1} Z"
        )
        bars.append(f'  <path class="growy" style="animation-delay:{i * 0.05:.2f}s" d="{d}" fill="{t["red"]}"/>')
        if i == peak:
            bars.append(
                f'  <text x="{cx:.1f}" y="{y - 9:.1f}" class="sans num" font-size="14" font-weight="700" text-anchor="middle" fill="{t["text"]}">{num(value)}</text>'
            )
        bars.append(
            f'  <text x="{cx:.1f}" y="{y1 + 24}" class="sans" font-size="13" text-anchor="middle" fill="{t["text"] if i == peak else t["faint"]}">{escape(name)}</text>'
        )
    body = f"""{frame(t, w, h, 16)}
{eyebrow(t, 36, 54, label, 13)}
{note(t, w - 36, 54, head)}
  <line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="{t["border"]}"/>
{chr(10).join(bars)}"""
    return svg(w, h, title, desc, body)


def weekdays(t: dict, s: dict) -> str:
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    full = ["Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays", "Sundays"]
    data = list(zip(names, s["by_weekday"]))
    best = max(range(7), key=lambda i: s["by_weekday"][i])
    weekend = (s["by_weekday"][5] + s["by_weekday"][6]) / (sum(s["by_weekday"]) or 1) * 100
    return columns(
        t,
        "Contributions by day of the week",
        "WHEN I SHIP",
        [("Busiest on ", False), (full[best], True), (f" · {weekend:.0f}% on weekends", False)],
        data,
        ", ".join(f"{n} {num(v)}" for n, v in data),
    )


def monthly(t: dict, s: dict) -> str:
    keys = list(s["months"])[-13:]
    data = [(dt.date(y, m, 1).strftime("%b"), s["months"][(y, m)]) for y, m in keys]
    best = max(keys, key=lambda k: s["months"][k])
    return columns(
        t,
        "Contributions per month",
        "MONTH BY MONTH",
        [("Peak in ", False), (dt.date(best[0], best[1], 1).strftime("%B %Y"), True)],
        data,
        ", ".join(f"{dt.date(y, m, 1).strftime('%b %Y')} {num(s['months'][(y, m)])}" for y, m in keys),
    )


# ---------------------------------------------------------------- languages


def languages(t: dict, s: dict) -> str:
    w, h = 620, 320
    langs = s["languages"]
    bx, bmax = 196, 300
    widest = max(p for _, p in langs) or 1
    rows = []
    for i, (name, pct) in enumerate(langs):
        y = 104 + i * 33
        bw = max(6, pct / widest * bmax)
        shown = f"{pct:.1f}%" if pct >= 0.1 else "<0.1%"
        other = name == "Other"
        mark = (
            f'<circle cx="45" cy="{y}" r="2.2" fill="{t["faint"]}"/><circle cx="38" cy="{y}" r="2.2" fill="{t["faint"]}"/><circle cx="52" cy="{y}" r="2.2" fill="{t["faint"]}"/>'
            if other
            else logo(t, name, 36, y - 9, 18)
        )
        rows.append(
            f"""  {mark}
  <text x="66" y="{y + 5}" class="sans" font-size="16" fill="{t["text"]}">{escape(name)}</text>
  <rect class="growx" style="animation-delay:{i * 0.07:.2f}s" x="{bx}" y="{y - 5}" width="{bw:.1f}" height="10" rx="5" fill="{t["faint"] if other else t["text"]}"/>
  <text x="{w - 36}" y="{y + 5}" class="sans num" font-size="15" text-anchor="end" fill="{t["muted"]}">{shown}</text>"""
        )
    body = f"""{frame(t, w, h, 16)}
{eyebrow(t, 36, 54, "LANGUAGES", 13)}
{note(t, w - 36, 54, [("by code size in ", False), (str(s["public_repos"]), True), (" public repos", False)])}
{chr(10).join(rows)}"""
    return svg(w, h, "Languages across public repositories", ", ".join(f"{n} {p:.1f}%" for n, p in langs), body)


# ---------------------------------------------------------------- career


def career(t: dict, s: dict) -> str:
    roles = s["roles"]
    w, row = 1280, 36
    top_y = 124
    h = top_y + len(roles) * row + 30
    x0, x1 = 360, w - 64
    first_year = min(r["start"].year for r in roles)
    last_year = s["today"].year + 1
    span = (dt.date(last_year, 1, 1) - dt.date(first_year, 1, 1)).days

    def xpos(d: dt.date) -> float:
        return x0 + (d - dt.date(first_year, 1, 1)).days / span * (x1 - x0)

    grid = []
    for year in range(first_year, last_year + 1):
        x = xpos(dt.date(year, 1, 1))
        grid.append(f'  <line x1="{x:.1f}" y1="{top_y - 14}" x2="{x:.1f}" y2="{h - 34}" stroke="{t["border"]}"/>')
        if year < last_year:
            grid.append(
                f'  <text x="{x + (xpos(dt.date(year + 1, 1, 1)) - x) / 2:.1f}" y="{top_y - 24}" class="sans num" font-size="13" text-anchor="middle" fill="{t["faint"]}">{year}</text>'
            )
    rows = []
    for i, r in enumerate(roles):
        y = top_y + i * row + 12
        a, b = xpos(r["start"]), xpos(r["end"])
        bw = max(10, b - a)
        color = t["red"] if r["current"] else t["muted"]
        name = r["company"] if len(r["company"]) <= 34 else r["company"][:33].rstrip() + "…"
        rows.append(
            f'  <text x="64" y="{y + 5}" class="sans" font-size="16" font-weight="{600 if r["current"] else 400}" fill="{t["text"] if r["current"] else t["muted"]}">{escape(name)}</text>'
        )
        rows.append(
            f'  <rect class="growx" style="animation-delay:{i * 0.06:.2f}s" x="{a:.1f}" y="{y - 6}" width="{bw:.1f}" height="12" rx="6" fill="{color}"/>'
        )
        if r["current"]:
            rows.append(f'  <circle class="pulse" cx="{a + bw - 6:.1f}" cy="{y}" r="3" fill="{t["bg"]}"/>')
            rows.append(
                f'  <text x="{a - 12:.1f}" y="{y + 5}" class="sans" font-size="13" text-anchor="end" fill="{t["muted"]}">since {escape(r["since"])}</text>'
            )
    now = sum(1 for r in roles if r["current"])
    lx = w - 64
    body = f"""{frame(t, w, h)}
{eyebrow(t, 64, 62, "CAREER")}
  <circle cx="{lx - 228}" cy="57" r="5" fill="{t["red"]}"/>
  <text x="{lx - 216}" y="62" class="sans" font-size="15" fill="{t["muted"]}">Current</text>
  <circle cx="{lx - 138}" cy="57" r="5" fill="{t["muted"]}"/>
  <text x="{lx - 126}" y="62" class="sans" font-size="15" fill="{t["muted"]}">Past</text>
{note(t, lx, 62, [(str(len(roles)), True), (" roles", False)])}
{chr(10).join(grid)}
{chr(10).join(rows)}"""
    desc = "; ".join(f'{r["company"]}: {r["start"].strftime("%b %Y")} to {"now" if r["current"] else r["end"].strftime("%b %Y")}' for r in roles)
    return svg(w, h, f"Career timeline: {len(roles)} roles, {now} current", desc, body)


# ---------------------------------------------------------------- toolbox


def toolbox(t: dict, s: dict) -> str:
    w = 1280
    x_label, x_chips, right = 64, 300, w - 64
    chip_h, gap, row_gap = 38, 10, 14
    y = 100
    parts = []
    for category, names in s["stack"].items():
        x = x_chips
        parts.append(
            f'  <text x="{x_label}" y="{y + 24}" class="mono" font-size="13" font-weight="600" letter-spacing="1.6" fill="{t["faint"]}">{escape(category.upper())}</text>'
        )
        for name in names:
            cw = round(14 + 18 + 9 + len(name) * 8.8 + 16)
            if x + cw > right:
                x = x_chips
                y += chip_h + gap
            parts.append(
                f'  <g><rect x="{x + 0.5}" y="{y + 0.5}" width="{cw - 1}" height="{chip_h - 1}" rx="10" fill="{t["panel"]}" stroke="{t["border"]}"/>'
                f'{logo(t, name, x + 14, y + 10, 18)}'
                f'<text x="{x + 41}" y="{y + 24.5}" class="sans" font-size="15" font-weight="500" fill="{t["text"]}">{escape(name)}</text></g>'
            )
            x += cw + gap
        y += chip_h + row_gap
    h = y + 26
    body = f"""{frame(t, w, h)}
{eyebrow(t, 64, 62, "TOOLBOX")}
{note(t, right, 62, [(str(s["tools"]), True), (" tools across ", False), (str(len(s["stack"])), True), (" areas", False)])}
{chr(10).join(parts)}"""
    desc = "; ".join(f"{c}: {', '.join(n)}" for c, n in s["stack"].items())
    return svg(w, h, "Tools I work with", desc, body)


# ---------------------------------------------------------------- cards


def card(t: dict, c: dict, s: dict) -> str:
    w, h = 620, 256
    info = s["repos"].get(c["repo"], {})
    desc = "\n".join(
        f'  <text x="36" y="{146 + i * 28}" class="sans" font-size="19" fill="{t["muted"]}">{escape(line)}</text>'
        for i, line in enumerate(c["lines"])
    )
    lang = info.get("language")
    mark = f"  {logo(t, lang, w - 36 - 26, 34, 26, t['muted'])}" if lang else ""
    stars = info.get("stars", 0)
    star = (
        f'  <text x="{w - 148}" y="231" class="sans num" font-size="14" text-anchor="end" fill="{t["muted"]}">★ {num(stars)}</text>'
        if stars
        else ""
    )
    body = f"""{frame(t, w, h, 16)}
{eyebrow(t, 36, 54, c["kind"], 13)}
{mark}
  <text x="35" y="108" class="sans" font-size="36" font-weight="700" letter-spacing="-1.1" fill="{t["text"]}">{escape(c["title"])}</text>
{desc}
  <line x1="36" y1="204" x2="{w - 36}" y2="204" stroke="{t["border"]}"/>
  <text x="36" y="231" class="mono" font-size="13" fill="{t["faint"]}">{LOGIN}/{escape(c["repo"])}</text>
{star}
  <text x="{w - 36}" y="231" class="sans" font-size="14" font-weight="600" text-anchor="end" fill="{t["text"]}">View repo →</text>"""
    return svg(w, h, c["title"], " ".join(c["lines"]), body)


# ---------------------------------------------------------------- main


def main() -> None:
    site = fetch_site()
    s = summarize(fetch_github(), site)
    s["work_baseline"] = work_baseline(s, bool(site.get("fresh")))
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.svg"):
        stale.unlink(missing_ok=True)
    count = 0
    for name, t in THEMES.items():
        files = {
            "hero": hero(t, s),
            "stats": github_tiles(t, s),
            "contributions": heatmap(t, s),
            "weekly": weekly(t, s),
            "weekdays": weekdays(t, s),
            "monthly": monthly(t, s),
            "languages": languages(t, s),
            "work": work_tiles(t, s),
            "career": career(t, s),
            "toolbox": toolbox(t, s),
            **{c["file"]: card(t, c, s) for c in CARDS},
            **{stem: link_button(t, label, icon, primary) for stem, label, icon, primary in LINKS},
        }
        for stem, content in files.items():
            (OUT / f"{stem}-{name}.svg").write_text(content, encoding="utf-8")
            count += 1
    print(
        f"Wrote {count} files. {num(s['total'])} contributions, streak {s['current']} (longest {s['longest']}), "
        f"{s['projects']} projects, {s['clients']} clients, {len(s['roles'])} roles, {s['tools']} tools."
    )


if __name__ == "__main__":
    main()
