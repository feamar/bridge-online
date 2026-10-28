"use strict";

const SEAT_NL = { N: "Noord", E: "Oost", S: "Zuid", W: "West" };
const SEAT_SHORT = { N: "N", E: "O", S: "Z", W: "W" };
const VUL_NL = { "-": "Niemand kwetsbaar", NS: "NZ kwetsbaar", EW: "OW kwetsbaar", ALL: "Allen kwetsbaar" };
const STRAINS = ["C", "D", "H", "S", "NT"];
const SUIT_SYM = { C: "♣", D: "♦", H: "♥", S: "♠", NT: "SA" };
const RED = new Set(["D", "H"]);
const RANK_NL = { A: "A", K: "H", Q: "V", J: "B", T: "10" };

const $ = (sel) => document.querySelector(sel);
let session = loadSession();
let socket = null;
let state = null;
let selectedLevel = null;
let publicUrl = "";
let explainIndex = null;

function loadSession() {
  try { return JSON.parse(localStorage.getItem("bridge-session")); } catch { return null; }
}
function saveSession(s) {
  session = s;
  try { s ? localStorage.setItem("bridge-session", JSON.stringify(s)) : localStorage.removeItem("bridge-session"); } catch {}
}

// ---------- rendering helpers ----------

function strainHtml(strain) {
  const cls = RED.has(strain) ? ' class="red"' : "";
  return `<span${cls}>${SUIT_SYM[strain]}</span>`;
}

function callHtml(call) {
  if (call === "P") return "Pas";
  if (call === "X" || call === "XX") return `<span class="red">${call}</span>`;
  return call[0] + strainHtml(call.slice(1));
}

function handHtml(hand, title) {
  const rows = ["S", "H", "D", "C"].map((s) => {
    const cards = hand[s].map((r) => RANK_NL[r] || r).join(" ") || "—";
    return `<div class="suit"><span class="sym">${strainHtml(s)}</span>${cards}</div>`;
  });
  return (title ? `<div class="who">${title}</div>` : "") + rows.join("");
}

function seatLabel(seat) {
  const name = state.names[seat];
  if (seat === state.seat) return `${SEAT_NL[seat]} (jij)`;
  if (name) return `${SEAT_NL[seat]} (${escapeHtml(name)})`;
  if (seat === "E" || seat === "W") return `${SEAT_NL[seat]} (computer)`;
  return SEAT_NL[seat];
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function isVulnerable(seat) {
  const v = state.vulnerability;
  return v === "ALL" || (v === "NS" && (seat === "N" || seat === "S")) || (v === "EW" && (seat === "E" || seat === "W"));
}

// ---------- game view ----------

function render() {
  const s = state;
  $("#board").textContent = s.board;
  $("#dealer").textContent = SEAT_NL[s.dealer];
  $("#vul").textContent = VUL_NL[s.vulnerability];
  $("#table-code").textContent = s.table;

  document.querySelectorAll("#auction th").forEach((th) => {
    const seat = th.dataset.seat;
    th.textContent = seat === s.seat ? `${SEAT_SHORT[seat]} (jij)` : (s.names[seat] || SEAT_SHORT[seat]);
    th.classList.toggle("vul", isVulnerable(seat));
    th.classList.toggle("me", seat === s.seat);
  });

  // Auction grid in W N E S columns, starting at the dealer's column.
  const order = ["W", "N", "E", "S"];
  const offset = order.indexOf(s.dealer);
  const cells = Array(offset).fill("");
  s.calls.forEach((c) => cells.push(callHtml(c)));
  const nextIndex = s.over ? -1 : cells.length;
  cells.push("");
  while (cells.length % 4) cells.push("");
  let rows = "";
  for (let i = 0; i < cells.length; i += 4) {
    rows += "<tr>" + cells.slice(i, i + 4).map((c, j) => {
      const callIndex = i + j - offset;
      const cls = [];
      if (i + j === nextIndex) cls.push("next");
      if (s.explanations[callIndex]) cls.push("has-explain");
      const attrs = s.explanations[callIndex] ? ` data-index="${callIndex}"` : "";
      return `<td class="${cls.join(" ")}"${attrs}>${c}</td>`;
    }).join("") + "</tr>";
  }
  $("#auction tbody").innerHTML = rows;
  renderExplain();
  $("#ai-warning").hidden = s.ai.available;

  $("#my-hand").innerHTML = handHtml(s.hands[s.seat], `Jouw hand · ${s.hcp[s.seat]} punten`);

  if (s.over) {
    $("#status").innerHTML = s.contract
      ? `Eindcontract: ${s.contract.level}${strainHtml(s.contract.strain)}${s.contract.doubled} door ${SEAT_NL[s.contract.declarer]}`
      : "Doorgepast.";
  } else if (s.toAct === s.seat) {
    $("#status").textContent = "Jij bent aan de beurt.";
  } else {
    $("#status").textContent = `Wachten op ${seatLabel(s.toAct)}…`;
  }

  $("#bidbox").hidden = s.over;
  $("#my-hand").hidden = s.over;
  $("#result").hidden = !s.over;
  if (s.over) {
    document.querySelectorAll(".compass .hand").forEach((el) => {
      const seat = el.dataset.seat;
      el.innerHTML = handHtml(s.hands[seat], `${seatLabel(seat)} · ${s.hcp[seat]} pt`);
    });
    renderReview();
  } else {
    renderBidBox();
  }
}

// BEN's explanations use BBA notation such as "!S" for a spade symbol.
function explanationHtml(text) {
  return escapeHtml(text).replace(/!([SHDC])/g, (_, st) => strainHtml(st)).replace(/\bNT\b/g, "SA");
}

function renderExplain() {
  const text = explainIndex !== null && state.explanations[explainIndex];
  $("#explain").hidden = !text;
  if (text) {
    const seat = seatOfCall(explainIndex);
    $("#explain").innerHTML = `<strong>${SEAT_NL[seat]} ${callHtml(state.calls[explainIndex])}</strong>: ${explanationHtml(text)}`;
  }
}

function seatOfCall(index) {
  const seats = ["N", "E", "S", "W"];
  return seats[(seats.indexOf(state.dealer) + index) % 4];
}

function contractHtml(c) {
  return `${c.level}${strainHtml(c.strain)}${c.doubled}`;
}

function scoreHtml(score) {
  if (score > 0) return `<span class="score-plus">+${score}</span>`;
  if (score < 0) return `<span class="score-min">${score}</span>`;
  return "0";
}

function resultText(result) {
  if (result === 0) return "precies gemaakt";
  if (result > 0) return `gemaakt met ${result} overslag${result > 1 ? "en" : ""}`;
  return `${-result} down`;
}

function renderReview() {
  const s = state;
  const r = s.review;
  if (!r) { $("#review").innerHTML = ""; return; }
  const parts = [];

  if (!r.dd) {
    parts.push(`<div class="card"><h2>Analyse</h2><p class="muted">Bezig met de double-dummy analyse…</p></div>`);
  } else {
    const dd = r.dd;
    let contractLine;
    if (s.contract) {
      const c = s.contract;
      contractLine = `<p>Jullie contract ${contractHtml(c)} door ${SEAT_NL[c.declarer]}: ${dd.contract.tricks} slagen bij perfect spel, ${resultText(dd.contract.result)}. Score voor jullie: ${scoreHtml(dd.contract.score)}.</p>`;
    } else {
      contractLine = `<p>Het spel is doorgepast. Score voor jullie: 0.</p>`;
    }
    const par = dd.par.contracts.length
      ? dd.par.contracts.map((c) => `${contractHtml(c)} door ${SEAT_NL[c.declarer]}`).join(" of ")
      : "doorpassen";
    const diff = dd.contract.score - dd.par.score;
    const verdict = diff === 0 ? "Precies de par-score." : diff > 0 ? `Dat is ${diff} punten beter dan par.` : `Dat is ${-diff} punten minder dan par.`;
    parts.push(`<div class="card"><h2>Resultaat</h2>${contractLine}
      <p>Par: ${par}, ${scoreHtml(dd.par.score)} voor jullie. ${verdict}</p></div>`);

    const strains = ["C", "D", "H", "S", "NT"];
    const seats = ["N", "S", "E", "W"];
    const head = `<tr><th></th>${strains.map((st) => `<th>${strainHtml(st)}</th>`).join("")}</tr>`;
    const body = seats.map((seat) => `<tr><th>${SEAT_NL[seat]}</th>${strains.map((st) => {
      const n = dd.tricks[st][seat];
      const cls = [n >= 7 ? "makes" : ""];
      if (s.contract && s.contract.declarer === seat && s.contract.strain === st) cls.push("contract");
      return `<td class="${cls.join(" ")}">${n}</td>`;
    }).join("")}</tr>`).join("");
    parts.push(`<div class="card"><h2>Slagen bij open kaart</h2><table class="dd">${head}${body}</table>
      <p class="muted">Aantal slagen dat elke speler als leider maakt in elke kleur, als iedereen perfect speelt.</p></div>`);
  }

  if (r.benStatus !== "off") {
    const items = r.ben.map((b) => `<li class="${b.same ? "same" : "diff"}">
        <span class="verdict">${b.same ? "✓" : "BEN: " + callHtml(b.ben)}</span>
        ${SEAT_NL[b.seat]} bood ${callHtml(b.call)}
        ${!b.same && b.explanation ? `<span class="why">${callHtml(b.ben)}: ${explanationHtml(b.explanation)}</span>` : ""}
      </li>`).join("");
    let note = "";
    if (r.benStatus === "pending") note = `<p class="muted">BEN bekijkt jullie biedingen…</p>`;
    if (r.benStatus === "unavailable") note = `<p class="muted">BEN is niet bereikbaar, dus de vergelijking ontbreekt.</p>`;
    const same = r.ben.filter((b) => b.same).length;
    const summary = r.benStatus === "done" ? `<p>${same} van de ${r.ben.length} biedingen ${same === 1 ? "is" : "zijn"} gelijk aan wat BEN zou bieden.</p>` : "";
    parts.push(`<div class="card"><h2>Wat zou BEN bieden?</h2>${summary}<ul class="ben-list">${items}</ul>${note}</div>`);
  }

  $("#review").innerHTML = parts.join("");
}

function renderBidBox() {
  const legal = new Set(state.legal);
  const myTurn = state.toAct === state.seat;
  $("#bidbox").classList.toggle("waiting", !myTurn);
  if (selectedLevel && !STRAINS.some((st) => legal.has(selectedLevel + st))) selectedLevel = null;

  $("#bidbox .levels").innerHTML = [1, 2, 3, 4, 5, 6, 7].map((l) => {
    const ok = STRAINS.some((st) => legal.has(l + st));
    return `<button data-level="${l}" ${ok ? "" : "disabled"} class="${selectedLevel === l ? "selected" : ""}">${l}</button>`;
  }).join("");

  $("#bidbox .strains").innerHTML = STRAINS.map((st) => {
    const ok = selectedLevel && legal.has(selectedLevel + st);
    return `<button data-strain="${st}" ${ok ? "" : "disabled"}>${strainHtml(st)}</button>`;
  }).join("");

  document.querySelectorAll("#bidbox .specials button").forEach((b) => { b.disabled = !legal.has(b.dataset.call); });
}

function sendCall(call) {
  selectedLevel = null;
  showGameError("");
  socket?.send(JSON.stringify({ type: "call", call }));
}

function showGameError(msg) {
  $("#game-error").textContent = msg;
  $("#game-error").hidden = !msg;
}

// ---------- connection ----------

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${proto}://${location.host}/ws/${session.table}?token=${encodeURIComponent(session.token)}`);
  socket.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === "state") {
      if (state && state.board !== msg.state.board) explainIndex = null;
      state = msg.state;
      showView("game");
      render();
    } else if (msg.type === "error") {
      showGameError(msg.message);
    }
  };
  socket.onclose = (ev) => {
    if (ev.code === 4404) {
      // Table no longer exists (e.g. the server restarted).
      saveSession(null);
      showView("lobby");
      showLobbyError("Deze tafel bestaat niet meer. Maak een nieuwe tafel aan.");
      return;
    }
    if (session) setTimeout(connect, 1500);
  };
}

function showView(name) {
  $("#lobby").hidden = name !== "lobby";
  $("#game").hidden = name !== "game";
}

function showLobbyError(msg) {
  $("#lobby-error").textContent = msg;
  $("#lobby-error").hidden = !msg;
}

async function enter(url) {
  showLobbyError("");
  const name = $("#name").value.trim();
  try { localStorage.setItem("bridge-name", name); } catch {}
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) });
  const body = await res.json();
  if (!res.ok) return showLobbyError(body.detail || "Er ging iets mis.");
  saveSession({ table: body.table, token: body.token });
  history.replaceState(null, "", location.pathname);
  connect();
}

// ---------- events ----------

$("#create").onclick = () => enter("/api/tables");
$("#join").onclick = () => {
  const code = $("#code").value.trim().toUpperCase();
  if (code.length !== 4) return showLobbyError("Vul de code van 4 letters in.");
  enter(`/api/tables/${code}/join`);
};

$("#bidbox").addEventListener("click", (ev) => {
  const b = ev.target.closest("button");
  if (!b || b.disabled) return;
  if (b.dataset.level) {
    selectedLevel = Number(b.dataset.level);
    renderBidBox();
  } else if (b.dataset.strain) {
    sendCall(selectedLevel + b.dataset.strain);
  } else if (b.dataset.call) {
    sendCall(b.dataset.call);
  }
});

$("#auction").addEventListener("click", (ev) => {
  const td = ev.target.closest("td[data-index]");
  const index = td ? Number(td.dataset.index) : null;
  explainIndex = index === explainIndex ? null : index;
  renderExplain();
});

$("#next").onclick = () => socket?.send(JSON.stringify({ type: "next" }));

$("#share").onclick = async () => {
  const url = `${publicUrl || location.origin}/?t=${state.table}`;
  const text = `Doe mee aan mijn bridgetafel, code ${state.table}`;
  if (navigator.share) {
    try { await navigator.share({ title: "Bridge Oefenen", text, url }); } catch {}
  } else {
    try { await navigator.clipboard.writeText(url); alert("Link gekopieerd: " + url); } catch { alert(url); }
  }
};

$("#leave").onclick = () => {
  if (!confirm("Tafel verlaten? Je kunt daarna niet terug op deze plaats.")) return;
  saveSession(null);
  socket?.close();
  showView("lobby");
};

// ---------- start ----------

try { $("#name").value = localStorage.getItem("bridge-name") || ""; } catch {}
const invite = new URLSearchParams(location.search).get("t");
if (invite) $("#code").value = invite.toUpperCase();

fetch("/api/config").then((r) => r.json()).then((c) => { publicUrl = (c.publicUrl || "").replace(/\/$/, ""); }).catch(() => {});

if (session && !invite) connect();
else showView("lobby");

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
