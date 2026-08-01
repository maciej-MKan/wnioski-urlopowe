// Uproszczony rejestr typów urlopu na potrzeby dema (odpowiednik app/domain/leave_type.py).
export type Field = {
  name: string;
  label: string;
  typ: "text" | "date" | "time" | "textarea" | "select" | "number";
  szerokosc?: "half" | "full";
  placeholder?: string;
  opcje?: { value: string; label: string }[];
  autoZZakresu?: boolean;
  hint?: string;
  // Pole widoczne tylko gdy inne pole ma daną wartość (odpowiednik visible_when z backendu).
  widoczneGdy?: [pole: string, wartosc: string];
};

export type LeaveType = {
  id: string;
  nazwa: string;
  kolor: string;
  jednostka: "dni_robocze" | "dni_kalendarzowe" | "godziny";
  limitDomyslnyDni: number | null;
  pola: Field[];
};

export const WSPOLNE: Field[] = [
  { name: "miejscowosc", label: "Miejscowość", typ: "text", szerokosc: "half", placeholder: "np. Warszawa" },
  { name: "data", label: "Data sporządzenia", typ: "date", szerokosc: "half" },
  { name: "imie_nazwisko", label: "Imię i nazwisko pracownika", typ: "text", szerokosc: "full", placeholder: "Jan Kowalski" },
  { name: "stanowisko", label: "Stanowisko / dział (opcjonalnie)", typ: "text", szerokosc: "full" },
  { name: "pracodawca", label: "Pracodawca / adresat (każda linia osobno)", typ: "textarea", szerokosc: "full" },
  { name: "dzial_kadr", label: "Kierowane do (opcjonalnie)", typ: "text", szerokosc: "full",
    placeholder: "np. Dział Kadr / Bezpośredni przełożony" },
];

const OD_DO: Field[] = [
  { name: "data_od", label: "Data od", typ: "date", szerokosc: "half" },
  { name: "data_do", label: "Data do", typ: "date", szerokosc: "half" },
];

export const TYPY: LeaveType[] = [
  {
    id: "wypoczynkowy", nazwa: "Urlop wypoczynkowy", kolor: "#2f8f5b", jednostka: "dni_robocze",
    limitDomyslnyDni: 26,
    pola: [
      ...OD_DO,
      { name: "liczba_dni", label: "Liczba dni", typ: "text", szerokosc: "half", autoZZakresu: true, placeholder: "auto z zakresu" },
      { name: "rok_rozliczenia", label: "Rok rozliczenia", typ: "number", szerokosc: "half", placeholder: "np. 2026",
        hint: "Rok, z którego puli rozliczyć urlop (pusto = rok rozpoczęcia). Trafia na PDF." },
    ],
  },
  {
    id: "ojcowski", nazwa: "Urlop ojcowski", kolor: "#3a6ea5", jednostka: "dni_kalendarzowe",
    limitDomyslnyDni: 14,
    pola: [
      { name: "dziecko_imie_nazwisko", label: "Imię i nazwisko dziecka", typ: "text", szerokosc: "full" },
      { name: "dziecko_data_urodzenia", label: "Data urodzenia dziecka", typ: "date", szerokosc: "half" },
      { name: "wymiar", label: "Wymiar", typ: "text", szerokosc: "half", placeholder: "np. 2 tygodnie" },
      ...OD_DO,
    ],
  },
  {
    id: "opieka", nazwa: "Opieka nad dzieckiem", kolor: "#b06a2c", jednostka: "godziny",
    limitDomyslnyDni: 2,
    pola: [
      { name: "dziecko_imie_nazwisko", label: "Imię i nazwisko dziecka", typ: "text", szerokosc: "full" },
      { name: "dziecko_data_urodzenia", label: "Data urodzenia dziecka", typ: "date", szerokosc: "half" },
      { name: "forma", label: "Forma wykorzystania", typ: "select", szerokosc: "half",
        opcje: [{ value: "dni", label: "Dni" }, { value: "godziny", label: "Godziny" }] },
      { name: "wymiar", label: "Wymiar (liczba dni lub godzin)", typ: "text", szerokosc: "half", placeholder: "np. 2" },
      ...OD_DO,
      { name: "godzina_od", label: "Godzina od", typ: "time", szerokosc: "half", widoczneGdy: ["forma", "godziny"] },
      { name: "godzina_do", label: "Godzina do", typ: "time", szerokosc: "half", widoczneGdy: ["forma", "godziny"] },
    ],
  },
];

export const typeById = (id: string): LeaveType | undefined => TYPY.find((t) => t.id === id);
