# Implementační plán a pracovní stav

## 8. Načítání, virtualizace a paměť

### Zásady

- po otevření PDF se nejprve načtou pouze metadata stran;
- frontend vytvoří prázdné bloky se správným poměrem stran;
- skutečná stránka se vyžádá teprve v blízkosti viewportu;
- přednačte se omezený počet stran nad a pod aktuální pozicí;
- vzdálené obrazové objekty se z paměti uvolní;
- při změně zoomu se znovu vykreslí pouze viditelné stránky;
- zastaralé požadavky budou ignorovány podle `requestId` a generace dokumentu.

### Výchozí limity pro první verzi

- nejvýše 8 obrazových stran aktivních ve frontendu;
- přístup k aktivnímu PyMuPDF dokumentu je serializován jedním reentrantním zámkem;
- maximálně 2 čekající stránky před a 2 za viewportem;
- backendová LRU cache zatím není implementována; frontend drží nejvýše osm nevzdálených načtených stran, pokud není současně viditelných více;
- otevřený pouze jeden PyMuPDF dokument v renderovacím workeru.

Limity se upraví až podle měření na skutečných souborech.

---

## 9. Výběr složky

Aplikace bude podporovat tři způsoby:

1. tlačítko **Otevřít složku**;
2. ruční vložení cesty do pole;
3. argument při spuštění:

```bash
python main.py --folder "D:\\PDF\\OCR"
```

### Proč nebude hlavním řešením dialog z webového frontendu

Frontend může otevřít adresářový dialog pomocí `window.showDirectoryPicker()` nebo prvku `<input type="file" webkitdirectory>`. Tyto mechanismy ale vracejí webové objekty `FileSystemDirectoryHandle` nebo `File` a relativní názvy. Z bezpečnostních důvodů neposkytují Python backendu absolutní cestu ke zvolené složce.

Teoreticky by frontend mohl načíst všechny PDF jako binární data a poslat je backendu. To by však u velkého množství nebo velkých PDF zbytečně kopírovalo celé soubory mezi prohlížečem a Pythonem, komplikovalo opakované načítání a znemožnilo backendu přímo zapisovat manifest do zvolené složky. Tento režim proto není součástí návrhu.

### Backendový nativní dialog

Funkce `selectFolderB()` otevře dialog na backendu a vrátí skutečnou cestu. Implementace bude izolována v `folder_dialog.py`, takže není pevně svázána s konkrétní knihovnou.

Pro první verzi se použije `tkinter.filedialog.askdirectory()`, protože vrací cestu jako řetězec a Python jej dokumentuje jako dialog s nativním vzhledem. Pokud se při testování na cílové platformě ukáže problém s dostupností Tk nebo vzhledem dialogu, lze implementaci nahradit platformním dialogem bez změny API ani zbytku aplikace.

Ruční cesta a argument `--folder` zůstanou vždy funkční zálohou.

Technické podklady k tomuto rozhodnutí:

- [MDN: `showDirectoryPicker()`](https://developer.mozilla.org/en-US/docs/Web/API/Window/showDirectoryPicker) – vrací `FileSystemDirectoryHandle`, vyžaduje uživatelskou aktivaci a nemá plnou podporu ve všech běžných prohlížečích;
- [MDN: `FileSystemHandle`](https://developer.mozilla.org/en-US/docs/Web/API/FileSystemHandle) – veřejné vlastnosti handle jsou `name` a `kind`, nikoli absolutní systémová cesta;
- [MDN: `webkitdirectory`](https://developer.mozilla.org/en-US/docs/Web/API/HTMLInputElement/webkitdirectory) – zpřístupňuje vybrané soubory a relativní cesty uvnitř vybrané složky;
- [Python: `tkinter.filedialog.askdirectory()`](https://docs.python.org/3/library/dialog.html#tkinter.filedialog.askdirectory) – vrací cestu ke zvolené složce jako řetězec.

Výchozí skenování bude pouze v přímo vybrané složce. Rekurzivní procházení podsložek není součástí první verze, aby relativní názvy a manifest zůstaly jednoznačné. Lze je přidat později jako volbu.

---

## 10. Manifest JSON

Název souboru:

```text
pdf-ocr-reviewer.manifest.json
```

### Navržené schéma verze 1

```json
{
  "schema_version": 1,
  "application": "pdf-ocr-reviewer",
  "updated_at": "2026-08-04T12:00:00+02:00",
  "ui": {
    "last_file": "zpravodaj-1993-02.pdf",
    "zoom_percent": 100,
    "ocr_mode": "layout",
    "overlay": false,
    "status_filter": "all",
    "name_filter": "",
    "auto_advance": true
  },
  "files": {
    "zpravodaj-1993-02.pdf": {
      "identity": {
        "size": 21983210,
        "mtime_ns": 1785824750123456789
      },
      "status": "error",
      "last_page": 3,
      "problem_pages": [3, 6],
      "note": "Na straně 4 je chybné pořadí sloupců.",
      "reviewed_at": "2026-08-04T12:15:00+02:00"
    }
  }
}
```

### Pravidla manifestu

- klíčem souboru je relativní název vůči zvolené složce;
- čísla stran se v manifestu ukládají jako indexy od nuly, ale UI je zobrazuje od jedné;
- `size` a `mtime_ns` slouží k rozpoznání změny PDF;
- OCR text, náhledy a souřadnice se do manifestu neukládají;
- neznámé položky manifestu se při načtení nesmí potichu zahodit;
- neplatný stav nebo schéma vyvolá viditelnou chybu, nikoli tichý reset;
- nová verze schématu musí mít explicitní migrační funkci.

### Zápis

Při změně se použije tento postup:

1. serializovat celý manifest do dočasného souboru ve stejné složce;
2. dokončit zápis a synchronizaci souboru;
3. nahradit předchozí manifest;
4. při chybě ponechat původní manifest beze změny;
5. zobrazit v UI chybu, pokud stav nelze uložit.

Zápis se provede po změně stavu, problematické stránky nebo poznámky. Pozice při scrollování se může ukládat se zpožděním, aby se soubor nepřepisoval při každém pixelu posunu.

### Změněné a chybějící soubory

- nový PDF soubor dostane stav `unreviewed`;
- změněný soubor si zachová starý záznam, ale UI jej označí `changed_since_review`;
- soubor uvedený v manifestu, který ve složce chybí, se zobrazí pouze ve zvláštním filtru „chybějící“;
- automatické přiřazování přejmenovaných souborů podle hashů není součástí první verze.

---

## 11. Bezpečnost a integrita dat

- aplikace nesmí zapisovat do PDF;
- všechny požadavky frontendu používají interní `fileId`, ne libovolnou cestu;
- backend ověří, že požadovaný soubor pochází z aktuálního katalogu;
- OCR text se do DOM vkládá přes `textContent`, ne jako HTML;
- index stránky a zoom se validují na backendu;
- manifest je jediný trvalý soubor vytvářený ve zvolené složce;
- dočasné náhledy se neukládají vedle PDF;
- první verze předpokládá jediný spuštěný proces nad jednou složkou;
- pokud složka není zapisovatelná, prohlížení může pokračovat v režimu pouze pro čtení, ale UI musí trvale zobrazovat, že výsledky nejsou ukládány.

---

## 12. Chybové stavy, které musí UI rozlišovat

- složka neexistuje;
- složku nelze číst;
- manifest nelze přečíst;
- manifest obsahuje neplatný JSON;
- manifest má nepodporovanou verzi;
- manifest nelze zapsat;
- PDF nelze otevřít;
- PDF je zašifrované nebo vyžaduje heslo;
- stránku nelze vykreslit;
- OCR vrstva je prázdná;
- spojení WebUI bylo přerušeno;
- renderovací požadavek je zastaralý po přepnutí dokumentu.

Chyba jednoho PDF nesmí ukončit aplikaci ani znemožnit otevření dalšího souboru.

---

## 13. Testování

### Automatické testy

1. **Manifest**
   - nový manifest;
   - načtení platného manifestu;
   - odmítnutí neplatného JSON;
   - migrace schématu;
   - zachování neznámých položek;
   - bezpečný zápis při simulované chybě;
   - detekce změny souboru.

2. **Skenování složky**
   - pouze `.pdf` bez ohledu na velikost písmen přípony;
   - stabilní řazení názvů;
   - ignorování manifestu a jiných souborů;
   - chování při zániku souboru během skenování.

3. **PDF služba**
   - počet a rozměry stran;
   - rotované stránky;
   - stránka bez textu;
   - extrakce `words` a `rawdict`;
   - neplatný index stránky;
   - poškozené nebo zašifrované PDF.

4. **Binární paket**
   - správná délka hlavičky;
   - Unicode v JSON;
   - prázdné OCR;
   - poškozený paket;
   - velká stránka.

### Manuální přijímací testy

- rychlé přepínání alespoň 100 PDF v levém seznamu;
- plynulé rolování dokumentu s nejméně 100 stranami;
- správné zarovnání skenu a OCR u stran různých rozměrů;
- obnovení posledního souboru a stránky po restartu;
- světlý i tmavý režim;
- ovládání bez myši pomocí kláves;
- změna PDF po kontrole;
- odpojení a nové připojení UI;
- složka bez práva zápisu;
- neplatný manifest bez ztráty původních dat.

---

## 14. Měřitelné podmínky dokončení první verze

První verze je hotová, když:

- [ ] lze otevřít složku a zobrazit všechny její PDF;
- [ ] lze přepínat soubory vlevo bez restartu aplikace;
- [ ] stránky vybraného PDF jsou zobrazeny pod sebou;
- [ ] ke každé stránce existuje zarovnaný OCR panel;
- [ ] fungují režimy Layout, PDF order a Geometric order;
- [ ] funguje lazy loading a vzdálené stránky nezůstávají všechny v paměti;
- [ ] funguje zoom a overlay;
- [ ] lze označit stav souboru a problematické stránky;
- [ ] lze přidat poznámku;
- [ ] stav se uloží do manifestu a obnoví po restartu;
- [ ] změněné PDF je viditelně označeno;
- [ ] nečitelný soubor neukončí aplikaci;
- [x] jsou splněny automatické testy manifestu a binárního paketu;
- [x] README odpovídá skutečné implementaci a obsahuje nový pracovní stav.

---

## 15. Etapy práce

### Etapa 0 – schválení návrhu

- [x] odsouhlasit tento README;
- [x] případně upravit rozsah první verze;
- [x] potvrdit název aplikace `pdf-ocr-reviewer`.

**Výstup:** schválený plán bez implementačních změn.

### Etapa 1 – kostra a technický prototyp

- [x] vytvořit strukturu projektu;
- [x] převzít WebUI lifecycle a funkční vzory ovládacích prvků z příkladu;
- [x] přidat připnuté verze závislostí;
- [x] otevřít PDF z vybrané nebo zadané složky;
- [x] získat metadata první stránky;
- [x] poslat jeden PNG náhled přes `send_raw()`;
- [x] zobrazit OCR objekty v pravém panelu;
- [x] změřit čas, velikost paketu a spotřebu paměti;
- [ ] rozhodnout o definitivním transportu obrazu po reálném WebUI testu.

**Výstup:** jedna stránka PDF viditelná vedle OCR vrstvy.

### Etapa 2 – složka a seznam souborů

- [x] implementovat argument `--folder`;
- [x] implementovat ruční cestu;
- [x] implementovat `tkinter.filedialog.askdirectory()` za rozhraním `folder_dialog.py`;
- [x] proskenovat PDF;
- [x] vytvořit stabilní `fileId`;
- [x] zobrazit seznam a přepínání dokumentů;
- [x] ošetřit neplatné PDF.

**Výstup:** plně funkční levý panel.

### Etapa 3 – stránky, lazy loading a scroll

- [x] načíst metadata všech stran vybraného PDF;
- [x] vytvořit placeholdery;
- [x] implementovat sledování viewportu;
- [ ] nahradit serializovaný callback skutečnou renderovací frontou;
- [x] zrušit nebo ignorovat zastaralé požadavky;
- [x] uvolňovat Blob URL;
- [ ] ověřit dlouhý dokument.

**Výstup:** plynulé rolování bez načtení celého dokumentu do paměti.

### Etapa 4 – OCR diagnostika

- [x] Layout režim;
- [x] PDF order režim;
- [x] Geometric order režim;
- [x] OCR overlay;
- [x] volitelné rámečky slov nebo znaků;
- [x] prázdná OCR vrstva jako viditelný stav.

**Výstup:** všechny plánované způsoby kontroly OCR.

### Etapa 5 – manifest a workflow kontroly

- [x] model manifestu;
- [x] načtení a validace;
- [x] bezpečný zápis;
- [x] stavy souborů;
- [x] problematické stránky;
- [x] poznámky;
- [x] poslední pozice;
- [x] detekce změny PDF;
- [x] automatický přechod na další soubor.

**Výstup:** kontrolu lze přerušit a kdykoli obnovit.

### Etapa 6 – dokončení UI

- [x] filtry;
- [x] počty stavů;
- [x] zoom slider;
- [x] overlay switch;
- [x] světlý a tmavý režim;
- [x] klávesové zkratky;
- [x] chybová a stavová hlášení;
- [x] export CSV.

**Výstup:** použitelná první verze.

### Etapa 7 – testy a distribuce

- [x] automatické testy (10 testů);
- [ ] test na reálné složce s větším počtem PDF;
- [x] základní syntetické měření jednoho paketu;
- [ ] test Windows;
- [ ] test Linux;
- [ ] rozhodnutí o způsobu balení;
- [x] instalační a spouštěcí pokyny.

**Výstup:** reprodukovatelně spustitelná verze.

---

## 16. Věci mimo rozsah první verze

- přímé opravy OCR vrstvy;
- ukládání změn do PDF;
- OCR rozpoznávání nových dokumentů;
- porovnávání dvou verzí PDF;
- automatické jazykové hodnocení správnosti OCR;
- anotace jednotlivých slov;
- více současně připojených klientů;
- síťový nebo cloudový režim;
- rekurzivní procházení podsložek;
- automatické párování přejmenovaných PDF podle úplného hashe;
- pluginový systém.

Tyto funkce lze doplnit až po ověření základního kontrolního workflow.

---

## 17. Pravidla pro pokračování v rozdělané práci

Po každé dokončené pracovní jednotce se musí upravit tento README:

1. zaškrtnout skutečně dokončené úkoly;
2. aktualizovat sekci **Aktuální pracovní stav**;
3. uvést přesný následující krok;
4. zapsat důležité technické rozhodnutí do **Decision logu**;
5. zapsat známé chyby nebo neověřené části;
6. nepovažovat experiment za hotovou funkci bez testu;
7. při změně architektury upravit nejdříve plán a až potom kód.

### Aktuální pracovní stav

```text
Phase: 3 – integration and manual verification
Completed: project skeleton, PDF backend, folder scan, manifest, binary packet, WebUI UI, OCR modes, lazy loading prototype, CSV export, read-only viewing fallback, 10 automated tests
In progress: verification of the actual WebUI browser transport and native folder dialog
Next action: install webui2 in a normal environment and run a smoke test with a real OCR PDF
Blocking issue: webui2 is not available in the restricted package index used during this implementation session
Known limitation: rendering is serialized inside callbacks; render_worker.py is not implemented yet
Known limitation: platform acceptance tests and the asynchronous render worker are not implemented
Last verified reference commit: 538123e061622a702709a1dd9c5a22cd32592dd3
Last verified UI commit: 72070fe146df89d3e0a6325a0475783bfda6d40d
```

### Decision log

| Datum | Rozhodnutí | Důvod |
|---|---|---|
| 2026-08-04 | Použít WebUI místo PySide6 | Uživatel zvolil WebUI a dodal referenční projekt |
| 2026-08-04 | Použít manifest JSON místo SQLite | Rozsah stavu je malý a lokální |
| 2026-08-04 | Jeden společný scroll pro sken a OCR | Zaručí trvalé vertikální zarovnání |
| 2026-08-04 | Převzít ovládací a synchronizační vzory z dodaného příkladu | Jednotný ověřený základ projektu |
| 2026-08-04 | Nepoužívat frontend jako Git submodul | UI bude specifické pro `pdf-ocr-reviewer` |
| 2026-08-04 | První verze PDF pouze čte | Oddělení kontroly od pozdějších oprav |
| 2026-08-04 | Název projektu je `pdf-ocr-reviewer` | Přesně popisuje účel a je vhodný pro repozitář i balíček |
| 2026-08-04 | Použít pouze ručně udržovaný CSS, bez SCSS | Sestavení CSS není pro rozsah UI potřebné |
| 2026-08-04 | Nepřidávat samostatný režim `--server` | Aplikace je určena jako lokální jednouživatelské GUI |
| 2026-08-04 | Výběr složky řešit backendovým dialogem | Webové API nepředá Pythonu absolutní cestu; první implementace bude `tkinter.filedialog.askdirectory()` |
| 2026-08-04 | Přenos stránky používá 4B délku JSON hlavičky, JSON a následný PNG payload | Formát lze jednoznačně rozdělit v Pythonu i JavaScriptu |
| 2026-08-04 | Přístup k aktivnímu PyMuPDF dokumentu serializovat pomocí `threading.RLock` | WebUI může obsluhovat callbacky souběžně; jeden dokument se nesmí zpracovávat souběžně |
| 2026-08-04 | Frontend udržuje nejvýše osm vzdáleně načtených stran | Lazy loading sám o sobě neuvolní stránky, kterými už uživatel prošel |

### Work log

| Datum | Provedeno | Výsledek |
|---|---|---|
| 2026-08-04 | Prozkoumán dodaný ZIP, hlavní Python backend, HTML, JavaScript, CSS a Git metadata | Identifikovány prvky použitelné pro `pdf-ocr-reviewer` |
| 2026-08-04 | Sestaven implementační plán | Čeká na schválení uživatelem |
| 2026-08-04 | Plán upraven: název, čistý CSS, odstranění server mode a volba backendového dialogu | README odpovídá aktuálním rozhodnutím |
| 2026-08-04 | Vytvořena struktura projektu, backend API, manifest, skener složky, PDF služba a binární paket | Backend lze testovat bez spuštěného WebUI |
| 2026-08-04 | Vytvořen WebUI frontend se seznamem PDF, společným scrollem, OCR režimy, overlayem, zoomem, filtry a klávesami | Implementace je připravena k ručnímu smoke testu |
| 2026-08-04 | Doplněna serializace PyMuPDF a uvolňování vzdálených Blob URL | Odstraněna dvě rizika souběhu a růstu paměti |
| 2026-08-04 | Spuštěno `pytest -q` a kontrola syntaxe Pythonu i JavaScriptu | 10 testů prošlo; `node --check ui/index.js` bez chyby |
| 2026-08-04 | Syntetická stránka 1200 px / 405 slov: render a sestavení paketu | 130,171 ms; paket 424 251 B; PNG 366 923 B; JSON 57 324 B; tracemalloc peak 1 219 660 B |
| 2026-08-04 | Doplněn export CSV a fallback při selhání zápisu manifestu | PDF lze dál otevřít a vykreslit; chyba ukládání je předána UI |

---

## 18. Známé neověřené části prototypu

- V tomto pracovním prostředí nebylo možné nainstalovat `webui2`, protože použitý omezený balíčkový index balíček nenabízí. Backend i frontend proto prošly automatickými a syntaktickými testy, ale skutečné otevření okna a přenos přes `send_raw` ještě nebyly ručně ověřeny.
- `render_worker.py` je zatím záměrně pouze rezervovaný modul. Vykreslování probíhá synchronně v callbacku a je serializováno zámkem.
- Prohlížení při selhání zápisu manifestu je ověřeno automatickým testem se simulovanou chybou; skutečná nezapisovatelná složka na cílovém systému ještě nebyla ručně vyzkoušena.
- Layout zobrazuje OCR po slovech z `get_text("words")`; znakový režim z `rawdict` zatím není přidán.
- Nebyly provedeny přijímací testy na Windows, Linuxu ani na dlouhém reálném dokumentu.

---

## 19. Původně odsouhlasený rozsah

Schválením tohoto plánu se potvrzuje zejména:

- WebUI + Python + PyMuPDF;
- vanilla JavaScript a ručně udržovaný CSS bez SCSS;
- `pdf-ocr-reviewer.manifest.json` bez SQLite;
- jeden společný scroll pro prostřední a pravý sloupec;
- první verze PDF pouze kontroluje a nemění;
- tři OCR režimy a volitelný overlay;
- lazy loading viditelných stran;
- stav souboru, problematické stránky, poznámka a obnovení pozice;
- backendový výběr složky s první implementací přes `tkinter.filedialog.askdirectory()`;
- žádný samostatný režim `--server`;
- technický prototyp přenosu jedné stránky přes `send_raw()` jako první implementační krok;
- rekurzivní složky, editace OCR a automatické opravy až mimo první verzi.
