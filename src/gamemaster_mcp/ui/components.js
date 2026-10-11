/* Gamemaster MCP views: one renderer per kind of game data, shared by the
 * MCP widgets (one view each) and the web pages (several at once).
 * Each factory returns { el, render(data) } and keeps what it needs between
 * updates: the last hit points (to flash a hit or a heal), the last roll. */
"use strict";

const Views = (() => {
  const { h, fill, t } = GM;
  const signed = (n) => (n >= 0 ? `+${n}` : `${n}`);
  const section = (title, ...content) => h("div", { class: "section" }, h("h4", {}, title), ...content);
  const empty = (key) => h("div", { class: "empty small" }, t(key));
  const head = (...children) => h("div", { class: "head" }, ...children);
  const HEALTH = { down: 0, bloodied: 1, hurt: 2, unhurt: 3 };

  const deathSaves = (c) => h("div", { class: "small" }, `${t("deathSaves")} `,
    GM.pips(c.death_saves[0], 3, "good"), " ", GM.pips(c.death_saves[1], 3, "bad"));
  const slots = (c) => c.slots.map(([level, left, max]) =>
    h("span", { class: "slot" }, `${t("lvl")} ${level} `, GM.pips(left, max)));

  /** Initiative order with hit points; for the players, how hurt a monster looks. */
  function combat() {
    const title = h("span", { class: "title" }, "⚔");
    const turn = h("span", { class: "muted small" });
    const order = h("div", { class: "order" });
    const defeated = h("div", { class: "defeated" });
    const el = h("div", { class: "card combat" }, head(title, turn), order, defeated);
    const last = new Map();

    function vitals(f) {
      if (f.health === undefined) return GM.hpBar(f.hp, f.hp_max, f.temp);
      return h("div", {}, f.health ? h("span", { class: `health ${f.health}` }, t(f.health)) : null);
    }

    function fighter(f) {
      const value = f.health === undefined ? f.hp : HEALTH[f.health];
      const before = last.get(f.name);
      last.set(f.name, value);
      const known = before !== undefined && before !== null && value !== undefined && value !== null;
      const change = !known ? "" : value < before ? " hurt" : value > before ? " healed" : "";
      const down = f.hp === 0 || f.health === "down";
      const classes = "fighter" + (f.pc ? " pc" : "") + (f.current ? " current" : "") + (down ? " down" : "") + change;
      return h("div", { class: classes },
        h("div", { class: "init" }, f.initiative),
        h("div", { class: "name" }, f.current ? h("span", { class: "arrow" }, "▶") : null, f.name,
          f.ac !== null && f.ac !== undefined ? h("span", { class: "ac" }, `${t("ac")} ${f.ac}`) : null),
        vitals(f),
        GM.conditions(f.conditions, f.exhaustion));
    }

    function render(data) {
      const current = data.order.find((f) => f.current);
      title.textContent = data.in_combat ? `⚔ ${t("round")} ${data.round}` : "⚔";
      turn.textContent = current ? t("turnOf", { name: current.name }) : "";
      fill(order, data.order.length ? data.order.map(fighter) : h("div", { class: "empty" }, t("noCombat")));
      fill(defeated, data.defeated.length ? [
        h("span", { class: "muted small" }, `${t("defeated")}:`),
        data.defeated.map((name) => h("span", { class: "chip gone" }, name)),
        data.xp ? h("span", { class: "chip warn" }, `${data.xp} ${t("xp")}`) : null,
      ] : null);
    }

    return { el, render };
  }

  /** Where the party stands and each character's vitals; *quests* adds their progress. */
  function party({ quests = true } = {}) {
    const name = h("span", { class: "title" }, "🛡");
    const session = h("span", { class: "muted small" });
    const facts = h("div", { class: "facts muted small" });
    const banner = h("div");
    const grid = h("div", { class: "grid" });
    const questList = h("div");
    const el = h("div", { class: "card party" }, head(name, session), facts, banner, grid,
      quests ? section(t("quests"), questList) : null);

    const member = (c) => h("div", { class: "pc" + (c.hp === 0 ? " down" : "") },
      h("div", { class: "top" }, h("b", {}, c.name), h("span", { class: "muted small" }, `${t("ac")} ${c.ac}`)),
      h("div", { class: "muted small" }, c.summary),
      GM.hpBar(c.hp, c.hp_max, c.temp),
      c.hp === 0 ? deathSaves(c) : null,
      c.slots.length ? h("div", { class: "small muted" }, slots(c)) : null,
      GM.conditions(c.conditions, c.exhaustion));

    const progress = (q) => h("div", { class: "quest" }, h("span", {}, q.title),
      h("div", { class: "bar", title: `${q.done}/${q.total}` },
        h("i", { style: `width:${(q.total ? q.done / q.total : 0) * 100}%` })));

    function render(data) {
      name.textContent = data.campaign;
      session.textContent = `${t("session")} ${data.session}`;
      fill(facts, [["📍", data.location], ["📅", data.date], [t("funds"), data.funds]]
        .filter(([, value]) => value)
        .map(([label, value]) => h("span", {}, `${label} `, h("b", {}, value))));
      fill(banner, data.in_combat
        ? h("div", { class: "banner" }, `⚔ ${t("inCombat")} — ${t("round")} ${data.round}` +
            (data.current ? ` — ${t("turnOf", { name: data.current })}` : ""))
        : null);
      fill(grid, data.characters.length ? data.characters.map(member) : h("div", { class: "empty" }, t("noParty")));
      fill(questList, data.quests.length ? data.quests.map(progress) : empty("noQuest"));
    }

    return { el, render };
  }

  /** One character's sheet. */
  function character() {
    const el = h("div", { class: "card sheet" }, h("div", { class: "empty" }, "…"));

    function render(c) {
      const stats = [[t("ac"), c.ac], [t("proficiency"), signed(c.proficiency)], [t("xp"), c.xp]];
      const xpRatio = c.next_level_xp ? Math.min(1, c.xp / c.next_level_xp) : 1;
      fill(el,
        head(h("span", { class: "title" }, c.inspiration ? `${c.name} ★` : c.name),
          h("span", { class: "muted small" }, c.summary + (c.player ? ` — ${c.player}` : ""))),
        h("div", { class: "vitals" }, GM.hpBar(c.hp, c.hp_max, c.temp)),
        c.hp === 0 ? deathSaves(c) : null,
        h("div", { class: "stats" }, stats.map(([label, value]) =>
          h("div", { class: "stat" }, h("b", {}, value), h("span", {}, label)))),
        c.next_level_xp ? h("div", { class: "muted small" }, `${t("nextLevel")}: ${c.next_level_xp} ${t("xp")}`,
          h("div", { class: "xp" }, h("i", { style: `width:${xpRatio * 100}%` }))) : null,
        h("div", { class: "abilities" }, c.abilities.map((a) => h("div", { class: "ability" },
          h("div", { class: "key" }, t(a.key)), h("div", { class: "mod" }, signed(a.mod)),
          h("div", { class: "score" }, a.score)))),
        GM.conditions(c.conditions, c.exhaustion),
        c.slots.length ? section(t("slots"), h("div", { class: "list" }, slots(c))) : null,
        c.spells.length ? section(t("spells"), h("div", { class: "list" }, c.spells.map((s) =>
          h("span", { class: "chip" + (s.prepared ? " warn" : "") },
            `${s.name} · ${s.level === 0 ? t("cantrip") : `${t("level")} ${s.level}`}`)))) : null,
        c.inventory.length ? section(t("inventory"), h("div", { class: "list" }, c.inventory.map((i) =>
          h("span", { class: "chip" }, i.qty > 1 ? `${i.name} ×${i.qty}` : i.name)))) : null,
      );
    }

    return { el, render };
  }

  /** Active quests and their objectives, and the latest moments of the adventure log. */
  function journal() {
    const quests = h("div", { class: "quests" });
    const events = h("div", { class: "events" });
    const el = h("div", { class: "card journal" }, section(t("quests"), quests), section(t("journal"), events));

    const quest = (q) => h("div", { class: "questlog" },
      h("div", {}, h("b", {}, q.title), q.giver ? h("span", { class: "muted small" }, ` — ${t("from", { name: q.giver })}`) : null),
      q.objectives.length ? h("ul", {}, q.objectives.map((o) => h("li", { class: o.done ? "done" : "" }, o.text))) : null);

    const event = (e) => h("div", { class: "event" },
      h("div", {}, h("span", { class: "chip" }, t(e.type)), " ", h("b", {}, e.title),
        e.location ? h("span", { class: "muted small" }, ` — ${e.location}`) : null),
      e.description ? h("div", { class: "muted small" }, e.description) : null);

    function render(data) {
      fill(quests, data.quests.length ? data.quests.map(quest) : empty("noQuest"));
      fill(events, data.events.length ? data.events.map(event) : empty("noEvent"));
    }

    return { el, render };
  }

  /** The players' links as QR codes, for the table screen; they fold away once scanned. */
  function join() {
    const hint = h("div", { class: "muted small" });
    const codes = h("div", { class: "codes" });
    const toggle = h("button", { type: "button", class: "toggle" });
    const el = h("div", { class: "card join" }, head(h("span", { class: "title" }, t("players")), toggle), hint, codes);
    const remembered = () => { try { return localStorage.getItem("gm-codes"); } catch (_) { return null; } };

    function unfold(visible) {
      hint.hidden = codes.hidden = !visible;
      toggle.textContent = t(visible ? "hideCodes" : "showCodes");
      try { localStorage.setItem("gm-codes", visible ? "shown" : "hidden"); } catch (_) { /* storage off */ }
    }
    toggle.addEventListener("click", () => unfold(codes.hidden));
    unfold(remembered() !== "hidden");

    function render(data) {
      hint.textContent = t(data.reachable ? "scanToJoin" : "unreachable");
      fill(codes, data.players.length ? data.players.map((p) =>
        h("a", { class: "code", href: p.url, target: "_blank", rel: "noopener" },
          h("img", { src: p.qr, alt: p.name }), h("b", {}, p.name),
          p.player ? h("span", { class: "muted small" }, p.player) : null)) : empty("noParty"));
    }

    return { el, render };
  }

  /** What only the game master sees: plans, secrets, notes, the bestiary. */
  function backstage() {
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

  return { combat, party, character, journal, join, backstage, dice: DiceTray };
})();
