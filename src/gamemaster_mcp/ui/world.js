/* The world as the game master knows it, for the backstage: NPCs with their
 * secrets, the places (the party's own marked), and the bestiary's stat
 * blocks. Each entry opens on its details. */
"use strict";

function World() {
  const { h, fill, t } = GM;
  const empty = (key) => h("div", { class: "empty small" }, t(key));
  const lists = { npcs: h("div"), locations: h("div"), monsters: h("div") };
  const card = (title, list) => h("div", { class: "card world" },
    h("div", { class: "head" }, h("span", { class: "title" }, title)), list);
  const el = h("div", { class: "worldgrid" },
    card(t("npcs"), lists.npcs), card(t("locations"), lists.locations), card(t("bestiary"), lists.monsters));
  const fact = (label, value) => (value || value === 0
    ? h("div", { class: "small" }, h("b", {}, `${label} `), Array.isArray(value) ? value.join(", ") : value)
    : null);
  const secret = (label, text) => (text ? h("div", { class: "note small" }, h("b", {}, `${label} `), text) : null);
  const line = (...parts) => parts.filter(Boolean).join(" · ");
  const signed = (n) => (n >= 0 ? `+${n}` : `${n}`);

  const entry = (summary, ...body) => h("details", { class: "entry" }, h("summary", {}, ...summary), ...body);

  const npc = (n) => entry(
    [h("b", {}, n.name), n.attitude ? h("span", { class: `chip ${n.attitude}` }, t(n.attitude)) : null,
      h("span", { class: "muted small" }, line(n.race, n.occupation, n.location))],
    n.description ? h("p", { class: "small" }, n.description) : null,
    fact(t("ties"), n.ties.length ? n.ties : null), fact(t("stats"), n.stats.length ? n.stats : null),
    secret(`🔒 ${t("secret")}`, n.bio), secret(t("notes"), n.notes));

  const place = (p) => entry(
    [h("b", {}, p.name), h("span", { class: "muted small" }, p.type),
      p.current ? h("span", { class: "chip here" }, `📍 ${t("partyHere")}`) : null],
    p.description ? h("p", { class: "small" }, p.description) : null,
    fact(t("population"), p.population), fact(t("government"), p.government),
    fact(t("notable"), p.features.length ? p.features : null), fact(t("npcs"), p.npcs.length ? p.npcs : null),
    fact(t("leadsTo"), p.connections.length ? p.connections : null), secret(t("notes"), p.notes));

  const monster = (m) => entry(
    [m.boss ? h("span", { class: "crown" }, "♛") : null, h("b", {}, m.name),
      h("span", { class: "muted small" }, line(`${t("ac")} ${m.ac}`, `${t("hp")} ${m.hp}`, m.cr ? `CR ${m.cr}` : "")),
      m.fighting ? h("span", { class: "chip warn" }, `${m.fighting} ${t("inFight")}`) : null],
    h("div", { class: "muted small" }, line(t(m.size), m.speed, `${t("initiative")} ${signed(m.initiative)}`, `${m.xp} ${t("xp")}`)),
    m.legendary[0] || m.legendary[1] ? h("div", { class: "small" },
      `${t("legendaryActions")} ${m.legendary[0]} · ${t("legendaryResistances")} ${m.legendary[1]}`) : null,
    m.actions ? h("p", { class: "small actions" }, m.actions) : null, secret(t("notes"), m.notes));

  function render(data) {
    fill(lists.npcs, data.npcs.length ? data.npcs.map(npc) : empty("noNpc"));
    fill(lists.locations, data.locations.length ? data.locations.map(place) : empty("noLocation"));
    fill(lists.monsters, data.monsters.length ? data.monsters.map(monster) : empty("noMonster"));
  }

  return { el, render };
}
