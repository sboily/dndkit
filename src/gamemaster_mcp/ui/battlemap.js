/* The battle map in SVG: 5-foot squares named like a chessboard (A1 top left),
 * walls, difficult terrain, a token per combatant (the party gold, its foes
 * red, the hidden ones faint on the game master's screen), the squares the
 * acting creature can still reach this turn, and the last area of effect. */
"use strict";

function BattleMap(map, me) {
  const NS = "http://www.w3.org/2000/svg";
  const CELL = 40;
  const GUTTER = 22;
  const at = (n) => GUTTER + n * CELL;

  function s(tag, attrs, ...children) {
    const el = document.createElementNS(NS, tag);
    for (const [key, value] of Object.entries(attrs || {})) {
      if (value !== null && value !== undefined && value !== false) el.setAttribute(key, value);
    }
    el.append(...children.flat().filter((child) => child !== null && child !== undefined));
    return el;
  }

  const square = (cls) => ([x, y]) => s("rect", { x: at(x), y: at(y), width: CELL, height: CELL, class: cls });

  function initials(name) {
    const words = name.trim().split(/\s+/);
    const last = words[words.length - 1];
    if (words.length > 1 && /^\d+$/.test(last)) return words[0].charAt(0).toUpperCase() + last;
    if (words.length > 1) return (words[0].charAt(0) + words[1].charAt(0)).toUpperCase();
    return name.slice(0, 2);
  }

  function token(t) {
    const radius = (t.size * CELL) / 2;
    const cx = at(t.x) + radius;
    const cy = at(t.y) + radius;
    const classes = ["token", t.party ? "party" : "foe", t.current && "current", t.down && "down",
      t.hidden && "hidden", me && t.name === me && "me", t.health].filter(Boolean).join(" ");
    const ratio = t.hp_max ? Math.max(0, Math.min(1, t.hp / t.hp_max)) : null;
    const bar = ratio === null ? null : [
      s("rect", { x: cx - radius + 6, y: cy + radius - 7, width: 2 * radius - 12, height: 4, class: "life" }),
      s("rect", { x: cx - radius + 6, y: cy + radius - 7, width: (2 * radius - 12) * ratio, height: 4,
        class: "life-left" + (ratio > 0.5 ? "" : ratio > 0.25 ? " mid" : " low") }),
    ];
    return s("g", { class: classes }, s("title", {}, t.name),
      s("circle", { cx, cy, r: radius - 5 }),
      s("text", { x: cx, y: cy + 4.5 }, initials(t.name)), bar);
  }

  const width = at(map.width);
  const height = at(map.height);
  const lines = [];
  for (let x = 0; x <= map.width; x++) lines.push(`M${at(x)},${GUTTER}V${height}`);
  for (let y = 0; y <= map.height; y++) lines.push(`M${GUTTER},${at(y)}H${width}`);

  return s("svg", { viewBox: `0 0 ${width + 2} ${height + 2}`, class: "battlemap", role: "img" },
    s("defs", {}, s("pattern", { id: "gm-rough", width: 8, height: 8, patternUnits: "userSpaceOnUse" },
      s("path", { d: "M0,8 L8,0 M-2,2 L2,-2 M6,10 L10,6", class: "hatch" }))),
    s("rect", { x: GUTTER, y: GUTTER, width: width - GUTTER, height: height - GUTTER, class: "floor" }),
    map.moves.map(square("reach")),
    map.difficult.map(square("rough")),
    s("path", { d: lines.join(""), class: "grid" }),
    map.walls.map(square("wall")),
    (map.area || []).map(square("area")),
    Array.from({ length: map.width }, (_, x) =>
      s("text", { x: at(x) + CELL / 2, y: GUTTER - 7, class: "label" }, String.fromCharCode(65 + x))),
    Array.from({ length: map.height }, (_, y) =>
      s("text", { x: GUTTER - 5, y: at(y) + CELL / 2 + 4, class: "label row" }, String(y + 1))),
    map.tokens.map(token));
}
