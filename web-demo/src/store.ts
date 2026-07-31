import { amount, type LeaveRecord, type Status } from "./domain";

export type Profile = Record<string, string>;
export type Settings = Record<string, { aktywny: boolean; limitDni: number }>;

let seq = 0;

export const state = {
  records: [] as LeaveRecord[],
  profile: {} as Profile,
  settings: {} as Settings,
};

export function nextId(): number {
  return ++seq;
}

function addSeedRecord(typ: string, status: Status, dane: Record<string, string>): void {
  const a = amount(typ, dane);
  state.records.push({
    id: nextId(), typ, status,
    dataOd: dane.data_od || "", dataDo: dane.data_do || "",
    dniRobocze: a.dni, godziny: a.godziny, dane: { ...state.profile, ...dane, typ },
  });
}

/** Zasiewa dane demonstracyjne (w pamięci). Wywoływane raz przy starcie; reset = odświeżenie strony. */
export function seed(): void {
  seq = 0;
  state.records = [];
  state.profile = {
    miejscowosc: "Warszawa",
    imie_nazwisko: "Jan Kowalski",
    stanowisko: "Specjalista, Dział IT",
    pracodawca: "ACME Sp. z o.o.\nul. Testowa 1\n00-001 Warszawa",
  };
  state.settings = {
    wypoczynkowy: { aktywny: true, limitDni: 26 },
    ojcowski: { aktywny: false, limitDni: 14 },
    opieka: { aktywny: true, limitDni: 2 },
  };
  addSeedRecord("wypoczynkowy", "do_akceptacji", { data_od: "2026-07-13", data_do: "2026-07-17" });
  addSeedRecord("wypoczynkowy", "zaakceptowany", { data_od: "2026-05-04", data_do: "2026-05-08" });
  addSeedRecord("opieka", "zaakceptowany", { forma: "godziny", wymiar: "4", data_od: "2026-06-10", data_do: "2026-06-10" });
}
