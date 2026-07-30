# Wnioski urlopowe — klient Android

Natywna aplikacja **Kotlin + Jetpack Compose** do obsługi wniosków urlopowych — mobilny klient
tego samego backendu co aplikacja web (patrz [README główne](../README.md)). Korzysta wyłącznie
z REST API (`/api/*`), więc wszystkie reguły biznesowe (rejestr typów, limity, dni wolne za
święto, izolacja danych per użytkownik) są współdzielone z serwerem — klient ich nie duplikuje.

## Funkcje

- **Logowanie** hasłem (OAuth2 password → JWT) oraz **rejestracja** konta z poziomu aplikacji;
  opcjonalnie **logowanie przez Google** (gdy backend ma skonfigurowane `GOOGLE_CLIENT_ID/SECRET`).
- **Kalendarz** miesięczny: urlopy kolorowane wg rejestru typów, święta i weekendy, statusy
  rekordów (do akceptacji / zaakceptowany / odrzucony) oddane przezroczystością.
- **Panel dnia** z akcjami na rekordzie: **Zaakceptuj / Odrzuć / Usuń** oraz **pobranie PDF**
  (dla wniosków) otwierane w zewnętrznej przeglądarce dokumentów.
- **Zaznaczanie okresu** kliknięciami (tap = początek, drugi tap = koniec) → skróty
  **Nowy wniosek** / **Dodaj ręcznie** z wypełnionymi datami.
- **Nowy wniosek** z **dynamicznego rejestru** (`/api/typy`) — pola generowane z metadanych typu
  (text/number/textarea/select/date/time, widoczność warunkowa). Dla urlopu wypoczynkowego
  pojawia się pytanie o **dni wolne za święto** (osobny wniosek, nie schodzi z urlopu).
- **Dodawanie ręczne** urlopu odbytego spoza aplikacji (bez PDF), z wyborem statusu.
- **Saldo i ustawienia**: bilans wykorzystania na dany rok oraz **edycja limitów**
  (dni przysługujące / zaległe, przełączniki „przysługuje", system jednozmianowy).
- **Profil** — domyślne dane wspólne (imię i nazwisko, stanowisko, pracodawca…) zapisywane
  w bazie i **wspólne z klientem web**; wstawiane automatycznie do kolejnych wniosków.

## Stos technologiczny

- **Język / UI:** Kotlin 2.0.21, **Jetpack Compose** (BOM 2024.09.03, Material 3), `compileSdk 35`,
  `minSdk 26`. Budowa: Gradle 8.9 (wrapper) + AGP 8.6.1.
- **Sieć:** Retrofit 2.11 + OkHttp 4.12 + **kotlinx.serialization** (konwerter
  `com.squareup.retrofit2:converter-kotlinx-serialization`). Bearer token dokładany
  interceptorem OkHttp.
- **Stan:** `ViewModel` + `StateFlow`, kolekcjonowany w Compose przez `collectAsStateWithLifecycle`.
- **Bezpieczeństwo:** token JWT w **`EncryptedSharedPreferences`** (`androidx.security-crypto`).
- **Nawigacja:** bez biblioteki Navigation — prosty `sealed interface Nav` przełączany w
  `MainActivity` (aplikacja ma kilka ekranów, więc lekki własny router wystarcza).

## Architektura

Dwie warstwy, ręcznie zszyte w **korzeniu kompozycji** (`AppContainer`) — odpowiednik
`composition.py` z backendu. `data/` nie zna `ui/`; ekrany dostają repozytoria przez kontener.

```
app/src/main/java/pl/wnioski/urlopowe/
├─ MainActivity.kt        # host Compose + router (sealed Nav) + deep link Google (onNewIntent)
├─ data/                  # warstwa danych — sieć, modele, repozytoria, sesja
│  ├─ ApiService.kt         # kontrakt REST (Retrofit) — wszystkie endpointy
│  ├─ Models.kt             # DTO (@Serializable), klucze wire po polsku (@SerialName)
│  ├─ ApiFactory.kt         # budowa Retrofit/OkHttp + interceptor bearer + logging
│  ├─ AppContainer.kt       # korzeń kompozycji: token store, api, repozytoria
│  ├─ TokenStore.kt         # port sesji  ·  EncryptedTokenStore.kt — implementacja (szyfrowana)
│  ├─ AuthRepository.kt     # logowanie / rejestracja / health / token z deep linka
│  ├─ CalendarRepository.kt # rekordy, typy, święta, zmiana statusu, usuwanie, PDF
│  ├─ SettingsRepository.kt # saldo, ustawienia (odczyt/zapis), rejestr
│  └─ ApplicationRepository.kt # tworzenie wniosków (+ §dni za święto), ręczne, profil
└─ ui/                    # warstwa prezentacji — ekrany + ViewModel-e
   ├─ LoginScreen / LoginViewModel          # logowanie, rejestracja, Google
   ├─ CalendarScreen / CalendarViewModel    # siatka miesiąca, zaznaczanie okresu, panel dnia
   ├─ CreateScreen / CreateViewModel        # dynamiczny formularz wniosku + dialog dni za święto
   ├─ ManualScreen / ManualViewModel        # dodawanie ręczne
   ├─ BalanceScreen / BalanceViewModel      # saldo + edycja limitów
   ├─ ProfileScreen / ProfileViewModel      # profil (domyślne dane wspólne)
   ├─ FormFields.kt                         # reużywalne kontrolki pól (date/time/select/…)
   └─ PdfOpener.kt                          # zapis PDF do cache + otwarcie przez FileProvider
```

Deep link powrotu z Google (`pl.wnioski.urlopowe://auth#token=…`) obsługuje `MainActivity`
(`launchMode="singleTask"` + `onNewIntent`); token trafia do `AuthRepository.acceptToken`.

## Konfiguracja backendu (adres per wariant)

Adres API jest wstrzykiwany jako `BuildConfig.BASE_URL` — **inny dla każdego wariantu build**:

| Wariant | `BASE_URL` | Uwagi |
|---|---|---|
| `debug` | `http://10.0.2.2:8138/` | backend **DEV** widziany z emulatora (`10.0.2.2` = host) |
| `release` | `http://10.0.2.2:8137/` | backend **PROD**; nadpisywalny (patrz niżej) |

- Z **fizycznego telefonu** użyj adresu IP komputera w sieci LAN zamiast `10.0.2.2`.
- Adres prod nadpiszesz przy budowaniu: `./gradlew assembleRelease -PPROD_BASE_URL=https://twoj-serwer/`.
- Ruch **cleartext HTTP** jest dozwolony (`usesCleartextTraffic`), bo backend bywa serwowany po
  http w sieci lokalnej. Dla publicznego prod z TLS ustaw `PROD_BASE_URL=https://…` i rozważ
  ograniczenie cleartext do wariantu debug.

## Wymagania

- **JDK 21** — pełny (z `jlink`); AGP nie zbuduje się na samym JRE.
- **Android SDK**: `platforms;android-35`, `build-tools;35.0.0`, `platform-tools` (zaakceptowane
  licencje). Ścieżkę SDK podaj w `local.properties` (`sdk.dir=…`) lub przez `ANDROID_HOME`.

## Budowanie i uruchomienie

```bash
export JAVA_HOME=/ścieżka/do/jdk21
export ANDROID_HOME=$HOME/Android/Sdk

# Debug (celuje w backend DEV :8138)
./gradlew :app:assembleDebug          # → app/build/outputs/apk/debug/app-debug.apk
./gradlew :app:testDebugUnitTest      # testy jednostkowe JVM

# Instalacja na uruchomionym emulatorze / urządzeniu
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Do testów lokalnych najwygodniej użyć emulatora (backend DEV na hoście, port 8138). Pierwszy
build pobiera zależności i trwa dłużej.

## Wydanie (podpisany APK)

Wariant `release` jest **podpisywany**, gdy istnieje `keystore.properties` w katalogu `android/`
(plik i keystore są w `.gitignore` — nie trafiają do repozytorium). Bez niego release powstaje
niepodpisany (np. na CI bez sekretów).

1. Wygeneruj keystore:
   ```bash
   keytool -genkeypair -v -keystore keystore/release.jks -alias wnioski \
     -keyalg RSA -keysize 2048 -validity 10000 \
     -dname "CN=Wnioski Urlopowe, O=Wnioski, C=PL"
   ```
2. Utwórz `keystore.properties`:
   ```properties
   storeFile=keystore/release.jks
   storePassword=…
   keyAlias=wnioski
   keyPassword=…
   ```
3. Zbuduj i (opcjonalnie) sprawdź podpis:
   ```bash
   ./gradlew :app:assembleRelease        # → app/build/outputs/apk/release/app-release.apk
   $ANDROID_HOME/build-tools/35.0.0/apksigner verify --print-certs app-release.apk
   ```

> Klucz debugowy i release są różne — instalując release na urządzeniu z wersją debug, najpierw
> `adb uninstall pl.wnioski.urlopowe`.

## Testy

Testy jednostkowe **JVM** (`./gradlew :app:testDebugUnitTest`) pokrywają logikę bez zależności
od Androida: serializację DTO, budowę siatki kalendarza i zaznaczanie okresu, oraz ViewModel-e
(logowanie/rejestracja, kalendarz, tworzenie wniosku z dialogiem dni za święto, dodawanie ręczne,
saldo/ustawienia, profil). Współpraca z API jest podmieniana atrapą `FakeApi`; korutyny testowane
przez `MainDispatcherRule` (`UnconfinedTestDispatcher`).

## Logowanie i konta

Konta są wspólne z aplikacją web (ta sama baza po stronie backendu). Zakładanie konta i logowanie
Google patrz [README główne → Konta i logowanie](../README.md#konta-i-logowanie). W aplikacji
mobilnej przycisk „Zaloguj przez Google" pojawia się tylko, gdy backend zgłasza włączony Google
(`/api/health`), a po autoryzacji serwer wraca do aplikacji **deep linkiem** z tokenem.
