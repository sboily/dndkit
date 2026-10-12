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

  /** The battle map, if any, and the initiative order with hit points; for the players,
   *  how hurt a monster looks. *me*: the name of the player's own token, to ring it. */
  function combat({ me = () => null } = {}) {
    const title = h("span", { class: "title" }, "⚔");
    const turn = h("span", { class: "muted small" });
    const map = h("div", { class: "map" });
    const order = h("div", { class: "order" });
    const defeated = h("div", { class: "defeated" });
    const el = h("div", { class: "card combat" }, head(title, turn), map, order, defeated);
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
        h("div", { class: "name" }, f.current ? h("span", { class: "arrow" }, "▶") : null,
          f.boss ? h("span", { class: "crown", title: t("boss") }, "♛") : null, f.name,
          f.ac !== null && f.ac !== undefined ? h("span", { class: "ac" }, `${t("ac")} ${f.ac}`) : null,
          f.position ? h("span", { class: "pos" }, f.position) : null,
          f.hidden ? h("span", { class: "chip away" }, t("hidden")) : null),
        vitals(f),
        GM.conditions(f.conditions, f.exhaustion),
        legendary(f));
    }

    /** The game master's count of legendary actions and resistances. */
    function legendary(f) {
      if (!f.legendary || !(f.legendary[1] || f.resistances)) return null;
      return h("div", { class: "legendary small muted" },
        f.legendary[1] ? h("span", {}, `${t("legendaryActions")} `, GM.pips(f.legendary[0], f.legendary[1])) : null,
        f.resistances ? h("span", {}, `${t("legendaryResistances")} `, GM.pips(f.resistances, f.resistances)) : null);
    }

    function render(data) {
      const current = data.order.find((f) => f.current);
      title.textContent = data.in_combat ? `⚔ ${t("round")} ${data.round}` : "⚔";
      turn.textContent = current ? t("turnOf", { name: current.name }) : "";
      fill(map, data.map ? BattleMap(data.map, me()) : null);
      map.hidden = !data.map;
      fill(order, data.order.length ? data.order.map(fighter) : h("div", { class: "empty" }, t("noCombat")));
      fill(defeated, data.defeated.length ? [
        h("span", { class: "muted small" }, `${t("defeated")}:`),
        data.defeated.map((name) => h("span", { class: "chip gone" }, name)),
        data.xp ? h("span", { class: "chip warn" }, `${data.xp} ${t("xp")}`) : null,
      ] : null);
    }

    return { el, render };
  }

  /** A web page's heading: the campaign's name and pitch, the session, where and when. */
  function campaign() {
    const name = h("h1", {});
    const pitch = h("p", { class: "pitch" });
    const facts = h("div", { class: "facts muted" });
    const el = h("header", { class: "campaign" }, name, pitch, facts);
    pitch.addEventListener("click", () => pitch.classList.toggle("open"));

    function render(data) {
      name.textContent = data.campaign;
      pitch.textContent = data.description || "";
      pitch.hidden = !data.description;
      fill(facts, [[t("session"), data.session], ["📍", data.location], ["📅", data.date]]
        .filter(([, value]) => value)
        .map(([label, value]) => h("span", {}, `${label} `, h("b", {}, value))));
    }

    return { el, render };
  }

  /** Each character's vitals. *campaign*: under the campaign's name, with where and
   *  when (a widget), else under "Party" (a web page, whose heading says the rest).
   *  *quests* adds their progress. */
  function party({ quests = true, campaign = true } = {}) {
    const name = h("span", { class: "title" }, "🛡");
    const session = h("span", { class: "muted small" });
    const facts = h("div", { class: "facts muted small" });
    const banner = h("div");
    const grid = h("div", { class: "grid" });
    const questList = h("div");
    const el = h("div", { class: "card party" }, head(name, session), facts, banner, grid,
      quests ? section(t("quests"), questList) : null);

    const member = (c) => h("div", { class: "pc" + (c.hp === 0 ? " down" : "") + (c.present === false ? " away" : "") },
      h("div", { class: "top" }, h("b", {}, c.name), h("span", { class: "muted small" }, `${t("ac")} ${c.ac}`)),
      h("div", { class: "muted small" }, c.summary + (c.player ? ` — ${c.player}` : ""),
        c.present === false ? h("span", { class: "chip away" }, t(c.player ? "away" : "unplayed")) : null),
      GM.hpBar(c.hp, c.hp_max, c.temp),
      c.hp === 0 ? deathSaves(c) : null,
      c.slots.length ? h("div", { class: "small muted" }, slots(c)) : null,
      GM.conditions(c.conditions, c.exhaustion));

    const progress = (q) => h("div", { class: "quest" }, h("span", {}, q.title),
      h("div", { class: "bar", title: `${q.done}/${q.total}` },
        h("i", { style: `width:${(q.total ? q.done / q.total : 0) * 100}%` })));

    function render(data) {
      name.textContent = campaign ? data.campaign : `🛡 ${t("party")}`;
      session.textContent = campaign ? `${t("session")} ${data.session}` : "";
      const place = campaign ? [["📍", data.location], ["📅", data.date]] : [];
      fill(facts, [...place, [t("funds"), data.funds]]
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

  /** Who sits at the table: the players around it with their characters, then who is
   *  missing. A narrow screen or a big table lists them instead. */
  function seating() {
    const session = h("span", { class: "muted small" });
    const round = h("div", { class: "round" });
    const others = h("div", { class: "others" });
    const el = h("div", { class: "card seating" },
      head(h("span", { class: "title" }, t("theTable")), session), round, others);
    let seats = 0;
    const layout = () => round.classList.toggle("list", seats > 8 || el.clientWidth < 440);
    new ResizeObserver(layout).observe(el);

    function seat(s, index) {
      const angle = (index / seats) * 2 * Math.PI - Math.PI / 2;  // clockwise from the top
      const style = `left:${50 + 37 * Math.cos(angle)}%;top:${50 + 38 * Math.sin(angle)}%`;
      return h("div", { class: "seat" + (s.characters.length ? "" : " new"), style },
        h("b", {}, s.player),
        s.characters.length
          ? s.characters.map((c) => h("span", { class: "plays", title: c.summary }, c.name))
          : h("span", { class: "muted small" }, t("noCharacter")));
    }

    const chips = (label, items) => (items.length
      ? h("div", { class: "row small" }, h("span", { class: "muted" }, `${t(label)}:`), items.map((text) => h("span", { class: "chip" }, text)))
      : null);

    function render(data) {
      seats = data.seats.length;
      session.textContent = `${t("session")} ${data.session}`;
      fill(round, seats ? [h("div", { class: "top" }, h("span", {}, data.campaign)), data.seats.map(seat)] : null);
      round.hidden = !seats;
      layout();
      fill(others,
        data.called ? null : h("div", { class: "empty small" }, t("nobodySeated")),
        chips(data.called ? "absentees" : "knownPlayers", data.absent.map((a) => `${a.player} (${a.name})`)),
        chips("noPlayer", data.unplayed));
    }

    return { el, render };
  }

  /** One character's sheet. */
  function character() {
    const el = h("div", { class: "card sheet" }, h("div", { class: "empty" }, "…"));

    function render(c) {
      const stats = [[t("ac"), c.ac], [t("speed"), I18N.distance(c.speed)],
        [t("proficiency"), signed(c.proficiency)], [t("xp"), c.xp]];
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

  return { campaign, combat, party, seating, character, journal, join, backstage: Backstage, dice: DiceTray };
})();
