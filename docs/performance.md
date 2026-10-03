# Výkon: měření a rozhodnutí (2026-10-03)

Ergonomii uživatel schválil 2026-10-03. Měřená sada: 60 stran, 86,8 MB PDF,
1 000 připomínek s 20 položkami historie, manifest 6,64 MB. Deterministický
syntetický sken (seed 42), Linux, Python 3.14.7, PyMuPDF 1.26.7. Pět vzorků na
operaci, skutečné atomické zápisy, fsync a zálohy. Každý běh používá novou
složku v /tmp. Součástí času je serializace odpovědi API; síť a DOM nikoli.

| Operace | Před, medián | Po, medián |
|---|---:|---:|
| Uložení poznámky připomínky | 451,58 ms | 146,52 ms |
| Uložení poznámky PDF | 231,15 ms | 93,46 ms |
| Nastavení UI | 321,10 ms | 93,49 ms |
| Uložení stejné stránky | 238,58 ms | 3,84 ms |
| SHA-256 celého PDF | 49,48 ms | 50,55 ms |
| Render šířky 1 200 px | 172,28 ms | 171,23 ms |
| Render šířky 2 400 px | 180,88 ms | 181,62 ms |

Odpověď při změně jedné připomínky klesla z 3 493 629 na 4 227 bajtů.
API vrací změněnou připomínku a počty; celé pole načítá při otevření PDF.
Historie a neznámá rozšíření manifestu zůstávají zachované. Python API má nadále
možnost úplné odpovědi. Kopírují se jen měněné větve manifestu a upravovaná
připomínka; serializace čte ostatní hodnoty pod aplikačním zámkem. Neúspěšný
zápis vrací původní stav bez změn sdílených vnořených objektů.

Stejná pozice či hodnota už nevytváří zápis ani zálohu, ale stále ověřuje revizi
pod společným zámkem. Ve vzorcích nastavení se jeden z pěti zápisů stal no-op;
zbývající čtyři jsou skutečné zápisy. Rychlé změny nastavení UI se slučují za
220 ms. Regresní scénář pěti změn názvového filtru a jedné změny zoomu odesílá
jeden zápis před přechodem do jiného dokumentu. Novější změny během zápisu se
dopíší v pořadí. Poznámky se nadále žurnálují a před navigací dopisují.

SHA-256 PDF se **neukládá do cache podle velikosti/času souboru**. Úspora z
vynechání kontroly by v této sadě byla přibližně 50 ms za mutaci, ale stejná
velikost a obnovený čas nevylučují změnu obsahu externím OCR. Regresní test
výslovně mění bajty při zachované velikosti a mtime a vyžaduje odmítnutí zápisu.
Bez spolehlivé vazby na neměnný obsah není další opětovné použití hashe oprávněné.

Opakování:

```bash
python tools/benchmark_review.py --output /tmp/review.json
python tools/benchmark_review.py --pdf /cesta/k/velkemu.pdf --output /tmp/real-review.json
```

Oba benchmarky (`benchmark_review.py` i `benchmark_page.py`) zapisují pouze do
dočasných kopií. Zdrojové PDF ani jeho sousední manifest se nemění. Výsledky
jsou v [původním měření](measurements/review-before.json) a
[měření po úpravě](measurements/review-after.json). Časy závisí na stroji,
úložišti a obsahu PDF; nejsou limitem v CI. CI ověřuje počty zápisů, integritu,
pořadí odpovědí a omezení renderování deterministickými testy.

## Fronta renderování a velikost rastru

Původní frontend při nárazovém požadavku na osm stran odeslal všech osm ještě
před dokončením první. Backend je zpracovává pod jedním zámkem, takže se tím
nevytvořil paralelní výkon. Nyní je odeslaný nejvýše jeden render; čekající
požadavky se sloučí podle stránky a rozlišení se určí až při odeslání. Pokud se
uživatel mezitím přesune k poslední straně, reprodukce provede dva rendery místo
osmi. Změna PDF zahodí starou frontu, změna zoomu ponechá pouze poslední rozlišení.
Rozpracovaný nativní render se násilně nepřerušuje.

Jednotlivý rastr je omezen na 8 milionů pixelů a 16 384 pixelů na delší straně.
Pro stránku 100 × 10 000 bodů by samotný požadavek šířky 4 000 px znamenal
1,6 miliardy pixelů (4,8 GB surových RGB dat); limit ho zmenší před alokací.
OCR souřadnice i text zůstávají v rozměrech stránky. Testy kontrolují extrémní
poměry stran a běžnou stránku při maximálním zoomu. PNG komprese, dekódované
obrázky v prohlížeči a paměť PyMuPDF mají další režii; limit není slibem celkové
spotřeby RAM aplikace. Threadový renderer, cache PDF hashů a přepis DOM seznamů
se nezavádějí bez dalšího doloženého přínosu.
