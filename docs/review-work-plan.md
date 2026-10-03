# Plán práce po code review

Datum: 2026-09-29. Výchozí revize: `02afcfb` (`v0.1.4`).
Stav: etapy 1–5 implementovány; uživatel ergonomii schválil 2026-10-03.
Etapa 6 je dokončena, měření a rozhodnutí jsou v [performance.md](performance.md).
Kontroly etapy 7 prošly 2026-10-03 na Linuxu i Windows, včetně souborových zámků
a self-testů obou binárek: [úspěšný běh CI](https://github.com/triuk/pdf-ocr-reviewer/actions/runs/37112115852).
Release commit připravuje v0.1.5; workflow vydání zveřejní až po opakovaném
úspěšném ověření finálního commitu.

Plán pokrývá sedm nálezů z celkového code review a navržená vylepšení
testování, ergonomie, zotavení po chybě a výkonu. Nejvyšší prioritu má
ochrana připomínek a výsledků oprav, poté správnost ovládání.

## Zachované požadavky

- `pdf-ocr-reviewer.manifest.json` zůstává společným zadáním a evidencí oprav.
- Krátký prompt s rozsahem PDF zůstává dostačující; technický postup popisuje
  aktuální `repair_instructions` v manifestu.
- Reviewer sám neupravuje PDF. Vrácení opravy znovu otevírá připomínku.
- Zachovat stavy open/fixed/verified/dismissed, historii, barevné označení,
  klávesové zkratky, název „Špatná velikost boxu“ a křížek přímo na boxu.
- Zachovat načítání dosavadních manifestů i neznámá rozšiřující pole.
- Zálohy a neuložené koncepty jsou pomocná data; platné zadání oprav zůstává
  v manifestu. Jejich umístění a obnova budou dokumentované.

## 1. Bezpečný zápis a validace manifestu

Priorita: nejvyšší. Řeší nálezy 1, 4 a 7; podmínka pro další úpravy persistence.

- [x] Přidat regresní test zápisu druhého procesu mezi kontrolou revize a
      nahrazením manifestu.
- [x] Zavést společný zápisový helper a protokol zamčení pro reviewer i externí
      opravný nástroj. Kontrola očekávané revize a atomický zápis proběhnou pod
      týmž zámkem. Konflikt nesmí být vyřešen slepým opakováním nad novou revizí.
- [x] Ošetřit souběh dvou instancí, timeout zámku a ukončení procesu; ověřit
      chování na Linuxu i Windows. Nepodporovaný zámek nesmí tiše vypnout ochranu.
- [x] Zpřístupnit helper externímu opravnému postupu a aktualizovat instrukce
      i dokumentaci. Popsat hranici ochrany: nespolupracující přímý zápis cizího
      programu nelze tímto protokolem plně zabezpečit.
- [x] Doplnit typovou validaci všech známých používaných polí, včetně resources,
      identity, poznámek a nastavení UI. Chyby musí obsahovat cestu k poli a
      skončit řízenou odpovědí API. Neznámá pole zachovat.
- [x] Při otevření PDF ověřit použitelnost odkazů na stránky a geometrii
      připomínek; neplatná připomínka nesmí vypadat jako platná k potvrzení.
- [x] Změny nastavení validovat nad kopií a převzít až jako celek. Odmítnutý
      požadavek nesmí změnit paměť ani později prosáknout na disk.
- [x] Aktualizovat starší vestavěné repair_instructions řízenou migrací;
      zachovat uživatelská rozšíření a popsat změnu protokolu.

Hotovo, když testy souběhu neztratí cizí změny, chybná data mají srozumitelné
chyby a odmítnuté operace nezmění stav. Ověřit také starší manifesty,
neznámá pole, složku pouze pro čtení a selhání zápisu.

Implementováno a automaticky ověřeno na Linuxu i Windows: společný zámek,
CLI, validace a atomické změny nastavení. CI zahrnuje souběžné procesy,
timeout zámku a uvolnění zámku po ukončení procesu.

## 2. Spolehlivé přepínání dokumentů a opožděné odpovědi

Priorita: vysoká. Řeší nálezy 2 a 3.

- [x] Zavést jednotný kontext požadavku: identita otevřené složky, soubor,
      generace dokumentu a podle operace revize PDF/manifestu.
- [x] Opravit stav souboru, problémové stránky, ukládání poznámek, odpovědi
      připomínek a automatický přechod. Odpověď patří původnímu kontextu;
      nesmí změnit mezitím otevřený dokument ani spustit jeho navigaci.
- [x] Ošetřit stejný název PDF ve dvou různých složkách i více rychlých
      požadavků na otevření. Ochranu kontextu uplatnit také na backendu.
- [x] Nový dokument otevřít a ověřit před výměnou aktivního. Při selhání
      zachovat původní plně funkční dokument, nebo zobrazit jednoznačný prázdný
      stav, pokud původní kontext už neexistuje.
- [x] Zamezit ztrátě novějšího konceptu při dokončení staršího autosave.
- [x] Přidat deterministické JS testy s řízeným pořadím odpovědí a integrační
      scénáře přepnutí během zápisu, reloadu a chyby otevření PDF.

Hotovo, když rychlé přepínání nemění cizí soubor ani neztrácí text a po chybě
otevření odpovídají zobrazený dokument, jeho ovládání a backend stejnému stavu.

## 3. Navigace podle filtrů a správné rozlišení stránek

Priorita: střední. Řeší nálezy 5 a 6. Navazuje na kontext požadavků z etapy 2.

- [x] Sdílet výběr souborů mezi seznamem, šipkami a automatickým přechodem.
      Zohlednit aktivní filtry, prázdný výsledek i soubor, který po změně stavu
      z právě použitého filtru zmizí.
- [x] Zavést revizi renderu nebo explicitní požadované rozlišení. Změna zoomu
      zneplatní rozpracované obrázky v nesprávném rozlišení a zajistí nové načtení.
- [x] Zachovat správnou polohu OCR a připomínek při změně zoomu; staré výsledky
      nesmějí nahrazovat novější ani hromadit Blob URL.
- [x] Přidat testy kombinovaných filtrů, automatického přechodu, rychlých
      změn zoomu a zpožděných obrazových paketů.

Hotovo, když navigace prochází pouze odpovídající soubory a po dokončení
načítání viditelné stránky odpovídají poslednímu zoomu.

## 4. Zotavení po chybě a restartu

Priorita: střední. Navazuje na bezpečný zápis a kontext dokumentů.

- [x] Uchovávat omezený počet ověřených záloh manifestu. Chybný manifest nesmí
      přepsat poslední použitelnou zálohu; obnova nesmí tiše zahodit novější stav.
- [x] Průběžně ukládat rozepsané poznámky do lokálního úložiště aplikace,
      nezávislého na dostupnosti sdíleného manifestu a náhodném portu WebUI.
- [x] Koncepty jednoznačně přiřadit ke složce, PDF, připomínce a výchozí revizi.
      Smazat je teprve po potvrzeném zápisu odpovídajícího obsahu.
- [x] Po restartu nabídnout obnovený koncept přímo v příslušném editoru.
      Při souběžné úpravě nebo chybějící připomínce zachovat oba texty a umožnit
      jejich vyřešení bez tichého přepsání.
- [x] Ověřit restart s neuloženou poznámkou, změnu PDF, chybějící soubor,
      poškozený manifest a nedostatek oprávnění k zápisu.

Hotovo, když lze obnovit neuložený text i poslední platný manifest a aplikace
srozumitelně rozlišuje uložený stav, koncept a konflikt.

## 5. Ergonomie připomínek

- [x] Filtry PDF kombinují název, stav souboru a připomínky; navigace je respektuje.
- [x] J/K vybírá připomínky v PDF, N otevře poznámku, M označování.
- [x] Po zpětné vazbě odstranit potvrzování V → C a vracení R.
- [x] Červené i modré ponechané označení je zadání pro další externí OCR průchod.
- [x] Spokojený uživatel smaže označení × přímo na boxu, ostatní ponechá.
- [x] Smazané i dříve potvrzené označení je v Archivu s možností obnovy.
- [x] Aktualizovat manifestové instrukce a migrovat původní pravidla bez ztráty historie.
- [x] Ověřit externí výsledek, smazání/obnovu, opakovaný průchod a filtry přes více PDF.
- [x] Zjednodušit lištu: Obnovit, nezávislé OK u každého PDF vlevo, Zálohy/CSV v nabídce Další.
- [x] Uživatelsky ověřit zjednodušený postup podle `ergonomics-acceptance.md` (schváleno 2026-10-03).

OCR běží mimo program; reviewer pouze připravuje manifest a načítá výsledky.
Uživatelská zkouška je schválená; navazující etapa 6 je dokončená.

## 6. Výkon autosave a renderování

Priorita: po dokončení správnosti. Optimalizace podložit měřením.

- [x] Změřit latenci uložení, počty zápisů, dobu hashování a odezvu při
      renderování na velkém PDF i manifestu s mnoha připomínkami a historií.
- [x] Sloučit zbytečně časté zápisy nastavení a autosave při zachování
      spolehlivého dokončení před přechodem mezi kontexty.
- [x] Omezit kopírování celého manifestu, vracení všech připomínek a
      překreslování seznamů tam, kde měření prokáže dopad.
- [x] Navrhnout opětovné použití ověřeného hashe pouze s jasnými pravidly
      zneplatnění. Nezaměnit pouhou shodu velikosti a času souboru za záruku
      shodného obsahu; zachovat kontrolu verze před uložením připomínky.
- [x] Omezit frontu nepotřebných renderů a velikost výsledného rastru podle
      počtu pixelů. Změnu renderovací architektury provést jen při doložené potřebě.
- [x] Zapsat srovnání před/po na stejných datech a ověřit regresní scénáře.

Výsledky: poznámka 452 → 147 ms, odpověď 3,5 MB → 4,2 kB; beze změny
se nezapisuje manifest. SHA-256 zůstává plný při každé mutaci. Fronta má jeden
aktivní render, obrázek nejvýše 8 MP. Přepis DOM a hash cache nemají doložený
bezpečný přínos a nezavádějí se. Viz podrobné měření.

Hotovo, když měření doloží přínos změn a zůstanou splněny podmínky integrity
dat, detekce změněného PDF a omezené spotřeby paměti.

## 7. Automatické kontroly, dokumentace a vydání

Testy doplňovat průběžně v etapách 1–6; tato etapa dokončí jejich zapojení a
ověří celý výsledek.

- [x] Zařadit Python a JS regresní testy do CI; souborové zámky testovat
      na Linuxu i Windows.
- [x] Zařadit prohlížečový smoke test přes skutečné WebUI na Linuxu.
      Používat malé syntetické PDF, včetně otočené/oříznuté stránky;
      uživatelovo PDF nesmí být nutnou součástí CI.
- [x] Zachovat self-test zdrojové aplikace a obou zabalených binárek.
- [x] Ověřit integračně externí opravu, načtení výsledků, smazání,
      obnovení připomínky a obnovu po konfliktu či restartu.
- [x] Aktualizovat popis manifestu, API, klávesových zkratek, záloh a externího
      zápisového postupu; uvést skutečně ověřené platformy a známé limity.
- [x] Připravit release poznámky a vydání až po splnění přejímacích podmínek.
      Publikaci v0.1.5 provede workflow po kontrolách release commitu.

## Postup práce a další krok

Každou etapu rozdělit do samostatně kontrolovatelných commitů; změnu chování
spojit s příslušným regresním testem. Po dokončení aktualizovat tento checklist
i stav v `implementation-plan.md`. Odhad výkonu ani experiment neoznačovat
za hotovou funkci bez ověření.

Etapy 1–3 tvoří první celek oprav potvrzených chyb. Etapy 4–6 přidávají
odsouhlasená vylepšení. Etapa 7 je společná podmínka vydání.

Nejbližší konkrétní krok: nechat workflow ověřit release commit a publikovat
v0.1.5; poté ověřit dostupnost obou binárek a jejich kontrolní součty.
Změny jsou rozděleny do samostatných commitů.

Výchozí ověření z code review 2026-09-28: 42 úspěšných Python testů,
aplikační self-test a prohlížečový smoke test na dočasné kopii dodaného PDF.
Sedm nálezů bylo reprodukováno samostatně a následně pokryto trvalými
regresními testy. Závěrečné CI obsahuje 83 Python testů a 23 JS scénářů.
