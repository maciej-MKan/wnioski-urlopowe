// Wierny podgląd/„PDF" wniosku dla dema — odwzorowanie backendowych szablonów Jinja
// (app/templates/*.html) + druk do ukrytego iframe (bez popupów). Zamiast uproszczonego
// window.open renderujemy dokument A4 identyczny jak z WeasyPrint i drukujemy „Zapisz jako PDF".
import { calendarDays, type LeaveRecord } from "./domain";
import { typeById } from "./registry";

const esc = (s: string): string => (s || "").replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c] as string));

// ---------------- Filtry dat (odpowiednik app/infrastructure/formatting.py) ----------------
const MIESIACE = [
  "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
  "lipca", "sierpnia", "września", "października", "listopada", "grudnia",
];
type YMD = { y: number; m: number; day: number };
const parseISO = (d?: string): YMD | null => {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec((d || "").trim());
  return m ? { y: +m[1], m: +m[2], day: +m[3] } : null;
};
/** '2026-07-24' → '24 lipca 2026 r.'; nierozpoznane wejście zwracamy bez zmian. */
const slownie = (d?: string): string => {
  const p = parseISO(d);
  return p ? `${p.day} ${MIESIACE[p.m - 1]} ${p.y} r.` : (d || "");
};
/** '2026-07-24' → '24.07.2026'; nierozpoznane wejście zwracamy bez zmian. */
const krotko = (d?: string): string => {
  const p = parseISO(d);
  if (!p) return d || "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(p.day)}.${pad(p.m)}.${p.y}`;
};
/** Odmiana słowa „dzień" przez liczbę (1 → „dnia", inaczej → „dni"). */
const dniSlowo = (n: string): string => (parseInt(String(n).trim(), 10) === 1 ? "dnia" : "dni");
const dniKalendarzowe = (od?: string, doo?: string): number =>
  (od && doo ? calendarDays(od, doo) : 0);

// Wielokropek na brakujące pole (jak w szablonach backendu).
const DOTS = ".....................................................";

// ---------------- Treści per typ (odpowiednik app/templates/<typ>.html) ----------------
type Dane = Record<string, string>;

function trescWypoczynkowy(d: Dane): string {
  const cal = dniKalendarzowe(d.data_od, d.data_do);
  const liczba = d.liczba_dni || (cal > 0 ? String(cal) : "");
  const rok = d.rok_rozliczenia || (d.data_od ? d.data_od.slice(0, 4) : "");
  const termin = d.data_od || d.data_do
    ? `${d.data_od ? `od <strong>${esc(krotko(d.data_od))}</strong>` : ""}${d.data_do ? ` do <strong>${esc(krotko(d.data_do))}</strong>` : ""}`
    : "od dnia ..................... do dnia .....................";
  return `
    <p>Na podstawie art.&nbsp;152 i&nbsp;art.&nbsp;163 Kodeksu pracy zwracam się z uprzejmą prośbą
       o udzielenie mi urlopu wypoczynkowego${liczba ? ` w wymiarze <strong>${esc(liczba)}</strong> ${dniSlowo(liczba)}` : ""}
       w terminie ${termin}.</p>
    <p class="podstawa">Za okres nieobecności proszę o rozliczenie urlopu z przysługującego mi
       wymiaru urlopu wypoczynkowego${rok ? ` za rok <strong>${esc(rok)}</strong>` : ""}.</p>`;
}

function trescOjcowski(d: Dane): string {
  const termin = d.data_od || d.data_do
    ? `${d.data_od ? `od <strong>${esc(krotko(d.data_od))}</strong>` : ""}${d.data_do ? ` do <strong>${esc(krotko(d.data_do))}</strong>` : ""}`
    : "od dnia ..................... do dnia .....................";
  return `
    <p>Na podstawie art.&nbsp;182<sup>3</sup> Kodeksu pracy zwracam się z wnioskiem
       o udzielenie mi urlopu ojcowskiego${d.wymiar ? ` w wymiarze <strong>${esc(d.wymiar)}</strong>` : ""}
       w terminie ${termin}.</p>
    <p>Urlopu ojcowskiego dotyczy dziecko:</p>
    <table class="dane-tabela">
      <tr><td class="klucz">Imię i nazwisko dziecka:</td>
          <td><strong>${d.dziecko_imie_nazwisko ? esc(d.dziecko_imie_nazwisko) : DOTS}</strong></td></tr>
      <tr><td class="klucz">Data urodzenia dziecka:</td>
          <td><strong>${d.dziecko_data_urodzenia ? esc(krotko(d.dziecko_data_urodzenia)) : DOTS}</strong></td></tr>
    </table>
    <p class="podstawa">Oświadczam, że nie korzystałem/-am dotychczas z urlopu ojcowskiego na powyższe
       dziecko w wymiarze wyczerpującym uprawnienie wynikające z art.&nbsp;182<sup>3</sup> Kodeksu pracy.</p>`;
}

function trescOpieka(d: Dane): string {
  const jednostka = d.forma === "godziny" ? "godzin" : "dni";
  const godziny = d.godzina_od && d.godzina_do
    ? `${esc(d.godzina_od)}–${esc(d.godzina_do)}`
    : (d.godzina_od ? `od ${esc(d.godzina_od)}` : "");
  let termin: string;
  if (d.forma === "godziny" && d.data_od) {
    termin = `w dniu <strong>${esc(krotko(d.data_od))}</strong>` +
      (d.data_do && d.data_do !== d.data_od ? ` – <strong>${esc(krotko(d.data_do))}</strong>` : "") +
      (godziny ? ` w godzinach <strong>${godziny}</strong>` : "") + ".";
  } else if (d.data_od) {
    termin = `od <strong>${esc(krotko(d.data_od))}</strong>` +
      (d.data_do ? ` do <strong>${esc(krotko(d.data_do))}</strong>` : "") + ".";
  } else {
    termin = "..................................................................... .";
  }
  return `
    <p>Na podstawie art.&nbsp;188 Kodeksu pracy wnoszę o udzielenie mi zwolnienia od pracy
       z tytułu sprawowania opieki nad dzieckiem w wieku do lat 14${d.wymiar ? `, w wymiarze <strong>${esc(d.wymiar)} ${jednostka}</strong>` : ""}.</p>
    <p>Zwolnienie wykorzystam w terminie: ${termin}</p>
    <p>Zwolnienie dotyczy dziecka:</p>
    <table class="dane-tabela">
      <tr><td class="klucz">Imię i nazwisko dziecka:</td>
          <td><strong>${d.dziecko_imie_nazwisko ? esc(d.dziecko_imie_nazwisko) : DOTS}</strong></td></tr>
      <tr><td class="klucz">Data urodzenia dziecka:</td>
          <td><strong>${d.dziecko_data_urodzenia ? esc(krotko(d.dziecko_data_urodzenia)) : DOTS}</strong></td></tr>
    </table>
    <p class="podstawa">Oświadczam, że drugi z rodziców / opiekunów nie korzysta z tego samego
       uprawnienia w wymiarze wyczerpującym roczny limit określony w art.&nbsp;188 Kodeksu pracy.</p>`;
}

function trescWolneZaSwieta(d: Dane): string {
  let termin: string;
  if (d.data_od && d.data_do && d.data_od !== d.data_do) {
    termin = `w terminie od <strong>${esc(krotko(d.data_od))}</strong> do <strong>${esc(krotko(d.data_do))}</strong>`;
  } else if (d.data_od) {
    termin = `w dniu <strong>${esc(krotko(d.data_od))}</strong>`;
  } else {
    termin = "w dniu .....................";
  }
  return `
    <p>Na podstawie art.&nbsp;130 §&nbsp;2 Kodeksu pracy zwracam się z uprzejmą prośbą o udzielenie mi
       dnia wolnego od pracy przysługującego w zamian za święto przypadające w sobotę
       (obniżające wymiar czasu pracy w okresie rozliczeniowym) ${termin}.</p>
    <p class="podstawa">Powyższy dzień wolny nie jest urlopem wypoczynkowym i nie obniża
       przysługującego mi wymiaru urlopu.</p>`;
}

const TYTULY: Record<string, string> = {
  wypoczynkowy: "Wniosek o udzielenie urlopu wypoczynkowego",
  ojcowski: "Wniosek o udzielenie urlopu ojcowskiego",
  opieka: "Wniosek o udzielenie zwolnienia od pracy na opiekę nad dzieckiem",
  wolne_za_swieta: "Wniosek o udzielenie dnia wolnego za święto przypadające w sobotę",
};
const TRESCI: Record<string, (d: Dane) => string> = {
  wypoczynkowy: trescWypoczynkowy,
  ojcowski: trescOjcowski,
  opieka: trescOpieka,
  wolne_za_swieta: trescWolneZaSwieta,
};

// ---------------- Dokument A4 (odpowiednik app/templates/base.html) ----------------
export function dokumentHtml(rec: LeaveRecord): string {
  const d: Dane = { ...rec.dane };
  d.data_od = d.data_od || rec.dataOd;
  d.data_do = d.data_do || rec.dataDo;

  const tytul = TYTULY[rec.typ] || (typeById(rec.typ)?.nazwa ?? rec.typ);
  const tresc = (TRESCI[rec.typ] || (() => `<p>${esc(tytul)}</p>`))(d);
  const dataDok = slownie(d.data);
  const pracodawcaLinie = (d.pracodawca || "").split("\n").map((l) => l.trim()).filter(Boolean);

  const naglowekPrawy = `${esc(d.miejscowosc || "")}${d.miejscowosc && dataDok ? ", " : ""}${esc(dataDok)}`;
  const adresat = pracodawcaLinie.length || d.dzial_kadr
    ? `<div class="adresat"><div class="etykieta">Do:</div>
        ${pracodawcaLinie.map((l) => `<div>${esc(l)}</div>`).join("")}
        ${d.dzial_kadr ? `<div>${esc(d.dzial_kadr)}</div>` : ""}
      </div>`
    : "";

  return `<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>${esc(tytul)}</title>
<style>
  @page { size: A4; margin: 28mm 25mm 25mm 25mm; }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  body {
    font-family: "DejaVu Sans", "Liberation Sans", Arial, sans-serif;
    font-size: 11.5pt; line-height: 1.55; color: #111;
    max-width: 210mm; margin: 0 auto; padding: 28mm 25mm 25mm 25mm; background: #fff;
  }
  @media print { body { padding: 0; max-width: none; } }
  .naglowek { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 26mm; }
  .pracownik { max-width: 55%; }
  .miejsce-data { text-align: right; white-space: nowrap; }
  .adresat { margin-left: auto; width: 47%; margin-bottom: 16mm; }
  .adresat .etykieta { color: #444; }
  .tytul { text-align: center; font-size: 13.5pt; font-weight: bold; letter-spacing: .3px;
           margin: 4mm 0 10mm 0; text-transform: uppercase; }
  .tresc p { margin: 0 0 4.5mm 0; text-align: justify; }
  .podstawa { color: #333; font-size: 10.5pt; }
  .dane-tabela { margin: 3mm 0 3mm 0; }
  .dane-tabela td { padding: 1mm 0; vertical-align: top; }
  .dane-tabela td.klucz { width: 48%; color: #333; padding-right: 6mm; }
  .adnotacje { margin-top: 16mm; padding-top: 4mm; border-top: 1px solid #ccc; color: #555; font-size: 9.5pt; }
  .adnotacje .rzad { display: flex; gap: 12mm; margin-top: 8mm; }
  .adnotacje .pole { flex: 1; border-top: 1px dotted #999; padding-top: 1.5mm; text-align: center; }
  strong { font-weight: bold; }
</style></head>
<body>
  <div class="naglowek">
    <div class="pracownik">
      ${d.imie_nazwisko ? `<div><strong>${esc(d.imie_nazwisko)}</strong></div>` : ""}
      ${d.stanowisko ? `<div>${esc(d.stanowisko)}</div>` : ""}
    </div>
    <div class="miejsce-data">${naglowekPrawy}</div>
  </div>
  ${adresat}
  <div class="tytul">${esc(tytul)}</div>
  <div class="tresc">${tresc}</div>
  <div class="adnotacje">
    <div>Decyzja pracodawcy / adnotacje:</div>
    <div class="rzad">
      <div class="pole">data i podpis przełożonego</div>
      <div class="pole">data i podpis osoby zatwierdzającej</div>
    </div>
  </div>
</body></html>`;
}

// ---------------- Druk przez ukryty iframe ----------------
/** Renderuje wniosek do ukrytego iframe i otwiera systemowy dialog druku („Zapisz jako PDF"). */
export function openPreview(rec: LeaveRecord): void {
  const iframe = document.createElement("iframe");
  iframe.setAttribute("aria-hidden", "true");
  // Bez allow-scripts (dokument nie ma JS); allow-same-origin — by rodzic mógł wywołać print(),
  // allow-modals — by dialog druku mógł się otworzyć z wnętrza ramki.
  iframe.setAttribute("sandbox", "allow-same-origin allow-modals");
  Object.assign(iframe.style, {
    position: "fixed", right: "0", bottom: "0", width: "0", height: "0", border: "0",
  });
  iframe.srcdoc = dokumentHtml(rec);

  iframe.onload = () => {
    const win = iframe.contentWindow;
    if (!win) { iframe.remove(); return; }
    const cleanup = () => setTimeout(() => iframe.remove(), 1000);
    win.addEventListener("afterprint", cleanup, { once: true });
    // Bezpiecznik: gdyby afterprint nie przyszedł (część przeglądarek), sprzątamy po czasie.
    setTimeout(() => { if (iframe.isConnected) iframe.remove(); }, 60000);
    win.focus();
    win.print();
  };

  document.body.appendChild(iframe);
}
