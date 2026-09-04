#!/usr/bin/env python3
"""
probe.py — kitalálja, melyik ATS-t használja egy cég karrieroldala,
és kiírja a kész companies.yml blokkot.

    python probe.py https://www.valamibank.ch/karriere
    python probe.py https://www.valamibank.ch/karriere --name "Valami Bank AG"
"""

from __future__ import annotations

import argparse
import re
import sys
from urllib.parse import urlparse

import requests

import adapters

# Az oldal HTML-jében keresett ujjlenyomatok -> (típus, token kinyerő regex)
FINGERPRINTS = [
    ("greenhouse", r"boards\.greenhouse\.io/(?:embed/job_board\?for=)?([a-z0-9_-]+)"),
    ("greenhouse", r"job-boards\.greenhouse\.io/([a-z0-9_-]+)"),
    ("lever", r"jobs\.lever\.co/([a-z0-9_-]+)"),
    ("ashby", r"jobs\.ashbyhq\.com/([a-z0-9_.-]+)"),
    ("smartrecruiters", r"jobs\.smartrecruiters\.com/([A-Za-z0-9_-]+)"),
    ("smartrecruiters", r"careers\.smartrecruiters\.com/([A-Za-z0-9_-]+)"),
    ("workable", r"apply\.workable\.com/([a-z0-9_-]+)"),
    ("workable", r"([a-z0-9_-]+)\.workable\.com"),
    ("personio", r"([a-z0-9_-]+)\.jobs\.personio\.(?:de|com)"),
    ("recruitee", r"([a-z0-9_-]+)\.recruitee\.com"),
]


def probe(url: str, name: str | None = None) -> None:
    company = name or urlparse(url).netloc.replace("www.", "")

    try:
        r = requests.get(url, headers=adapters.HEADERS, timeout=adapters.TIMEOUT)
        r.raise_for_status()
    except Exception as e:
        print(f"Nem sikerült letölteni: {type(e).__name__}: {e}")
        return

    body = r.text
    hits = []
    for kind, pattern in FINGERPRINTS:
        for m in re.finditer(pattern, body, re.I):
            token = m.group(1)
            if (kind, token) not in hits:
                hits.append((kind, token))

    if not hits:
        print(f"# Nem találtam ismert ATS-t a(z) {url} oldalon.")
        print("# Használd a html adaptert, és nézd meg mit talál:\n")
        print(_block(company, "html", url=url))
        _try_it({"name": company, "type": "html", "url": url})
        return

    print(f"# {len(hits)} lehetséges találat a(z) {url} oldalon:\n")
    for kind, token in hits:
        print(_block(company, kind, token=token))
        _try_it({"name": company, "type": kind, "token": token})
        print()


def _block(company: str, kind: str, token: str = "", url: str = "") -> str:
    lines = [f'  - name: "{company}"', f"    type: {kind}"]
    if token:
        lines.append(f'    token: "{token}"')
    if url:
        lines.append(f'    url: "{url}"')
    return "\n".join(lines)


def _try_it(entry: dict) -> None:
    """Rögtön le is próbáljuk, hogy tényleg jönnek-e pozíciók."""
    try:
        jobs = adapters.fetch(entry)
    except Exception as e:
        print(f"    # -> nem működik: {type(e).__name__}")
        return
    print(f"    # -> MŰKÖDIK, {len(jobs)} pozíciót talált. Például:")
    for j in jobs[:4]:
        print(f"    #    {j.title} ({j.location or '?'})")


WD_HOSTS = ["wd1", "wd2", "wd3", "wd5", "wd8", "wd10", "wd12"]
WD_SITES = [
    "External", "Careers", "External_Careers", "ExternalCareerSite",
    "Global", "Professional", "Experienced", "Jobs", "careers", "External_Site",
    "Internships", "Campus",
]


def workday_scan(tenant: str, name: str | None = None, quick: bool = False,
                 quiet: bool = False) -> int:
    """
    Végigpróbálja a Workday host/oldal kombinációkat egy cégnévre.

    Például:  python probe.py --workday juliusbaer
    """
    company = name or tenant
    hosts = WD_HOSTS[:4] if quick else WD_HOSTS
    sites = WD_SITES[:5] if quick else WD_SITES
    if not quiet:
        print(f"# Workday keresés: {tenant}\n")
    found = 0
    for wd in hosts:
        for site in sites:
            token = f"{tenant}/{wd}/{site}"
            try:
                jobs = adapters.workday(company, token)
            except Exception:
                continue
            if not jobs:
                continue
            found += 1
            print(f'  - name: "{company}"')
            print(f"    type: workday")
            print(f'    token: "{token}"')
            print(f"    # -> {len(jobs)} pozíció. Például: {jobs[0].title}")
            print()
    if not found and not quiet:
        print(f"# Nem találtam működő Workday-oldalt '{tenant}' néven.")
        print("# Próbáld más írásmóddal (pl. szóköz és kötőjel nélkül, csak kisbetűvel),")
        print("# vagy nézd meg a cég karrieroldalán, hova mutat a 'Bewerben' gomb.")
    return found


def workday_batch(path: str) -> None:
    """Sok cégazonosítót próbál végig egy fájlból, és csak a találatokat írja ki."""
    names = [l.strip() for l in open(path, encoding="utf-8")]
    names = [n for n in names if n and not n.startswith("#")]

    print(f"# {len(names)} cégazonosító ellenőrzése. Ez pár percig tart.")
    print("# Csak a MŰKÖDŐ találatok jelennek meg — másold be őket a companies.yml-be.\n")
    print("companies:")

    hits = 0
    for i, tenant in enumerate(names, 1):
        print(f"# [{i}/{len(names)}] {tenant} ...", file=sys.stderr)
        hits += workday_scan(tenant, quiet=True, quick=True)

    print(f"\n# Kész: {hits} működő találat {len(names)} próbálkozásból.", file=sys.stderr)
    if hits == 0:
        print("# Egy találat sem volt. A cégek valószínűleg más rendszert használnak —",
              file=sys.stderr)
        print("# ilyenkor a karrieroldal URL-jével próbáld: python probe.py <url>",
              file=sys.stderr)


def batch(path: str) -> None:
    """Fájlból olvas: soronként egy URL, vagy 'Cégnév | URL'."""
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            nm, url = [x.strip() for x in line.split("|", 1)]
        else:
            nm, url = None, line
        print(f"\n{'='*70}\n# {nm or url}\n{'='*70}")
        probe(url, nm)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("url", nargs="?", help="a cég karrieroldalának URL-je")
    p.add_argument("--name", help="a cég neve a configban")
    p.add_argument("--workday", help="Workday cégazonosító keresése, pl. juliusbaer")
    p.add_argument("--batch", help="fájl, soronként egy URL vagy 'Cégnév | URL'")
    p.add_argument("--workday-batch", dest="workday_batch",
                   help="fájl cégazonosítókkal, soronként egy (pl. banks.txt)")
    args = p.parse_args()

    if args.workday_batch:
        workday_batch(args.workday_batch)
    elif args.workday:
        workday_scan(args.workday, args.name)
    elif args.batch:
        batch(args.batch)
    elif args.url:
        probe(args.url, args.name)
    else:
        p.error("adj meg egy URL-t, vagy használd a --workday / --batch kapcsolót")


if __name__ == "__main__":
    main()
