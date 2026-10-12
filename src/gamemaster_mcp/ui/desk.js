/* The game master's desk, on the backstage: what the model called (to follow
 * and debug it), the campaign's notebook, and every full sheet with its notes. */
"use strict";

/** The model's calls, newest first: tool, arguments, answer or error, time taken. */
function Activity() {
  const { h, fill, t } = GM;
  const count = h("span", { class: "muted small" });
  const calls = h("div", { class: "calls" });
  const el = h("div", { class: "card activity" },
    h("div", { class: "head" }, h("span", { class: "title" }, t("activity")), count), calls);
  const firstLine = (text) => (text || "").split("\n")[0];

  const call = (c) => h("details", { class: "call" + (c.failed ? " failed" : "") + (c.kind === "skill" ? " skill" : "") },
    h("summary", {},
      h("span", { class: "when" }, c.time),
      h("b", { class: "tool" }, c.name),
      h("span", { class: "gist" }, firstLine(c.failed ? `⚠ ${c.outcome}` : c.outcome)),
      h("span", { class: "ms" }, `${c.ms} ms`)),
    c.arguments ? h("pre", { class: "args" }, c.arguments) : null,
    c.outcome ? h("pre", { class: "outcome" }, c.outcome) : null);

  function render(data) {
    count.textContent = data.failures ? t("failures", { n: data.failures }) : "";
    fill(calls, data.calls.length ? data.calls.map(call) : h("div", { class: "empty small" }, t("noCall")));
  }

  return { el, render };
}

/** Situation, world notes, setting, past sessions, and where the campaign lives. */
function Notebook() {
  const { h, fill, t } = GM;
  const section = (title, ...content) => h("div", { class: "section" }, h("h4", {}, title), ...content);
  const body = h("div");
  const el = h("div", { class: "card notebook" },
    h("div", { class: "head" }, h("span", { class: "title" }, t("notebook"))), body);
  const text = (value) => h("p", { class: "small prose" }, value);

  function render(n) {
    const server = n.server;
    fill(body,
      n.situation ? section(t("situation"), text(n.situation)) : null,
      n.world_notes ? section(t("worldNotes"), text(n.world_notes)) : null,
      n.setting ? section(t("setting"), h("details", {}, h("summary", { class: "small" }, t("show")), text(n.setting))) : null,
      n.sessions.length ? section(t("sessions"), n.sessions.map((s) => h("details", { class: "session" },
        h("summary", {}, h("b", {}, `${t("session")} ${s.number}`), s.title ? ` — ${s.title}` : ""),
        text(s.summary),
        s.moments.length ? h("ul", { class: "small" }, s.moments.map((m) => h("li", {}, m))) : null,
        h("div", { class: "muted small" }, [s.present.join(", "), s.xp ? `${s.xp} ${t("xp")}` : "",
          s.treasure.length ? `${t("treasure")}: ${s.treasure.join(", ")}` : ""].filter(Boolean).join(" · ")),
        s.notes ? text(s.notes) : null))) : null,
      !n.situation && !n.world_notes && !n.setting && !n.sessions.length
        ? h("div", { class: "empty small" }, t("noNotes")) : null,
      h("div", { class: "server muted small" },
        n.dm ? [`${t("dm")} ${n.dm}`, h("br")] : null,
        `gamemaster-mcp ${server.version} · ${server.file || "—"} · ${t("saved")} ${server.saved}`, h("br"),
        `${server.data_dir} · ${t("skills")}: ${server.skills.join(", ") || "—"}`));
  }

  return { el, render };
}

/** Every character's full sheet, with the game master's notes under it. */
function Sheets() {
  const { h, fill, t } = GM;
  const el = h("div", { class: "sheets" });
  const shown = new Map();

  function render(data) {
    const cards = data.sheets.map((sheet) => {
      if (!shown.has(sheet.name)) {
        const view = CharacterSheet();
        const notes = h("div", { class: "note small" });
        shown.set(sheet.name, { view, notes, box: h("div", { class: "sheetbox" }, view.el, notes) });
      }
      const { view, notes, box } = shown.get(sheet.name);
      view.render(sheet);
      fill(notes, sheet.notes ? [h("b", {}, `${t("notes")} `), sheet.notes] : null);
      return box;
    });
    const names = new Set(data.sheets.map((sheet) => sheet.name));
    [...shown.keys()].filter((name) => !names.has(name)).forEach((name) => shown.delete(name));
    fill(el, cards);
  }

  return { el, render };
}
