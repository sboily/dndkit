/* Gamemaster MCP widgets: the MCP Apps bridge and shared helpers.
 *
 * roomkit-ui hands a page only the tool's text result, sometimes to the
 * widget it replaces, so pages read their data through tools/call
 * get_screen_data. The host answers request ids as strings, may not listen
 * yet when the page loads (ui/initialize is retried), and shows any
 * console.error under the widget, so errors are rendered, never logged.
 */
"use strict";

const GM = (() => {
  const pending = new Map();
  const inputWaiters = [];
  const resultHandlers = [];
  let nextId = 1;
  let ready = false;
  let input = null;
  let lastHeight = 0;

  const post = (message) => window.parent.postMessage({ jsonrpc: "2.0", ...message }, "*");
  const notify = (method, params) => post({ method, params });
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  function request(method, params, timeoutMs) {
    const id = nextId++;
    post({ id, method, params });
    return new Promise((resolve, reject) => {
      pending.set(String(id), { resolve, reject });
      setTimeout(() => {
        if (pending.delete(String(id))) reject(new Error("timeout"));
      }, timeoutMs);
    });
  }

  window.addEventListener("message", (event) => {
    const msg = event.data;
    if (!msg || msg.jsonrpc !== "2.0") return;
    if (msg.id !== undefined && msg.method === undefined) {
      const waiter = pending.get(String(msg.id));
      if (!waiter) return;
      pending.delete(String(msg.id));
      if (msg.error) waiter.reject(new Error(msg.error.message || "error"));
      else waiter.resolve(msg.result);
    } else if (msg.method === "ui/notifications/tool-input") {
      input = (msg.params && msg.params.arguments) || {};
      inputWaiters.splice(0).forEach((resolve) => resolve(input));
    } else if (msg.method === "ui/notifications/tool-result") {
      resultHandlers.forEach((handler) => handler(msg.params || {}));
    }
  });

  async function connect() {
    for (let attempt = 0; attempt < 10 && !ready; attempt++) {
      try {
        await request(
          "ui/initialize",
          {
            protocolVersion: "2026-01-26",
            appInfo: { name: "gamemaster-mcp", version: "1" },
            appCapabilities: {},
          },
          800,
        );
        ready = true;
      } catch (_) {
        /* the host was not listening yet: ask again */
      }
    }
    notify("ui/notifications/initialized", {});
  }

  /** The arguments the model called the tool with ({} if none arrive). */
  function toolInput(timeoutMs = 3000) {
    if (input) return Promise.resolve(input);
    return new Promise((resolve) => {
      inputWaiters.push(resolve);
      setTimeout(() => resolve(input || {}), timeoutMs);
    });
  }

  async function callTool(name, args) {
    const result = await request("tools/call", { name, arguments: args || {} }, 15000);
    const text = ((result && result.content) || [])
      .filter((block) => block.type === "text")
      .map((block) => block.text)
      .join("\n");
    if (result && result.isError) throw new Error(text || "error");
    return text;
  }

  const data = async (view, extra) =>
    JSON.parse(await callTool("get_screen_data", { view, ...(extra || {}) }));

  /** Re-render from get_screen_data every few seconds, only when the data changed. */
  function live(view, extra, render, intervalMs) {
    let previous = "";
    let failures = 0;
    const tick = async () => {
      try {
        const text = await callTool("get_screen_data", { view, ...(extra || {}) });
        failures = 0;
        if (text !== previous) {
          previous = text;
          render(JSON.parse(text));
          status("");
        }
      } catch (error) {
        failures += 1;
        status(error.message);
      }
      if (failures < 5) setTimeout(tick, intervalMs);
    };
    tick();
  }

  function fit() {
    const height = Math.ceil(document.body.getBoundingClientRect().height) + 2;
    if (Math.abs(height - lastHeight) < 4) return;
    lastHeight = height;
    notify("ui/notifications/size-changed", { width: document.body.scrollWidth, height });
  }

  function status(message) {
    const box = document.getElementById("status");
    if (box) box.textContent = message || "";
    fit();
  }

  /** Children to append: nested lists flattened, empty values dropped
   *  (DOM methods would print null as the text "null"). */
  const nodes = (children) =>
    children
      .flat(Infinity)
      .filter((child) => child !== null && child !== undefined && child !== false && child !== "")
      .map((child) => (child instanceof Node ? child : document.createTextNode(String(child))));

  /** Replace an element's content. */
  const fill = (el, ...children) => el.replaceChildren(...nodes(children));

  /** Build DOM without innerHTML: names come from players and the model. */
  function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs || {})) {
      if (value === null || value === undefined || value === false) continue;
      if (key === "class") el.className = value;
      else if (key === "style") el.style.cssText = value;
      else el.setAttribute(key, value === true ? "" : value);
    }
    el.append(...nodes(children));
    return el;
  }

  const FRENCH = (navigator.language || "").toLowerCase().startsWith("fr");
  const WORDS = {
    round: ["Round", "Round"], turn: ["turn", "tour"], hp: ["HP", "PV"], ac: ["AC", "CA"],
    total: ["Total", "Total"], advantage: ["Advantage", "Avantage"],
    disadvantage: ["Disadvantage", "Désavantage"], waiting: ["Rolling…", "Lancer…"],
    noCombat: ["No combat running.", "Aucun combat en cours."],
    defeated: ["Overcome", "Vaincus"], xp: ["XP", "XP"], session: ["Session", "Session"],
    funds: ["Funds", "Bourse"], quests: ["Active quests", "Quêtes en cours"],
    noQuest: ["No active quest.", "Aucune quête en cours."], inCombat: ["In combat", "En combat"],
    party: ["Party", "Groupe"], noParty: ["No character yet.", "Aucun personnage."],
    slots: ["Spell slots", "Emplacements de sorts"], spells: ["Spells", "Sorts"],
    inventory: ["Inventory", "Inventaire"], cantrip: ["Cantrip", "Tour de magie"],
    level: ["Level", "Niveau"], prepared: ["prepared", "préparé"],
    proficiency: ["Proficiency", "Maîtrise"], inspiration: ["Inspiration", "Inspiration"],
    deathSaves: ["Death saves", "Jets contre la mort"], exhaustion: ["Exhaustion", "Épuisement"],
    temp: ["temp", "temp"], unknown: ["unknown", "inconnu"], nextLevel: ["next level", "niveau suivant"],
    turnOf: ["{name}'s turn", "Tour de {name}"], lvl: ["Lvl", "Niv."],
    str: ["STR", "FOR"], dex: ["DEX", "DEX"], con: ["CON", "CON"], int: ["INT", "INT"],
    wis: ["WIS", "SAG"], cha: ["CHA", "CHA"],
    blinded: ["blinded", "aveuglé"], charmed: ["charmed", "charmé"], deafened: ["deafened", "assourdi"],
    frightened: ["frightened", "effrayé"], grappled: ["grappled", "agrippé"],
    incapacitated: ["incapacitated", "neutralisé"], invisible: ["invisible", "invisible"],
    paralyzed: ["paralyzed", "paralysé"], petrified: ["petrified", "pétrifié"],
    poisoned: ["poisoned", "empoisonné"], prone: ["prone", "à terre"],
    restrained: ["restrained", "entravé"], stunned: ["stunned", "étourdi"],
    unconscious: ["unconscious", "inconscient"],
  };
  const t = (key, values) => {
    const text = (WORDS[key] ? WORDS[key][FRENCH ? 1 : 0] : key).replace(/\{(\w+)\}/g, (_, name) =>
      values && values[name] !== undefined ? values[name] : "");
    // French elision: "Tour de Élodie" -> "Tour d'Élodie".
    return FRENCH ? text.replace(/\bde ([aeiouyàâéèêëîïôûü])/gi, "d'$1") : text;
  };

  function hpBar(hp, max, temp) {
    if (hp === null || hp === undefined || !max) return h("div", { class: "muted small" }, t("hp") + " ?");
    const ratio = Math.max(0, Math.min(1, hp / max));
    const tone = ratio > 0.5 ? "" : ratio > 0.25 ? " mid" : " low";
    const label = `${hp}/${max}` + (temp ? ` (+${temp} ${t("temp")})` : "");
    return h(
      "div",
      { class: "hp" },
      h("div", { class: "hpbar" + tone }, h("i", { style: `width:${ratio * 100}%` })),
      h("span", { class: "hplabel" }, label),
    );
  }

  const conditions = (names, exhaustion) =>
    h(
      "div",
      { class: "chips" },
      (names || []).map((name) => h("span", { class: "chip cond" }, t(name))),
      exhaustion ? h("span", { class: "chip warn" }, `${t("exhaustion")} ${exhaustion}`) : null,
    );

  function pips(filled, total, kind) {
    return h(
      "span",
      { class: "pips " + (kind || "") },
      Array.from({ length: total }, (_, i) => h("i", { class: i < filled ? "on" : "" })),
    );
  }

  /** Connect to the host, then run the page's main function. */
  function start(main) {
    new ResizeObserver(fit).observe(document.body);
    connect().then(main).catch((error) => status(error.message));
  }

  return { start, toolInput, data, live, callTool, h, fill, t, hpBar, conditions, pips, status, fit, sleep,
    onResult: (handler) => resultHandlers.push(handler) };
})();
