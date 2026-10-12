/* The dice tray: polyhedral dice tumble and settle on the faces rolled; a
 * natural 20 glows, a natural 1 shakes, the die advantage drops fades. */
"use strict";

import { GM } from "./shared.js";

export function DiceTray() {
  const { h, fill, t } = GM;
  const MAX_SHOWN = 24;
  const COLORS = { 4: ["#d9674c", "#8f2f1d"], 6: ["#4f8fdc", "#1f4f8f"], 8: ["#5fb57a", "#226b3c"],
    10: ["#9a73dc", "#55308f"], 12: ["#dc9a4f", "#8f5520"], 20: ["#d8b45c", "#7d5a14"] };
  const SHAPES = {
    4: '<polygon points="50,6 95,90 5,90"/>',
    6: '<rect x="10" y="10" width="80" height="80" rx="14"/>',
    8: '<polygon points="50,3 96,50 50,97 4,50"/><polyline points="4,50 96,50" class="edge"/>',
    10: '<polygon points="50,3 94,40 78,92 22,92 6,40"/><path d="M6,40 L50,58 L94,40 M50,58 L50,92" class="edge"/>',
    12: '<polygon points="50,3 95,35 78,92 22,92 5,35"/><polygon points="50,24 72,40 64,66 36,66 28,40" class="edge"/>',
    20: '<polygon points="50,3 92,27 92,73 50,97 8,73 8,27"/><polygon points="50,22 76,66 24,66" class="edge"/>',
  };

  const notation = h("span", { class: "title" }, "🎲");
  const mode = h("span", { class: "muted small" });
  const tray = h("div", { class: "dice" });
  const total = h("div", { class: "total" }, h("span", { class: "muted" }, "…"));
  const history = h("div", { class: "history" });
  const el = h("div", { class: "dicebox" },
    h("div", { class: "card tray" }, h("div", { class: "head" }, notation, mode), tray, total), history);
  let shown = null;

  function svgDie(sides) {
    const [light, dark] = COLORS[sides] || ["#8d8a96", "#4a4752"];
    const shape = SHAPES[sides] || '<circle cx="50" cy="50" r="46"/>';
    return `<svg viewBox="0 0 100 100"><defs><linearGradient id="g${sides}" x1="0" y1="0" x2="1" y2="1">` +
      `<stop offset="0" stop-color="${light}"/><stop offset="1" stop-color="${dark}"/></linearGradient></defs>` +
      `<g fill="url(#g${sides})" stroke="rgba(255,255,255,.35)" stroke-width="2">${shape}</g></svg>`;
  }

  function dieElement(sides, face, delay, classes) {
    const die = h("div", { class: `die d${sides} ${classes}`, style: `animation-delay:${delay}ms` });
    die.innerHTML = svgDie(Number(sides)); // static markup from SHAPES only, no outside text
    die.querySelectorAll(".edge").forEach((edge) => edge.setAttribute("fill", "none"));
    const number = h("span", { class: "face" }, "?");
    die.append(number, h("span", { class: "kind" }, `d${sides}`));
    const settleAt = performance.now() + delay + 750;
    const spin = () => {
      if (performance.now() >= settleAt) { number.textContent = face; return; }
      number.textContent = 1 + Math.floor(Math.random() * sides);
      setTimeout(spin, 70);
    };
    setTimeout(spin, delay);
    return die;
  }

  /** Roll *roll* on screen; *rolls* (the latest ones) fill the history under it. */
  function show(roll, rolls) {
    shown = `${roll.n}@${roll.t}`;
    tray.replaceChildren();
    let delay = 0;
    let count = 0;
    let crit = false;
    let fumble = false;
    roll.terms.forEach((term, index) => {
      if (index > 0 || term.sign < 0) tray.append(h("span", { class: "const" }, term.sign < 0 ? "−" : "+"));
      if (!term.sides) { tray.append(h("span", { class: "const" }, term.faces[0])); return; }
      term.faces.forEach((face, i) => {
        if (count >= MAX_SHOWN) return;
        const kept = term.kept === null || term.kept === undefined || (face === term.kept && i === term.faces.indexOf(term.kept));
        const natural = term.sides === 20 && kept ? (face === 20 ? "crit" : face === 1 ? "fumble" : "") : "";
        crit = crit || natural === "crit";
        fumble = fumble || natural === "fumble";
        tray.append(dieElement(term.sides, face, delay, (kept ? "" : "dropped ") + natural));
        delay += 110;
        count += 1;
      });
    });
    const hidden = roll.terms.reduce((n, term) => n + (term.sides ? term.faces.length : 0), 0) - count;
    if (hidden > 0) tray.append(h("span", { class: "chip" }, `+${hidden}`));
    notation.textContent = (roll.secret ? "🔒 " : "") + roll.notation;
    mode.textContent = roll.mode === "normal" ? "" : t(roll.mode);
    total.className = "total";
    fill(total, h("span", { class: "muted small" }, t("waiting")));
    setTimeout(() => {
      total.className = "total" + (crit ? " crit" : fumble ? " fumble" : "");
      fill(total, h("span", { class: "muted small" }, t("total")), h("b", {}, roll.total));
      GM.fit();
    }, delay + 800);
    const older = (rolls || []).filter((r) => r.n !== roll.n).slice(-5).reverse();
    fill(history, older.map((r) => h("span", { class: "chip" }, `${r.secret ? "🔒 " : ""}${r.notation} → ${r.total}`)));
    GM.fit();
  }

  /** Web pages: roll the newest roll when one arrives. */
  function render(data) {
    const latest = data.rolls[data.rolls.length - 1];
    if (latest && `${latest.n}@${latest.t}` !== shown) show(latest, data.rolls);
  }

  return { el, show, render };
}
