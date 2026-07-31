// Uproszczona logika domenowa dema (odpowiedniki working_days.py / balance.py).
import { isHoliday } from "./holidays";
import { typeById } from "./registry";

export type Status = "do_akceptacji" | "zaakceptowany" | "odrzucony";

export type LeaveRecord = {
  id: number;
  typ: string;
  status: Status;
  dataOd: string;
  dataDo: string;
  dniRobocze: number | null;
  godziny: number | null;
  dane: Record<string, string>;
};

export const STATUS_LABEL: Record<Status, string> = {
  do_akceptacji: "do akceptacji",
  zaakceptowany: "zaakceptowany",
  odrzucony: "odrzucony",
};

// --- Pomocnicze na datach ISO (YYYY-MM-DD), bez pułapek stref czasowych ---
export function isoOf(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}
function parse(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}
export function eachDay(od: string, doo: string): string[] {
  if (!od || !doo) return [];
  const out: string[] = [];
  const end = parse(doo);
  for (const cur = parse(od); cur <= end; cur.setDate(cur.getDate() + 1)) out.push(isoOf(cur));
  return out;
}

export function workingDays(od: string, doo: string): number {
  return eachDay(od, doo).filter((iso) => {
    const wd = parse(iso).getDay(); // 0=nd,6=so
    return wd >= 1 && wd <= 5 && !isHoliday(iso);
  }).length;
}
export function calendarDays(od: string, doo: string): number {
  return eachDay(od, doo).length;
}

/** Wymiar rekordu (dni/godziny) — zależnie od typu i formy. */
export function amount(typ: string, dane: Record<string, string>): { dni: number | null; godziny: number | null } {
  const t = typeById(typ);
  const od = dane.data_od || "";
  const doo = dane.data_do || "";
  const forma = dane.forma;
  const num = (v: string | undefined) => {
    const n = parseFloat((v || "").replace(",", "."));
    return Number.isFinite(n) ? n : null;
  };
  if (forma === "godziny") return { dni: null, godziny: num(dane.wymiar) };
  if (forma === "dni") return { dni: num(dane.wymiar), godziny: null };
  if (t?.jednostka === "godziny") return { dni: null, godziny: num(dane.wymiar) };
  if (t?.jednostka === "dni_kalendarzowe") return { dni: calendarDays(od, doo), godziny: null };
  return { dni: workingDays(od, doo), godziny: null };
}

export type BalanceItem = {
  typ: string; etykieta: string; jednostka: string;
  limit: number; wykorzystano: number; zaplanowano: number; pozostalo: number;
};

/** Saldo: limit vs wykorzystano (zaakceptowane) vs zaplanowano (do akceptacji). */
export function computeBalance(records: LeaveRecord[], settings: Record<string, { aktywny: boolean; limitDni: number }>): BalanceItem[] {
  const items: BalanceItem[] = [];
  for (const t of Object.keys(settings)) {
    const s = settings[t];
    if (!s.aktywny) continue;
    const type = typeById(t);
    if (!type) continue;
    const recs = records.filter((r) => r.typ === t && r.status !== "odrzucony");
    const godzinowy = type.jednostka === "godziny";
    const val = (r: LeaveRecord) => (godzinowy ? (r.godziny ?? (r.dniRobocze ?? 0) * 8) : (r.dniRobocze ?? 0));
    const wykorzystano = recs.filter((r) => r.status === "zaakceptowany").reduce((a, r) => a + val(r), 0);
    const zaplanowano = recs.filter((r) => r.status === "do_akceptacji").reduce((a, r) => a + val(r), 0);
    const limit = godzinowy ? s.limitDni * 8 : s.limitDni;
    items.push({
      typ: t, etykieta: type.nazwa, jednostka: godzinowy ? "godziny" : "dni",
      limit, wykorzystano, zaplanowano, pozostalo: limit - wykorzystano,
    });
  }
  return items;
}
