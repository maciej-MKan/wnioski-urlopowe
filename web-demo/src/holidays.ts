// DEMO: statyczna lista polskich świąt (rok 2026). W pełnej wersji liczone algorytmem
// paschalnym (app/domain/holidays.py) dla dowolnego roku.
export const HOLIDAYS_2026: Record<string, string> = {
  "2026-01-01": "Nowy Rok",
  "2026-01-06": "Trzech Króli",
  "2026-04-05": "Wielkanoc",
  "2026-04-06": "Poniedziałek Wielkanocny",
  "2026-05-01": "Święto Pracy",
  "2026-05-03": "Święto Konstytucji 3 Maja",
  "2026-05-24": "Zesłanie Ducha Świętego",
  "2026-06-04": "Boże Ciało",
  "2026-08-15": "Wniebowzięcie NMP",
  "2026-11-01": "Wszystkich Świętych",
  "2026-11-11": "Święto Niepodległości",
  "2026-12-25": "Boże Narodzenie (1. dzień)",
  "2026-12-26": "Boże Narodzenie (2. dzień)",
};

export const holidayName = (iso: string): string | undefined => HOLIDAYS_2026[iso];
export const isHoliday = (iso: string): boolean => iso in HOLIDAYS_2026;
