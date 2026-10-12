/* The backstage, for the game master only: encounters still to fight, NPCs
 * with their secrets, every quest with its notes, the bestiary. */
"use strict";

/** What only the game master sees: plans, secrets, notes, the bestiary. */
function Backstage() {
  const { h, fill, t } = GM;
  const section = (title, ...content) => h("div", { class: "section" }, h("h4", {}, title), ...content);
  const empty = (key) => h("div", { class: "empty small" }, t(key));
  const head = (...children) => h("div", { class: "head" }, ...children);
  const lists = { encounters: h("div"), npcs: h("div"), quests: h("div"), monsters: h("div", { class: "list" }) };
  const el = h("div", { class: "card backstage" }, head(h("span", { class: "title" }, t("backstage"))),
    section(t("encounters"), lists.encounters), section(t("npcs"), lists.npcs),
    section(t("allQuests"), lists.quests), section(t("bestiary"), lists.monsters));
  const note = (label, text) => (text ? h("div", { class: "note small" }, h("b", {}, `${label} `), text) : null);
  const line = (...parts) => parts.filter(Boolean).join(" — ");

  const encounter = (e) => h("div", { class: "entry" },
    h("div", { class: "row" }, h("b", {}, e.name), h("span", { class: "chip" }, t(e.status)),
      e.difficulty ? h("span", { class: `chip rating ${e.difficulty}` }, `${t(e.difficulty)} · ${e.xp} ${t("xp")}`) : null),
    h("div", { class: "muted small" }, line(e.monsters.join(", "), e.location)),
    e.description ? h("div", { class: "small" }, e.description) : null,
    note(t("notes"), e.notes));

  const npc = (n) => h("div", { class: "entry" },
    h("div", { class: "row" }, h("b", {}, n.name),
      n.attitude ? h("span", { class: `chip ${n.attitude}` }, t(n.attitude)) : null,
      h("span", { class: "muted small" }, line(n.occupation, n.location))),
    n.description ? h("div", { class: "small" }, n.description) : null,
    note(`🔒 ${t("secret")}`, n.bio), note(t("notes"), n.notes));

  const quest = (q) => h("div", { class: "entry" },
    h("div", { class: "row" }, h("b", {}, q.title), h("span", { class: "chip" }, t(q.status)),
      q.total ? h("span", { class: "muted small" }, `${q.done}/${q.total}`) : null),
    note(t("reward"), q.reward), note(t("notes"), q.notes));

  const monster = (m) => h("span", { class: "chip" },
    `${m.name} · ${t("ac")} ${m.ac} · ${t("hp")} ${m.hp}` + (m.cr ? ` · CR ${m.cr}` : ""));

  function render(data) {
    fill(lists.encounters, data.encounters.length ? data.encounters.map(encounter) : empty("noEncounter"));
    fill(lists.npcs, data.npcs.length ? data.npcs.map(npc) : empty("noNpc"));
    fill(lists.quests, data.quests.length ? data.quests.map(quest) : empty("noQuest"));
    fill(lists.monsters, data.monsters.length ? data.monsters.map(monster) : empty("noMonster"));
  }

  return { el, render };
}
