/* The game master's plans: encounters still to fight, and every quest with
 * its objectives, reward and notes. */
"use strict";

function Backstage() {
  const { h, fill, t } = GM;
  const section = (title, ...content) => h("div", { class: "section" }, h("h4", {}, title), ...content);
  const empty = (key) => h("div", { class: "empty small" }, t(key));
  const encounters = h("div");
  const quests = h("div");
  const el = h("div", { class: "card backstage" },
    h("div", { class: "head" }, h("span", { class: "title" }, t("backstage"))),
    section(t("encounters"), encounters), section(t("allQuests"), quests));
  const note = (label, text) => (text ? h("div", { class: "note small" }, h("b", {}, `${label} `), text) : null);
  const line = (...parts) => parts.filter(Boolean).join(" — ");

  const encounter = (e) => h("div", { class: "entry" + (e.status === "done" ? " done" : "") },
    h("div", { class: "row" }, h("b", {}, e.name), h("span", { class: "chip" }, t(e.status)),
      e.difficulty ? h("span", { class: `chip rating ${e.difficulty}` }, `${t(e.difficulty)} · ${e.xp} ${t("xp")}`) : null),
    h("div", { class: "muted small" }, line(e.monsters.join(", "), e.location)),
    e.description ? h("div", { class: "small" }, e.description) : null,
    note(t("notes"), e.notes));

  const quest = (q) => h("div", { class: "entry" },
    h("div", { class: "row" }, h("b", {}, q.title), h("span", { class: "chip" }, t(q.status)),
      q.total ? h("span", { class: "muted small" }, `${q.done}/${q.total}`) : null),
    q.giver || q.description ? h("div", { class: "small" },
      q.giver ? h("span", { class: "muted" }, `${t("from", { name: q.giver })}. `) : null, q.description) : null,
    q.objectives.length ? h("ul", { class: "objectives small" },
      q.objectives.map((o) => h("li", { class: o.done ? "done" : "" }, o.text))) : null,
    note(t("reward"), q.reward), note(t("notes"), q.notes));

  function render(data) {
    fill(encounters, data.encounters.length ? data.encounters.map(encounter) : empty("noEncounter"));
    fill(quests, data.quests.length ? data.quests.map(quest) : empty("noQuest"));
  }

  return { el, render };
}
