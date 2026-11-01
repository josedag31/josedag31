"""Genera las imágenes del perfil con datos reales de GitHub, sin servicios de terceros.

Salida (en <carpeta>): contribution-wave.svg, stats.svg, languages.svg, featured.svg

Uso:
    GITHUB_TOKEN=... python build.py <usuario> <carpeta>      (en el workflow)
    python build.py <usuario> <carpeta>                       (en local, usa `gh`)
    python build.py <usuario> <carpeta> --input datos.json    (pruebas sin red)

Los repos privados y de organizaciones no cuentan: el token del workflow solo
ve lo público.
"""
import html
import json
import os
import subprocess
import sys
import urllib.request

FEATURED_REPO = "WinAirdrop"

QUERY = """
query($login: String!, $repo: String!) {
  user(login: $login) {
    followers { totalCount }
    repository(name: $repo) {
      name description stargazerCount forkCount
      primaryLanguage { name color }
    }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
      }
    }
  }
}
"""

FONT = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"

# Paleta: oscuro por defecto, claro si el visor lo pide.
THEME = """
  :root { --bg:#0d1117; --border:#30363d; --text:#c9d1d9; --muted:#8b949e; --title:#58a6ff;
          --l0:#161b22; --l1:#0e4429; --l2:#006d32; --l3:#26a641; --l4:#39d353; }
  @media (prefers-color-scheme: light) {
    :root { --bg:#ffffff; --border:#d0d7de; --text:#24292f; --muted:#57606a; --title:#0969da;
            --l0:#ebedf0; --l1:#9be9a8; --l2:#40c463; --l3:#30a14e; --l4:#216e39; }
  }
  text { font-family: %s; fill: var(--text); }
  .title { font-size: 16px; font-weight: 600; fill: var(--title); }
  .label { font-size: 13px; }
  .value { font-size: 13px; font-weight: 600; text-anchor: end; }
  .muted { font-size: 12px; fill: var(--muted); }
  .card-bg { fill: var(--bg); stroke: var(--border); }
  .fade { animation: fade .9s ease-out both; }
  @keyframes fade { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
  @media (prefers-reduced-motion: reduce) { .fade, .c, .grow { animation: none; } }
""" % FONT


# ---------- datos ----------

def fetch(login):
    variables = {"login": login, "repo": FEATURED_REPO}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": QUERY, "variables": variables}).encode(),
            headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    out = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={QUERY}", "-F", f"login={login}", "-F", f"repo={FEATURED_REPO}"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


# ---------- mapa de contribuciones en ola ----------

CELL, GAP = 11, 3
STEP = CELL + GAP
PAD = 10
DELAY_PER_WEEK = 0.045  # la ola avanza de izquierda a derecha
DELAY_PER_DAY = 0.03    # y se inclina en diagonal
REVEAL = 1.1            # lo que tarda cada punto en aparecer


def level(count, top):
    if count == 0:
        return 0
    q = count / top
    return 1 if q <= 0.25 else 2 if q <= 0.5 else 3 if q <= 0.75 else 4


def wave_svg(calendar):
    weeks = calendar["weeks"]
    top = max((d["contributionCount"] for w in weeks for d in w["contributionDays"]), default=1) or 1
    width = PAD * 2 + len(weeks) * STEP - GAP
    height = PAD * 2 + 7 * STEP - GAP
    cells = []
    for wi, week in enumerate(weeks):
        for d in week["contributionDays"]:
            lv = level(d["contributionCount"], top)
            delay = wi * DELAY_PER_WEEK + d["weekday"] * DELAY_PER_DAY
            cells.append(
                f'<rect class="c l{lv}" x="{PAD + wi * STEP}" y="{PAD + d["weekday"] * STEP}" '
                f'width="{CELL}" height="{CELL}" rx="2" style="animation-delay:{delay:.2f}s"/>'
            )
    css = f"""{THEME}
  .c {{ transform-box: fill-box; transform-origin: center;
        animation: reveal {REVEAL}s cubic-bezier(.22,.8,.3,1) both; }}
  .l0 {{ fill: var(--l0); }} .l1 {{ fill: var(--l1); }} .l2 {{ fill: var(--l2); }}
  .l3 {{ fill: var(--l3); }} .l4 {{ fill: var(--l4); }}
  @keyframes reveal {{
    from {{ opacity: 0; transform: scale(.3); filter: blur(3px); }}
    to {{ opacity: 1; transform: scale(1); filter: blur(0); }}
  }}"""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
        f'height="{height}" role="img" aria-label="Contribution heatmap">\n<style>{css}</style>\n'
        + "\n".join(cells) + "\n</svg>\n"
    )


# ---------- tarjetas ----------

def card(width, height, title, body):
    css = THEME
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
        f'height="{height}" role="img" aria-label="{html.escape(title)}">\n<style>{css}</style>\n'
        f'<rect class="card-bg" x=".5" y=".5" width="{width - 1}" height="{height - 1}" rx="8"/>\n'
        f'<g class="fade"><text class="title" x="22" y="34">{html.escape(title)}</text>\n{body}</g>\n</svg>\n'
    )


def stats_svg(user, calendar):
    cc = user["contributionsCollection"]
    repos = user["repositories"]["nodes"]
    rows = [
        ("Contributions (last year)", calendar["totalContributions"]),
        ("Commits", cc["totalCommitContributions"]),
        ("Pull requests", cc["totalPullRequestContributions"]),
        ("Issues", cc["totalIssueContributions"]),
        ("Public repositories", user["repositories"]["totalCount"]),
        ("Stars earned", sum(r["stargazerCount"] for r in repos)),
    ]
    w = 400
    body = []
    for i, (label, value) in enumerate(rows):
        y = 66 + i * 24
        body.append(f'<text class="label" x="22" y="{y}">{html.escape(label)}</text>')
        body.append(f'<text class="value" x="{w - 22}" y="{y}">{value:,}</text>')
    return card(w, 200, "GitHub stats", "\n".join(body))


def languages_svg(user):
    sizes, colors = {}, {}
    for repo in user["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            name = e["node"]["name"]
            sizes[name] = sizes.get(name, 0) + e["size"]
            colors[name] = e["node"]["color"] or "#8b949e"
    total = sum(sizes.values()) or 1
    top = sorted(sizes.items(), key=lambda kv: -kv[1])[:6]
    w, bar_w = 400, 400 - 44
    body = ['<clipPath id="bar"><rect x="22" y="50" width="%d" height="8" rx="4"/></clipPath>' % bar_w,
            '<g clip-path="url(#bar)">']
    x = 22.0
    for name, size in top:
        seg = bar_w * size / total
        body.append(f'<rect x="{x:.1f}" y="50" width="{seg:.1f}" height="8" fill="{colors[name]}"/>')
        x += seg
    body.append("</g>")
    for i, (name, size) in enumerate(top):
        col, row = i % 2, i // 2
        cx, cy = 22 + col * 180, 92 + row * 26
        body.append(f'<circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{colors[name]}"/>')
        body.append(f'<text class="label" x="{cx + 18}" y="{cy}">{html.escape(name)} '
                    f'<tspan class="muted">{100 * size / total:.1f}%</tspan></text>')
    return card(w, 200, "Top languages", "\n".join(body))


def featured_svg(user):
    repo = user["repository"]
    w = 804
    desc = html.escape(repo["description"] or "")
    lang = repo["primaryLanguage"]
    body = [
        f'<text class="label" x="22" y="64">{desc}</text>',
    ]
    x = 22
    if lang:
        body.append(f'<circle cx="{x + 5}" cy="{86}" r="5" fill="{lang["color"] or "#8b949e"}"/>')
        body.append(f'<text class="muted" x="{x + 18}" y="90">{html.escape(lang["name"])}</text>')
        x += 40 + 8 * len(lang["name"])
    body.append(f'<text class="muted" x="{x}" y="90">★ {repo["stargazerCount"]}</text>')
    body.append(f'<text class="muted" x="{x + 60}" y="90">⑂ {repo["forkCount"]}</text>')
    return card(w, 110, repo["name"], "\n".join(body))


def main():
    login, outdir = sys.argv[1], sys.argv[2]
    if "--input" in sys.argv:
        with open(sys.argv[sys.argv.index("--input") + 1], encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = fetch(login)
    if data.get("errors"):
        raise SystemExit(f"GraphQL: {data['errors']}")
    user = data["data"]["user"]
    calendar = user["contributionsCollection"]["contributionCalendar"]
    os.makedirs(outdir, exist_ok=True)
    files = {
        "contribution-wave.svg": wave_svg(calendar),
        "stats.svg": stats_svg(user, calendar),
        "languages.svg": languages_svg(user),
        "featured.svg": featured_svg(user),
    }
    for name, content in files.items():
        with open(os.path.join(outdir, name), "w", encoding="utf-8") as f:
            f.write(content)
    print(f"{calendar['totalContributions']} contribuciones -> {', '.join(files)}")


if __name__ == "__main__":
    main()
