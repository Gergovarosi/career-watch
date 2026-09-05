# career-watch

**EN:** A small, dependency-light Python tool that watches the *own* career portals of
~60 Swiss (and a few global) banks, private banks and asset managers, and e-mails you
when a **new** position appears that matches your keyword / location filters. No LinkedIn,
no third-party job boards — only the employers' own sites. It runs for free on GitHub
Actions (daily cron), keeps a `state.json` of everything already seen so you never get the
same job twice, and supports 15+ applicant-tracking systems out of the box (Workday,
SuccessFactors, Oracle Recruiting, SmartRecruiters, Umantis, rexx, softgarden, Prospective/
OHWS, Personio, teamtailor/RSS, generic JSON and server-rendered HTML lists).

**Quick start (fork & run):** fork this repo → *Settings → Secrets and variables → Actions*:
add `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS` (Gmail app password), `MAIL_TO` →
*Settings → Actions → General → Workflow permissions: Read and write* → *Actions → career-watch →
Run workflow* with **seed** ticked once (marks everything current as seen, no e-mail) → done.
Edit `companies.yml` to change filters, locations or the list of companies. Licence: MIT.

---

Figyeli a megadott cégek **saját karrierportálját**, és e-mailt küld, amint új
svájci pozíció jelenik meg, ami megfelel a szűrőknek. LinkedIn nincs benne.

Nem kell programozónak lenned. Az alábbi lépéseket sorban, másolás-beillesztéssel
végig lehet csinálni. Ahol gépelni kell, az félkövérrel van jelölve.

---

## 1. lépés — Terminál megnyitása

A Macen nyomj `Cmd + Szóköz`, írd be: **Terminal**, Enter.
Ez egy fekete/fehér ablak, ahova parancsokat lehet írni. Minden parancs után Enter.

## 2. lépés — A mappa előkészítése

Töltsd le a `career-watch` mappát az Asztalra. Aztán a Terminálba:

```
cd ~/Desktop/career-watch
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Ha a sor elején megjelenik egy `(.venv)`, jó helyen vagy.
Ezt a `source .venv/bin/activate` sort minden új Terminál-ablaknál meg kell ismételni.

## 3. lépés — Az első teszt

```
python watch.py --doctor
```

Kapsz egy táblázatot. A `✓` azt jelenti, hogy az adott cég figyelése működik.
A Citi és a Julius Bär sorok élesben tesztelve vannak, ezeknek mennie kell.
Ha valahol `✗` vagy `!` van, az még nincs baj — a 4. lépés erről szól.

## 4. lépés — A többi bank felvétele

Ebben van a program legtöbb munkája elrejtve. A `banks.txt`-ben kb. 60 cégnév van
(nagybankok, svájci privátbankok, biztosítók, Big Four). Futtasd:

```
python probe.py --workday-batch banks.txt > talalatok.txt
```

Ez pár percig fut. Végignézi, melyik cégnek van nyilvános Workday-állásportálja,
és a `talalatok.txt`-be kiírja a kész, bemásolható blokkokat — csak azokat,
amik tényleg működnek.

Nyisd meg a `talalatok.txt`-et (dupla katt), másold ki a benne lévő blokkokat,
és illeszd be a `companies.yml` végére, a `companies:` lista alá. Ügyelj arra,
hogy a behúzás (a sor eleji szóközök) ugyanolyan legyen, mint a meglévőknél.

Utána újra:

```
python watch.py --doctor
```

**Egyedi cég felvétele** (ha nincs a listán): keresd meg a cég karrieroldalát a
böngészőben, másold ki a címsort, és:

```
python probe.py https://www.cegneve.com/careers --name "Cég AG"
```

Ez megmondja, milyen rendszert használnak, és kiírja a kész blokkot.

## 5. lépés — E-mail beállítása

Gmail kell hozzá (a Yahoo SMTP-je macerás). A Google-fiókodban kapcsold be a
kétlépcsős azonosítást, majd Google Account → Security → **App passwords** →
generálj egy 16 karakteres jelszót.

Készíts egy `.env` nevű fájlt a mappában, ezzel a tartalommal:

```
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=sajat.cimed@gmail.com
export SMTP_PASS=abcdefghijklmnop
export MAIL_TO=ahova.kered@example.com
```

Az `SMTP_PASS` az app-jelszó, NEM a rendes Google-jelszavad. Aztán:

```
source .env
```

## 6. lépés — Éles indítás

```
python watch.py --seed
```

Ez a jelenleg nyitott pozíciókat "látottnak" jelöli. **Ne hagyd ki**, különben az
első e-mail több száz régi pozíciót tartalmazna.

Innentől:

```
python watch.py
```

Ez már csak az ÚJ pozíciókról küld e-mailt.

## 7. lépés — Automatikus futtatás

**Ajánlott: GitHub Actions** (a géped lehet kikapcsolva)

1. Csinálj egy ingyenes GitHub-fiókot, és hozz létre egy **privát** repót.
2. Töltsd fel a mappa tartalmát (a GitHub weboldalán: Add file → Upload files).
   A `.env` fájlt NE töltsd fel.
3. A repóban: Settings → Secrets and variables → Actions → New repository secret.
   Vedd fel egyesével: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `MAIL_TO`
   ugyanazokkal az értékekkel, mint a `.env`-ben.
4. Actions fül → career-watch → Run workflow. Innentől 30 percenként magától fut.

Privát repónál havi 2000 ingyenes perc jár; ez futásonként fél perc, bőven elég.

**Alternatíva: helyben, a Macen**

```
crontab -e
```

majd illeszd be (Esc, `:wq`, Enter a mentéshez):

```
*/30 7-19 * * 1-5 cd ~/Desktop/career-watch && ./.venv/bin/python watch.py >> log.txt 2>&1
```

Csak akkor fut, ha a gép be van kapcsolva.

---

## Hangolás

Minden a `companies.yml` tetején van, sima szövegként:

- **Túl sok e-mail?** Írj több szót az `exclude_keywords` alá.
- **Túl kevés?** Vegyél ki szavakat az `include_keywords` alól, vagy töröld
  az egész listát (`include_keywords: []`) — akkor minden svájci pozíció átmegy.
- **Más városok is érdekelnek?** Bővítsd a `locations` listát.

## Ha egy cég nem megy

A `--doctor` táblázatban `✗` vagy `!`:

- **`!` 0 pozícióval**: lehet, hogy tényleg nincs nyitott állásuk. Nézd meg
  böngészőben. Ha van, akkor JavaScripttel töltik be — keresd meg, hova mutat a
  "Bewerben"/"Apply" gomb, és arra a címre futtasd a `probe.py`-t.
- **`✗` hibaüzenettel**: a portál megváltozott vagy blokkol. Az UBS a
  legzártabb ilyen; ha az nem megy, addig is használd az UBS saját
  "Save this search" funkcióját a job boardjukon — az e-mailt küld új pozícióról.

Bármelyik esetben: másold ki a `--doctor` táblázatot, abból pontosan látszik,
mit kell javítani.

## Adapterek

| típus | mire jó |
|---|---|
| `workday` | a legtöbb nagybank (Julius Bär, és sok más) |
| `joblinks` | szerver-oldalon renderelt találati oldalak (Citi) |
| `brassring` | IBM Talent Gateway (UBS) |
| `greenhouse`, `lever`, `ashby`, `workable`, `smartrecruiters`, `personio`, `recruitee` | kisebb cégek, butikok |
| `html` | minden más karrieroldal |

---

## 2026-09-04 — bővítés (Claude)

**Mi változott:** a `companies.yml` most ~60 céget figyel (svájci nagybankok,
kantonális és regionális bankok, privátbankok, valamint a nagy nemzetközi
bankok/vagyonkezelők — az utóbbiaknál csak a svájci pozíciók mennek át).
Új portál-típusok kerültek az `adapters.py`-ba:

| típus | mire jó |
|---|---|
| `successfactors`, `sfcsb` | SAP SuccessFactors (pl. SIX, Swiss Re) |
| `oraclecloud` | Oracle Recruiting (JPMorgan, BNY, Schroders, Lazard) |
| `ohws` | Prospective/OHWS — Raiffeisen, BEKB |
| `softgarden` | Cembra, Bank Frick |
| `rss` | teamtailor és bármilyen RSS (Bank SLM) |
| `jsonapi` | általános JSON-végpont (Bank CIC, Regiobank — Abacus jobportal) |
| `joblinks` (Umantis, rexx, refline) | BKB, BLKB, GKB, ABS, WIR, LLB, GLKB, HBL, Rahn+Bodmer, ZKB |

**Dupla kattintásos parancsfájlok** (Terminál nélkül is futnak):

- `run_doctor.command` — minden cég ellenőrzése, eredmény a `doctor_report.txt`-ben
- `run_discover.command` — új bankok karrierportáljának felderítése (`discover.py`, a lista a fájl elején)

**Szűrő-újdonság:** egy cégnél a `filters: {strict_location: true}` azt jelenti,
hogy ha a portál nem ad külön helyszínt, a pozíció CÍMÉBEN kell svájci
városnak lennie — ezt a globális portáloknál (JPMorgan, BlackRock stb.) használjuk.

**Ami még nem megy (JavaScript tölti be a listát, kézi vizsgálat kell):**
Pictet (SuccessFactors régi felület), PostFinance, BCV, SZKB, SHKB, Migros Bank,
EFG, Edmond de Rothschild, J. Safra Sarasin, UBP, Syz (HiBob), Goldman Sachs,
Morgan Stanley, Deutsche Bank, BNP Paribas, Leonteq, Partners Group, Valiant,
BCGE, Bank Cler, Clientis, Bank Thalwil / Maerki Baumann (Ostendis).
Ezeknél addig a portál saját "Job alert" e-mailje a megoldás.
