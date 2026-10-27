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
  const cells = Array(order.indexOf(s.dealer)).fill("");
  s.calls.forEach((c) => cells.push(callHtml(c)));
  const nextIndex = s.over ? -1 : cells.length;
  cells.push("");
  while (cells.length % 4) cells.push("");
  let rows = "";
  for (let i = 0; i < cells.length; i += 4) {
    rows += "<tr>" + cells.slice(i, i + 4).map((c, j) => `<td${i + j === nextIndex ? ' class="next"' : ""}>${c}</td>`).join("") + "</tr>";
  }
  $("#auction tbody").innerHTML = rows;

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
  } else {
    renderBidBox();
  }
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

$("#next").onclick = () => socket?.send(JSON.stringify({ type: "next" }));

$("#share").onclick = async () => {
  const url = `${location.origin}/?t=${state.table}`;
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

if (session && !invite) connect();
else showView("lobby");

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
