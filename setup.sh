#!/usr/bin/env bash
# Pierwsze uruchomienie (§23.1): ustawia hasło PostgreSQL w .env, potem startuje stack.
# - jeśli .env ma już POSTGRES_PASSWORD → nie pyta,
# - inaczej pyta interaktywnie (Enter = wygeneruj losowe, URL-safe),
# - zapisuje do .env (gitignored, chmod 600) i uruchamia docker compose.
set -euo pipefail
cd "$(dirname "$0")"

ENV_FILE=".env"

has_password() {
  [ -f "$ENV_FILE" ] && grep -qE '^POSTGRES_PASSWORD=.+' "$ENV_FILE"
}

if has_password; then
  echo "POSTGRES_PASSWORD już ustawione w $ENV_FILE — pomijam."
else
  echo "Konfiguracja hasła bazy PostgreSQL (zapiszę w $ENV_FILE, gitignored)."
  # -s: nie echuj; jeśli brak TTY (skrypt w potoku) → od razu generujemy.
  if [ -t 0 ]; then
    read -rsp "Podaj hasło (Enter = wygeneruj losowe): " PW; echo
  else
    PW=""
  fi
  if [ -z "${PW:-}" ]; then
    # URL-safe (litery/cyfry) — trafia do WNIOSKI_DB_URL.
    PW="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)"
    echo "Wygenerowano losowe hasło (zapisz je bezpiecznie): $PW"
  fi
  touch "$ENV_FILE"
  grep -v '^POSTGRES_PASSWORD=' "$ENV_FILE" > "$ENV_FILE.tmp" 2>/dev/null || true
  mv "$ENV_FILE.tmp" "$ENV_FILE" 2>/dev/null || true
  printf 'POSTGRES_PASSWORD=%s\n' "$PW" >> "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "Zapisano do $ENV_FILE."
fi

echo "Uruchamiam stack: docker compose up --build -d"
docker compose up --build -d
echo
echo "Gotowe. Status: docker compose ps"
echo "Przy pierwszym starcie z Postgresem dane z SQLite migrują się automatycznie (SQLite zostaje jako backup)."
