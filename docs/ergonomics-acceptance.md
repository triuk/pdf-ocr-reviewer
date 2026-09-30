# Uživatelská zkouška ergonomie

Aktualizováno 2026-09-30 podle zpětné vazby: OCR průchody probíhají mimo program,
manifest je jejich řídicí soubor. Potvrzování V → C ani vracení R už není potřeba.
Výkonová etapa 6 ani nové vydání zatím nejsou zahájené.

## Spuštění připravené Linuxové verze

Z kořene projektu spusťte:

```bash
./dist/spustit-test-ergonomie.sh
```

Spouštěč používá `dist/pdf-ocr-reviewer-ergonomie`, složku
`dist/ergonomie-demo` a samostatné lokální koncepty v `dist/ergonomie-state`.
Aktualizuje se binárka; vaše dosavadní testovací poznámky a označení zůstávají.
Staré manifestové instrukce se při uložení převedou na nový postup.

Tři PDF jsou zkušební kopie. Barevné stavy oprav jsou simulované pro test
ovládání; nejsou dokladem provedené opravy OCR. Původní PDF se nemění.

## Co vyzkoušet

1. **Označení:** M zapne označování. Vyberte „Špatná velikost boxu“, klikněte
   na slovo nebo tažením označte oblast. Poznámka se ukládá automaticky,
   typ další připomínky zůstává zapamatovaný.
2. **Po externí opravě:** použijte „Obnovit“. V ukázce jsou některá místa
   už modrá. Pokud výsledek vyhovuje, smažte označení × přímo na boxu.
   Po smazání se vybere další připomínka podle aktuálního filtru; po poslední
   zbývající se výběr vyprázdní. Pokud nevyhovuje, prostě ho ponechte; případně doplňte poznámku.
3. **Další průchod:** není potřeba nic potvrzovat ani přebarvovat. Externí
   nástroj podle manifestu zpracuje červená i modrá ponechaná označení.
   Smazaná místa vynechá. Zkušební aplikace sama žádnou OCR opravu nespouští.
4. **Navigace a obnova:** „Má ponechané připomínky“ filtruje PDF s červenými
   i modrými místy, „Má místa po opravě“ jen PDF s modrými. J/K přechází mezi
   místy v aktuálním PDF, X smaže vybrané označení, N otevře poznámku.
   Omylem smazané označení najdete v „Archiv“ a vrátíte pomocí „Obnovit označení“. Dříve potvrzená označení
   ze staré verze jsou také v Archivu a automaticky se neopravují.
5. **Dokončená prohlídka:** zaškrtněte „OK“ u názvu souboru vlevo. Vyzkoušejte
   i jiný než otevřený soubor: pravá část se nepřepne, připomínky zůstávají. Zrušte zaškrtnutí a zkuste filtr dokončení vlevo.
   V nabídce „Další“ najdete Zálohy a Export CSV; zavře se i přes Esc či klik ven.
6. **Návrat k práci:** zavřete aplikaci, spusťte ji znovu a zkontrolujte
   ponechaná místa, poznámky a Archiv.

Stačí zpětná vazba, kde bylo nutné hledat ovládání, zbytečně klikat nebo
vracet fokus. U chyby pomůže název PDF, poslední akce a očekávaný výsledek.

## Opakovatelnost a ověření

Novou zkušební sadu vytvoříte takto; existující složka se nepřepíše:

```bash
python tools/create_ergonomics_demo.py /nova/testovaci/slozka --source /cesta/ke/kopirovanemu.pdf
```

Bez `--source` vzniknou syntetické PDF. Pro běh ze zdrojů použijte
`python main.py --folder /nova/testovaci/slozka`.

Lokálně na Linuxu prošlo 74 Python testů a 13 JS scénářů. Skutečný WebUI/Chromium
průchod ověřil označení, autosave, smazání/obnovu, ponechané modré označení při
druhém externím průchodu, filtry přes dvě PDF, konflikt, restart, obnovu poznámky
a výběr zálohy. Zdrojový i zabalený self-test prošly před předáním binárky.
Windows běh a úplné CI dosud nebyly v této práci provedeny. Výkon a veřejné
vydání patří do dalších etap po uživatelské zkoušce.
