#!/usr/bin/env python3
"""Generate the profile README artwork (hero banner and project cards).

Run from the repo root:  python3 scripts/build_assets.py
Every image is written twice, as -dark.svg and -light.svg, into assets/.
Edit CARDS or the hero copy below, then run the script again.
"""

from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "assets"

SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"

# Colors follow the bahrul.me palette: warm neutrals, one gold, one blue-gray.
THEMES = {
    "dark": {
        "bg": "#121212",
        "surface": "#1e1e1d",
        "border": "#2f2f2f",
        "chrome": "#40403f",
        "text": "#faf9f6",
        "muted": "#b4b4b2",
        "faint": "#868684",
        "gold": "#bd9f65",
        "cobalt": "#8fa3bf",
        "glow": "0.16",
    },
    "light": {
        "bg": "#faf9f6",
        "surface": "#ffffff",
        "border": "#e3e2e0",
        "chrome": "#d6d5d2",
        "text": "#121212",
        "muted": "#4f4f4d",
        "faint": "#6b6b69",
        "gold": "#7d6126",
        "cobalt": "#3f5878",
        "glow": "0.14",
    },
}

CARDS = [
    {
        "file": "card-sawit",
        "kind": "RUST · MACOS APP",
        "title": "Sawit",
        "lines": [
            "Postgres, an editor and a terminal in one native",
            "macOS app, without Docker.",
        ],
        "repo": "bahrulbangsawan/sawit.dev",
    },
    {
        "file": "card-claude-pool",
        "kind": "SWIFT · MENU BAR APP",
        "title": "Claude Pool",
        "lines": [
            "Switch between Claude Code accounts and see",
            "every account's usage limits at a glance.",
        ],
        "repo": "bahrulbangsawan/claude-pool",
    },
    {
        "file": "card-content-studio",
        "kind": "CLAUDE CODE SKILL",
        "title": "Content Studio",
        "lines": [
            "A Claude skill and CLI that builds educational",
            "Instagram carousels and Reels.",
        ],
        "repo": "bahrulbangsawan/content-studio",
    },
    {
        "file": "card-manujujaya-mcp",
        "kind": "CLOUDFLARE WORKERS · MCP",
        "title": "Manuju Jaya MCP",
        "lines": [
            "A remote MCP server that gives AI assistants",
            "read-only access to live Qasir POS data.",
        ],
        "repo": "bahrulbangsawan/manujujaya-mcp",
    },
]


def hero(t: dict) -> str:
    term_x, term_y, term_w, term_h = 764, 76, 452, 248
    lx = term_x + 26
    rows = [
        ("cmd", "whoami"),
        ("out", "bahrul, gtm engineer"),
        ("cmd", "ls building/"),
        ("ls", "sawit  claude-pool  content-studio"),
        ("cursor", "open bahrul.me"),
    ]
    lines = []
    y = term_y + 82
    for kind, text in rows:
        if kind in ("cmd", "cursor"):
            lines.append(
                f'<text x="{lx}" y="{y}" class="mono" font-size="17">'
                f'<tspan fill="{t["gold"]}">$</tspan>'
                f'<tspan fill="{t["text"]}" dx="10">{escape(text)}</tspan></text>'
            )
            if kind == "cursor":
                cx = lx + 20.4 + len(text) * 10.25 + 8
                lines.append(
                    f'<rect class="cursor" x="{cx:.1f}" y="{y - 15}" width="9" height="19" '
                    f'fill="{t["gold"]}"/>'
                )
        else:
            fill = t["cobalt"] if kind == "ls" else t["muted"]
            lines.append(
                f'<text x="{lx}" y="{y}" class="mono" font-size="17" fill="{fill}">'
                f"{escape(text)}</text>"
            )
        y += 32

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 400" width="1280" height="400" role="img" aria-labelledby="title desc">
  <title id="title">Bahrul Bangsawan, GTM Engineer</title>
  <desc id="desc">I help businesses get more customers: websites, marketing automation, and data that shows what works. Available for new projects.</desc>
  <defs>
    <radialGradient id="glow" cx="88%" cy="0%" r="70%">
      <stop offset="0" stop-color="{t["gold"]}" stop-opacity="{t["glow"]}"/>
      <stop offset="1" stop-color="{t["gold"]}" stop-opacity="0"/>
    </radialGradient>
    <clipPath id="frame"><rect width="1280" height="400" rx="20"/></clipPath>
    <style>
      .sans {{ font-family: {SANS}; }}
      .mono {{ font-family: {MONO}; }}
      .cursor {{ animation: blink 1.2s steps(1) infinite; }}
      @keyframes blink {{ 50% {{ opacity: 0; }} }}
      @media (prefers-reduced-motion: reduce) {{ .cursor {{ animation: none; }} }}
    </style>
  </defs>
  <g clip-path="url(#frame)">
    <rect width="1280" height="400" fill="{t["bg"]}"/>
    <rect width="1280" height="400" fill="url(#glow)"/>
  </g>
  <rect x="0.5" y="0.5" width="1279" height="399" rx="19.5" fill="none" stroke="{t["border"]}"/>

  <text x="64" y="112" class="mono" font-size="17" letter-spacing="3.4" fill="{t["gold"]}">GTM ENGINEER · INDONESIA</text>
  <text x="62" y="190" class="sans" font-size="68" font-weight="600" letter-spacing="-2" fill="{t["text"]}">Bahrul Bangsawan</text>
  <text x="64" y="246" class="sans" font-size="27" letter-spacing="-0.3" fill="{t["text"]}">I help businesses get more customers.</text>
  <text x="64" y="284" class="sans" font-size="21" fill="{t["muted"]}">Websites, marketing automation, and data</text>
  <text x="64" y="313" class="sans" font-size="21" fill="{t["muted"]}">that shows what works.</text>
  <circle cx="70" cy="349" r="5" fill="{t["gold"]}"/>
  <text x="86" y="354" class="mono" font-size="15" letter-spacing="0.4" fill="{t["faint"]}">Available for new projects</text>

  <rect x="{term_x}" y="{term_y}" width="{term_w}" height="{term_h}" rx="12" fill="{t["surface"]}" stroke="{t["border"]}"/>
  <circle cx="{term_x + 24}" cy="{term_y + 24}" r="5.5" fill="{t["chrome"]}"/>
  <circle cx="{term_x + 44}" cy="{term_y + 24}" r="5.5" fill="{t["chrome"]}"/>
  <circle cx="{term_x + 64}" cy="{term_y + 24}" r="5.5" fill="{t["chrome"]}"/>
  <text x="{term_x + term_w / 2}" y="{term_y + 29}" class="mono" font-size="13" text-anchor="middle" fill="{t["faint"]}">~/bahrul</text>
  <line x1="{term_x}" y1="{term_y + 48}" x2="{term_x + term_w}" y2="{term_y + 48}" stroke="{t["border"]}"/>
  {chr(10).join("  " + line for line in lines).strip()}
</svg>
"""


def card(t: dict, c: dict) -> str:
    desc = "\n".join(
        f'  <text x="36" y="{142 + i * 29}" class="sans" font-size="20" fill="{t["muted"]}">'
        f"{escape(line)}</text>"
        for i, line in enumerate(c["lines"])
    )
    summary = escape(" ".join(c["lines"]))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 620 236" width="620" height="236" role="img" aria-labelledby="title desc">
  <title id="title">{escape(c["title"])}</title>
  <desc id="desc">{summary}</desc>
  <defs>
    <style>
      .sans {{ font-family: {SANS}; }}
      .mono {{ font-family: {MONO}; }}
    </style>
  </defs>
  <rect x="0.5" y="0.5" width="619" height="235" rx="15.5" fill="{t["surface"]}" stroke="{t["border"]}"/>
  <text x="36" y="54" class="mono" font-size="14" letter-spacing="2.4" fill="{t["gold"]}">{escape(c["kind"])}</text>
  <text x="35" y="102" class="sans" font-size="34" font-weight="600" letter-spacing="-0.8" fill="{t["text"]}">{escape(c["title"])}</text>
{desc}
  <text x="36" y="206" class="mono" font-size="14" fill="{t["cobalt"]}">{escape(c["repo"])}  →</text>
</svg>
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, t in THEMES.items():
        (OUT / f"hero-{name}.svg").write_text(hero(t), encoding="utf-8")
        for c in CARDS:
            (OUT / f'{c["file"]}-{name}.svg').write_text(card(t, c), encoding="utf-8")
    print(f"Wrote {2 + 2 * len(CARDS)} files to {OUT}")


if __name__ == "__main__":
    main()
