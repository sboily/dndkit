/* Gamemaster MCP pages: how they get their data, and shared DOM helpers.
 *
 * Two transports, same pages. As an MCP App in roomkit-ui, a page gets only
 * the tool's text result, sometimes in the widget it replaces, so it reads
 * its data through tools/call get_screen_data and polls it. The host answers
 * request ids as strings, may not listen yet when the page loads
 * (ui/initialize is retried), and shows any console.error under the widget,
 * so errors are rendered, never logged.
 * As a web page (window.GM_WEB, set by the server), a page opens one event
 * stream for all its views and the server pushes each change.
 */
"use strict";

const GM = (() => {
  const WEB = window.GM_WEB || null;
  const t = I18N.t;
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

  /** Render *view* now and at every change: pushed on the web, polled in a widget. */
  function live(view, extra, render, intervalMs) {
    if (WEB) return feed.add(view, render);
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

  /** The web pages' one event stream: every view a page shows, sent at each change. */
  const feed = {
    renders: new Map(),
    source: null,
    add(view, render) {
      if (!this.renders.has(view)) this.renders.set(view, []);
      this.renders.get(view).push(render);
      if (!this.source) this.source = Promise.resolve().then(() => this.open());
    },
    open() {
      const views = [...this.renders.keys()].join(",");
      const source = new EventSource(`${WEB.feed}?views=${encodeURIComponent(views)}`);
      for (const [view, renders] of this.renders) {
        source.addEventListener(view, (event) => {
          const data = JSON.parse(event.data);
          if (data.error) return status(t(data.error));
          status("");
          renders.forEach((render) => render(data));
        });
      }
      // The browser reconnects by itself; the server then sends every view again.
      source.onerror = () => status(t("offline"));
      source.onopen = () => status("");
    },
  };

  function fit() {
    if (WEB) return;
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

  /** Connect to the host (a widget) or not (a web page), then run the page's main function. */
  function start(main) {
    if (!WEB) new ResizeObserver(fit).observe(document.body);
    (WEB ? Promise.resolve() : connect()).then(main).catch((error) => status(error.message));
  }

  return { web: Boolean(WEB), start, toolInput, data, live, callTool, h, fill, t, hpBar, conditions, pips,
    status, fit, sleep, onResult: (handler) => resultHandlers.push(handler) };
})();
