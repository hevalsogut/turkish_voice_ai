"use strict";

/* ---------- helpers ---------- */

function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "value") el.value = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return el;
}

async function api(method, url, body) {
  const res = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) { /* not json */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.headers.get("content-type")?.includes("json") ? res.json() : res;
}

let toastTimer;
function toast(message, isError = false) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.className = "show" + (isError ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.className = ""), isError ? 6000 : 2800);
}

const fail = (e) => toast(e.message || String(e), true);
const main = () => document.getElementById("main");
const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/* ---------- status rail ---------- */

async function refreshStatus() {
  try {
    const hl = await api("GET", "/api/health");
    const rows = [
      ["Deepgram key", hl.keys.deepgram],
      ["OpenAI key", hl.keys.openai],
      ["ElevenLabs key", hl.keys.elevenlabs],
      ["Voice server", hl.livekit_server],
    ];
    document.getElementById("status").replaceChildren(
      ...rows.map(([label, ok]) => h("div", {}, h("span", { class: "dot " + (ok ? "ok" : "bad") }), label)),
    );
    state.health = hl;
  } catch (_) { /* dashboard offline; next poll retries */ }
  try {
    const msgs = await api("GET", "/api/handoffs");
    const badge = document.getElementById("msg-count");
    badge.hidden = msgs.length === 0;
    badge.textContent = msgs.length;
  } catch (_) { /* ignore */ }
}

/* ---------- state shared across pages ---------- */

const state = {
  health: null,
  mode: "voice",
  turns: [],        // {id, who, text, interim}
  latency: [],      // {eot, llm, tts, total}
  tools: [],
  pending: {},
  room: null,
  callState: "idle", // idle | connecting | live
  chatId: crypto.randomUUID(),
  joinTimer: null,
};

/* ---------- router ---------- */

const pages = { test: renderTest, calls: renderCalls, agent: renderAgent, knowledge: renderKnowledge,
  appointments: renderAppointments, messages: renderMessages };

function route() {
  const name = (location.hash || "#test").slice(1);
  const page = pages[name] ? name : "test";
  document.querySelectorAll("#nav a").forEach((a) => {
    if (a.dataset.page === page) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  main().replaceChildren();
  pages[page]().catch(fail);
}

/* ---------- test console ---------- */

function pageHeader(title, lede) {
  return [h("h1", {}, title), h("p", { class: "lede" }, lede)];
}

async function renderTest() {
  const callBtn = h("button", { class: "callbtn", id: "callbtn", onclick: toggleCall },
    h("span", { class: "pulse" }), h("span", { id: "calllabel" }, "Start call"));
  const callState = h("span", { id: "callstate", class: "callstate" });
  const modeBtn = (mode, label) => h("button", {
    "aria-pressed": String(state.mode === mode),
    onclick: () => { state.mode = mode; renderTest(); },
  }, label);

  const composer = h("form", { class: "composer", id: "composer", hidden: state.mode !== "text",
    onsubmit: sendText },
    h("input", { type: "text", id: "textin", placeholder: "Type what the caller says, in Turkish",
      autocomplete: "off", "aria-label": "Message as caller" }),
    h("button", { class: "btn primary", type: "submit" }, "Send"),
    h("button", { class: "btn", type: "button", onclick: resetChat }, "New chat"));

  main().replaceChildren(
    ...pageHeader("Test call",
      "Talk to the agent exactly as a caller would. Changes you save in Agent settings or the knowledge base apply to the next call."),
    h("div", { class: "console" },
      h("section", {},
        h("div", { class: "callbar" },
          h("div", { class: "segmented", role: "group", "aria-label": "Test mode" },
            modeBtn("voice", "Voice"), modeBtn("text", "Text")),
          state.mode === "voice" ? callBtn : null,
          state.mode === "voice" ? callState : null),
        h("div", { class: "transcript", id: "transcript", "aria-live": "polite" }),
        composer),
      h("aside", { class: "hood" },
        h("div", { class: "panel" },
          h("h2", {}, "Response time"),
          h("div", { class: "legend" },
            h("span", {}, h("i", { class: "c-eot" }), "Waiting for end of turn"),
            h("span", {}, h("i", { class: "c-llm" }), "Thinking"),
            h("span", {}, h("i", { class: "c-tts" }), "Voice")),
          h("div", { class: "lat-list", id: "latlist" }),
          h("p", { class: "muted" }, "The red line marks 1 second, roughly where a pause starts to feel unnatural.")),
        h("div", { class: "panel" },
          h("h2", {}, "What the agent did"),
          h("div", { class: "events", id: "events" })))),
  );
  paintTranscript(); paintLatency(); paintTools(); paintCall();
}

function paintCall() {
  const btn = document.getElementById("callbtn");
  if (!btn) return;
  const s = state.callState;
  btn.classList.toggle("live", s !== "idle");
  document.getElementById("calllabel").textContent =
    s === "idle" ? "Start call" : s === "connecting" ? "Connecting…" : "End call";
  const cs = document.getElementById("callstate");
  cs.textContent = s === "live" ? "Live. Speak when the agent finishes greeting." : "";
  cs.classList.toggle("live", s === "live");
}

function paintTranscript() {
  const box = document.getElementById("transcript");
  if (!box) return;
  if (state.turns.length === 0) {
    box.replaceChildren(h("p", { class: "empty" },
      state.mode === "voice"
        ? "Start a call and speak Turkish. The conversation appears here as it happens."
        : "Type a caller message below to start a text conversation with the same agent."));
    return;
  }
  box.replaceChildren(...state.turns.map((t) =>
    h("div", { class: `turn ${t.who}${t.interim ? " interim" : ""}` },
      h("small", {}, t.who === "agent" ? "Agent" : "Caller"), t.text)));
  box.scrollTop = box.scrollHeight;
}

function paintLatency() {
  const list = document.getElementById("latlist");
  if (!list) return;
  if (state.latency.length === 0) {
    list.replaceChildren(h("p", { class: "muted" }, "Appears after the agent's first reply."));
    return;
  }
  const MAX = 3; // seconds shown across the full track
  const seg = (cls, sec) => h("span", { class: cls, style: `width:${Math.min(sec / MAX, 1) * 100}%` });
  list.style.setProperty("--target", `${(1 / MAX) * 100}%`);
  list.replaceChildren(...state.latency.slice(-8).reverse().map((r) =>
    h("div", { class: "lat" },
      h("div", { class: "lat-track", style: `--target:${(1 / MAX) * 100}%`,
        title: r.title || "" },
        r.eot != null ? seg("c-eot", r.eot) : null, seg("c-llm", r.llm || 0), r.tts != null ? seg("c-tts", r.tts) : null),
      h("b", { class: r.total > 1.5 ? "slow" : "" }, `${r.total.toFixed(2)}s`))));
}

function paintTools() {
  const box = document.getElementById("events");
  if (!box) return;
  if (state.tools.length === 0) {
    box.replaceChildren(h("p", { class: "muted" }, "Bookings, availability checks and staff messages show up here."));
    return;
  }
  box.replaceChildren(...state.tools.slice(-12).reverse().map((t) =>
    h("div", { class: "tool" }, h("strong", {}, t.name),
      h("pre", {}, JSON.stringify(t.args, null, 1)), h("pre", {}, "→ " + t.result))));
}

function upsertTurn(id, who, text, interim) {
  const existing = state.turns.find((t) => t.id === id);
  if (existing) { existing.text = text; existing.interim = interim; }
  else state.turns.push({ id, who, text, interim });
  paintTranscript();
}

function onAgentEvent(ev) {
  if (ev.type === "tool") { state.tools.push(ev); paintTools(); }
  if (ev.type === "latency") {
    const key = { end_of_turn: "eot", llm: "llm", tts: "tts" }[ev.stage];
    state.pending[key] = ev.seconds;
    if (ev.stage === "tts") {
      const p = state.pending;
      state.latency.push({ ...p, total: (p.eot || 0) + (p.llm || 0) + (p.tts || 0) });
      state.pending = {};
      paintLatency();
    }
  }
}

/* voice call */

async function toggleCall() {
  if (state.callState !== "idle") return endCall();
  state.turns = []; state.latency = []; state.tools = []; state.pending = {};
  state.callState = "connecting"; paintCall(); paintTranscript(); paintLatency(); paintTools();
  try {
    const { url, token } = await api("POST", "/api/voice/token");
    const { Room, RoomEvent } = LivekitClient;
    const room = new Room();
    state.room = room;

    room.on(RoomEvent.TrackSubscribed, (track) => {
      if (track.kind === "audio") document.body.append(track.attach());
    });
    room.on(RoomEvent.TrackUnsubscribed, (track) => track.detach().forEach((e) => e.remove()));
    room.on(RoomEvent.ParticipantConnected, () => {
      clearTimeout(state.joinTimer);
      state.callState = "live"; paintCall();
    });
    room.on(RoomEvent.Disconnected, () => { cleanupCall(); });
    room.on(RoomEvent.DataReceived, (payload, _p, _k, topic) => {
      if (topic !== "agent-events") return;
      try { onAgentEvent(JSON.parse(new TextDecoder().decode(payload))); } catch (_) { /* ignore */ }
    });
    room.registerTextStreamHandler("lk.transcription", async (reader, info) => {
      const attrs = reader.info.attributes || {};
      const id = attrs["lk.segment_id"] || reader.info.id;
      const isAgent = info.identity !== room.localParticipant.identity;
      const final = attrs["lk.transcription_final"] === "true";
      let text = "";
      for await (const chunk of reader) {
        text += chunk;
        upsertTurn(id, isAgent ? "agent" : "caller", text, isAgent ? false : !final);
      }
      upsertTurn(id, isAgent ? "agent" : "caller", text, false);
    });

    await room.connect(url, token);
    await room.startAudio();
    await room.localParticipant.setMicrophoneEnabled(true);
    if (room.remoteParticipants.size > 0) { state.callState = "live"; paintCall(); }
    state.joinTimer = setTimeout(() => {
      if (state.callState === "connecting") {
        toast("The agent did not join. Is the voice worker running? Start everything with: voiceagent dev", true);
      }
    }, 12000);
  } catch (e) {
    fail(e); cleanupCall();
  }
}

function endCall() { state.room?.disconnect(); cleanupCall(); }

function cleanupCall() {
  clearTimeout(state.joinTimer);
  state.room = null; state.callState = "idle";
  document.querySelectorAll("audio").forEach((a) => a.remove());
  paintCall();
}

/* text chat */

async function sendText(ev) {
  ev.preventDefault();
  const input = document.getElementById("textin");
  const message = input.value.trim();
  if (!message) return;
  input.value = ""; input.disabled = true;
  upsertTurn(crypto.randomUUID(), "caller", message, false);
  try {
    const res = await api("POST", "/api/chat", { session_id: state.chatId, message });
    res.replies.forEach((r) => upsertTurn(crypto.randomUUID(), "agent", r, false));
    res.tools.forEach((t) => state.tools.push(t));
    state.latency.push({ llm: res.seconds, total: res.seconds,
      title: "Text round trip: model thinking plus tool calls (no speech)" });
    paintTools(); paintLatency();
  } catch (e) { fail(e); }
  input.disabled = false; input.focus();
}

async function resetChat() {
  await api("DELETE", `/api/chat/${state.chatId}`).catch(() => {});
  state.chatId = crypto.randomUUID();
  state.turns = []; state.latency = []; state.tools = [];
  paintTranscript(); paintLatency(); paintTools();
}

/* ---------- agent settings ---------- */

const LLM_MODELS = [["", "Default (from .env)"], ["gpt-4.1-mini", "gpt-4.1-mini"], ["gpt-4.1", "gpt-4.1"],
  ["gpt-4o-mini", "gpt-4o-mini"], ["gpt-4.1-nano", "gpt-4.1-nano"]];
const TTS_MODELS = [["", "Default (from .env)"], ["eleven_flash_v2_5", "Flash v2.5 (fastest)"],
  ["eleven_turbo_v2_5", "Turbo v2.5"], ["eleven_multilingual_v2", "Multilingual v2 (best quality, slower)"]];

async function renderAgent() {
  const [cfg, defaults] = await Promise.all([api("GET", "/api/config"), api("GET", "/api/defaults")]);
  const a = cfg.agent;
  const f = {};
  const text = (key, label, value, hint) => (f[key] = h("input", { type: "text", value })) && fieldWrap(label, f[key], hint);
  const fieldWrap = (label, input, hint) =>
    h("label", { class: "field" }, label, input, hint ? h("small", {}, hint) : null);
  const select = (key, options, value) => {
    f[key] = h("select", {}, options.map(([v, l]) => h("option", { value: v, selected: v === value }, l)));
    return f[key];
  };

  f.open_days = DAY_NAMES.map((d, i) =>
    h("label", {}, h("input", { type: "checkbox", value: i, checked: cfg.open_days.includes(i) }), d));
  f.open_time = h("input", { type: "time", value: cfg.open_time.slice(0, 5) });
  f.close_time = h("input", { type: "time", value: cfg.close_time.slice(0, 5) });
  f.slot_minutes = h("input", { type: "number", min: 10, max: 120, step: 5, value: cfg.slot_minutes });
  f.departments = h("textarea", { rows: 4 }, cfg.departments.join("\n"));
  f.greeting = h("input", { type: "text", value: a.greeting, placeholder: "Leave empty for a natural greeting" });
  f.style = h("textarea", { rows: 16, spellcheck: "false" });
  f.style.value = a.style_guide || defaults.style_guide;
  f.extra = h("textarea", { rows: 6, placeholder: "Example: Never quote prices over the phone. Always offer the earliest available slot first." }, a.extra_instructions);
  let provider = a.tts_provider || "elevenlabs";
  let voiceId = provider === "elevenlabs" ? a.tts_voice_id : "";  // ElevenLabs voice id
  let oaVoice = provider === "openai" && a.tts_voice_id ? a.tts_voice_id : "marin";  // OpenAI voice name
  f.oa_instructions = h("textarea", { rows: 4 });
  f.oa_instructions.value = a.tts_instructions || defaults.tts_instructions;

  const voiceBox = h("div", { class: "voices" }, h("p", { class: "muted" }, "Loading voices…"));
  const voiceSearch = h("input", { type: "text", placeholder: "Search voices", "aria-label": "Search voices" });
  let allVoices = [];
  const audio = new Audio();
  const play = async (url) => { audio.src = url; await audio.play(); };

  // Turkish voice library: sample clips are free to play; "Add" puts the voice in this account.
  let tab = "mine", libPage = 0, libVoices = [], libMore = false, libLoaded = false;
  const libBox = h("div", { class: "voices", hidden: true });
  const usageLine = h("p", { class: "muted" });
  api("GET", "/api/usage").then((u) => {
    usageLine.textContent = `ElevenLabs ${u.tier} plan: ${u.characters_used.toLocaleString()} of ` +
      `${u.characters_limit.toLocaleString()} characters used this month, ${u.voice_slots} voice slots. ` +
      "Agent speech uses roughly 800 characters per minute.";
  }).catch(() => {});
  const tabMine = h("button", { type: "button", onclick: () => setTab("mine") }, "My voices");
  const tabLib = h("button", { type: "button", onclick: () => setTab("library") }, "Turkish voice library");
  function setTab(t) {
    tab = t;
    tabMine.setAttribute("aria-pressed", String(t === "mine"));
    tabLib.setAttribute("aria-pressed", String(t === "library"));
    voiceBox.hidden = voiceSearch.hidden = t !== "mine";
    libBox.hidden = t !== "library";
    if (t === "library" && !libLoaded) loadLibrary();
  }
  async function loadLibrary() {
    libLoaded = true;
    try {
      const res = await api("GET", `/api/voices/library?page=${libPage}`);
      libVoices = libVoices.concat(res.voices); libMore = res.has_more; paintLibrary();
    } catch (e) { libLoaded = false; fail(e); }
  }
  function paintLibrary() {
    libBox.replaceChildren(
      ...libVoices.map((v) => h("div", { class: "voice" },
        h("span"),
        h("div", {}, h("strong", {}, v.name),
          h("div", { class: "meta" }, [v.gender, v.age, v.accent, v.use_case].filter(Boolean).join(", "))),
        h("div", { class: "actions", style: "margin:0" },
          v.preview_url ? h("button", { class: "btn small", type: "button", onclick: () => play(v.preview_url).catch(fail) }, "Listen") : null,
          h("button", { class: "btn small primary", type: "button", onclick: async (e) => {
            e.target.disabled = true;
            try {
              const r = await api("POST", "/api/voices/library/add",
                { public_owner_id: v.public_owner_id, voice_id: v.voice_id, name: v.name });
              voiceId = r.voice_id;
              allVoices = await api("GET", "/api/voices");
              setTab("mine"); paintVoices();
              toast(`${v.name} added and selected. Save changes to use it.`);
            } catch (err) { fail(err); e.target.disabled = false; }
          } }, "Add and use")))),
      libMore ? h("button", { class: "btn", type: "button", onclick: () => { libPage += 1; loadLibrary(); } }, "Show more") : null,
    );
  }

  function paintVoices() {
    const q = voiceSearch.value.toLowerCase();
    const rows = allVoices.filter((v) => !q || (v.name + JSON.stringify(v.labels)).toLowerCase().includes(q));
    voiceBox.replaceChildren(
      h("label", { class: "voice" + (voiceId === "" ? " selected" : "") },
        h("input", { type: "radio", name: "voice", checked: voiceId === "", onchange: () => { voiceId = ""; paintVoices(); } }),
        h("div", {}, h("strong", {}, "Default voice"), h("div", { class: "meta" }, "Whatever .env or the plugin picks")),
        h("span")),
      ...rows.map((v) => h("label", { class: "voice" + (voiceId === v.voice_id ? " selected" : "") },
        h("input", { type: "radio", name: "voice", checked: voiceId === v.voice_id,
          onchange: () => { voiceId = v.voice_id; paintVoices(); } }),
        h("div", {}, h("strong", {}, v.name),
          h("div", { class: "meta" }, [v.category, ...Object.values(v.labels || {})].filter(Boolean).join(", "))),
        h("button", { class: "btn small", type: "button", onclick: async (e) => {
          e.preventDefault();
          e.target.disabled = true;
          try {
            const res = await api("POST", "/api/voices/preview", { voice_id: v.voice_id, model: f.tts_model.value });
            await play(URL.createObjectURL(await res.blob()));
          } catch (err) { fail(err); }
          e.target.disabled = false;
        } }, "Preview"))),
    );
  }
  voiceSearch.addEventListener("input", paintVoices);
  setTab("mine");
  api("GET", "/api/voices").then((v) => { allVoices = v; paintVoices(); })
    .catch((e) => voiceBox.replaceChildren(h("p", { class: "muted" }, "Could not load voices: " + e.message)));

  const elBox = h("div", {},
    usageLine,
    h("div", { class: "segmented", role: "group", "aria-label": "Voice source" }, tabMine, tabLib),
    h("p", { class: "muted", style: "margin:10px 0 0" },
      "Native Turkish voices sound far better than the English presets. Listening in the library is free; Preview on your own voices costs about 70 characters."),
    voiceSearch, voiceBox, libBox);

  // OpenAI voices: fixed list, steered with written instructions
  const oaList = h("div", { class: "voices" });
  function paintOpenAI() {
    oaList.replaceChildren(...defaults.openai_voices.map((name) => h("label", { class: "voice" + (oaVoice === name ? " selected" : "") },
      h("input", { type: "radio", name: "oavoice", checked: oaVoice === name, onchange: () => { oaVoice = name; paintOpenAI(); } }),
      h("div", {}, h("strong", {}, name), h("div", { class: "meta" }, name === "marin" || name === "cedar" ? "Recommended by OpenAI for best quality" : "")),
      h("button", { class: "btn small", type: "button", onclick: async (e) => {
        e.preventDefault(); e.target.disabled = true;
        try {
          const res = await api("POST", "/api/voices/preview", { voice_id: name, provider: "openai", instructions: f.oa_instructions.value });
          await play(URL.createObjectURL(await res.blob()));
        } catch (err) { fail(err); }
        e.target.disabled = false;
      } }, "Preview"))));
  }
  paintOpenAI();
  const oaBox = h("div", {},
    h("p", { class: "muted" }, "OpenAI's voices are built for English, so Turkish may carry an accent. The instructions below steer accent and tone. Preview costs a fraction of a cent."),
    fieldWrap("Voice instructions", f.oa_instructions, "Written in English works best."),
    h("div", { style: "margin-top:12px" }, oaList));

  const provBtns = ["elevenlabs", "openai"].map((id) => h("button", { type: "button",
    onclick: () => { provider = id; syncProvider(); } }, id === "elevenlabs" ? "ElevenLabs" : "OpenAI"));
  function syncProvider() {
    provBtns.forEach((b, i) => b.setAttribute("aria-pressed", String(["elevenlabs", "openai"][i] === provider)));
    elBox.hidden = provider !== "elevenlabs";
    oaBox.hidden = provider !== "openai";
  }
  syncProvider();

  const save = async () => {
    const body = {
      ...cfg,
      name: f.name.value, agent_name: f.agent_name.value, address: f.address.value,
      timezone: f.timezone.value,
      open_days: f.open_days.map((l) => l.firstChild).filter((c) => c.checked).map((c) => Number(c.value)),
      open_time: f.open_time.value, close_time: f.close_time.value,
      slot_minutes: Number(f.slot_minutes.value),
      departments: f.departments.value.split("\n").map((s) => s.trim()).filter(Boolean),
      agent: { llm_model: f.llm_model.value, tts_provider: provider, tts_model: f.tts_model.value,
        tts_voice_id: provider === "openai" ? oaVoice : voiceId,
        tts_instructions: f.oa_instructions.value.trim() === defaults.tts_instructions ? "" : f.oa_instructions.value.trim(),
        greeting: f.greeting.value.trim(),
        style_guide: f.style.value.trim() === defaults.style_guide.trim() ? "" : f.style.value.trim(),
        extra_instructions: f.extra.value.trim() },
    };
    try { await api("PUT", "/api/config", body); toast("Saved. Applies to the next call."); } catch (e) { fail(e); }
  };

  main().replaceChildren(
    ...pageHeader("Agent settings", "How the agent introduces itself, what the clinic offers, and which voice and model it uses."),
    h("div", { class: "panel" }, h("h2", {}, "Clinic"),
      h("div", { class: "grid2" },
        text("name", "Clinic name", cfg.name), text("agent_name", "Agent's name", cfg.agent_name),
        text("address", "Address", cfg.address), text("timezone", "Time zone", cfg.timezone)),
      h("div", { class: "grid2", style: "margin-top:16px" },
        h("div", { class: "field" }, "Open days", h("div", { class: "days" }, f.open_days)),
        fieldWrap("Opens", f.open_time), fieldWrap("Closes", f.close_time),
        fieldWrap("Appointment length (minutes)", f.slot_minutes),
        fieldWrap("Departments", f.departments, "One per line. Callers book into these."))),
    h("div", { class: "panel" }, h("h2", {}, "Speaking style"),
      h("p", { class: "muted" }, "Who the agent is and how it talks, in Turkish. The examples of good and bad replies shape the tone more than anything else. {agent_name} is replaced by the name above."),
      f.style,
      h("div", { class: "actions" }, h("button", { class: "btn small", type: "button", onclick: () => { f.style.value = defaults.style_guide; toast("Default style restored. Save to keep it."); } }, "Restore default style"))),
    h("div", { class: "panel" }, h("h2", {}, "Behaviour"),
      fieldWrap("Opening line", f.greeting, "Spoken as-is at the start of every call. Leave empty for a natural greeting that matches the time of day."),
      h("div", { style: "margin-top:16px" },
        fieldWrap("Extra instructions", f.extra, "Written in your own words, any language. Added to the agent's rules."))),
    h("div", { class: "panel" }, h("h2", {}, "Models"),
      h("div", { class: "grid2" },
        fieldWrap("Language model", select("llm_model", LLM_MODELS, a.llm_model)),
        fieldWrap("Voice model", select("tts_model", TTS_MODELS, a.tts_model)))),
    h("div", { class: "panel" }, h("h2", {}, "Voice"),
      h("div", { class: "segmented", role: "group", "aria-label": "Voice provider", style: "margin-bottom:12px" }, provBtns),
      elBox, oaBox),
    h("div", { class: "actions" }, h("button", { class: "btn primary", onclick: save }, "Save changes")),
  );
}

/* ---------- knowledge base ---------- */

async function renderKnowledge() {
  const { text } = await api("GET", "/api/knowledge");
  let saved = text;
  const area = h("textarea", { "aria-label": "Knowledge base", spellcheck: "false" });
  area.value = text;
  const counter = h("span", { class: "counter" });
  const dirty = h("span", { class: "muted" });
  const update = () => {
    const chars = area.value.length;
    const tokens = Math.round(chars / 3);
    counter.textContent = `${chars.toLocaleString()} characters, about ${tokens.toLocaleString()} tokens`;
    counter.classList.toggle("warn", tokens > 20000);
    if (tokens > 20000) counter.textContent += ". Long text slows every reply; search-based retrieval is the next step.";
    dirty.textContent = area.value === saved ? "" : "Unsaved changes";
  };
  area.addEventListener("input", update);
  const save = async () => {
    try { await api("PUT", "/api/knowledge", { text: area.value }); saved = area.value; update(); toast("Saved. Applies to the next call."); }
    catch (e) { fail(e); }
  };
  main().replaceChildren(
    ...pageHeader("Knowledge base",
      "Everything the agent may tell callers: hours, prices, preparation instructions, policies. Plain Markdown, written in Turkish. If it isn't here, the agent takes a message instead of guessing."),
    h("div", { class: "panel" }, h("h2", {}, "Writing it well"),
      h("p", { class: "muted", style: "margin:0" },
        "Write facts, not instructions: one short section per topic, with the answer in the first line. Put numbers, prices and hours exactly as the agent should say them. For anything the agent should never answer, say so under a heading like “Personele yönlendir”. How the agent talks is set in Agent settings, not here.")),
    h("div", { class: "panel editor" }, area,
      h("div", { class: "actions" },
        h("button", { class: "btn primary", onclick: save }, "Save changes"), counter, dirty)),
  );
  update();
}

/* ---------- call history ---------- */

async function renderCalls() {
  const calls = await api("GET", "/api/calls");
  const detail = h("div", { class: "panel", style: "margin:0" }, h("p", { class: "muted" }, "Select a call to read it."));
  const list = h("div", { class: "lat-list", style: "max-height:70vh" });
  const fmt = (iso) => new Date(iso).toLocaleString("tr-TR", { dateStyle: "medium", timeStyle: "short" });

  async function open(id) {
    const events = await api("GET", `/api/calls/${encodeURIComponent(id)}`);
    const blocks = [];
    let pending = {};
    for (const e of events) {
      if (e.kind === "message") {
        blocks.push(h("div", { class: `turn ${e.role === "assistant" ? "agent" : "caller"}` },
          h("small", {}, e.role === "assistant" ? "Agent" : "Caller"), e.text));
      } else if (e.kind === "tool") {
        blocks.push(h("div", { class: "tool" }, h("strong", {}, e.name),
          h("pre", {}, JSON.stringify(e.args)), h("pre", {}, e.result == null ? "(done)" : "→ " + e.result)));
      } else if (e.kind === "latency") {
        pending[e.stage] = e.seconds;
        if (e.stage === "tts") {
          const t = (pending.end_of_turn || 0) + (pending.llm || 0) + (pending.tts || 0);
          blocks.push(h("div", { class: "muted", style: "text-align:right" }, `response ${t.toFixed(2)}s`));
          pending = {};
        }
      } else if (e.kind === "end") {
        blocks.push(h("div", { class: "muted", style: "text-align:center" }, "Call ended"));
      }
    }
    detail.replaceChildren(h("h2", {}, fmt(events[0].t)),
      h("div", { class: "transcript", style: "height:auto;max-height:68vh" }, blocks));
  }

  list.replaceChildren(...(calls.length === 0
    ? [h("p", { class: "muted" }, "No calls yet. Start one from Test call; it will appear here.")]
    : calls.map((c) => h("button", { class: "btn", style: "text-align:left", onclick: () => open(c.id) },
      h("strong", {}, fmt(c.started)), h("div", { class: "muted" },
        `${c.messages} messages. ${c.preview ? "“" + c.preview.slice(0, 60) + "”" : ""}`)))));
  main().replaceChildren(
    ...pageHeader("Call history", "Every voice call, with what was said, what the agent did, and how fast it answered. Use it to find where the agent sounds off."),
    h("div", { class: "console", style: "grid-template-columns:minmax(260px,1fr) minmax(0,2fr)" }, list, detail));
}

/* ---------- appointments ---------- */

async function renderAppointments() {
  const [appts, cfg] = await Promise.all([api("GET", "/api/appointments"), api("GET", "/api/config")]);
  const fmt = (iso) => new Date(iso).toLocaleString("tr-TR", {
    timeZone: cfg.timezone, dateStyle: "full", timeStyle: "short" });
  const rows = appts.map((a) => h("tr", {},
    h("td", {}, fmt(a.start)), h("td", {}, a.patient_name), h("td", {}, a.patient_phone),
    h("td", {}, a.department),
    h("td", {}, h("button", { class: "btn small", onclick: async () => {
      try { await api("POST", `/api/appointments/${a.id}/cancel`); toast("Appointment cancelled."); renderAppointments(); }
      catch (e) { fail(e); }
    } }, "Cancel"))));
  main().replaceChildren(
    ...pageHeader("Appointments", "Everything the agent has booked, from voice and text tests alike."),
    appts.length === 0
      ? h("p", { class: "muted" }, "No appointments yet. Book one from the Test call page.")
      : h("table", {}, h("thead", {}, h("tr", {}, ["When", "Patient", "Phone", "Department", ""].map((t) => h("th", {}, t)))),
        h("tbody", {}, rows)),
  );
}

/* ---------- staff messages ---------- */

async function renderMessages() {
  const msgs = await api("GET", "/api/handoffs");
  main().replaceChildren(
    ...pageHeader("Staff messages", "Things the agent could not resolve. Staff call these callers back."),
    msgs.length === 0
      ? h("p", { class: "muted" }, "Nothing to follow up. When a caller asks something outside the knowledge base, it lands here.")
      : h("div", {}, msgs.map((m) => h("article", { class: "msg" + (m.urgent ? " urgent" : "") },
        h("h3", {}, m.caller_name || "Unknown caller", m.urgent ? h("span", { class: "tag" }, "Urgent") : null),
        h("div", {}, h("strong", {}, m.caller_phone), "  ", new Date(m.created_at).toLocaleString("tr-TR")),
        h("p", {}, m.summary), h("p", { class: "muted" }, "Needs: " + m.unresolved)))),
  );
}

/* ---------- boot ---------- */

window.addEventListener("hashchange", route);
refreshStatus();
setInterval(refreshStatus, 6000);
route();
