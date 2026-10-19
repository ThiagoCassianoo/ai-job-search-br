#!/usr/bin/env python3
"""Daily LinkedIn collector for the Radar de Vagas feed.

Runs the linkedin-search CLI for a fixed set of queries, drops senior/intern
titles and postings already in the feed, fetches the full description of the
survivors, cleans each one with posting_guard, applies the candidate's hard
filters, and writes a JSON list the scheduled session scores and pushes to the
Radar's `feed` collection.

Hard filters live here, in code, not in the scoring prompt: LinkedIn's own
"remote" filter lets through on-site jobs in other cities, so the workplace
type is read from the description itself. A posting that is on-site or hybrid
outside Espírito Santo is dropped before any model sees it; a posting that
requires English above basic is kept but flagged, for the scorer to cap.

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

# (query, location, remote filter or None). "remoto" in the keywords narrows
# better than LinkedIn's remote filter alone; the ES searches take any
# workplace type, since Grande Vitória is in commuting range.
SEARCHES = [
    ("analista de dados remoto", "Brazil", "remote"),
    ("analista de BI remoto", "Brazil", "remote"),
    ("engenheiro de dados remoto", "Brazil", "remote"),
    ("power bi remoto", "Brazil", "remote"),
    ("analista de dados", "Espírito Santo, Brazil", None),
    ("analista de BI", "Espírito Santo, Brazil", None),
    ("analista de processos", "Espírito Santo, Brazil", None),
]

SENIOR_RE = re.compile(r"\b(s[eê]nior|sr\.?|especialista|lead|principal|staff|coordenador|gerente|head|manager|est[aá]gi\w*|trainee|intern)\b", re.I)
REMOTE_RE = re.compile(r"100\s*%\s*remot|\b(remoto|remota|trabalho remoto|teletrabalho|home[\s-]?office|fully remote|remote[\s-]?first|work from anywhere)\b", re.I)
# Seniority stated only in the body ("Nível: Sênior"), which the title filter cannot see.
SENIOR_BODY_RE = re.compile(r"\bn[ií]vel\s*:?\s*(s[eê]nior|especialista)\b|\bseniority\s*:?\s*senior\b", re.I)
HYBRID_RE = re.compile(r"\b(h[ií]brid[oa]|hybrid)\b", re.I)
ONSITE_RE = re.compile(r"\b(presencia(l|is)|on[\s-]?site|in[\s-]?office)\b", re.I)
ES_RE = re.compile(r"esp[ií]rito santo", re.I)
ENGLISH_REQ_RE = re.compile(
    r"ingl[eê]s\s*(:|-)?\s*(fluente|avan[cç]ado|intermedi[aá]rio|conversa[cç][aã]o|t[eé]cnico avan[cç]ado)"
    r"|(fluent|advanced|upper[\s-]intermediate|proficient)\s+(in\s+)?english"
    r"|english\s*(:|-)?\s*(fluent|advanced|fluency|proficiency|c1|c2|b2)",
    re.I,
)
EN_WORDS = re.compile(r"\b(the|and|with|you|will|our|for|we|are|experience)\b", re.I)
PT_WORDS = re.compile(r"\b(de|e|com|você|para|nossa|nosso|experiência|em|dados)\b", re.I)


def dedupe_key(card: dict) -> tuple:
    """The same posting is often listed once per city: title + company identify it."""
    return ((card.get("title") or "").strip().lower(), (card.get("company") or "").strip().lower())


def excluded_title(title: str) -> bool:
    return bool(SENIOR_RE.search(title or ""))


def detect_modality(text: str) -> str:
    """remoto | hibrido | presencial | indefinido, read from the description.

    Explicit on-site or hybrid wording wins over a passing "remoto" (e.g.
    "não é remoto"); both at once is ambiguous, so it stays undecided.
    """
    remote, hybrid, onsite = (bool(r.search(text or "")) for r in (REMOTE_RE, HYBRID_RE, ONSITE_RE))
    if hybrid and not remote:
        return "hibrido"
    if onsite and not remote and not hybrid:
        return "presencial"
    if remote and not onsite and not hybrid:
        return "remoto"
    return "indefinido"


def in_es(location: str) -> bool:
    return bool(ES_RE.search(location or ""))


def mostly_english(text: str) -> bool:
    en, pt = len(EN_WORDS.findall(text or "")), len(PT_WORDS.findall(text or ""))
    return en >= 15 and en > 2 * pt


def requires_english(text: str) -> bool:
    return bool(ENGLISH_REQ_RE.search(text or "")) or mostly_english(text)


def hard_filter(location: str, text: str) -> tuple:
    """(keep, modality, english_required). Drops only what the profile rules out:
    on-site or hybrid work outside Espírito Santo means moving city, and a
    senior level stated in the body is outside the Júnior/Pleno target."""
    modality = detect_modality(text)
    moves_city = modality in ("presencial", "hibrido") and not in_es(location)
    keep = not moves_city and not SENIOR_BODY_RE.search(text or "")
    return keep, modality, requires_english(text)


def cli(*args: str) -> dict:
    out = subprocess.run(["bun", "run", str(CLI), *args, "--format", "json"], capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip()[:300] or f"exit {out.returncode}")
    return json.loads(out.stdout)


def collect_cards(days: int, skip: set, errors: list) -> dict:
    cards, seen = {}, set()
    for q, loc, remote in SEARCHES:
        args = ["search", "-q", q, "-l", loc, "--jobage", str(days), "--limit", "25"]
        if remote:
            args += ["--remote", remote]
        try:
            for c in cli(*args).get("results", []):
                key = dedupe_key(c)
                if c["id"] in skip or c["id"] in cards or key in seen or excluded_title(c.get("title")):
                    continue
                seen.add(key)
                cards[c["id"]] = c
        except Exception as e:  # one failed query must not sink the run
            errors.append(f"{q} @ {loc}: {e}")
    return cards


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--skip-ids", type=Path, help="file with LinkedIn ids already in the feed, one per line")
    ap.add_argument("--max", type=int, default=20, help="max postings kept after the hard filter")
    ap.add_argument("--days", type=int, default=1, choices=[1, 7, 14, 30])
    a = ap.parse_args(argv)

    skip = set(a.skip_ids.read_text().split()) if a.skip_ids and a.skip_ids.exists() else set()
    errors: list = []
    cards = collect_cards(a.days, skip, errors)

    items, dropped, fetched = [], 0, 0
    for c in cards.values():
        if len(items) >= a.max or fetched >= a.max * 2:  # cap LinkedIn traffic, not just output
            break
        time.sleep(1.5)
        fetched += 1
        try:
            d = cli("detail", c["id"])
        except Exception as e:
            errors.append(f"detail {c['id']}: {e}")
            continue
        if d.get("isActive") is False or not d.get("description"):
            continue
        text, findings = guard(d["description"], "text")
        keep, modality, english = hard_filter(c.get("location") or "", text)
        if not keep:
            dropped += 1
            continue
        items.append({
            "id": c["id"],
            "titulo": c.get("title") or "",
            "empresa": c.get("company") or "",
            "local": c.get("location") or "",
            "data": c.get("date") or "",
            "url": c.get("url") or d.get("url") or "",
            "senioridade": d.get("seniority") or "",
            "tipo": d.get("employmentType") or "",
            "modalidade": modality,
            "ingles_exigido": english,
            "descricao": text[:8000],
            "guard": findings["verdict"],
        })

    a.out.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"linkedin_feed: {len(cards)} new cards, {fetched} read, {dropped} dropped (on-site/hybrid outside ES), {len(items)} kept -> {a.out}")
    for e in errors:
        print("linkedin_feed: warning:", e, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
