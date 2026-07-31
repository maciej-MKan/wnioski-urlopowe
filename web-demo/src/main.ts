import "./styles.css";
import { seed } from "./store";
import { viewCalendar, viewCreate, viewSaldo, viewUstawienia, type AppState } from "./views";

seed(); // dane demonstracyjne w pamięci

const st: AppState = { view: "kalendarz", ym: { y: 2026, m: 7 }, sel: null, prefill: null };

const NAV: { view: AppState["view"]; label: string }[] = [
  { view: "kalendarz", label: "Kalendarz" },
  { view: "nowy", label: "Nowy wniosek" },
  { view: "saldo", label: "Saldo" },
  { view: "ustawienia", label: "Ustawienia" },
];

const appEl = document.getElementById("app")!;

function render(): void {
  appEl.innerHTML = `
    <div class="demo-banner">
      <b>DEMO</b>
      <span>Pokaz uproszczonej wersji — dane trzymane tylko w pamięci przeglądarki i znikają po odświeżeniu.</span>
      <a href="./roznice.html" target="_blank">Czego brakuje vs pełna wersja?</a>
    </div>
    <div class="wrap">
      <h1>Wnioski urlopowe</h1>
      <p class="sub">Klient web — wersja demonstracyjna (bez backendu, logowania i trwałości danych).</p>
      <div class="topnav">
        ${NAV.map((n) => `<button data-view="${n.view}" class="${st.view === n.view ? "on" : ""}">${n.label}</button>`).join("")}
      </div>
      <div id="view"></div>
    </div>`;

  appEl.querySelectorAll<HTMLButtonElement>("[data-view]").forEach((b) =>
    b.addEventListener("click", () => {
      st.view = b.dataset.view as AppState["view"];
      if (st.view !== "nowy") st.prefill = null;
      render();
    }));

  const view = appEl.querySelector<HTMLElement>("#view")!;
  if (st.view === "kalendarz") viewCalendar(view, st, render);
  else if (st.view === "nowy") viewCreate(view, st, render);
  else if (st.view === "saldo") viewSaldo(view);
  else viewUstawienia(view, render);
}

render();
