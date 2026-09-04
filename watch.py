#!/usr/bin/env python3
"""
career-watch — figyeli a megadott cégek karrierportáljait, és e-mailt küld,
amint új pozíció jelenik meg, ami megfelel a szűrőknek.

Használat:
    python watch.py                 # teljes futás (ez megy időzítve)
    python watch.py --dry-run       # lekér + szűr, de nem küld e-mailt és nem ír state-et
    python watch.py --only "Cégnév" # csak egy céget néz (teszteléshez)
    python watch.py --seed          # első futás: mindent "látottnak" jelöl, nem küld e-mailt
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

import adapters
from notify import send_email

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "companies.yml"
STATE_PATH = ROOT / "state.json"


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------

def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"seen": {}}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# --------------------------------------------------------------------------
# Szűrés
# --------------------------------------------------------------------------

def matches(job: adapters.Job, f: dict) -> bool:
    """A szűrő a cím + a helyszín szövegén dolgozik, kisbetűsítve."""
    hay = f"{job.title} {job.location}".lower()

    exclude = [w.lower() for w in f.get("exclude_keywords", [])]
    if any(w in hay for w in exclude):
        return False

    include = [w.lower() for w in f.get("include_keywords", [])]
    if include and not any(w in hay for w in include):
        return False

    locs = [w.lower() for w in f.get("locations", [])]
    if locs:
        if job.location:
            if not _loc_match(job.location.lower(), locs):
                return False
        elif f.get("strict_location"):
            # globális portáloknál: ha nincs külön helyszín-mező, a címben
            # KELL szerepelnie egy svájci helynek, különben kiesik
            if not _loc_match(hay, locs):
                return False

    return True


def _loc_match(text: str, locs: list) -> bool:
    """Helyszín-kulcsszó SZÓHATÁRRAL — hogy a 'gland' ne találjon az 'England'-re,
    a 'sion' a 'Division'-re, a 'chur' a 'Church'-re. A 'ch' országkódot is érti."""
    for w in locs:
        if re.search(r"(?<![a-z\u00e0-\u00ff])" + re.escape(w) + r"(?![a-z\u00e0-\u00ff])", text):
            return True
    # országkód: "Gland, CH", "Zurich (CH)", "CH-8001"
    return re.search(r"(?<![a-z])ch(?![a-z])", text) is not None


def merged_filters(global_f: dict, entry: dict) -> dict:
    """A cégnél megadott szűrő felülírja a globálisat (kulcsonként)."""
    out = dict(global_f or {})
    out.update(entry.get("filters") or {})
    return out


# --------------------------------------------------------------------------
# Fő logika
# --------------------------------------------------------------------------

def run(dry_run=False, only=None, seed=False) -> int:
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    companies = cfg.get("companies", [])
    global_filters = cfg.get("filters", {})

    if only:
        companies = [c for c in companies if only.lower() in c["name"].lower()]
        if not companies:
            print(f"Nincs ilyen cég a configban: {only}")
            return 1

    state = load_state()
    seen: dict = state.setdefault("seen", {})

    new_jobs: list[adapters.Job] = []
    errors: list[str] = []

    for entry in companies:
        name = entry["name"]
        if entry.get("enabled") is False:
            continue
        try:
            jobs = adapters.fetch(entry)
        except Exception as e:
            errors.append(f"{name}: {type(e).__name__}: {e}")
            print(f"  ! {name}: {type(e).__name__}: {e}", file=sys.stderr)
            continue

        f = merged_filters(global_filters, entry)
        kept = [j for j in jobs if matches(j, f)]
        fresh = [j for j in kept if j.uid not in seen]

        print(f"  {name}: {len(jobs)} pozíció, {len(kept)} illeszkedik, {len(fresh)} új")
        for j in fresh:
            print(f"      + {j.title} — {j.location or '?'}")

        new_jobs.extend(fresh)
        # MINDEN illeszkedő pozíciót elmentünk látottként, nem csak az újakat
        for j in kept:
            seen.setdefault(j.uid, {
                "company": j.company,
                "title": j.title,
                "url": j.url,
                "first_seen": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            })

    if errors:
        print(f"\n{len(errors)} cégnél hiba volt (lásd fent).", file=sys.stderr)

    if seed:
        save_state(state)
        print(f"\nSeed kész: {len(seen)} pozíció elmentve látottként. E-mail nem ment ki.")
        return 0

    if new_jobs:
        print(f"\n{len(new_jobs)} ÚJ pozíció.")
        if not dry_run:
            send_email(new_jobs)
            print("E-mail elküldve.")
    else:
        print("\nNincs új pozíció.")

    if not dry_run:
        save_state(state)

    return 0


def doctor() -> int:
    """Végigpróbálja az összes céget, és kiír egy állapottáblázatot."""
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    companies = [c for c in cfg.get("companies", []) if c.get("enabled") is not False]
    global_filters = cfg.get("filters", {})

    print(f"\n{len(companies)} cég ellenőrzése...\n")
    print(f"{'':2} {'CÉG':32} {'TÍPUS':14} {'TALÁLT':>7} {'ILLESZK.':>9}  MEGJEGYZÉS")
    print("-" * 96)

    ok = broken = 0
    for entry in companies:
        name = entry["name"][:32]
        kind = entry.get("type", "html")
        try:
            jobs = adapters.fetch(entry)
        except Exception as e:
            print(f"{'✗':2} {name:32} {kind:14} {'-':>7} {'-':>9}  {type(e).__name__}: {str(e)[:40]}")
            broken += 1
            continue

        f = merged_filters(global_filters, entry)
        kept = [j for j in jobs if matches(j, f)]

        if not jobs:
            mark, note = "!", "0 pozíció - lehet valós, de ellenőrizd"
            broken += 1
        else:
            mark, note = "✓", ""
            ok += 1
            if kept:
                note = f"pl. {kept[0].title[:38]}"
        print(f"{mark:2} {name:32} {kind:14} {len(jobs):>7} {len(kept):>9}  {note}")

    print("-" * 96)
    print(f"\n✓ {ok} működik   ✗/! {broken} igényel figyelmet\n")
    print("Az '✓' oszlop a lényeg. Ha valahol ✗ vagy ! van, másold ki ezt a")
    print("táblázatot — abból pontosan látszik, mit kell javítani.\n")
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--doctor", action="store_true", help="minden cég tesztelése, állapottáblázat")
    p.add_argument("--dry-run", action="store_true", help="ne küldjön e-mailt, ne írjon state-et")
    p.add_argument("--only", help="csak egy cég (részleges név)")
    p.add_argument("--seed", action="store_true", help="első futás: minden meglévőt látottnak jelöl")
    args = p.parse_args()
    if args.doctor:
        sys.exit(doctor())
    sys.exit(run(dry_run=args.dry_run, only=args.only, seed=args.seed))


if __name__ == "__main__":
    main()
