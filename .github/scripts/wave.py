"""Genera tu mapa de contribuciones real como SVG, con los puntos apareciendo en ola.

Uso:
    GITHUB_TOKEN=... python wave.py <usuario> <salida.svg>
    python wave.py <usuario> <salida.svg> --input calendario.json   (pruebas sin red)
"""
import json
import os
import sys
import urllib.request

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
      }
    }
  }
}
"""

CELL, GAP = 11, 3
STEP = CELL + GAP
PAD_X, PAD_Y = 10, 10
DELAY_PER_WEEK = 0.045  # retraso entre columnas: la ola avanza de izquierda a derecha
DELAY_PER_DAY = 0.03  # retraso entre filas: da inclinación diagonal a la ola
DURATION = 1.1  # lo que tarda cada punto en aparecer


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def level(count, top):
    if count == 0:
        return 0
    q = count / top
    return 1 if q <= 0.25 else 2 if q <= 0.5 else 3 if q <= 0.75 else 4


def build(calendar):
    weeks = calendar["weeks"]
    top = max((d["contributionCount"] for w in weeks for d in w["contributionDays"]), default=1) or 1
    width = PAD_X * 2 + len(weeks) * STEP - GAP
    height = PAD_Y * 2 + 7 * STEP - GAP
    cells = []
    for wi, week in enumerate(weeks):
        for d in week["contributionDays"]:
            lv = level(d["contributionCount"], top)
            x = PAD_X + wi * STEP
            y = PAD_Y + d["weekday"] * STEP
            delay = wi * DELAY_PER_WEEK + d["weekday"] * DELAY_PER_DAY
            cells.append(
                f'<rect class="c l{lv}" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" '
                f'style="animation-delay:{delay:.2f}s"/>'
            )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="Contribution heatmap">
<style>
  :root {{ --l0:#161b22; --l1:#0e4429; --l2:#006d32; --l3:#26a641; --l4:#39d353; }}
  @media (prefers-color-scheme: light) {{
    :root {{ --l0:#ebedf0; --l1:#9be9a8; --l2:#40c463; --l3:#30a14e; --l4:#216e39; }}
  }}
  .c {{
    transform-box: fill-box; transform-origin: center;
    animation: reveal {DURATION}s cubic-bezier(.22,.8,.3,1) both;
  }}
  .l0 {{ fill: var(--l0); }} .l1 {{ fill: var(--l1); }} .l2 {{ fill: var(--l2); }}
  .l3 {{ fill: var(--l3); }} .l4 {{ fill: var(--l4); }}
  @keyframes reveal {{
    from {{ opacity: 0; transform: scale(.3); filter: blur(3px); }}
    to {{ opacity: 1; transform: scale(1); filter: blur(0); }}
  }}
  @media (prefers-reduced-motion: reduce) {{ .c {{ animation: none; }} }}
</style>
{chr(10).join(cells)}
</svg>
"""


def main():
    login, out = sys.argv[1], sys.argv[2]
    if "--input" in sys.argv:
        with open(sys.argv[sys.argv.index("--input") + 1], encoding="utf-8") as f:
            raw = json.load(f)
        calendar = raw["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    else:
        calendar = fetch(login, os.environ["GITHUB_TOKEN"])
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(build(calendar))
    print(f"{calendar['totalContributions']} contribuciones -> {out}")


if __name__ == "__main__":
    main()
