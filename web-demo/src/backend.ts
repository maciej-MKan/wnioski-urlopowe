// Fasada „API" dema — odpowiednik endpointów /api/* w pełnej wersji, ale na danych w pamięci.
import { state, nextId, type Profile, type Settings } from "./store";
import { TYPY, WSPOLNE, type LeaveType, type Field } from "./registry";
import { amount, computeBalance, type BalanceItem, type LeaveRecord, type Status } from "./domain";
import { holidayName } from "./holidays";

export const backend = {
  types: (): LeaveType[] => TYPY,
  common: (): Field[] => WSPOLNE,
  activeTypes: (): LeaveType[] => TYPY.filter((t) => state.settings[t.id]?.aktywny),
  records: (): LeaveRecord[] => state.records.slice(),
  holiday: (iso: string): string | undefined => holidayName(iso),
  balance: (): BalanceItem[] => computeBalance(state.records, state.settings),
  profile: (): Profile => ({ ...state.profile }),
  saveProfile: (p: Profile): void => { state.profile = { ...p }; },
  settings: (): Settings => state.settings,

  create(typ: string, values: Record<string, string>): LeaveRecord {
    const a = amount(typ, values);
    const rec: LeaveRecord = {
      id: nextId(), typ, status: "do_akceptacji",
      dataOd: values.data_od || "", dataDo: values.data_do || "",
      dniRobocze: a.dni, godziny: a.godziny, dane: { ...values, typ },
    };
    state.records.push(rec);
    return rec;
  },
  setStatus(id: number, status: Status): void {
    const r = state.records.find((x) => x.id === id);
    if (r) r.status = status;
  },
  remove(id: number): void {
    state.records = state.records.filter((x) => x.id !== id);
  },
};
