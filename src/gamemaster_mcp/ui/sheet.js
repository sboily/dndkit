/* A character sheet as its player reads it: who they are, their numbers, how
 * they cast, their spells (each opening on its description), their gear,
 * proficiencies and story. */
"use strict";

import { I18N } from "./words.js";
import { GM } from "./shared.js";

export function CharacterSheet() {
  const { h, fill, t } = GM;
  const signed = (n) => (n >= 0 ? `+${n}` : `${n}`);
  const section = (title, ...content) => h("div", { class: "section" }, h("h4", {}, title), ...content);
  const chips = (items) => h("div", { class: "list" }, items.map((item) => h("span", { class: "chip" }, item)));
  const bonus = (name, value) => (value === null || value === undefined ? name : `${name} ${signed(value)}`);
  const stat = ([label, value]) => h("div", { class: "stat" }, h("b", {}, value), h("span", {}, label));
  const el = h("div", { class: "card sheet" }, h("div", { class: "empty" }, "…"));

  const spell = (s) => h("details", { class: "spell" + (s.prepared ? " prepared" : "") },
    h("summary", {}, h("b", {}, s.name), " ",
      h("span", { class: "muted small" }, s.level === 0 ? t("cantrip") : `${t("level")} ${s.level}`),
      s.prepared ? h("span", { class: "chip warn" }, t("prepared")) : null),
    s.details ? h("div", { class: "muted small" }, s.details) : null,
    s.description ? h("p", { class: "small" }, s.description) : null);

  const item = (i) => h("div", { class: "item" },
    i.slot ? h("span", { class: "chip" }, i.slot) : null, " ",
    h("b", {}, i.qty > 1 ? `${i.name} ×${i.qty}` : i.name),
    i.details ? h("span", { class: "muted small" }, ` (${i.details})`) : null,
    i.description ? h("span", { class: "muted small" }, ` — ${i.description}`) : null);

  function render(c) {
    const stats = [[t("ac"), c.ac], [t("speed"), I18N.distance(c.speed)], [t("initiative"), signed(c.initiative)],
      [t("proficiency"), signed(c.proficiency)], [t("xp"), c.xp]];
    const casting = c.casting ? [[t("castsWith"), t(c.casting.ability.slice(0, 3))], [t("spellAttack"), signed(c.casting.attack)],
      [t("spellDc"), c.casting.dc]] : [];
    const xpRatio = c.next_level_xp ? Math.min(1, c.xp / c.next_level_xp) : 1;
    const identity = [c.background, c.alignment].filter(Boolean).join(" · ");
    const deathSaves = c.hp === 0 ? h("div", { class: "small" }, `${t("deathSaves")} `,
      GM.pips(c.death_saves[0], 3, "good"), " ", GM.pips(c.death_saves[1], 3, "bad")) : null;
    fill(el,
      h("div", { class: "head" }, h("span", { class: "title" }, c.inspiration ? `${c.name} ★` : c.name),
        h("span", { class: "muted small" }, c.summary + (c.player ? ` — ${c.player}` : ""))),
      identity ? h("div", { class: "muted small identity" }, identity) : null,
      h("div", { class: "vitals" }, GM.hpBar(c.hp, c.hp_max, c.temp)),
      deathSaves,
      h("div", { class: "stats" }, stats.map(stat)),
      casting.length ? h("div", { class: "stats casting" }, casting.map(stat)) : null,
      c.next_level_xp ? h("div", { class: "muted small" }, `${t("nextLevel")}: ${c.next_level_xp} ${t("xp")}`,
        h("div", { class: "xp" }, h("i", { style: `width:${xpRatio * 100}%` }))) : null,
      h("div", { class: "abilities" }, c.abilities.map((a) => h("div", { class: "ability" },
        h("div", { class: "key" }, t(a.key)), h("div", { class: "mod" }, signed(a.mod)),
        h("div", { class: "score" }, a.score)))),
      GM.conditions(c.conditions, c.exhaustion, c.concentration),
      c.slots.length ? section(t("slots"), h("div", { class: "list" }, c.slots.map(([level, left, max]) =>
        h("span", { class: "slot" }, `${t("lvl")} ${level} `, GM.pips(left, max))))) : null,
      c.spells.length ? section(t("spells"), h("div", { class: "spells" }, c.spells.map(spell))) : null,
      c.equipment.length ? section(t("equipped"), h("div", {}, c.equipment.map(item))) : null,
      c.inventory.length ? section(t("inventory"), h("div", {}, c.inventory.map(item))) : null,
      c.race.subrace || c.race.traits.length ? section(c.race.subrace ? `${c.race.name} · ${c.race.subrace}` : c.race.name,
        chips(c.race.traits)) : null,
      c.features.length ? section(t("features"), chips(c.features)) : null,
      c.skills.length || c.saves.length ? section(t("proficiencies"),
        chips([...c.skills.map((s) => bonus(t(s.name), s.bonus)),
          ...c.saves.map((s) => bonus(`${t("save")} ${t(s.name)}`, s.bonus))])) : null,
      c.languages.length ? section(t("languages"), chips(c.languages)) : null,
      c.description || c.bio ? section(t("story"),
        c.description ? h("p", { class: "small appearance" }, c.description) : null,
        c.bio ? h("p", { class: "small" }, c.bio) : null) : null,
      h("div", { class: "muted small" }, `${t("hitDice")}: ${c.hit_dice}`),
    );
  }

  return { el, render };
}
