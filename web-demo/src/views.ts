import { backend } from "./backend";
import { STATUS_LABEL, calendarDays, type LeaveRecord, type Status } from "./domain";
import { typeById, type Field } from "./registry";

export type View = "kalendarz" | "nowy" | "saldo" | "profil";
export type AppState = {
  view: View;
  ym: { y: number; m: number }; // m: 1-12
  sel: string | null; // zaznaczony dzień (ISO)
  prefill: { od: string; to: string } | null;
};

const DOW = ["Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd"];
const MIES = ["styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec",
  "lipiec", "sierpień", "wrzesień", "październik", "listopad", "grudzień"];

const esc = (s: string): string => s.replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c] as string));

const alphaHex: Record<Status, string> = { zaakceptowany: "d9", do_akceptacji: "70", odrzucony: "30" };
function cellColor(rec: LeaveRecord | undefined): string {
  if (!rec) return "transparent";
  const base = typeById(rec.typ)?.kolor ?? "#888888";
  return base + alphaHex[rec.status];
}

const pad = (n: number) => String(n).padStart(2, "0");
const iso = (y: number, m: number, d: number) => `${y}-${pad(m)}-${pad(d)}`;
const recordsOn = (day: string): LeaveRecord[] =>
  backend.records().filter((r) => r.dataOd && r.dataDo && day >= r.dataOd && day <= r.dataDo);

// ---------------- Kalendarz ----------------
export function viewCalendar(root: HTMLElement, st: AppState, rerender: () => void): void {
  const { y, m } = st.ym;
  const first = new Date(y, m - 1, 1);
  const offset = (first.getDay() + 6) % 7; // pon = 0
  const days = new Date(y, m, 0).getDate();

  const cells: string[] = [];
  for (let i = 0; i < offset; i++) cells.push(`<div class="cal-cell empty"></div>`);
  for (let d = 1; d <= days; d++) {
    const day = iso(y, m, d);
    const rec = recordsOn(day)[0];
    const dow = new Date(y, m - 1, d).getDay();
    const weekend = dow === 0 || dow === 6;
    const cls = ["cal-cell", weekend ? "weekend" : "", st.sel === day ? "sel" : ""].join(" ");
    const bg = rec ? ` style="background:${cellColor(rec)}"` : "";
    cells.push(`<div class="${cls}"${bg} data-day="${day}">${d}</div>`);
  }

  root.innerHTML = `
    <div class="card">
      <div class="cal-head">
        <button class="ghost" data-nav="-1">‹</button>
        <div class="title">${MIES[m - 1]} ${y}</div>
        <button class="ghost" data-nav="1">›</button>
      </div>
      <div class="cal-grid">${DOW.map((x) => `<div class="cal-dow">${x}</div>`).join("")}</div>
      <div class="cal-grid" id="cal-cells">${cells.join("")}</div>
    </div>
    <div id="day-panel"></div>`;

  root.querySelectorAll<HTMLElement>("[data-nav]").forEach((b) =>
    b.addEventListener("click", () => {
      const delta = Number(b.dataset.nav);
      let nm = m + delta, ny = y;
      if (nm < 1) { nm = 12; ny--; } if (nm > 12) { nm = 1; ny++; }
      st.ym = { y: ny, m: nm }; st.sel = null; rerender();
    }));
  root.querySelectorAll<HTMLElement>("#cal-cells [data-day]").forEach((c) =>
    c.addEventListener("click", () => { st.sel = c.dataset.day!; rerender(); }));

  if (st.sel) renderDayPanel(root.querySelector("#day-panel")!, st, rerender);
}

function renderDayPanel(panel: HTMLElement, st: AppState, rerender: () => void): void {
  const day = st.sel!;
  const recs = recordsOn(day);
  const hol = backend.holiday(day);
  const rows = recs.map((r) => {
    const nazwa = typeById(r.typ)?.nazwa ?? r.typ;
    const zakres = r.dataOd === r.dataDo ? r.dataOd : `${r.dataOd} – ${r.dataDo}`;
    const acts = [
      r.status !== "zaakceptowany" ? `<button class="ghost" data-act="ok:${r.id}">Zaakceptuj</button>` : "",
      r.status !== "odrzucony" ? `<button class="ghost" data-act="no:${r.id}">Odrzuć</button>` : "",
      `<button class="ghost" data-act="pdf:${r.id}">PDF</button>`,
      `<button class="ghost" data-act="del:${r.id}">Usuń</button>`,
    ].join("");
    return `<div class="record-row"><div><b>${esc(nazwa)}</b><div class="muted">${zakres}</div></div>
      <span class="badge">${STATUS_LABEL[r.status]}</span><div class="actions">${acts}</div></div>`;
  }).join("");

  panel.innerHTML = `<div class="card">
    <h2>Dzień ${day}</h2>
    ${hol ? `<p class="muted">Święto: ${esc(hol)}</p>` : ""}
    <div class="actions" style="margin-bottom:8px">
      <button class="prim" data-new>Nowy wniosek na ten dzień</button>
    </div>
    ${rows || `<p class="muted">Brak urlopów.</p>`}
  </div>`;

  panel.querySelector("[data-new]")!.addEventListener("click", () => {
    st.view = "nowy"; st.prefill = { od: day, to: day }; rerender();
  });
  panel.querySelectorAll<HTMLElement>("[data-act]").forEach((b) =>
    b.addEventListener("click", () => {
      const [act, idS] = b.dataset.act!.split(":");
      const id = Number(idS);
      if (act === "ok") backend.setStatus(id, "zaakceptowany");
      else if (act === "no") backend.setStatus(id, "odrzucony");
      else if (act === "del") backend.remove(id);
      else if (act === "pdf") { openPreview(backend.records().find((r) => r.id === id)!); return; }
      rerender();
    }));
}

// ---------------- Nowy wniosek ----------------
export function viewCreate(root: HTMLElement, st: AppState, rerender: () => void): void {
  const typy = backend.activeTypes();
  const values: Record<string, string> = { ...backend.profile() };
  if (!values.data) values.data = new Date().toISOString().slice(0, 10);
  if (st.prefill) { values.data_od = st.prefill.od; values.data_do = st.prefill.to; }
  let activeTyp = typy[0]?.id ?? "";

  root.innerHTML = `<div class="card">
    <h2>Nowy wniosek</h2>
    <div class="tabs" id="type-tabs"></div>
    <div id="fields"></div>
    <div style="margin-top:8px"><button class="prim" id="submit">Utwórz wniosek</button>
      <span class="flash hidden" id="ok">dodano</span></div>
    <div id="post" style="margin-top:12px"></div>
  </div>`;

  const tabs = root.querySelector("#type-tabs")!;
  tabs.innerHTML = typy.map((t) =>
    `<span class="tab ${t.id === activeTyp ? "on" : ""}" data-typ="${t.id}">${esc(t.nazwa)}</span>`).join("");
  tabs.querySelectorAll<HTMLElement>("[data-typ]").forEach((el) =>
    el.addEventListener("click", () => { collect(); activeTyp = el.dataset.typ!; syncTabs(); renderFields(); }));

  const syncTabs = () => tabs.querySelectorAll<HTMLElement>("[data-typ]").forEach((el) =>
    el.classList.toggle("on", el.dataset.typ === activeTyp));

  const fieldsEl = root.querySelector("#fields")!;
  const renderField = (f: Field): string => {
    const v = esc(values[f.name] ?? "");
    const cls = f.szerokosc === "full" || f.typ === "textarea" ? "field full" : "field";
    let input: string;
    if (f.typ === "textarea") input = `<textarea id="f_${f.name}">${v}</textarea>`;
    else if (f.typ === "select") input = `<select id="f_${f.name}">${(f.opcje ?? []).map((o) =>
      `<option value="${o.value}" ${values[f.name] === o.value ? "selected" : ""}>${esc(o.label)}</option>`).join("")}</select>`;
    else input = `<input id="f_${f.name}" type="${f.typ === "date" ? "date" : "text"}" value="${v}" placeholder="${esc(f.placeholder ?? "")}">`;
    const hint = f.autoZZakresu && values.data_od && values.data_do
      ? `<div class="hint">Zakres obejmuje ${calendarDays(values.data_od, values.data_do)} dni kalendarzowych.</div>` : "";
    return `<div class="${cls}"><label>${esc(f.label)}</label>${input}${hint}</div>`;
  };
  function renderFields(): void {
    const t = typeById(activeTyp)!;
    fieldsEl.innerHTML =
      `<div class="grid">${t.pola.map(renderField).join("")}</div>
       <h2 style="margin:14px 0 8px">Dane wspólne</h2>
       <div class="grid">${backend.common().map(renderField).join("")}</div>`;
    // odśwież podpowiedź „auto z zakresu" po zmianie dat
    fieldsEl.querySelectorAll<HTMLInputElement>('input[type="date"]').forEach((el) =>
      el.addEventListener("change", () => { collect(); renderFields(); }));
  }
  function collect(): void {
    const t = typeById(activeTyp);
    [...(t?.pola ?? []), ...backend.common()].forEach((f) => {
      const el = document.getElementById(`f_${f.name}`) as HTMLInputElement | null;
      if (el) values[f.name] = el.value;
    });
  }

  renderFields();

  root.querySelector("#submit")!.addEventListener("click", () => {
    collect();
    const rec = backend.create(activeTyp, { ...values, typ: activeTyp });
    const ok = root.querySelector("#ok")!; ok.classList.remove("hidden");
    root.querySelector("#post")!.innerHTML =
      `<p class="muted">Wniosek dodany do kalendarza (dane w pamięci).</p>
       <button class="ghost" id="prev">Podgląd / drukuj (PDF)</button>
       <button class="ghost" id="tocal">Do kalendarza</button>`;
    root.querySelector("#prev")!.addEventListener("click", () => openPreview(rec));
    root.querySelector("#tocal")!.addEventListener("click", () => { st.view = "kalendarz"; st.prefill = null; rerender(); });
  });
}

// ---------------- Saldo ----------------
export function viewBalance(root: HTMLElement): void {
  const items = backend.balance();
  const fmt = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));
  root.innerHTML = `<h2>Saldo (rok 2026)</h2>` + items.map((it) => `
    <div class="card">
      <b>${esc(it.etykieta)}</b>
      <div class="metrics">
        <div class="metric"><div class="lab">Limit</div><div class="val">${fmt(it.limit)}</div><div class="lab">${it.jednostka}</div></div>
        <div class="metric"><div class="lab">Wykorzystano</div><div class="val">${fmt(it.wykorzystano)}</div><div class="lab">${it.jednostka}</div></div>
        <div class="metric"><div class="lab">Zaplanowano</div><div class="val">${fmt(it.zaplanowano)}</div><div class="lab">${it.jednostka}</div></div>
        <div class="metric hl"><div class="lab">Pozostało</div><div class="val">${fmt(it.pozostalo)}</div><div class="lab">${it.jednostka}</div></div>
      </div>
    </div>`).join("");
}

// ---------------- Profil ----------------
export function viewProfile(root: HTMLElement, rerender: () => void): void {
  const p = backend.profile();
  root.innerHTML = `<div class="card">
    <h2>Profil</h2>
    <p class="muted">Domyślne dane wspólne wstawiane do wniosków (w pamięci).</p>
    ${backend.common().filter((f) => f.name !== "data").map((f) => {
      const v = esc(p[f.name] ?? "");
      const input = f.typ === "textarea" ? `<textarea id="p_${f.name}">${v}</textarea>`
        : `<input id="p_${f.name}" type="text" value="${v}">`;
      return `<div class="field"><label>${esc(f.label)}</label>${input}</div>`;
    }).join("")}
    <button class="prim" id="save">Zapisz profil</button><span class="flash hidden" id="ok">zapisano</span>
  </div>`;
  root.querySelector("#save")!.addEventListener("click", () => {
    const next: Record<string, string> = {};
    backend.common().filter((f) => f.name !== "data").forEach((f) => {
      const el = document.getElementById(`p_${f.name}`) as HTMLInputElement | null;
      if (el) next[f.name] = el.value;
    });
    backend.saveProfile(next);
    root.querySelector("#ok")!.classList.remove("hidden");
    setTimeout(rerender, 800);
  });
}

// ---------------- Podgląd / „PDF" (druk) ----------------
function openPreview(rec: LeaveRecord): void {
  const t = typeById(rec.typ)?.nazwa ?? rec.typ;
  const d = rec.dane;
  const w = window.open("", "_blank");
  if (!w) return;
  w.document.write(`<!doctype html><html lang="pl"><head><meta charset="utf-8">
    <title>${esc(t)}</title>
    <style>body{font-family:system-ui,sans-serif;max-width:640px;margin:40px auto;padding:0 20px;color:#111}
    h1{font-size:1.2rem}.row{margin:6px 0}.k{color:#666;font-size:.85rem}pre{white-space:pre-wrap;font:inherit}
    .note{margin-top:24px;font-size:.75rem;color:#999;border-top:1px solid #ddd;padding-top:8px}</style></head>
    <body>
    <div class="row k">${esc(d.miejscowosc || "")}, ${esc(d.data || "")}</div>
    <h1>Wniosek — ${esc(t)}</h1>
    <div class="row"><span class="k">Pracownik:</span> ${esc(d.imie_nazwisko || "")}</div>
    ${d.stanowisko ? `<div class="row"><span class="k">Stanowisko:</span> ${esc(d.stanowisko)}</div>` : ""}
    <div class="row"><span class="k">Okres:</span> ${esc(rec.dataOd)} – ${esc(rec.dataDo)}</div>
    ${d.pracodawca ? `<div class="row"><span class="k">Pracodawca / adresat:</span><pre>${esc(d.pracodawca)}</pre></div>` : ""}
    <div class="note">DEMO — uproszczony podgląd HTML zamiast PDF z WeasyPrint. Użyj „Drukuj → Zapisz jako PDF".</div>
    </body></html>`);
  w.document.close();
  w.focus();
  setTimeout(() => w.print(), 300);
}
