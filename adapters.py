"""
Adapterek a különböző karrierportál-rendszerekhez (ATS).

Minden adapter ugyanazt csinálja: kap egy "token"-t (a cég azonosítója az adott
rendszerben) vagy egy URL-t, és visszaad egy lista Job objektumot.

Ha egy cég nem használ ismert ATS-t, ott van a "html" adapter, ami a nyers
oldalt nézi.
"""

from __future__ import annotations

import hashlib
from html import unescape as _html_unescape
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

TIMEOUT = 25
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "de-CH,de;q=0.9,en;q=0.8",
}


@dataclass
class Job:
    company: str
    title: str
    location: str
    url: str
    uid: str  # stabil azonosító — ez alapján tudjuk, hogy már láttuk-e

    def to_dict(self):
        return asdict(self)


def _uid(company: str, raw: str) -> str:
    """Stabil, rövid azonosító a cég + a pozíció nyers azonosítója alapján."""
    h = hashlib.sha1(f"{company}::{raw}".encode("utf-8")).hexdigest()
    return h[:16]


_SESSION_PARAMS = re.compile(
    r"^(sid|phpsessid|jsessionid|sessionid|session|utm_[a-z]+|gclid|fbclid|_ga|_gl|ref|source|src|tracking|trk)$",
    re.I)


def _clean_url(url: str) -> str:
    """Session- és követő-paraméterek eltávolítása, hogy ugyanaz a pozíció
    ne kapjon minden futásnál új azonosítót (pl. rexx: ?sid=...)."""
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    try:
        p = urlsplit(url)
        q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not _SESSION_PARAMS.match(k)]
        return urlunsplit((p.scheme, p.netloc, p.path, urlencode(q), ""))
    except Exception:
        return url


def _get(url: str, **kw):
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, **kw)
    r.raise_for_status()
    return r


# --------------------------------------------------------------------------
# ATS adapterek
# --------------------------------------------------------------------------

def greenhouse(company: str, token: str, **_) -> list[Job]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    data = _get(url).json()
    out = []
    for j in data.get("jobs", []):
        out.append(Job(
            company=company,
            title=j.get("title", ""),
            location=(j.get("location") or {}).get("name", ""),
            url=j.get("absolute_url", ""),
            uid=_uid(company, str(j.get("id"))),
        ))
    return out


def lever(company: str, token: str, **_) -> list[Job]:
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    data = _get(url).json()
    out = []
    for j in data:
        cat = j.get("categories") or {}
        out.append(Job(
            company=company,
            title=j.get("text", ""),
            location=cat.get("location", ""),
            url=j.get("hostedUrl", ""),
            uid=_uid(company, str(j.get("id"))),
        ))
    return out


def ashby(company: str, token: str, **_) -> list[Job]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    data = _get(url).json()
    out = []
    for j in data.get("jobs", []):
        out.append(Job(
            company=company,
            title=j.get("title", ""),
            location=j.get("location", ""),
            url=j.get("jobUrl", ""),
            uid=_uid(company, str(j.get("id"))),
        ))
    return out


def smartrecruiters(company: str, token: str, **_) -> list[Job]:
    url = f"https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=100"
    data = _get(url).json()
    out = []
    for j in data.get("content", []):
        loc = j.get("location") or {}
        city = ", ".join(x for x in [loc.get("city"), loc.get("country")] if x)
        out.append(Job(
            company=company,
            title=j.get("name", ""),
            location=city,
            url=(j.get("ref") or "").replace(
                "https://api.smartrecruiters.com/v1/companies/",
                "https://jobs.smartrecruiters.com/",
            ) or f"https://jobs.smartrecruiters.com/{token}",
            uid=_uid(company, str(j.get("id"))),
        ))
    return out


def workable(company: str, token: str, **_) -> list[Job]:
    url = f"https://apply.workable.com/api/v1/widget/accounts/{token}?details=true"
    data = _get(url).json()
    out = []
    for j in data.get("jobs", []):
        out.append(Job(
            company=company,
            title=j.get("title", ""),
            location=", ".join(x for x in [j.get("city"), j.get("country")] if x),
            url=j.get("url") or j.get("application_url", ""),
            uid=_uid(company, str(j.get("shortcode") or j.get("id"))),
        ))
    return out


def personio(company: str, token: str, **_) -> list[Job]:
    """Personio XML feed — DACH régióban nagyon gyakori."""
    url = f"https://{token}.jobs.personio.de/xml"
    root = ET.fromstring(_get(url).content)
    out = []
    for pos in root.iter("position"):
        def txt(tag):
            el = pos.find(tag)
            return (el.text or "").strip() if el is not None and el.text else ""
        pid = txt("id")
        out.append(Job(
            company=company,
            title=txt("name"),
            location=txt("office"),
            url=f"https://{token}.jobs.personio.de/job/{pid}",
            uid=_uid(company, pid),
        ))
    return out


def recruitee(company: str, token: str, **_) -> list[Job]:
    url = f"https://{token}.recruitee.com/api/offers/"
    data = _get(url).json()
    out = []
    for j in data.get("offers", []):
        out.append(Job(
            company=company,
            title=j.get("title", ""),
            location=", ".join(x for x in [j.get("city"), j.get("country")] if x),
            url=j.get("careers_url") or j.get("careers_apply_url", ""),
            uid=_uid(company, str(j.get("id"))),
        ))
    return out


# --------------------------------------------------------------------------
# Általános HTML fallback
# --------------------------------------------------------------------------

_JOB_HINTS = re.compile(
    r"(job|jobs|stelle|stellen|karriere|career|vacan|position|offene|apply|bewerb)",
    re.I,
)


def html(company: str, url: str, selector: str | None = None, **_) -> list[Job]:
    """
    Ha a cég nem használ ismert ATS-t: végignézzük a karrieroldal linkjeit,
    és azokat vesszük pozíciónak, amik állás-szerű URL-re mutatnak.

    A `selector` (CSS) megadásával pontosítható, ha a heurisztika zajos.
    """
    soup = BeautifulSoup(_get(url).text, "html.parser")
    anchors = soup.select(selector) if selector else soup.find_all("a", href=True)

    out, seen = [], set()
    for a in anchors:
        href = a.get("href")
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        title = " ".join(a.get_text(" ", strip=True).split())
        if not title or len(title) < 4 or len(title) > 140:
            continue
        full = urljoin(url, href)
        # csak ugyanarról a domainről, és állás-szerű útvonalról
        if not selector:
            if urlparse(full).netloc != urlparse(url).netloc:
                continue
            if not _JOB_HINTS.search(urlparse(full).path):
                continue
        if full in seen:
            continue
        seen.add(full)
        out.append(Job(
            company=company,
            title=title,
            location="",
            url=full,
            uid=_uid(company, full),
        ))
    return out


ADAPTERS = {
    "greenhouse": greenhouse,
    "lever": lever,
    "ashby": ashby,
    "smartrecruiters": smartrecruiters,
    "workable": workable,
    "personio": personio,
    "recruitee": recruitee,
    "html": html,
}


def _dedupe(jobs: list) -> list:
    """Egy uid csak egyszer szerepelhet — a portalok neha ismetlik magukat."""
    seen, out = set(), []
    for j in jobs:
        if j.uid in seen:
            continue
        seen.add(j.uid)
        out.append(j)
    return out


def fetch(entry: dict) -> list[Job]:
    """Egy config-bejegyzés lekérése."""
    kind = entry.get("type", "html")
    fn = ADAPTERS.get(kind)
    if fn is None:
        raise ValueError(f"Ismeretlen típus: {kind}")
    kwargs = {k: v for k, v in entry.items()
              if k not in ("name", "type", "enabled", "filters")}
    kwargs.setdefault("token", "")
    kwargs.setdefault("url", "")
    jobs = fn(company=entry["name"], **kwargs)
    for j in jobs:  # HTML-entitások (&amp; stb.) kitakarítása a címekből
        j.title = _html_unescape(j.title or "")
        j.location = _html_unescape(j.location or "")
    return _dedupe(jobs)


# --------------------------------------------------------------------------
# NAGYVÁLLALATI ATS-EK
# --------------------------------------------------------------------------

def workday(company: str, token: str, **kw) -> list[Job]:
    """
    Workday — a legtöbb nagybank ezt használja.

    token formátum:  "tenant/wdN/site"
    példa:           "juliusbaer/wd3/External"
    ez a böngészőben: https://juliusbaer.wd3.myworkdayjobs.com/External
    """
    parts = token.split("/")
    if len(parts) != 3:
        raise ValueError('workday token formátum: "tenant/wdN/site"')
    tenant, wd, site = parts

    base = f"https://{tenant}.{wd}.myworkdayjobs.com"
    api = f"{base}/wday/cxs/{tenant}/{site}/jobs"

    out, offset, limit, total = [], 0, 20, None
    while offset < 600:  # biztonsági felső korlát
        payload = {"appliedFacets": {}, "limit": limit, "offset": offset,
                   "searchText": kw.get("search") or ""}
        r = requests.post(
            api, json=payload, timeout=TIMEOUT,
            headers={**HEADERS, "Accept": "application/json",
                     "Content-Type": "application/json"},
        )
        r.raise_for_status()
        data = r.json()
        postings = data.get("jobPostings", [])
        if not postings:
            break
        for j in postings:
            path = j.get("externalPath", "")
            out.append(Job(
                company=company,
                title=j.get("title", ""),
                location=j.get("locationsText", "") or "",
                url=f"{base}/{site}{path}",
                uid=_uid(company, path or j.get("bulletFields", [""])[0]),
            ))
        # a "total" csak az első oldalon jön meg biztosan — jegyezzük meg
        if total is None or data.get("total"):
            total = data.get("total") or total or 0
        offset += limit
        if offset >= total:
            break
    return out


_LOC_NOISE = re.compile(
    r"(save for later|save job|apply|mehr erfahren|weiterlesen|hybrid|remote|on-site)",
    re.I,
)


def joblinks(company: str, url: str, link_pattern: str = r"/job/",
             title_attr: bool = False, **_) -> list[Job]:
    """
    Szerver-oldalon renderelt találati oldalakhoz (Citi, Vontobel és sok más
    saját karrieroldal).

    link_pattern : csak az ilyen URL-re mutató linkeket veszi pozíciónak
    title_attr   : ha true, a link "title" attribútumát használja címként.
                   Sok oldal a link szövegébe belezsúfolja a dátumot és a
                   részleget is; a title attribútum viszont tiszta.
                   Ilyenkor a maradék szöveg lesz a helyszín.
    """
    soup = BeautifulSoup(_get(url).text, "html.parser")
    pat = re.compile(link_pattern)

    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        full = _clean_url(urljoin(url, a["href"]))
        if not pat.search(full) or full in seen:
            continue

        linktext = " ".join(a.get_text(" ", strip=True).split())
        clean = " ".join((a.get("title") or "").split())

        if title_attr and clean:
            title = clean
            # a link szövegéből kivonjuk a címet -> marad a dátum + részleg + hely
            location = linktext.replace(clean.replace("&amp;", "&"), " ")
            location = re.sub(r"\d+\s*(days?|hours?|Tage?|Stunden?)\s*ago", " ", location, flags=re.I)
            location = " ".join(location.split())[:120]
        else:
            title = clean if (clean and len(clean) < len(linktext)) else linktext
            location = ""
            parent = a.find_parent(["li", "article", "div", "tr"])
            if parent:
                ptext = " ".join(parent.get_text(" ", strip=True).split())
                rest = ptext.replace(title, " ", 1).strip(" -\u2013|\u00b7")
                location = _LOC_NOISE.sub("", rest).strip(" -\u2013|\u00b7,")[:120]

        if _GENERIC_TEXT.match(title or ""):
            title = _title_from_context(a, full)
        if not title or len(title) < 4:
            continue
        seen.add(full)
        out.append(Job(company=company, title=title, location=location,
                       url=full, uid=_uid(company, full)))
    return out


_GENERIC_TEXT = re.compile(
    r"^(zur position|zur stelle|zum inserat|zum angebot|zum job|mehr erfahren|mehr|more details|more|"
    r"view job|view|details|apply|apply now|jetzt bewerben|bewerben|read more|weiterlesen|hier|here|"
    r"en savoir plus|postuler|voir|voir plus|scopri|candidati|stellenbeschrieb.*)$", re.I)


def _title_from_context(a, url: str) -> str:
    """Ha a link szövege semmitmondó ("Mehr erfahren"), a környező címsorból
    vagy az URL utolsó darabjából csinálunk címet."""
    parent = a
    for _ in range(4):
        parent = parent.parent
        if parent is None:
            break
        h = parent.find(["h1", "h2", "h3", "h4", "h5", "strong"])
        if h:
            t = " ".join(h.get_text(" ", strip=True).split())
            if 3 < len(t) < 140 and not _GENERIC_TEXT.match(t):
                return t
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    slug = re.sub(r"\.(html?|pdf|aspx?)$", "", slug, flags=re.I)
    slug = re.sub(r"[-_+]+", " ", slug)
    slug = re.sub(r"\b(stelleninserat|stellenausschreibung|job|de|en|fr|it)\b", " ", slug, flags=re.I)
    return " ".join(slug.split()).strip()


def brassring(company: str, token: str, **_) -> list[Job]:
    """
    IBM/Kenexa BrassRing "Talent Gateway" — az UBS ilyet használ.

    token formátum:  "partnerid/siteid"   pl. "25008/5012"

    Két lépés kell hozzá:
      1) megnyitunk egy munkamenetet a portál kezdőoldalán (sütiket kapunk),
      2) ugyanarra a domainre küldjük a keresést, nem a sjobs.brassring.com-ra.

    A pozíció adatai a "Questions" listában vannak, QuestionName/Value párokként.
    """
    parts = token.split("/")
    if len(parts) != 2:
        raise ValueError('brassring token formátum: "partnerid/siteid"')
    partnerid, siteid = parts

    host = "https://jobs.ubs.com" if partnerid == "25008" else "https://sjobs.brassring.com"
    home = f"{host}/TGnewUI/Search/Home/Home?partnerid={partnerid}&siteid={siteid}"

    s = requests.Session()
    s.headers.update(HEADERS)
    s.get(home, timeout=TIMEOUT)  # munkamenet nyitása

    out, seen_uids, start, page = [], set(), 0, 50
    while start < 600:  # biztonsági felső korlát
        payload = {
            "partnerId": partnerid, "siteId": siteid,
            "keyword": "", "location": "",
            "startrow": str(start), "pageSize": str(page),
            "sortOrder": "1", "sortField": "1",
            "brandId": "0", "recordstart": str(start + 1),
        }
        r = s.post(
            f"{host}/TGnewUI/Search/Ajax/ProcessSortAndShowMoreJobs",
            json=payload, timeout=TIMEOUT,
            headers={"Accept": "application/json", "Content-Type": "application/json",
                     "Referer": home, "X-Requested-With": "XMLHttpRequest"},
        )
        r.raise_for_status()
        rows = (r.json().get("Jobs") or {}).get("Job") or []
        if not rows:
            break

        before = len(out)

        for j in rows:
            q = {}
            for item in (j.get("Questions") or []):
                nm, val = item.get("QuestionName"), item.get("Value")
                if nm and isinstance(val, str):
                    q[nm] = val.strip()

            title = q.get("jobtitle") or q.get("Job_Title") or ""
            if not title:
                continue

            # a helyszín több mezőben szórakozik; az elsőt vesszük, amiben van valami
            location = ""
            for key in ("formtext23", "formtext22", "location", "city",
                        "formtext24", "formtext25"):
                if q.get(key):
                    location = q[key]
                    break

            jid = q.get("reqid") or title
            link = (j.get("Link") or "").replace("\\/", "/")
            if not link:
                link = (f"{host}/TGnewUI/Search/home/HomeWithPreLoad"
                        f"?partnerid={partnerid}&siteid={siteid}"
                        f"&PageType=JobDetails&jobid={jid}")

            uid = _uid(company, jid)
            if uid in seen_uids:
                continue
            seen_uids.add(uid)
            out.append(Job(company=company, title=title, location=location,
                           url=link, uid=uid))

        # Ha a lapozas nem lep tovabb (a portal ugyanazt adja vissza),
        # akkor nincs ertelme tovabb kerdezni.
        if len(out) == before or len(rows) < page:
            break
        start += page
    return _dedupe(out)


ADAPTERS.update({
    "workday": workday,
    "joblinks": joblinks,
    "brassring": brassring,
})


# --------------------------------------------------------------------------
# TOVÁBBI NAGYVÁLLALATI ATS-EK (2026-09 bővítés)
# --------------------------------------------------------------------------

def successfactors(company: str, token: str, **kw) -> list[Job]:
    """
    SAP SuccessFactors "klasszikus" karrieroldal (career?company=...).
    Sok svájci bank ezt használja (pl. Pictet).

    token formátum:  "host/company"   pl. "career012.successfactors.eu/banquepict"
    """
    parts = token.split("/")
    if len(parts) != 2:
        raise ValueError('successfactors token formátum: "host/company"')
    host, comp = parts
    base = f"https://{host}/career"
    start = (f"{base}?company={comp}&career_ns=job_listing_summary"
             f"&navBarLevel=JOB_SEARCH&career_job_req_id=&selected_lang=en_US")

    s = requests.Session()
    s.headers.update(HEADERS)
    out, seen_pages, queue = [], set(), [start]
    while queue and len(seen_pages) < 30:
        url = queue.pop(0)
        if url in seen_pages:
            continue
        seen_pages.add(url)
        r = s.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full = urljoin(url, href)
            if "career_ns=job_listing" in full and "jobPk=" in full and "job_listing_summary" not in full:
                title = " ".join(a.get_text(" ", strip=True).split())
                if not title or len(title) < 3:
                    continue
                m = re.search(r"jobPk=(\d+)", full)
                pk = m.group(1) if m else full
                location = ""
                tr = a.find_parent("tr")
                if tr:
                    cells = [" ".join(td.get_text(" ", strip=True).split()) for td in tr.find_all("td")]
                    cells = [c for c in cells if c and c != title]
                    if cells:
                        location = cells[-1][:120]
                out.append(Job(company=company, title=title, location=location,
                               url=full, uid=_uid(company, pk)))
            elif "job_listing_summary" in full and ("startPage" in full or "_s.crb" in full or "page" in full.lower()):
                if full not in seen_pages:
                    queue.append(full)
    return _dedupe(out)


def sfcsb(company: str, url: str, **kw) -> list[Job]:
    """
    SAP SuccessFactors "Career Site Builder" — a jobs.cegneve.com típusú oldalak,
    ahol a keresés a /search/?q= útvonalon megy, és a találatok
    <a class="jobTitle-link"> linkek.

    url:  a karrieroldal gyökere, pl. "https://jobs.swisslife.ch"
    """
    base = url.rstrip("/")
    s = requests.Session()
    s.headers.update(HEADERS)
    out, startrow = [], 0
    while startrow < 1000:
        r = s.get(f"{base}/search/?q=&sortColumn=referencedate&sortDirection=desc&startrow={startrow}",
                  timeout=TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select("a.jobTitle-link")
        if not rows:
            rows = [a for a in soup.find_all("a", href=True)
                    if re.search(r"/job/[^/]+/\d+/?$", a["href"])]
            # ugyanaz a link többször is előfordulhat (cím + "Mehr" gomb)
            seen_h, uniq = set(), []
            for a in rows:
                if a["href"] in seen_h or not a.get_text(strip=True):
                    continue
                seen_h.add(a["href"]); uniq.append(a)
            rows = uniq
        if not rows:
            break
        before = len(out)
        for a in rows:
            title = " ".join(a.get_text(" ", strip=True).split())
            full = urljoin(base, a["href"])
            location = ""
            tr = a.find_parent("tr") or a.find_parent("li") or a.find_parent("div", class_=re.compile("job", re.I))
            if tr:
                loc = tr.select_one(".jobLocation, .job-location, [class*=ocation]")
                if loc:
                    location = " ".join(loc.get_text(" ", strip=True).split())[:120]
            m = re.search(r"/(\d+)/?$", full)
            out.append(Job(company=company, title=title, location=location, url=full,
                           uid=_uid(company, m.group(1) if m else full)))
        if len(out) == before:
            break
        startrow += len(rows)
    return _dedupe(out)


def oraclecloud(company: str, token: str, **kw) -> list[Job]:
    """
    Oracle Recruiting Cloud (pl. JPMorgan).

    token formátum:  "host/siteNumber"   pl. "jpmc.fa.oraclecloud.com/CX_1001"
    """
    parts = token.split("/")
    if len(parts) != 2:
        raise ValueError('oraclecloud token formátum: "host/siteNumber"')
    host, site = parts
    api = f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    search = kw.get("search") or ""
    out, offset, limit = [], 0, 50
    while offset < 2000:
        finder = (f"findReqs;siteNumber={site},keyword={search},limit={limit},offset={offset},"
                  f"sortBy=POSTING_DATES_DESC")
        r = requests.get(api, params={"onlyData": "true",
                                      "expand": "requisitionList.secondaryLocations",
                                      "finder": finder},
                         headers={**HEADERS, "Accept": "application/json"}, timeout=TIMEOUT)
        r.raise_for_status()
        items = r.json().get("items", [])
        reqs = items[0].get("requisitionList", []) if items else []
        if not reqs:
            break
        for j in reqs:
            rid = str(j.get("Id"))
            locs = [j.get("PrimaryLocation") or ""]
            for sl in j.get("secondaryLocations", []) or []:
                locs.append(sl.get("Name", ""))
            out.append(Job(company=company, title=j.get("Title", ""),
                           location="; ".join(x for x in locs if x)[:200],
                           url=f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{rid}",
                           uid=_uid(company, rid)))
        if len(reqs) < limit:
            break
        offset += limit
    return _dedupe(out)


def jsonapi(company: str, url: str, items: str = "", title: str = "title",
            location: str = "location", link: str = "url", id: str = "id",
            base: str = "", method: str = "GET", body: dict | None = None,
            link_template: str = "", **kw) -> list[Job]:
    """
    Általános JSON-lekérdező olyan oldalakhoz, amelyeknek van egy nyilvános
    JSON végpontjuk. A mezőneveket pontokkal elválasztott útvonalként lehet
    megadni (pl. "location.name").

    items : hol van a találati lista a JSON-ban (pl. "data.jobs"); üres = a gyökér lista
    """
    if method.upper() == "POST":
        r = requests.post(url, json=body or {}, headers={**HEADERS, "Accept": "application/json"},
                          timeout=TIMEOUT)
    else:
        r = requests.get(url, headers={**HEADERS, "Accept": "application/json"}, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()

    def dig(obj, path):
        cur = obj
        for p in [x for x in path.split(".") if x]:
            if isinstance(cur, dict):
                cur = cur.get(p)
            elif isinstance(cur, list) and p.isdigit():
                cur = cur[int(p)] if int(p) < len(cur) else None
            else:
                return None
            if cur is None:
                return None
        return cur

    rows = dig(data, items) if items else data
    out = []
    for j in rows or []:
        t = dig(j, title) or ""
        loc = dig(j, location) or ""
        if isinstance(loc, list):
            loc = ", ".join(str(x) for x in loc)
        u = dig(j, link) or ""
        if u and base and not str(u).startswith("http"):
            u = urljoin(base, str(u))
        jid = dig(j, id) or u or t
        if not u and link_template:
            u = link_template.replace("{id}", str(jid))
        out.append(Job(company=company, title=str(t), location=str(loc), url=str(u),
                       uid=_uid(company, str(jid))))
    return _dedupe(out)


ADAPTERS.update({
    "successfactors": successfactors,
    "sfcsb": sfcsb,
    "oraclecloud": oraclecloud,
    "jsonapi": jsonapi,
})


def softgarden(company: str, url: str, **kw) -> list[Job]:
    """
    softgarden karrieroldal (pl. karriere.bankfrick.li, careers.cembra.ch):
    a /jobs.feed.json schema.org DataFeed-et adja vissza.

    url: a karrieroldal gyökere, pl. "https://careers.cembra.ch"
    """
    base = url.rstrip("/")
    data = _get(f"{base}/jobs.feed.json").json()
    out = []
    for el in data.get("dataFeedElement", []):
        j = el.get("item") or {}
        loc = j.get("jobLocation")
        locs = loc if isinstance(loc, list) else ([loc] if loc else [])
        names = []
        for l in locs:
            addr = (l or {}).get("address") or {}
            nm = addr.get("addressLocality") or addr.get("addressRegion") or addr.get("addressCountry") or ""
            if nm:
                names.append(str(nm))
        ident = j.get("identifier") or {}
        jid = str(ident.get("value") if isinstance(ident, dict) else ident) or j.get("url", "")
        out.append(Job(company=company, title=j.get("title", ""), location=", ".join(names)[:120],
                       url=j.get("url", ""), uid=_uid(company, jid)))
    return _dedupe(out)


def rss(company: str, url: str, **kw) -> list[Job]:
    """RSS/Atom feed (pl. teamtailor: karriere.cegneve.ch/jobs.rss)."""
    root = ET.fromstring(_get(url).content)
    out = []
    ns = {"tt": "https://teamtailor.com/locations", "atom": "http://www.w3.org/2005/Atom"}
    items = root.iter("item")
    for it in items:
        def t(tag):
            el = it.find(tag)
            return (el.text or "").strip() if el is not None and el.text else ""
        title, link, guid = t("title"), t("link"), t("guid")
        loc = ""
        for el in it.iter():
            if el.tag.lower().endswith("location") and el.text:
                loc = el.text.strip(); break
        if not title:
            continue
        out.append(Job(company=company, title=title, location=loc[:120], url=link,
                       uid=_uid(company, guid or link or title)))
    if not out:  # Atom
        for e in root.findall("atom:entry", ns):
            title = (e.findtext("atom:title", default="", namespaces=ns) or "").strip()
            link_el = e.find("atom:link", ns)
            link = link_el.get("href") if link_el is not None else ""
            jid = (e.findtext("atom:id", default="", namespaces=ns) or link).strip()
            out.append(Job(company=company, title=title, location="", url=link, uid=_uid(company, jid)))
    return _dedupe(out)


ADAPTERS.update({"softgarden": softgarden, "rss": rss})


def ohws(company: str, token: str, url: str = "", lang: str = "de", **kw) -> list[Job]:
    """
    Prospective Media Services "OHWS" JSON API — sok svájci cég karrieroldala
    (pl. BEKB, Raiffeisen) mögött ez van.

    token : a medium/careercenter azonosító, pl. "1509"
    url   : (opcionális) a cég saját álláslista-oldala — ez lesz a link, ha a
            JSON nem ad direkt linket
    """
    api = f"https://ohws.prospective.ch/public/v1/medium/{token}/jobs"
    out, offset, limit = [], 0, 100
    while offset < 2000:
        r = requests.get(api, params={"lang": lang, "offset": offset, "limit": limit},
                         headers={**HEADERS, "Accept": "application/json"}, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        jobs = data.get("jobs", [])
        if not jobs:
            break
        for j in jobs:
            jid = str(j.get("id") or j.get("viewkey") or "")
            attrs = j.get("attributes") or {}
            locs = []
            for k in ("20", "10", "location", "place"):
                v = attrs.get(k)
                if isinstance(v, list):
                    locs.extend(str(x) for x in v)
                elif v:
                    locs.append(str(v))
            link = (j.get("links") or {}).get("directlink") if isinstance(j.get("links"), dict) else None
            link = link or j.get("url") or j.get("directlink") or j.get("apply_url") or ""
            if not link:
                link = url or f"https://ohws.prospective.ch/public/v1/medium/{token}/job/{jid}"
            out.append(Job(company=company, title=j.get("title", ""), location=", ".join(locs)[:120],
                           url=link, uid=_uid(company, jid)))
        total = data.get("total") or 0
        offset += limit
        if offset >= total:
            break
    return _dedupe(out)


ADAPTERS.update({"ohws": ohws})
