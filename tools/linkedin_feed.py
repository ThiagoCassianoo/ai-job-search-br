#!/usr/bin/env python3
"""Daily LinkedIn collector for the Radar de Vagas feed.

Runs the linkedin-search CLI for a fixed set of queries, drops senior/intern
titles and postings already in the feed, fetches the full description of the
survivors, cleans each one with posting_guard, and writes a JSON list the
scheduled session scores and pushes to the Radar's `feed` collection.

Nothing here judges fit or writes to the Radar: scoring stays with the model.
Volume is deliberately low (personal use; LinkedIn's terms forbid bulk
automated access): one pass per day, a pause between detail fetches.

Usage:
  python3 tools/linkedin_feed.py --out feed.json [--skip-ids ids.txt] [--max 20] [--days 1]
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / ".agents/skills/linkedin-search/cli/src/cli.ts"
sys.path.insert(0, str(ROOT / "tools"))
from posting_guard import guard  # noqa: E402

# (query, location, remote filter or None). Remote searches cover Brazil;
# the ES searches take any workplace type, since Grande Vitória is in range.
SEARCHES = [
    ("analista de dados", "Brazil", "remote"),
    ("analista de BI", "Brazil", "remote"),
    ("engenheiro de dados", "Brazil", "remote"),
    ("power bi", "Brazil", "remote"),
    ("analista de dados", "Espírito Santo, Brazil", None),
    ("analista de BI", "Espírito Santo, Brazil", None),
    ("analista de processos", "Espírito Santo, Brazil", None),
]
SENIOR_RE = re.compile(r"\b(s[eê]nior|sr\.?|especialista|lead|principal|staff|coordenador|gerente|head|manager|est[aá]gi|trainee|intern)\b", re.I)


def cli(*args: str) -> dict:
    out = subprocess.run(["bun", "run", str(CLI), *args, "--format", "json"], capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip()[:300] or f"exit {out.returncode}")
    return json.loads(out.stdout)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--skip-ids", type=Path, help="file with LinkedIn ids already in the feed, one per line")
    ap.add_argument("--max", type=int, default=20, help="max detail fetches")
    ap.add_argument("--days", type=int, default=1, choices=[1, 7, 14, 30])
    a = ap.parse_args(argv)

    skip = set(a.skip_ids.read_text().split()) if a.skip_ids and a.skip_ids.exists() else set()
    cards, errors, seen_titles = {}, [], set()
    for q, loc, remote in SEARCHES:
        args = ["search", "-q", q, "-l", loc, "--jobage", str(a.days), "--limit", "25"]
        if remote:
            args += ["--remote", remote]
        try:
            for c in cli(*args).get("results", []):
                # the same posting is often listed once per city: keep the first
                key = ((c.get("title") or "").strip().lower(), (c.get("company") or "").strip().lower())
                if c["id"] in skip or c["id"] in cards or key in seen_titles or SENIOR_RE.search(c.get("title") or ""):
                    continue
                seen_titles.add(key)
                cards[c["id"]] = c
        except Exception as e:  # one failed query must not sink the run
            errors.append(f"{q} @ {loc}: {e}")

    items = []
    for c in list(cards.values())[: a.max]:
        time.sleep(1.5)
        try:
            d = cli("detail", c["id"])
        except Exception as e:
            errors.append(f"detail {c['id']}: {e}")
            continue
        if d.get("isActive") is False or not d.get("description"):
            continue
        text, findings = guard(d["description"], "text")
        items.append({
            "id": c["id"],
            "titulo": c.get("title") or "",
            "empresa": c.get("company") or "",
            "local": c.get("location") or "",
            "data": c.get("date") or "",
            "url": c.get("url") or d.get("url") or "",
            "senioridade": d.get("seniority") or "",
            "tipo": d.get("employmentType") or "",
            "descricao": text[:8000],
            "guard": findings["verdict"],
        })

    a.out.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"linkedin_feed: {len(cards)} new cards, {len(items)} with full text -> {a.out}")
    for e in errors:
        print("linkedin_feed: warning:", e, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
