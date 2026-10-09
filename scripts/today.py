"""Render the neofetch-style profile card (dark_mode.svg / light_mode.svg).

Static copy lives in PROFILE below; GitHub numbers are fetched live. Runs
daily from .github/workflows/update-card.yml, or locally with:

    GH_TOKEN=$(gh auth token) python scripts/today.py

Standard library only, so the workflow needs no pip install.
"""
import json
import os
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USER = os.environ.get("USER_NAME", "ignaciojsoler")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
LOC_CACHE = ROOT / "cache/loc.json"

HANDLE = "ignacio@soler"
PROFILE = [
    ("Role", "Full-Stack Engineer"),
    ("Host", "Phinx Lab · AprendeBA"),
    ("GitHub.Uptime", None),  # filled in from the account creation date
    ("Location", "Argentina · Remote"),
    ("Editor", "Cursor, Claude Code"),
    None,
    ("Languages.Programming", "TypeScript, JavaScript, Python"),
    ("Stack.Frontend", "React, Next.js, Astro, Tailwind"),
    ("Stack.Backend", "Node.js, NestJS, Express"),
    ("Stack.Data", "PostgreSQL, MongoDB, Supabase, pgvector"),
    ("Stack.AI", "LLMs, Agents, RAG, MCP, LangChain"),
    ("Stack.Infra", "Docker, AWS, Vercel, GitHub Actions"),
    None,
    ("Shipped", "Cinépolis payments, AprendeBA, LinkTurno"),
    ("Awards", "Site of the Day ×2 · CSS Light"),
]
CONTACT = [
    ("Email", "ignaciojsoler@gmail.com"),
    ("LinkedIn", "ignaciojsoler"),
    ("Portfolio", "ignaciosoler.com"),
]

# Layout. The portrait uses a smaller font than the text column so it can
# have more rows (detail) while both columns end up the same height.
WIDTH = 62  # characters per info line
INFO_FONT, INFO_LINE = 14, 20
ART_FONT, ART_LINE = 11, 13
PAD = 32
ART_X = PAD
INFO_X = 492
SVG_W = INFO_X + round(WIDTH * INFO_FONT * 0.602) + PAD

THEMES = {
    "dark": {
        "bg": "#08090c", "border": "#1c1f26", "art": "#b4b9c2",
        "text": "#f4f4f2", "key": "#d8ff3e", "dim": "#3a3f48",
        "add": "#3fb950", "del": "#f85149",
    },
    "light": {
        "bg": "#fbfbf9", "border": "#e4e5e1", "art": "#3d4148",
        "text": "#08090c", "key": "#4f6b00", "dim": "#b9bcc2",
        "add": "#1a7f37", "del": "#cf222e",
    },
}


# ── GitHub ───────────────────────────────────────────────────────────────

def request(url, body=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.status, json.loads(res.read() or "null")


def graphql(query, **variables):
    _, res = request("https://api.github.com/graphql",
                     {"query": query, "variables": variables})
    if res.get("errors"):
        raise RuntimeError(res["errors"])
    return res["data"]


def fetch_stats():
    repos, after = [], None
    while True:
        data = graphql("""
            query($login: String!, $after: String) {
              user(login: $login) {
                createdAt
                followers { totalCount }
                repositoriesContributedTo(
                  contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY]
                ) { totalCount }
                repositories(first: 100, after: $after,
                             ownerAffiliations: OWNER, privacy: PUBLIC) {
                  totalCount
                  pageInfo { hasNextPage endCursor }
                  nodes { nameWithOwner stargazerCount isFork }
                }
              }
            }""", login=USER, after=after)["user"]
        repos += data["repositories"]["nodes"]
        if not data["repositories"]["pageInfo"]["hasNextPage"]:
            break
        after = data["repositories"]["pageInfo"]["endCursor"]

    created = datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00"))
    return {
        "created": created.date(),
        "repos": data["repositories"]["totalCount"],
        "contributed": data["repositoriesContributedTo"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "followers": data["followers"]["totalCount"],
        "commits": count_commits(created),
        "loc": count_loc([r["nameWithOwner"] for r in repos if not r["isFork"]]),
    }


def count_commits(since):
    """contributionsCollection only spans a year per query, so walk them."""
    total, start = 0, since
    now = datetime.now(timezone.utc)
    while start < now:
        end = min(start.replace(year=start.year + 1), now)
        c = graphql("""
            query($login: String!, $from: DateTime!, $to: DateTime!) {
              user(login: $login) {
                contributionsCollection(from: $from, to: $to) {
                  totalCommitContributions restrictedContributionsCount
                }
              }
            }""", login=USER, **{"from": start.isoformat(), "to": end.isoformat()})
        c = c["user"]["contributionsCollection"]
        total += c["totalCommitContributions"] + c["restrictedContributionsCount"]
        start = end
    return total


def count_loc(repos):
    """Lines added/removed by USER across their own repos.

    GitHub computes /stats/contributors lazily and answers 202 until it's
    ready, so each repo gets a few retries; a repo that still isn't ready
    keeps its number from the last run (cache/loc.json).
    """
    cache = json.loads(LOC_CACHE.read_text()) if LOC_CACHE.exists() else {}
    for repo in repos:
        for attempt in range(4):
            try:
                status, stats = request(
                    f"https://api.github.com/repos/{repo}/stats/contributors")
            except urllib.error.HTTPError:
                break
            if status == 200:
                mine = next((s for s in stats or []
                             if s["author"] and s["author"]["login"].lower() == USER.lower()), None)
                weeks = mine["weeks"] if mine else []
                cache[repo] = [sum(w["a"] for w in weeks), sum(w["d"] for w in weeks)]
                break
            if status == 204:  # empty repo
                cache[repo] = [0, 0]
                break
            time.sleep(2 + attempt * 3)
    cache = {r: v for r, v in cache.items() if r in repos}
    LOC_CACHE.parent.mkdir(exist_ok=True)
    LOC_CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n")
    added = sum(a for a, _ in cache.values())
    removed = sum(d for _, d in cache.values())
    return added, removed


# ── Text layout ──────────────────────────────────────────────────────────
# A line is a list of (css class, text) runs: key, text, dim, add, del, cursor.

def age(since, today):
    years = today.year - since.year
    months = today.month - since.month
    days = today.day - since.day
    if days < 0:
        months -= 1
        prev_month_end = date(today.year, today.month, 1).toordinal() - 1
        days += date.fromordinal(prev_month_end).day
    if months < 0:
        years -= 1
        months += 12
    plural = lambda n, word: f"{n} {word}{'' if n == 1 else 's'}"
    return f"{plural(years, 'year')}, {plural(months, 'month')}, {plural(days, 'day')}"


def entry(key, value, width=WIDTH, value_cls="text"):
    """`. Key: ........ value`, padded with dots to exactly `width`."""
    value_len = sum(len(t) for _, t in value) if isinstance(value, list) else len(value)
    dots = width - len(f". {key}: ") - value_len - 1
    runs = [("dim", ". "), ("key", key), ("text", ": "), ("dim", "." * max(dots, 1) + " ")]
    runs += value if isinstance(value, list) else [(value_cls, value)]
    return runs


def pair(left, right, split=38):
    """Two entries on one line, `left | right`, still `WIDTH` wide overall."""
    # The right entry drops its leading ". ", hence the +2.
    return entry(*left, width=split) + [("dim", " | ")] + entry(*right, width=WIDTH - split - 3 + 2)[1:]


def heading(title):
    lead = f"- {title} "
    return [("dim", "- "), ("key", title), ("dim", " " + "─" * (WIDTH - len(lead)))]


def build_lines(stats, today):
    lines = [[("key", HANDLE), ("dim", " " + "─" * (WIDTH - len(HANDLE) - 1))]]
    for item in PROFILE:
        if item is None:
            lines.append([])
        elif item[1] is None:
            lines.append(entry(item[0], age(stats["created"], today)))
        else:
            lines.append(entry(*item))

    lines += [[], heading("Contact")]
    lines += [entry(*item) for item in CONTACT]

    n = lambda v: f"{v:,}"
    added, removed = stats["loc"]
    lines += [[], heading("GitHub Stats")]
    lines.append(pair(("Repos", f"{n(stats['repos'])} {{Contributed: {n(stats['contributed'])}}}"),
                      ("Stars", n(stats["stars"]))))
    lines.append(pair(("Commits", n(stats["commits"])),
                      ("Followers", n(stats["followers"]))))
    lines.append(entry("Lines of Code", [
        ("text", f"{n(added - removed)} ( "), ("add", f"{n(added)}++"),
        ("text", ", "), ("del", f"{n(removed)}--"), ("text", " )"),
    ]))
    lines += [[], [("key", f"{HANDLE}:~$ "), ("cursor", "█")]]
    return lines


# ── SVG ──────────────────────────────────────────────────────────────────

def render(theme, art, lines):
    c = THEMES[theme]
    info_h = len(lines) * INFO_LINE
    art_h = len(art) * ART_LINE
    height = max(info_h, art_h) + PAD * 2
    art_top = PAD + (height - PAD * 2 - art_h) // 2 + ART_FONT
    info_top = PAD + (height - PAD * 2 - info_h) // 2 + INFO_FONT

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_W}" height="{height}" '
        f'viewBox="0 0 {SVG_W} {height}" font-family="ui-monospace, SFMono-Regular, '
        f"'SF Mono', Menlo, Consolas, 'Liberation Mono', 'DejaVu Sans Mono', monospace\">",
        "<style>",
        f".art{{fill:{c['art']};font-size:{ART_FONT}px}}",
        f".info{{font-size:{INFO_FONT}px}}",
        *(f".{k}{{fill:{c[k]}}}" for k in ("text", "key", "dim", "add", "del")),
        f".cursor{{fill:{c['key']};animation:blink 1.1s steps(1) infinite}}",
        "@keyframes blink{50%{fill-opacity:0}}",
        "@media (prefers-reduced-motion:reduce){.cursor{animation:none}}",
        "</style>",
        f'<rect x="0.5" y="0.5" width="{SVG_W - 1}" height="{height - 1}" rx="14" '
        f'fill="{c["bg"]}" stroke="{c["border"]}"/>',
        f'<text class="art" xml:space="preserve">',
    ]
    for i, row in enumerate(art):
        out.append(f'<tspan x="{ART_X}" y="{art_top + i * ART_LINE}">{escape(row)}</tspan>')
    out.append("</text>")

    out.append('<text class="info" xml:space="preserve">')
    for i, runs in enumerate(lines):
        y = info_top + i * INFO_LINE
        spans = "".join(f'<tspan class="{cls}">{escape(t)}</tspan>' for cls, t in runs)
        out.append(f'<tspan x="{INFO_X}" y="{y}">{spans}</tspan>')
    out.append("</text>")

    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    art = (ROOT / "assets/ascii.txt").read_text().rstrip("\n").split("\n")
    stats = fetch_stats()
    lines = build_lines(stats, date.today())
    for theme in THEMES:
        (ROOT / f"{theme}_mode.svg").write_text(render(theme, art, lines))
    print(json.dumps({**stats, "created": str(stats["created"])}, indent=2))


if __name__ == "__main__":
    main()
