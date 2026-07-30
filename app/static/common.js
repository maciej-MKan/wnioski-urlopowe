"use strict";
/* Wspólne helpery frontu: skrót do DOM, klient API (z bearer tokenem), narzędzia dat,
   bramka logowania i badge środowiska. Ładowany na każdej stronie PRZED jej skryptem inline. */

// Skrót do document.getElementById.
const $ = id => document.getElementById(id);

// --- Uwierzytelnianie (§18): token w localStorage, bearer na każdym żądaniu ---
const _TOKEN_KEY = "wnioski_token";
const getToken = () => localStorage.getItem(_TOKEN_KEY);
const setToken = t => localStorage.setItem(_TOKEN_KEY, t);
const clearToken = () => localStorage.removeItem(_TOKEN_KEY);

function authHeaders(extra){
  const h = extra ? { ...extra } : {};
  const t = getToken();
  if(t) h["Authorization"] = "Bearer " + t;
  return h;
}
function _check401(r){ if(r.status === 401) onUnauthorized(); return r; }

// Klient API — jednolite pobieranie i wysyłanie JSON z tokenem.
const api = {
  async get(url){
    const r = await fetch(url, { headers: authHeaders() });
    if(r.status === 401){ onUnauthorized(); throw new Error("401"); }
    if(!r.ok) throw new Error(`GET ${url} → ${r.status}`);
    return r.json();
  },
  postJson(url, body){
    return fetch(url, { method:"POST", headers: authHeaders({"Content-Type":"application/json"}),
                        body: JSON.stringify(body) }).then(_check401);
  },
  putJson(url, body){
    return fetch(url, { method:"PUT", headers: authHeaders({"Content-Type":"application/json"}),
                        body: JSON.stringify(body) }).then(_check401);
  },
  patchJson(url, body){
    return fetch(url, { method:"PATCH", headers: authHeaders({"Content-Type":"application/json"}),
                        body: JSON.stringify(body) }).then(_check401);
  },
  del(url){
    return fetch(url, { method:"DELETE", headers: authHeaders() }).then(_check401);
  },
  postForm(url, fields){  // multipart/form-data (upload) — bez ręcznego Content-Type
    return fetch(url, { method:"POST", headers: authHeaders(), body: fields }).then(_check401);
  },
};

// Otwiera plik chroniony tokenem (PDF/załącznik) w nowej karcie — link <a> nie niesie nagłówka.
async function openAuthed(url){
  const r = await fetch(url, { headers: authHeaders() });
  if(r.status === 401){ onUnauthorized(); return; }
  if(!r.ok){ alert("Nie udało się pobrać pliku."); return; }
  const blobUrl = URL.createObjectURL(await r.blob());
  window.open(blobUrl, "_blank");
  setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
}

// --- Narzędzia dat ---
const pad = n => String(n).padStart(2, "0");
const klucz = (y, m, d) => `${y}-${pad(m+1)}-${pad(d)}`;   // m: 0–11 (jak w JS Date)
function fmtZakres(od, do_){
  const f = s => { const [y, m, d] = s.split("-"); return `${d}.${m}.${y}`; };
  if(od && do_ && od !== do_) return `${f(od)} – ${f(do_)}`;
  return f(od || do_);
}

// --- Bramka logowania ---
let _HEALTH = null;
function onUnauthorized(){ clearToken(); showLogin(); }

function showLogin(){
  if(document.getElementById("login-overlay")) return;  // już pokazane
  const rejestracja = !_HEALTH || _HEALTH.rejestracja !== false;
  const ov = document.createElement("div");
  ov.id = "login-overlay"; ov.className = "modal-overlay";
  ov.innerHTML =
    `<div class="modal-box">
       <h3 id="login-tytul" style="margin:0 0 12px">Logowanie</h3>
       <div style="margin-bottom:10px"><label>Użytkownik</label>
         <input id="login-user" autocomplete="username" style="width:100%"></div>
       <div><label>Hasło</label>
         <input id="login-pass" type="password" autocomplete="current-password" style="width:100%"></div>
       <p id="login-err" class="login-err hidden"></p>
       <div class="login-actions">
         ${rejestracja ? '<button id="login-toggle" class="ghost">Załóż konto</button>' : ''}
         <button id="login-submit" class="prim">Zaloguj</button>
       </div>
       ${(_HEALTH && _HEALTH.google) ? '<div class="login-google"><span>lub</span></div>' +
         '<button id="login-google" class="google-btn">Zaloguj przez Google</button>' : ''}
     </div>`;
  document.body.appendChild(ov);
  let tryb = "login";
  const err = m => { const e = $("login-err"); e.textContent = m; e.classList.remove("hidden"); };
  if($("login-toggle")) $("login-toggle").addEventListener("click", () => {
    tryb = tryb === "login" ? "register" : "login";
    $("login-tytul").textContent = tryb === "login" ? "Logowanie" : "Rejestracja";
    $("login-submit").textContent = tryb === "login" ? "Zaloguj" : "Utwórz konto";
    $("login-toggle").textContent = tryb === "login" ? "Załóż konto" : "Mam już konto";
    $("login-err").classList.add("hidden");
  });
  const submit = async () => {
    const u = $("login-user").value.trim(), p = $("login-pass").value;
    if(!u || !p){ err("Podaj użytkownika i hasło."); return; }
    try{
      let token;
      if(tryb === "register"){
        const r = await fetch("/api/register", { method:"POST", headers:{"Content-Type":"application/json"},
          body: JSON.stringify({ username:u, password:p }) });
        if(!r.ok){ err(r.status === 409 ? "Nazwa użytkownika zajęta." : "Nie udało się utworzyć konta."); return; }
        token = (await r.json()).access_token;
      } else {
        const r = await fetch("/api/token", { method:"POST",
          headers:{"Content-Type":"application/x-www-form-urlencoded"},
          body: new URLSearchParams({ username:u, password:p }) });
        if(!r.ok){ err("Zły login lub hasło."); return; }
        token = (await r.json()).access_token;
      }
      setToken(token);
      location.reload();
    }catch(e){ err("Błąd połączenia."); }
  };
  $("login-submit").addEventListener("click", submit);
  $("login-pass").addEventListener("keydown", e => { if(e.key === "Enter") submit(); });
  if($("login-google")) $("login-google").addEventListener("click", () => { location.href = "/api/auth/google/login"; });
  $("login-user").focus();
}

// Wstawia do nawigacji info o zalogowanym użytkowniku + wylogowanie.
function addUserChip(username){
  const nav = document.querySelector(".topnav");
  if(!nav || document.getElementById("user-chip")) return;
  const chip = document.createElement("span"); chip.id = "user-chip"; chip.className = "user-chip";
  chip.innerHTML = `<span>${username}</span> · <a href="#" id="logout-link">Wyloguj</a>`;
  nav.appendChild(chip);
  $("logout-link").addEventListener("click", e => { e.preventDefault(); clearToken(); location.reload(); });
}

// --- Start: badge środowiska + bramka logowania ---
(async function boot(){
  // Token z callbacku Google (fragment URL, nie trafia na serwer) — zapisz i wyczyść adres.
  if(location.hash){
    const frag = new URLSearchParams(location.hash.slice(1));
    if(frag.get("token")){ setToken(frag.get("token")); history.replaceState(null, "", location.pathname + location.search); }
    else if(frag.get("google_error")){ history.replaceState(null, "", location.pathname + location.search); }
  }
  try{ _HEALTH = await (await fetch("/api/health")).json(); }catch(e){ _HEALTH = null; }
  // Badge środowiska (nie-prod).
  if(_HEALTH && _HEALTH.srodowisko && _HEALTH.srodowisko !== "prod"){
    const nav = document.querySelector(".topnav");
    if(nav){ const b = document.createElement("span"); b.className = "env-badge";
      b.textContent = _HEALTH.srodowisko.toUpperCase(); b.title = "Środowisko nieprodukcyjne"; nav.prepend(b); }
  }
  // Bramka: bez tokenu — pokaż logowanie; z tokenem — potwierdź i pokaż użytkownika.
  if(!getToken()){ showLogin(); return; }
  try{ addUserChip((await api.get("/api/me")).username); }
  catch(e){ /* 401 → onUnauthorized pokaże logowanie */ }
})();
