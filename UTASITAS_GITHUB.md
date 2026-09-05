# career-watch → GitHub Actions (napi 10:00-kor e-mail az ÚJ pozíciókról)

Ebben a mappában ("github-upload") pontosan azok a fájlok vannak, amiket fel kell tölteni.
A .env NINCS benne — a jelszó a GitHub "Secrets" részébe kerül (5. lépés).

## 1. GitHub-fiók
github.com → Sign up (ingyenes). Erősítsd meg az e-mailt.

## 2. Új privát repó
Jobb felül "+" → New repository
- Repository name: career-watch
- Private ← ezt válaszd
- Create repository

## 3. Fájlok feltöltése
Az új repó oldalán: "uploading an existing file" link (vagy Add file → Upload files).
Húzd be EGYSZERRE ennek a mappának az összes fájlját (a watch.yml-t és ezt az utasítást is, nem baj):
adapters.py, watch.py, notify.py, probe.py, discover.py, companies.yml,
requirements.txt, state.json, README.md, banks.txt
Alul: Commit changes.

## 4. A workflow-fájl (ez indítja naponta)
Add file → Create new file
- A fájlnév mezőbe ezt írd (pontosan, a pontokkal és perjelekkel):
      .github/workflows/watch.yml
- A nagy szövegmezőbe másold be a watch.yml teljes tartalmát (ebben a mappában van, nyisd meg TextEdit-tel, Cmd+A, Cmd+C).
- Commit changes.

## 5. Titkok (jelszavak)
Settings (a repó menüsorában) → bal oldalt Secrets and variables → Actions → New repository secret.
Ötöt vegyél fel egyesével (Name / Secret):
- SMTP_HOST   smtp.gmail.com
- SMTP_PORT   587
- SMTP_USER   (a Gmail-címed)
- SMTP_PASS   (a 16 karakteres Gmail app-jelszó — a Macen a career-watch/.env fájlban van)
- MAIL_TO     (ahova az e-mailt kéred)

## 6. Írási jog a robotnak (FONTOS, különben kétszer kapnád ugyanazt a pozíciót)
Settings → Actions → General → lent "Workflow permissions" → válaszd:
"Read and write permissions" → Save.

## 7. Első indítás
Actions fül → bal oldalt "career-watch" → jobb oldalt "Run workflow" → Run workflow.
1–2 perc múlva zöld pipa. Innentől minden nap 10:00-kor magától fut, és csak akkor
küld e-mailt, ha van új pozíció.

## Ha később módosítasz a companies.yml-en a Macen
GitHubon nyisd meg a fájlt → ceruza ikon → illeszd be az újat → Commit.
(Vagy töltsd fel újra az Upload files-szal — felülírja.)
