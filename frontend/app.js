/* Chat Locale AI — logica dell'interfaccia (vanilla JS, nessuna dipendenza) */
"use strict";

const $ = (id) => document.getElementById(id);

// ------------------------------- stato globale
let sid = null;              // id storia corrente
let stato = null;            // world state corrente
let interlocutore = "Narratore";
let ultimoIdLog = 0;         // per il polling dell'archivista
let staScrivendo = false;
let timerPolling = null;

const AVATAR_COLORI = ["linear-gradient(135deg,#f0568c,#c93a6f)", "linear-gradient(135deg,#8b5cf6,#6d28d9)",
  "linear-gradient(135deg,#0ea5e9,#6366f1)", "linear-gradient(135deg,#34d399,#0d9488)",
  "linear-gradient(135deg,#fbbf24,#f97316)", "linear-gradient(135deg,#f87171,#dc2626)"];

function coloreAvatar(nome) {
  let h = 0;
  for (const c of String(nome)) h = (h * 31 + c.codePointAt(0)) >>> 0;
  return AVATAR_COLORI[h % AVATAR_COLORI.length];
}
function iniziali(nome) {
  const parti = String(nome).trim().split(/\s+/);
  return parti.slice(0, 2).map(p => p[0] ? p[0].toUpperCase() : "").join("") || "?";
}

// ------------------------------- salute
async function controllaSalute() {
  const el = $("stato-salute");
  try {
    const r = await fetch("/api/salute");
    const s = await r.json();
    if (s.ollama_attivo && s.attore_presente) {
      el.textContent = `✅ Pronto: modello attore «${s.modello_attore}»`;
      el.className = "salute ok";
    } else if (s.ollama_attivo) {
      el.textContent = `⚠️ Ollama attivo ma manca il modello. Esegui: ollama pull ${s.modello_attore}`;
      el.className = "salute ko";
    } else {
      el.textContent = "⚠️ Ollama non è avviato: apri Ollama dal menu Start e ricarica la pagina.";
      el.className = "salute ko";
    }
  } catch {
    el.textContent = "⚠️ Server non raggiungibile.";
    el.className = "salute ko";
  }
}

// ------------------------------- benvenuto
async function mostraBenvenuto() {
  $("vista-chat").classList.add("nascosta");
  $("vista-benvenuto").classList.remove("nascosta");
  fermaPolling();
  controllaSalute();
  try {
    const r = await fetch("/api/storie");
    const dati = await r.json();
    const contenitore = $("lista-storie");
    contenitore.innerHTML = "";
    for (const s of dati.storie) {
      const b = document.createElement("button");
      b.className = "card";
      b.innerHTML = `
        <div class="nome-storia"></div>
        <div class="mini"></div>
        <div class="badge-riga">
          <span class="badge">👥 <span></span></span>
          <span class="badge">💬 <span></span></span>
        </div>`;
      b.querySelector(".nome-storia").textContent = s.nome;
      b.querySelector(".mini").textContent = s.premessa || "Senza premessa";
      const badgePers = b.querySelector(".badge-riga .badge:nth-child(1) span");
      const badgeMsg = b.querySelector(".badge-riga .badge:nth-child(2) span");
      badgePers.textContent = `${s.n_personaggi} personaggi`;
      badgeMsg.textContent = `${s.n_messaggi} messaggi`;
      b.addEventListener("click", () => apriStoria(s.id));
      contenitore.appendChild(b);
    }
  } catch {
    $("lista-storie").innerHTML = "<p class='mini'>Impossibile caricare le storie.</p>";
  }
}

// ------------------------------- nuova storia
$("bottone-nuova-storia").addEventListener("click", () => {
  $("modale-storia").classList.remove("nascosta");
  $("ns-errore").textContent = "";
});
$("ns-annulla").addEventListener("click", () => $("modale-storia").classList.add("nascosta"));

$("ns-crea").addEventListener("click", async () => {
  const nome = $("ns-nome").value.trim();
  const pnome = $("ns-pnome").value.trim();
  if (!nome) return ($("ns-errore").textContent = "Serve un nome per la storia.");
  if (!pnome) return ($("ns-errore").textContent = "Serve almeno un personaggio con il nome.");

  $("ns-crea").disabled = true;
  try {
    const r = await fetch("/api/storie", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nome,
        premessa: $("ns-premessa").value.trim(),
        tono: $("ns-tono").value.trim(),
        situazione: $("ns-situazione").value.trim(),
        personaggi: [{
          nome: pnome,
          descrizione: $("ns-pdescrizione").value.trim(),
          personalita: $("ns-ppersonalita").value.trim(),
          aspetto: $("ns-paspetto").value.trim(),
        }],
      }),
    });
    const dati = await r.json();
    if (!r.ok) return ($("ns-errore").textContent = dati.errore || "Errore nella creazione.");
    $("modale-storia").classList.add("nascosta");
    ["ns-nome", "ns-premessa", "ns-tono", "ns-situazione", "ns-pnome", "ns-paspetto", "ns-pdescrizione", "ns-ppersonalita"]
      .forEach(id => ($(id).value = ""));
    apriStoria(dati.id);
  } finally {
    $("ns-crea").disabled = false;
  }
});

// ------------------------------- apertura storia
async function apriStoria(id) {
  const r = await fetch(`/api/storie/${id}`);
  if (!r.ok) return alert("Storia non trovata.");
  const dati = await r.json();
  sid = id;
  stato = dati.stato;
  ultimoIdLog = 0;

  $("vista-benvenuto").classList.add("nascosta");
  $("vista-chat").classList.remove("nascosta");
  $("titolo-storia").textContent = stato.storia.nome;
  $("desc-storia").textContent = stato.storia.premessa || "";
  $("percorso-storia").textContent = id;

  // interlocutore predefinito: primo personaggio, altrimenti Narratore
  const primo = stato.personaggi[0];
  impostaInterlocutore(primo ? primo.id : "Narratore");

  renderPersonaggi();
  renderMessaggi(dati.messaggi);
  renderMemoria();
  controllaModello();
  avviaPolling();
}

$("bottone-torna").addEventListener("click", mostraBenvenuto);

$("bottone-elimina").addEventListener("click", async () => {
  if (!confirm("Eliminare davvero questa storia? Potrai recuperarla solo dalla cartella dati/storie sul disco.")) return;
  await fetch(`/api/storie/${sid}/elimina`, { method: "POST" });
  mostraBenvenuto();
});

function controllaModello() {
  fetch("/api/salute").then(r => r.json()).then(s => {
    const el = $("stato-modello");
    if (!s.ollama_attivo) el.textContent = "⚠️ Ollama non avviato";
    else if (!s.attore_presente) el.textContent = `⚠️ Manca il modello: ollama pull ${s.modello_attore}`;
    else el.textContent = `Modello: ${s.modello_attore}`;
  }).catch(() => {});
}

// ------------------------------- personaggi / interlocutore
function renderPersonaggi() {
  const contenitore = $("lista-personaggi");
  contenitore.innerHTML = "";
  for (const p of stato.personaggi) {
    const b = document.createElement("button");
    b.className = "personaggio-card" + (interlocutore === p.id ? " attivo" : "");
    b.innerHTML = `
      <div class="avatar"></div>
      <div class="info"><strong></strong><small></small></div>`;
    b.querySelector(".avatar").style.background = coloreAvatar(p.nome);
    b.querySelector(".avatar").textContent = iniziali(p.nome);
    b.querySelector("strong").textContent = p.nome;
    b.querySelector("small").textContent = p.descrizione || p.personalita || "…";
    b.addEventListener("click", () => impostaInterlocutore(p.id));
    contenitore.appendChild(b);
  }
  const btnNarr = $("bottone-narratore");
  btnNarr.classList.toggle("attivo", interlocutore === "Narratore");
}

function impostaInterlocutore(id) {
  interlocutore = id;
  if (!stato) return;
  const p = stato.personaggi.find(x => x.id === id);
  $("nome-attivo").textContent = p ? p.nome : "Narratore";
  $("avatar-attivo").textContent = p ? iniziali(p.nome) : "📖";
  $("avatar-attivo").style.background = p ? coloreAvatar(p.nome) : "linear-gradient(135deg,#64748b,#334155)";
  renderPersonaggi();
}

$("bottone-narratore").addEventListener("click", () => impostaInterlocutore("Narratore"));

// ------------------------------- messaggi
function bolla(msg) {
  const fila = document.createElement("div");
  const ruolo = msg.ruolo;
  fila.className = "fila-msg " + (ruolo === "utente" ? "utente" : ruolo === "narratore" ? "narratore" : "");

  const b = document.createElement("div");
  if (ruolo === "narratore") {
    b.className = "bolla narratore";
    b.textContent = msg.testo;
  } else {
    b.className = "bolla " + (ruolo === "utente" ? "utente" : "personaggio");
    const autore = document.createElement("span");
    autore.className = "autore";
    autore.textContent = msg.nome || "";
    const testo = document.createElement("span");
    testo.textContent = msg.testo;
    b.appendChild(autore);
    b.appendChild(testo);
    if (ruolo !== "utente") {
      const av = document.createElement("div");
      av.className = "avatar";
      av.style.background = coloreAvatar(msg.nome || "?");
      av.textContent = iniziali(msg.nome || "?");
      fila.appendChild(av);
    }
  }
  fila.appendChild(b);
  return fila;
}

function renderMessaggi(lista) {
  const contenitore = $("messaggi");
  contenitore.innerHTML = "";
  for (const m of lista) contenitore.appendChild(bolla(m));
  contenitore.scrollTop = contenitore.scrollHeight;
}

function aggiungiMessaggioTemporaneo(nome, ruolo) {
  return bolla({ ruolo, nome, testo: "" });
}

async function inviaMessaggio() {
  const input = $("input-testo");
  const testo = input.value.trim();
  if (!testo || staScrivendo || !sid) return;

  staScrivendo = true;
  $("bottone-invia").disabled = true;
  input.value = "";
  input.style.height = "auto";

  const contenitore = $("messaggi");
  contenitore.appendChild(bolla({ ruolo: "utente", nome: "Tu", testo }));

  const p = stato.personaggi.find(x => x.id === interlocutore);
  const bollaRisp = aggiungiMessaggioTemporaneo(p ? p.nome : "Narratore", p ? "personaggio" : "narratore");
  const span = bollaRisp.querySelector(".bolla");
  span.classList.add("cursore-scrive");
  contenitore.appendChild(bollaRisp);
  contenitore.scrollTop = contenitore.scrollHeight;

  try {
    const r = await fetch(`/api/storie/${sid}/messaggi`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ testo, interlocutore }),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.errore || "Errore del server.");
    }

    const lettore = r.body.getReader();
    const decodificatore = new TextDecoder();
    let accumulato = "";
    while (true) {
      const { done, value } = await lettore.read();
      if (done) break;
      accumulato += decodificatore.decode(value, { stream: true });
      span.textContent = accumulato;
      contenitore.scrollTop = contenitore.scrollHeight;
    }
    if (accumulato.includes("⚠️")) {
      span.classList.remove("cursore-scrive");
      span.className = "bolla sistema";
    }
  } catch (e) {
    span.classList.remove("cursore-scrive");
    span.textContent = "⚠️ " + e.message;
    span.className = "bolla sistema";
  } finally {
    span.classList.remove("cursore-scrive");
    staScrivendo = false;
    $("bottone-invia").disabled = false;
    input.focus();
    // aggiorna lo stato (l'archivista potrebbe già aver scritto)
    ricaricaStato();
  }
}

$("bottone-invia").addEventListener("click", inviaMessaggio);
$("input-testo").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); inviaMessaggio(); }
});
$("input-testo").addEventListener("input", function () {
  this.style.height = "auto";
  this.style.height = Math.min(this.scrollHeight, 130) + "px";
});

async function ricaricaStato() {
  if (!sid) return;
  const r = await fetch(`/api/storie/${sid}`);
  if (!r.ok) return;
  const dati = await r.json();
  stato = dati.stato;
  renderPersonaggi();
  renderMemoria();
  // riempi le bolle con i testi definitivi (in caso di duplicati, ripulisci)
  const contenitore = $("messaggi");
  const bolleTemporanee = contenitore.querySelectorAll(".cursore-scrive");
  bolleTemporanee.forEach(b => b.remove());
}

// ------------------------------- archivista (polling)
function avviaPolling() {
  fermaPolling();
  timerPolling = setInterval(controllaArchivista, 2500);
}

function fermaPolling() {
  if (timerPolling) { clearInterval(timerPolling); timerPolling = null; }
  $("toast").classList.add("nascosta");
  $("indicatore-archivista").classList.add("nascosta");
}

async function controllaArchivista() {
  if (!sid) return;
  try {
    const r = await fetch(`/api/storie/${sid}/archivista?dopo=${ultimoIdLog}`);
    const dati = await r.json();

    $("indicatore-archivista").classList.toggle("nascosta", !dati.in_corso);

    if (dati.voci && dati.voci.length > 0) {
      ultimoIdLog = dati.ultimo_id;
      const ultima = dati.voci[dati.voci.length - 1];
      const riep = (ultima.riepilogo || []).filter(x => x && !x.startsWith("(nessuna"));
      const nota = (ultima.riepilogo || []).find(x => x && x.startsWith("Nota: "));
      const testo = riep.length
        ? "🧠 " + (nota ? nota.replace("Nota: ", "") : riep.join(" · "))
        : "";
      if (testo) mostraToast(testo);
      if ($("pannello-memoria") && !$("pannello-memoria").classList.contains("nascosta")) {
        await ricaricaStato();
        renderMemoria();
      }
    }
  } catch { /* silenzioso: il server potrebbe essere occupato */ }
}

// ------------------------------- toast
let toastTimeout = null;
function mostraToast(testo) {
  $("toast-testo").textContent = testo;
  $("toast").classList.remove("nascosta");
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => $("toast").classList.add("nascosta"), 12000);
}

$("toast-chiudi").addEventListener("click", () => $("toast").classList.add("nascosta"));
$("toast-annulla").addEventListener("click", async () => {
  $("toast").classList.add("nascosta");
  const r = await fetch(`/api/storie/${sid}/annulla_memoria`, { method: "POST" });
  const dati = await r.json();
  alert(dati.msg || "Fatto.");
  await ricaricaStato();
  renderMemoria();
});

// ------------------------------- pannello memoria
$("bottone-memoria").addEventListener("click", async () => {
  await ricaricaStato();
  renderMemoria();
  $("pannello-memoria").classList.remove("nascosta");
});
$("chiudi-memoria").addEventListener("click", () => $("pannello-memoria").classList.add("nascosta"));

function schedaEntita(titolo, righe, json) {
  const d = document.createElement("div");
  d.className = "scheda-entita";
  const h = document.createElement("h4");
  h.textContent = titolo;
  d.appendChild(h);
  for (const [etichetta, valore] of righe) {
    if (valore === undefined || valore === null || valore === "") continue;
    const r = document.createElement("div");
    r.className = "riga";
    const e = document.createElement("span");
    e.className = "etichetta";
    e.textContent = etichetta;
    r.appendChild(e);
    r.appendChild(document.createTextNode(String(valore)));
    d.appendChild(r);
  }
  const det = document.createElement("details");
  const sum = document.createElement("summary");
  sum.textContent = "Mostra JSON";
  const pre = document.createElement("pre");
  pre.textContent = JSON.stringify(json, null, 2);
  det.appendChild(sum);
  det.appendChild(pre);
  d.appendChild(det);
  return d;
}

function renderMemoria() {
  if (!stato) return;
  const c = $("contenuto-memoria");
  c.innerHTML = "";

  const sez = (titolo) => {
    const s = document.createElement("div");
    s.className = "sezione-memoria";
    const h = document.createElement("h4");
    h.textContent = titolo;
    s.appendChild(h);
    c.appendChild(s);
    return s;
  };

  const s1 = sez("Personaggi");
  for (const p of stato.personaggi) {
    s1.appendChild(schedaEntita(p.nome, [
      ["Chi è", p.descrizione], ["Carattere", p.personalita], ["Aspetto", p.aspetto],
      ["Umore", p.stato_animo],
      ["Relazioni", Object.entries(p.relazioni || {}).map(([k, v]) => `${k}: ${v}`).join(" · ")],
      ["Fatti", (p.fatti_chiave || []).map(f => `• ${f}`).join("\n")],
    ], p));
  }

  const s2 = sez("Luoghi");
  for (const l of stato.luoghi) {
    s2.appendChild(schedaEntita(l.nome, [["Descrizione", l.descrizione], ["Atmosfera", l.atmosfera]], l));
  }

  const s3 = sez("Eventi");
  for (const e of stato.eventi) {
    s3.appendChild(schedaEntita(e.titolo, [
      ["Stato", e.stato], ["Descrizione", e.descrizione],
      ["Conseguenze", (e.conseguenze || []).map(x => `• ${x}`).join("\n")],
    ], e));
  }

  const s4 = sez("Scena corrente");
  const nomeLuogo = (stato.luoghi.find(l => l.id === stato.scena.luogo) || {}).nome || stato.scena.luogo;
  const presenti = stato.personaggi.filter(p => stato.scena.presente.includes(p.id)).map(p => p.nome);
  s4.appendChild(schedaEntita("Dove siamo ora", [
    ["Luogo", nomeLuogo], ["Presenti", presenti.join(", ")], ["Situazione", stato.scena.situazione],
  ], stato.scena));
}

// ------------------------------- avvio
mostraBenvenuto();
