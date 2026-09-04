#!/usr/bin/env python3
"""
discover.py — végigmegy a svájci bankok listáján, megkeresi a karrieroldalukat,
kitalálja, milyen rendszert (ATS) használnak, és le is teszteli.

Kimenet:
    discover_report.txt   — részletes napló (mit talált, mi működik)
    discover_found.yml    — a MŰKÖDŐ config-blokkok, bemásolhatók a companies.yml-be

Futtatás (a Macen, a career-watch mappában):
    ./.venv/bin/python discover.py
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import re
import sys
import time
from collections import Counter, defaultdict
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import adapters

TIMEOUT = 15
H = adapters.HEADERS

# ---------------------------------------------------------------------------
# BANKOK  (név, jelölt URL-ek). Az első, ami betölt, számít.
# ---------------------------------------------------------------------------
BANKS = [
    # --- nagybankok / állami / kantonális ---
    ("Raiffeisen Schweiz", ["https://www.raiffeisen.ch/rch/de/ueber-uns/karriere.html", "https://www.raiffeisen.ch/"]),
    ("Zürcher Kantonalbank", ["https://www.zkb.ch/de/karriere.html", "https://www.zkb.ch/"]),
    ("PostFinance", ["https://www.postfinance.ch/de/ueber-uns/karriere.html", "https://www.postfinance.ch/"]),
    ("Migros Bank", ["https://www.migrosbank.ch/de/ueber-uns/karriere.html", "https://www.migrosbank.ch/"]),
    ("Bank Cler", ["https://www.cler.ch/de/karriere", "https://www.cler.ch/"]),
    ("Basler Kantonalbank", ["https://www.bkb.ch/de/karriere", "https://www.bkb.ch/"]),
    ("Basellandschaftliche Kantonalbank", ["https://www.blkb.ch/karriere", "https://www.blkb.ch/"]),
    ("Banque Cantonale Vaudoise", ["https://www.bcv.ch/en/careers", "https://www.bcv.ch/"]),
    ("Banque Cantonale de Genève", ["https://www.bcge.ch/en/careers", "https://www.bcge.ch/"]),
    ("Berner Kantonalbank", ["https://www.bekb.ch/karriere", "https://www.bekb.ch/"]),
    ("Luzerner Kantonalbank", ["https://www.lukb.ch/karriere", "https://www.lukb.ch/"]),
    ("St.Galler Kantonalbank", ["https://www.sgkb.ch/karriere", "https://www.sgkb.ch/"]),
    ("Thurgauer Kantonalbank", ["https://www.tkb.ch/karriere", "https://www.tkb.ch/"]),
    ("Graubündner Kantonalbank", ["https://www.gkb.ch/karriere", "https://www.gkb.ch/"]),
    ("Aargauische Kantonalbank", ["https://www.akb.ch/karriere", "https://www.akb.ch/"]),
    ("Zuger Kantonalbank", ["https://www.zugerkb.ch/karriere", "https://www.zugerkb.ch/"]),
    ("Schwyzer Kantonalbank", ["https://www.szkb.ch/karriere", "https://www.szkb.ch/"]),
    ("Glarner Kantonalbank", ["https://www.glkb.ch/karriere", "https://www.glkb.ch/"]),
    ("Nidwaldner Kantonalbank", ["https://www.nkb.ch/karriere", "https://www.nkb.ch/"]),
    ("Obwaldner Kantonalbank", ["https://www.owkb.ch/karriere", "https://www.owkb.ch/"]),
    ("Urner Kantonalbank", ["https://www.ukb.ch/karriere", "https://www.ukb.ch/"]),
    ("Schaffhauser Kantonalbank", ["https://www.shkb.ch/karriere", "https://www.shkb.ch/"]),
    ("Appenzeller Kantonalbank", ["https://www.appkb.ch/karriere", "https://www.appkb.ch/"]),
    ("Banque Cantonale de Fribourg", ["https://www.bcf.ch/de/karriere", "https://www.bcf.ch/"]),
    ("Banque Cantonale Neuchâteloise", ["https://www.bcn.ch/carrieres", "https://www.bcn.ch/"]),
    ("Banque Cantonale du Jura", ["https://www.bcj.ch/", ]),
    ("Banque Cantonale du Valais", ["https://www.bcvs.ch/de/karriere", "https://www.bcvs.ch/"]),
    ("BancaStato Ticino", ["https://www.bancastato.ch/", ]),
    ("Valiant", ["https://www.valiant.ch/de/karriere", "https://www.valiant.ch/"]),
    ("Cembra Money Bank", ["https://www.cembra.ch/de/karriere", "https://www.cembra.ch/"]),
    ("Bank WIR", ["https://www.wir.ch/karriere", "https://www.wir.ch/"]),
    ("Alternative Bank Schweiz", ["https://www.abs.ch/de/karriere", "https://www.abs.ch/"]),
    ("Hypothekarbank Lenzburg", ["https://www.hbl.ch/karriere", "https://www.hbl.ch/"]),
    ("Bank Avera", ["https://www.bankavera.ch/karriere", "https://www.bankavera.ch/"]),
    ("Bank Linth", ["https://www.banklinth.ch/karriere", "https://www.banklinth.ch/"]),
    ("Clientis", ["https://www.clientis.ch/karriere", "https://www.clientis.ch/"]),
    ("Regiobank Solothurn", ["https://www.regiobank.ch/karriere", "https://www.regiobank.ch/"]),
    ("acrevis Bank", ["https://www.acrevis.ch/karriere", "https://www.acrevis.ch/"]),
    ("Bank Thalwil", ["https://www.bankthalwil.ch/karriere", "https://www.bankthalwil.ch/"]),
    ("Sparkasse Schwyz", ["https://www.sparkasse.ch/", ]),
    ("Bank EEK", ["https://www.eek.ch/", ]),
    ("Bank CIC (Schweiz)", ["https://www.cic.ch/de/karriere", "https://www.cic.ch/"]),
    ("Habib Bank Zürich", ["https://www.habibbank.com/", ]),
    ("Zürcher Landbank", ["https://www.zlb.ch/", ]),
    ("Bank Zimmerberg", ["https://www.bankzimmerberg.ch/", ]),
    ("AEK Bank 1826", ["https://www.aekbank.ch/", ]),
    ("Bank SLM", ["https://www.bankslm.ch/", ]),
    ("Baloise Bank", ["https://www.baloise.ch/de/ueber-uns/karriere.html", "https://www.baloise.com/"]),
    ("Liechtensteinische Landesbank", ["https://www.llb.li/de/karriere", "https://www.llb.li/"]),
    ("Bank Frick", ["https://www.bankfrick.li/de/karriere", "https://www.bankfrick.li/"]),
    ("LGT", ["https://www.lgt.com/global-en/about-us/career", "https://www.lgt.com/"]),
    ("VP Bank", ["https://www.vpbank.com/en/careers", "https://www.vpbank.com/"]),
    # --- privátbankok / vagyonkezelők ---
    ("Pictet", ["https://www.pictet.com/ch/en/careers"]),
    ("Lombard Odier", ["https://www.lombardodier.com/careers", "https://www.lombardodier.com/"]),
    ("EFG International", ["https://www.efginternational.com/careers.html", "https://www.efginternational.com/"]),
    ("Union Bancaire Privée", ["https://www.ubp.com/en/careers", "https://www.ubp.com/"]),
    ("Mirabaud", ["https://www.mirabaud.com/en/careers", "https://www.mirabaud.com/"]),
    ("J. Safra Sarasin", ["https://www.jsafrasarasin.com/content/jsafrasarasin/language-masters/en/careers.html", "https://www.jsafrasarasin.com/"]),
    ("Bergos", ["https://www.bergos.ch/karriere", "https://www.bergos.ch/"]),
    ("Rahn+Bodmer", ["https://www.rahnbodmer.ch/karriere", "https://www.rahnbodmer.ch/"]),
    ("Reichmuth & Co", ["https://www.reichmuthco.ch/karriere", "https://www.reichmuthco.ch/"]),
    ("Banque Syz", ["https://www.syzgroup.com/en/careers", "https://www.syzgroup.com/"]),
    ("Bordier & Cie", ["https://www.bordier.com/en/careers", "https://www.bordier.com/"]),
    ("Gonet & Cie", ["https://www.gonet.ch/", ]),
    ("Piguet Galland", ["https://www.piguetgalland.ch/", ]),
    ("REYL Intesa Sanpaolo", ["https://www.reyl.com/en/careers", "https://www.reyl.com/"]),
    ("Banque Cramer", ["https://www.banquecramer.ch/", ]),
    ("ONE swiss bank", ["https://www.oneswissbank.com/", ]),
    ("Maerki Baumann", ["https://www.maerki-baumann.ch/de/karriere", "https://www.maerki-baumann.ch/"]),
    ("Privatbank Von Graffenried", ["https://www.graffenried.ch/", ]),
    ("Globalance", ["https://www.globalance.com/", ]),
    ("Lienhardt & Partner", ["https://www.lienhardt.ch/", ]),
    ("Edmond de Rothschild", ["https://www.edmond-de-rothschild.com/en/careers", "https://www.edmond-de-rothschild.com/"]),
    ("Rothschild & Co", ["https://www.rothschildandco.com/en/careers/", "https://www.rothschildandco.com/"]),
    ("Banque Heritage", ["https://www.heritage.ch/", ]),
    ("CBH Compagnie Bancaire Helvétique", ["https://www.cbhbank.com/", ]),
    ("Hyposwiss Private Bank", ["https://www.hyposwiss.ch/", ]),
    ("Arab Bank (Switzerland)", ["https://www.arabbank.ch/", ]),
    ("Bank Audi (Suisse)", ["https://www.bankaudi.ch/", ]),
    ("Baumann & Cie", ["https://www.baumann-banquiers.ch/", ]),
    ("Zähringer Privatbank", ["https://www.zaehringerprivatbank.ch/", ]),
    ("Aquila", ["https://www.aquila.ch/", ]),
    ("Banque Eric Sturdza", ["https://www.banque-es.ch/", ]),
    ("Banque Thaler", ["https://www.banquethaler.com/", ]),
    ("Bank von Roll", ["https://www.bankvonroll.ch/", ]),
    ("Privatbank IHAG", ["https://www.ihag.ch/", ]),
    ("Scobag Privatbank", ["https://www.scobag.ch/", ]),
    ("Trafina Privatbank", ["https://www.trafina.ch/", ]),
    ("Bank Sparhafen", ["https://www.sparhafen.ch/", ]),
    ("Dreyfus Söhne & Cie", ["https://www.dreyfusbank.ch/", ]),
    ("E. Gutzwiller & Cie", ["https://www.gutzwiller.ch/", ]),
    ("Frankfurter Bankgesellschaft (Schweiz)", ["https://www.frankfurter-bankgesellschaft.com/", ]),
    ("Bellevue Group", ["https://www.bellevue.ch/en/careers", "https://www.bellevue.ch/"]),
    ("Swissquote", ["https://en.swissquote.com/careers", "https://www.swissquote.com/"]),
    ("Leonteq", ["https://www.leonteq.com/careers", "https://www.leonteq.com/"]),
    ("Partners Group", ["https://www.partnersgroup.com/en/careers/", "https://www.partnersgroup.com/"]),
    ("GAM", ["https://www.gam.com/en/careers", "https://www.gam.com/"]),
    ("Fisch Asset Management", ["https://www.fam.ch/", ]),
    ("SIX Group", ["https://www.six-group.com/en/company/career.html", "https://www.six-group.com/"]),
    ("Zurich Insurance", ["https://www.zurich.com/careers", "https://www.zurich.com/"]),
    ("Swiss Re", ["https://www.swissre.com/careers.html", "https://www.swissre.com/"]),
    ("Swiss Life", ["https://www.swisslife.com/en/home/career.html", "https://www.swisslife.com/"]),
    # --- nemzetközi bankok svájci jelenléttel ---
    ("JPMorgan", ["https://careers.jpmorgan.com/global/en/home", "https://www.jpmorgan.com/"]),
    ("Goldman Sachs", ["https://www.goldmansachs.com/careers/", "https://higher.gs.com/"]),
    ("Morgan Stanley", ["https://www.morganstanley.com/careers", "https://www.morganstanley.com/"]),
    ("Bank of America", ["https://careers.bankofamerica.com/en-us", "https://www.bankofamerica.com/"]),
    ("Deutsche Bank", ["https://careers.db.com/", "https://www.db.com/"]),
    ("BNP Paribas", ["https://group.bnpparibas/en/careers", "https://group.bnpparibas/"]),
    ("HSBC", ["https://www.hsbc.com/careers", "https://www.hsbc.com/"]),
    ("Barclays", ["https://home.barclays/careers/", "https://search.jobs.barclays/"]),
    ("Société Générale", ["https://careers.societegenerale.com/en", "https://www.societegenerale.com/"]),
    ("Indosuez Wealth Management", ["https://ca-indosuez.com/en/careers", "https://ca-indosuez.com/"]),
    ("Nomura", ["https://www.nomura.com/careers/", "https://www.nomura.com/"]),
    ("Standard Chartered", ["https://www.sc.com/en/careers/", "https://www.sc.com/"]),
    ("BlackRock", ["https://careers.blackrock.com/", "https://www.blackrock.com/"]),
    ("BNY", ["https://www.bny.com/corporate/global/en/careers.html", "https://www.bny.com/"]),
    ("Northern Trust", ["https://www.northerntrust.com/careers", "https://www.northerntrust.com/"]),
    ("Schroders", ["https://www.schroders.com/en/global/individual/careers/", "https://www.schroders.com/"]),
    ("Fidelity International", ["https://careers.fidelityinternational.com/", "https://www.fidelityinternational.com/"]),
    ("PIMCO", ["https://www.pimco.com/en-us/careers", "https://www.pimco.com/"]),
    ("Man Group", ["https://www.man.com/careers", "https://www.man.com/"]),
    ("Lazard", ["https://www.lazard.com/careers/", "https://www.lazard.com/"]),
    ("Rothschild & Co (Bank)", ["https://www.rothschildandco.com/en/careers/", ]),
    ("Wellershoff & Partners", ["https://www.wellershoff.ch/", ]),
    ("Quintet Private Bank", ["https://www.quintet.com/en-gb/careers", "https://www.quintet.com/"]),
    ("Banque Internationale à Luxembourg (Suisse)", ["https://www.bil.com/en/careers", "https://www.bil.com/"]),
    ("Credit Suisse (UBS)", ["https://www.ubs.com/global/en/careers.html"]),
]

# ---------------------------------------------------------------------------
# ATS-ujjlenyomatok a nyers HTML-ben / linkekben
# ---------------------------------------------------------------------------
WD_RE = re.compile(r"https?://([a-z0-9\-]+)\.(wd\d+)\.myworkdayjobs\.com(?:/[a-z]{2}-[A-Z]{2})?/([A-Za-z0-9_\-]+)", re.I)
WD_HOST_RE = re.compile(r"https?://([a-z0-9\-]+)\.(wd\d+)\.myworkdayjobs\.com", re.I)
SF_RE = re.compile(r"https?://(career\d*\.successfactors\.(?:eu|com))/career\?[^\"'\s]*company=([A-Za-z0-9_\-]+)", re.I)
SR_RE = re.compile(r"(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9_\-]+)", re.I)
GH_RE = re.compile(r"(?:boards|job-boards)\.greenhouse\.io/(?:embed/job_board\?for=)?([a-z0-9_\-]+)", re.I)
LV_RE = re.compile(r"jobs\.lever\.co/([a-z0-9_\-]+)", re.I)
PERS_RE = re.compile(r"https?://([a-z0-9_\-]+)\.jobs\.personio\.(?:de|com)", re.I)
REC_RE = re.compile(r"https?://([a-z0-9_\-]+)\.recruitee\.com", re.I)
WK_RE = re.compile(r"apply\.workable\.com/([a-z0-9_\-]+)", re.I)
ASH_RE = re.compile(r"jobs\.ashbyhq\.com/([a-z0-9_.\-]+)", re.I)
BR_RE = re.compile(r"partnerid=(\d+)&(?:amp;)?siteid=(\d+)", re.I)
ORA_RE = re.compile(r"https?://([a-z0-9\-]+\.fa\.[a-z0-9\-]+\.oraclecloud\.com)/hcmUI/CandidateExperience/[a-z]{2}/sites/([A-Za-z0-9_\-]+)", re.I)
UMANTIS_RE = re.compile(r"https?://([a-z0-9\-]+\.umantis\.com|[a-z0-9.\-]+)/Vacancies", re.I)
OTHER_HOST_RE = re.compile(r"https?://([a-z0-9.\-]*(?:jobs|karriere|career|stellen|recruit|talent|ostendis|prospective|softgarden|onlyfy|jobcloud|phenom|eightfold|icims|taleo|avature|csod|teamtailor|join\.com|jobbase|rexx|dvinci)[a-z0-9.\-]*)", re.I)

CAREER_LINK = re.compile(r"(karriere|career|carri[eè]re|jobs|stellen|arbeiten|working|join-us|lavora|emploi|vacanc|offene|opportunit)", re.I)
JOBLIST_LINK = re.compile(r"(job|vacan|offene|stellen|opportunit|position|search|listing|angebote|offres|posizioni)", re.I)

session = requests.Session()
session.headers.update(H)


def get(url):
    r = session.get(url, timeout=TIMEOUT, allow_redirects=True)
    r.raise_for_status()
    return r


def links_of(html, base):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tag in soup.find_all(["a", "iframe", "link", "script"]):
        href = tag.get("href") or tag.get("src")
        if not href:
            continue
        try:
            out.append((urljoin(base, href), " ".join(tag.get_text(" ", strip=True).split()) if tag.name == "a" else ""))
        except Exception:
            pass
    return out, soup


def same_site(a, b):
    ha = urlparse(a).hostname or ""
    hb = urlparse(b).hostname or ""
    ha = ha.replace("www.", "")
    hb = hb.replace("www.", "")
    return ha == hb or ha.endswith("." + hb) or hb.endswith("." + ha)


def detect(text_blobs: list[str]) -> list[dict]:
    """Ujjlenyomatok keresése — visszaad config-jelölteket."""
    cands, seen = [], set()

    def add(c):
        key = json.dumps(c, sort_keys=True)
        if key not in seen:
            seen.add(key)
            cands.append(c)

    for t in text_blobs:
        for m in WD_RE.finditer(t):
            tenant, wd, site = m.groups()
            if site.lower() in ("wday", "job", "jobs", "login", "en-us", "de-de", "fr-fr", "en-gb"):
                continue
            add({"type": "workday", "token": f"{tenant}/{wd}/{site}"})
        for m in WD_HOST_RE.finditer(t):
            tenant, wd = m.groups()
            add({"type": "workday_host", "token": f"{tenant}/{wd}"})
        for m in SF_RE.finditer(t):
            add({"type": "successfactors", "token": f"{m.group(1)}/{m.group(2)}"})
        for m in SR_RE.finditer(t):
            add({"type": "smartrecruiters", "token": m.group(1)})
        for m in GH_RE.finditer(t):
            add({"type": "greenhouse", "token": m.group(1)})
        for m in LV_RE.finditer(t):
            add({"type": "lever", "token": m.group(1)})
        for m in PERS_RE.finditer(t):
            add({"type": "personio", "token": m.group(1)})
        for m in REC_RE.finditer(t):
            add({"type": "recruitee", "token": m.group(1)})
        for m in WK_RE.finditer(t):
            add({"type": "workable", "token": m.group(1)})
        for m in ASH_RE.finditer(t):
            add({"type": "ashby", "token": m.group(1)})
        for m in BR_RE.finditer(t):
            add({"type": "brassring", "token": f"{m.group(1)}/{m.group(2)}"})
        for m in ORA_RE.finditer(t):
            add({"type": "oraclecloud", "token": f"{m.group(1)}/{m.group(2)}"})
        for m in UMANTIS_RE.finditer(t):
            add({"type": "joblinks", "url": f"https://{m.group(1)}/Vacancies", "link_pattern": r"/Vacancies/\d+"})
    return cands


WD_SITES = ["External", "Careers", "External_Careers", "ExternalCareerSite", "Global", "Professional",
            "Experienced", "Jobs", "careers", "External_Site", "Career", "Career_Site", "ExternalCareers",
            "External_Career_Site", "Job_Board", "en-US", "Search", "job_board", "jobs", "careers-home"]


def workday_sites_for_host(tenant, wd):
    found = []
    for site in WD_SITES:
        try:
            jobs = adapters.workday("x", f"{tenant}/{wd}/{site}")
        except Exception:
            continue
        if jobs:
            found.append((f"{tenant}/{wd}/{site}", jobs))
    return found


def auto_joblinks(url, html, soup):
    """Linkcsoportok keresése egy listaoldalon: melyik útvonal-minta néz ki állásnak."""
    groups = defaultdict(list)
    for a in soup.find_all("a", href=True):
        full = urljoin(url, a["href"])
        if not same_site(full, url) and not OTHER_HOST_RE.search(full):
            continue
        text = " ".join(a.get_text(" ", strip=True).split())
        if not text or len(text) < 6 or len(text) > 120:
            continue
        p = urlparse(full).path.rstrip("/")
        segs = [s for s in p.split("/") if s]
        if not segs:
            continue
        # minta: az utolsó szegmens előtti rész
        prefix = "/" + "/".join(segs[:-1]) + "/" if len(segs) > 1 else "/" + segs[0]
        groups[prefix].append((text, full))
    scored = []
    for prefix, items in groups.items():
        texts = {t for t, _ in items}
        if len(texts) < 3:
            continue
        jobby = sum(1 for t in texts if re.search(r"(manager|analyst|advisor|berater|spezialist|specialist|assistant|associate|officer|praktik|intern|trainee|lehr|leiter|head|expert|consultant|controller|engineer|developer|%|\bm/w|\(m|\bw/m|100%|80)", t, re.I))
        score = len(texts) + 3 * jobby + (5 if re.search(r"(job|stelle|vacan|position|offre|career|karriere)", prefix, re.I) else 0)
        scored.append((score, prefix, sorted(texts)[:4], len(texts)))
    scored.sort(reverse=True)
    return scored[:3]


def try_entry(entry):
    try:
        jobs = adapters.fetch(entry)
        return jobs, None
    except Exception as e:
        return [], f"{type(e).__name__}: {str(e)[:80]}"


def investigate(name, urls):
    log = [f"\n{'=' * 78}\n# {name}\n{'=' * 78}"]
    found = []          # working entries: (entry, jobs)
    blobs = []
    pages = []          # (url, html, soup)

    # 1) betöltjük a jelölt oldalakat
    base_ok = None
    for u in urls:
        try:
            r = get(u)
        except Exception as e:
            log.append(f"  x {u}: {type(e).__name__}")
            continue
        base_ok = r.url
        blobs.append(r.text)
        lk, soup = links_of(r.text, r.url)
        pages.append((r.url, r.text, soup))
        log.append(f"  ok {r.url}  ({len(r.text)//1000} kB)")
        # 2) karrier-szerű belső linkek követése (max 4)
        cands = []
        for full, text in lk:
            if same_site(full, r.url) and (CAREER_LINK.search(urlparse(full).path) or CAREER_LINK.search(text)):
                if full.split("#")[0] != r.url.split("#")[0] and full not in cands:
                    cands.append(full)
        # rövidebb (általánosabb) linkek előre
        cands.sort(key=len)
        for c in cands[:4]:
            try:
                r2 = get(c)
            except Exception:
                continue
            blobs.append(r2.text)
            lk2, soup2 = links_of(r2.text, r2.url)
            pages.append((r2.url, r2.text, soup2))
            log.append(f"     -> {r2.url}")
            # 3) még egy szint: állás-lista-szerű linkek
            sub = [f for f, t in lk2 if JOBLIST_LINK.search(urlparse(f).path + " " + t) and (same_site(f, r2.url) or OTHER_HOST_RE.search(f))]
            for s3 in sorted(set(sub), key=len)[:3]:
                if any(s3 == p[0] for p in pages):
                    continue
                try:
                    r3 = get(s3)
                except Exception:
                    continue
                blobs.append(r3.text)
                lk3, soup3 = links_of(r3.text, r3.url)
                pages.append((r3.url, r3.text, soup3))
                log.append(f"        -> {r3.url}")
        break  # az első működő alap-URL elég

    if not pages:
        log.append("  ! egyik URL sem töltött be")
        return name, log, found

    # 4) ujjlenyomatok
    all_links = "\n".join(u for u, _, _ in pages)
    cands = detect(blobs + [all_links])
    ext_hosts = sorted({m.group(1) for b in blobs for m in OTHER_HOST_RE.finditer(b)
                        if not same_site("https://" + m.group(1), base_ok)})
    if ext_hosts:
        log.append(f"  külső állás-hostok: {', '.join(ext_hosts[:8])}")

    tested = set()
    for c in cands:
        if c["type"] == "workday_host":
            tenant, wd = c["token"].split("/")
            if any(x.get("type") == "workday" and x["token"].startswith(f"{tenant}/{wd}/") for x in cands):
                continue
            for token, jobs in workday_sites_for_host(tenant, wd):
                e = {"name": name, "type": "workday", "token": token}
                found.append((e, jobs))
                log.append(f"  ✓ workday {token}: {len(jobs)} pozíció — pl. {jobs[0].title} ({jobs[0].location})")
            continue
        e = {"name": name, **c}
        key = json.dumps(c, sort_keys=True)
        if key in tested:
            continue
        tested.add(key)
        jobs, err = try_entry(e)
        if jobs:
            found.append((e, jobs))
            log.append(f"  ✓ {c['type']} {c.get('token') or c.get('url')}: {len(jobs)} pozíció — pl. {jobs[0].title} ({jobs[0].location})")
        else:
            log.append(f"  ✗ {c['type']} {c.get('token') or c.get('url')}: {err or '0 pozíció'}")

    # 5) SuccessFactors Career Site Builder gyanú (jobs.xxx / karriere.xxx host)
    for h in ext_hosts + [urlparse(base_ok).hostname]:
        if not h:
            continue
        base = f"https://{h}"
        e = {"name": name, "type": "sfcsb", "url": base}
        if json.dumps(e, sort_keys=True) in tested:
            continue
        tested.add(json.dumps(e, sort_keys=True))
        jobs, err = try_entry(e)
        if jobs:
            found.append((e, jobs))
            log.append(f"  ✓ sfcsb {base}: {len(jobs)} pozíció — pl. {jobs[0].title} ({jobs[0].location})")

    # 6) Workday-tipp a domain nevéből, ha még semmi
    if not found:
        host = (urlparse(base_ok).hostname or "").replace("www.", "")
        tenant = re.sub(r"\.(ch|com|li|net|org|group)$", "", host).split(".")[-1]
        tenant = re.sub(r"[^a-z0-9]", "", tenant.lower())
        if tenant and len(tenant) > 2:
            for wd in ("wd3", "wd1", "wd5", "wd103"):
                hits = workday_sites_for_host(tenant, wd)
                for token, jobs in hits:
                    e = {"name": name, "type": "workday", "token": token}
                    found.append((e, jobs))
                    log.append(f"  ✓ workday (tipp) {token}: {len(jobs)} pozíció — pl. {jobs[0].title}")
                if hits:
                    break

    # 7) automatikus joblinks-minták a betöltött oldalakon
    if not found:
        best = []
        for u, html, soup in pages:
            for score, prefix, samples, n in auto_joblinks(u, html, soup):
                best.append((score, u, prefix, samples, n))
        best.sort(reverse=True)
        for score, u, prefix, samples, n in best[:3]:
            e = {"name": name, "type": "joblinks", "url": u, "link_pattern": re.escape(prefix)}
            jobs, err = try_entry(e)
            tag = "✓" if jobs else "✗"
            log.append(f"  {tag} joblinks {u} minta={prefix!r}: {len(jobs)} link — pl. {samples[:2]}")
            if jobs and n >= 3:
                found.append((e, jobs))
                break

    if not found:
        log.append("  ! NINCS működő adapter — valószínűleg JavaScript tölti be a listát (kézi vizsgálat kell)")
    return name, log, found


def to_yaml(entry):
    lines = [f'  - name: "{entry["name"]}"', f"    type: {entry['type']}"]
    for k, v in entry.items():
        if k in ("name", "type"):
            continue
        lines.append(f'    {k}: "{v}"' if isinstance(v, str) else f"    {k}: {v}")
    return "\n".join(lines)


def main():
    names = sys.argv[1:]
    banks = [b for b in BANKS if not names or any(n.lower() in b[0].lower() for n in names)]
    t0 = time.time()
    print(f"{len(banks)} bank felderítése...", flush=True)
    results = []
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(investigate, n, u): n for n, u in banks}
        for i, f in enumerate(cf.as_completed(futs), 1):
            try:
                results.append(f.result())
            except Exception as e:
                results.append((futs[f], [f"\n# {futs[f]}\n  !! HIBA: {type(e).__name__}: {e}"], []))
            print(f"  [{i}/{len(banks)}] {futs[f]}", flush=True)
    results.sort(key=lambda r: r[0])

    with open("discover_report.txt", "w", encoding="utf-8") as rep:
        rep.write(f"# discover.py — {time.strftime('%Y-%m-%d %H:%M')} — {len(banks)} bank, {int(time.time()-t0)} mp\n")
        ok = [r for r in results if r[2]]
        rep.write(f"# {len(ok)} banknál van működő adapter, {len(results)-len(ok)} banknál nincs.\n")
        for name, log, found in results:
            rep.write("\n".join(log) + "\n")

    with open("discover_found.yml", "w", encoding="utf-8") as out:
        out.write("# discover.py által megtalált, MŰKÖDŐ bejegyzések. Másold a companies.yml-be.\n")
        out.write("companies:\n")
        for name, log, found in results:
            for e, jobs in found:
                out.write("\n" + to_yaml(e) + f"\n    # -> {len(jobs)} pozíció, pl.: {jobs[0].title} ({jobs[0].location})\n")

    print(f"\nKész {int(time.time()-t0)} mp alatt. Jelentés: discover_report.txt, találatok: discover_found.yml")


if __name__ == "__main__":
    main()
