/* Paradox - content script for novelphoenix.com
 *
 * What it does
 *  - Finds the chapter text (#content) and the Next / Prev chapter links.
 *  - Sends the whole chapter to the local Kokoro server and plays the audio.
 *  - Intercepts Next / Prev clicks and swaps the chapter in place, so audio
 *    keeps playing across chapters without a page reload.
 *  - Adds a small control bar (Shadow DOM, so the site's CSS cannot touch it).
 */

(() => {
  "use strict";

  if (window.top !== window.self) return;                 // main frame only
  if (window.__kokoroReader) return;                       // injected twice?
  window.__kokoroReader = true;

  // ------------------------------------------------------------------ config #
  const DEFAULTS = {
    enabled: true,
    autoRead: true,
    autoNext: true,
    seamless: true,
    voice: "af_heart",
    speed: 1.0,
    port: 8756,
  };

  const FALLBACK_VOICES = [
    "af_heart", "af_bella", "af_nicole", "af_sarah", "af_sky",
    "am_michael", "am_fenrir", "am_puck",
    "bf_emma", "bf_isabella", "bm_george", "bm_fable",
  ];

  const PROMO = [
    /novelphoenix\.com/i,
    /^\s*(read|reading)\s+(the\s+)?(latest|more|full|complete)\b/i,
    /^\s*(support|join)\s+(me|us)\b/i,
    /patreon|ko-?fi|buy me a coffee|discord\.gg/i,
    /^\s*(advertisement|sponsored)\b/i,
  ];

  const state = {
    settings: { ...DEFAULTS },
    server: null,
    info: null,
    audio: null,
    blobUrl: null,
    seq: 0,
    generating: false,
    playing: false,
  };

  let els = {};

  // ------------------------------------------------------------------ utils #
  const $ = (sel, root = document) => root.querySelector(sel);
  const cleanText = (s) =>
    (s || "")
      .replace(/\u00a0/g, " ")
      .replace(/[\t\r]+/g, " ")
      .replace(/[ ]{2,}/g, " ")
      .replace(/[\u200b\u200c\u200d\ufeff]/g, "")
      .trim();

  const fmt = (sec) => {
    if (!isFinite(sec) || sec < 0) sec = 0;
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${String(s).padStart(2, "0")}`;
  };

  const base = () => `http://127.0.0.1:${Number(state.settings.port) || DEFAULTS.port}`;

  function waitFor(fn, timeout = 12000, interval = 250) {
    return new Promise((resolve) => {
      const start = Date.now();
      const tick = () => {
        if (fn()) return resolve(true);
        if (Date.now() - start > timeout) return resolve(false);
        setTimeout(tick, interval);
      };
      tick();
    });
  }

  // -------------------------------------------------------------- extraction #
  // Find a previous/next link, tolerating class changes on the site.
  function navHref(root, dir, pageUrl) {
    const candidates =
      dir === "next"
        ? ['a[data-chapter-nav="next"]', "a.nextchap", "a.chnav.next", 'a[rel="next"]']
        : ['a[data-chapter-nav="prev"]', "a.prevchap", "a.chnav.prev", 'a[rel="prev"]'];

    for (const sel of candidates) {
      const el = root.querySelector ? root.querySelector(sel) : null;
      if (!el) continue;
      if (el.classList && el.classList.contains("isDisabled")) continue;
      const href = el.getAttribute("href");
      if (!href || href.startsWith("javascript")) continue;
      try {
        return new URL(href, pageUrl || location.href).href;
      } catch (_) {
        /* ignore */
      }
    }
    return null;
  }

  function looksLikePromo(line) {
    if (line.length > 180) return false;
    return PROMO.some((re) => re.test(line));
  }

  // Pull clean paragraphs out of a chapter container (live page or fetched HTML).
  function extractChapter(root, pageUrl) {
    const content =
      (root.querySelector && root.querySelector("#content")) ||
      (root.querySelector && root.querySelector("[data-reader-chapter-container]")) ||
      (root.querySelector && root.querySelector("#chapter-container"));
    if (!content) return null;

    const clone = content.cloneNode(true);
    clone
      .querySelectorAll(
        "script,style,noscript,iframe,ins,.nf-ads,[data-chapter-ad],.adsbygoogle," +
          "button,svg,img,figure,video,audio,.box-notice"
      )
      .forEach((n) => n.remove());

    const parts = [];
    const blocks = clone.querySelectorAll("p,h1,h2,h3,h4,h5,blockquote,li");
    if (blocks.length) {
      blocks.forEach((el) => {
        const t = cleanText(el.textContent);
        if (t) parts.push(t);
      });
    } else {
      const html = clone.innerHTML
        .replace(/<br\s*\/?>/gi, "\n")
        .replace(/<\/(div|p|section)>/gi, "\n");
      const tmp = document.createElement("div");
      tmp.innerHTML = html;
      (tmp.textContent || "").split(/\n+/).forEach((line) => {
        const t = cleanText(line);
        if (t) parts.push(t);
      });
    }

    const out = [];
    for (const p of parts) {
      if (!p || looksLikePromo(p)) continue;
      if (out.length && out[out.length - 1] === p) continue;
      out.push(p);
    }

    const titleEl = root.querySelector && root.querySelector(".chapter-title");
    const bookEl =
      (root.querySelector && root.querySelector("a.booktitle")) ||
      (root.querySelector && root.querySelector(".booktitle"));

    return {
      text: out.join("\n\n").trim(),
      title: cleanText(titleEl && titleEl.textContent),
      book: cleanText(bookEl && bookEl.textContent),
      chapterId: content.getAttribute ? content.getAttribute("data-chapter-id") : null,
      url: pageUrl || location.href,
      next: navHref(root, "next", pageUrl),
      prev: navHref(root, "prev", pageUrl),
    };
  }

  // ------------------------------------------------------------------- server #
  function setDot(kind) {
    if (!els.dot) return;
    els.dot.className = `dot ${kind || ""}`;
  }

  function setStatus(text, kind) {
    if (!els.status) return;
    els.status.textContent = text;
    els.status.className = `status ${kind || ""}`;
  }

  function setProgress(ratio) {
    if (!els.fill) return;
    els.fill.style.width = `${Math.max(0, Math.min(1, ratio || 0)) * 100}%`;
  }

  async function checkServer() {
    try {
      const res = await fetch(`${base()}/health`, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const info = await res.json();
      state.server = info;
      if (info.model_ready) {
        setDot("ok");
        return info;
      }
      setDot("busy");
      return info;
    } catch (_) {
      state.server = null;
      setDot("err");
      return null;
    }
  }

  async function loadVoices() {
    let flat = FALLBACK_VOICES;
    try {
      const res = await fetch(`${base()}/voices`, { cache: "no-store" });
      if (res.ok) {
        const info = await res.json();
        if (Array.isArray(info.flat) && info.flat.length) flat = info.flat;
      }
    } catch (_) {
      /* server offline - keep fallback list */
    }
    if (!els.voice) return;
    const current = state.settings.voice;
    els.voice.innerHTML = "";
    for (const name of flat) {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      els.voice.appendChild(opt);
    }
    els.voice.value = flat.includes(current) ? current : flat[0] || "af_heart";
  }

  // ------------------------------------------------------------------- audio #
  // Ask the local server for a whole-chapter MP3; fall back to the worker.
  async function requestTTS(text) {
    const payload = {
      text,
      voice: state.settings.voice,
      speed: Number(state.settings.speed) || 1,
      format: "mp3",
    };

    // Preferred path: talk to the local server directly from the page.
    try {
      const res = await fetch(`${base()}/tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        let detail = "";
        try {
          detail = await res.text();
        } catch (_) {}
        throw new Error(`server ${res.status}${detail ? ": " + detail.slice(0, 160) : ""}`);
      }
      return { blob: await res.blob() };
    } catch (directErr) {
      // Fallback: let the background worker fetch it (no CORS / PNA limits).
      let reply;
      try {
        reply = await chrome.runtime.sendMessage({ type: "synth", ...payload });
      } catch (bgErr) {
        throw new Error(
          /Failed to fetch|NetworkError/i.test(directErr.message)
            ? "Local server is offline - run Start server.bat"
            : directErr.message
        );
      }
      if (!reply || !reply.ok) {
        const msg = (reply && reply.error) || directErr.message || "unknown error";
        throw new Error(
          /Failed to fetch|NetworkError/i.test(msg)
            ? "Local server is offline - run Start server.bat"
            : msg
        );
      }
      const bin = atob(reply.base64);
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      return { blob: new Blob([bytes], { type: reply.mime || "audio/mpeg" }) };
    }
  }

  function stopAudio() {
    if (state.audio) {
      try {
        state.audio.pause();
      } catch (_) {}
      state.audio.src = "";
      state.audio = null;
    }
    if (state.blobUrl) {
      try {
        URL.revokeObjectURL(state.blobUrl);
      } catch (_) {}
      state.blobUrl = null;
    }
    state.playing = false;
    updatePlayButton();
  }

  function updatePlayButton() {
    if (!els.play) return;
    if (state.generating) {
      els.play.textContent = "…";
      els.play.disabled = true;
    } else {
      els.play.disabled = false;
      els.play.textContent = state.playing ? "❚❚" : "▶";
    }
  }

  function updateNav() {
    if (!els.prev || !els.next) return;
    els.prev.disabled = !navHref(document, "prev", location.href);
    els.next.disabled = !navHref(document, "next", location.href);
  }

  function updateProgressFrom(audio) {
    if (!audio || !isFinite(audio.duration) || audio.duration <= 0) return;
    setProgress(audio.currentTime / audio.duration);
    if (state.playing) {
      const title = state.info && state.info.title ? ` · ${state.info.title}` : "";
      setStatus(`${fmt(audio.currentTime)} / ${fmt(audio.duration)}${title}`, "ok");
    }
  }

  async function playAudio() {
    if (!state.audio) return;
    try {
      await state.audio.play();
      state.playing = true;
      updatePlayButton();
    } catch (err) {
      state.playing = false;
      updatePlayButton();
      if (err && err.name === "NotAllowedError") {
        setStatus("Press ▶ to start (browser blocked autoplay)", "warn");
      } else {
        setStatus(`Play failed: ${err.message}`, "error");
      }
    }
  }

  function togglePlay() {
    if (state.generating) return;
    if (!state.audio) {
      startReading();
      return;
    }
    if (state.audio.paused) {
      playAudio();
    } else {
      state.audio.pause();
      state.playing = false;
      updatePlayButton();
      setStatus("Paused.", "");
    }
  }

  async function onAudioEnded() {
    state.playing = false;
    updatePlayButton();
    setProgress(1);
    const next = navHref(document, "next", location.href);
    if (state.settings.autoNext && next) {
      setStatus("Chapter finished - loading next…", "busy");
      await goTo(next);
    } else {
      setStatus("Chapter finished.", "ok");
    }
  }

  // -------------------------------------------------------------- reading flow #
  // Extract the current chapter, synthesize it, and begin playback.
  async function startReading({ autoplay = true } = {}) {
    if (!state.settings.enabled) {
      setStatus("Reader is off - enable it in the settings.", "");
      return;
    }

    const info = extractChapter(document, location.href);
    updateNav();
    if (!info) {
      setStatus("Open a chapter page to listen.", "");
      return;
    }
    if (!info.text || info.text.length < 30) {
      setStatus("Could not find chapter text on this page.", "error");
      return;
    }

    state.info = info;
    const mySeq = ++state.seq;
    stopAudio();
    state.generating = true;
    updatePlayButton();
    setProgress(0);

    const words = info.text.split(/\s+/).length;
    setStatus(`Generating ${words.toLocaleString()} words…`, "busy");
    setDot("busy");

    try {
      const { blob } = await requestTTS(info.text);
      if (mySeq !== state.seq) return;

      state.generating = false;
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.preload = "auto";
      state.audio = audio;
      state.blobUrl = url;

      audio.addEventListener("timeupdate", () => updateProgressFrom(audio));
      audio.addEventListener("loadedmetadata", () => updateProgressFrom(audio));
      audio.addEventListener("ended", onAudioEnded);
      audio.addEventListener("error", () => setStatus("Audio playback error.", "error"));

      setDot("ok");
      updatePlayButton();
      setStatus(`Ready: ${info.title || "chapter"}`, "ok");
      if (autoplay) await playAudio();
    } catch (err) {
      if (mySeq !== state.seq) return;
      state.generating = false;
      updatePlayButton();
      setDot("err");
      setStatus(`TTS failed: ${err.message}`, "error");
    }
  }

  // Load a chapter in place when possible, otherwise fall back to navigation.
  async function goTo(url, { push = true } = {}) {
    if (!url) return;
    let target;
    try {
      target = new URL(url, location.href).href;
    } catch (_) {
      return;
    }

    setStatus("Loading chapter…", "busy");
    try {
      const res = await fetch(target, { credentials: "include" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const html = await res.text();
      const doc = new DOMParser().parseFromString(html, "text/html");

      const newContent = doc.querySelector("#content");
      const liveContent = document.querySelector("#content");

      if (state.settings.seamless && newContent && liveContent) {
        stopAudio();

        // Copy only the chapter body: no ads, iframes or scripts.
        const fresh = newContent.cloneNode(true);
        fresh
          .querySelectorAll(
            "[data-chapter-ad],.nf-ads,iframe,ins,.adsbygoogle,script,style,.box-notice"
          )
          .forEach((n) => n.remove());
        liveContent.innerHTML = fresh.innerHTML;
        const newId = newContent.getAttribute("data-chapter-id");
        if (newId) liveContent.setAttribute("data-chapter-id", newId);

        const newTitle = doc.querySelector(".chapter-title");
        const liveTitle = document.querySelector(".chapter-title");
        if (newTitle && liveTitle) liveTitle.textContent = newTitle.textContent;
        if (doc.title) document.title = doc.title;

        for (const dir of ["prev", "next"]) {
          const fresh = doc.querySelector(`[data-chapter-nav="${dir}"]`);
          const live = document.querySelector(`[data-chapter-nav="${dir}"]`);
          if (fresh && live) {
            live.setAttribute("href", fresh.getAttribute("href"));
            live.classList.toggle("isDisabled", fresh.classList.contains("isDisabled"));
          }
        }

        try {
          if (push) history.pushState({ kokoro: true }, "", target);
        } catch (_) {}
        state.info = null;
        window.scrollTo({ top: 0, behavior: "smooth" });
        await new Promise((r) => setTimeout(r, 60));
        await startReading();
        return;
      }

      // No #content (or seamless off): normal full navigation.
      location.assign(target);
    } catch (err) {
      setStatus(`Could not load chapter (${err.message}) - reloading…`, "error");
      location.assign(target);
    }
  }

  // --------------------------------------------------------------------- UI #
  const UI_CSS = `
    :host { all: initial; }
    * { box-sizing: border-box; }
    .panel {
      position: fixed; right: 18px; bottom: 18px; z-index: 2147483647;
      width: min(94vw, 430px); font-family: "Segoe UI", system-ui, sans-serif;
      background: rgba(22, 22, 32, .96); color: #eef0ff;
      border: 1px solid rgba(124, 108, 255, .45); border-radius: 14px;
      box-shadow: 0 12px 40px rgba(0,0,0,.45); backdrop-filter: blur(8px);
      overflow: hidden; font-size: 13px; line-height: 1.35;
    }
    .bar { display: flex; align-items: center; gap: 8px; padding: 9px 10px 8px; }
    .dot { width: 9px; height: 9px; border-radius: 50%; background: #8b8ba7; flex: 0 0 auto; }
    .dot.ok { background: #35d07f; box-shadow: 0 0 8px rgba(53,208,127,.7); }
    .dot.busy { background: #f5b642; box-shadow: 0 0 8px rgba(245,182,66,.7); animation: pulse 1s infinite; }
    .dot.err { background: #ff5d6c; box-shadow: 0 0 8px rgba(255,93,108,.7); }
    @keyframes pulse { 50% { opacity: .35; } }
    .brand { font-weight: 700; letter-spacing: .2px; color: #c9c2ff; flex: 0 0 auto; }
    .status {
      flex: 1 1 auto; min-width: 0; color: #c7c9dd;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .status.ok { color: #cfe9da; }
    .status.warn { color: #ffd27a; }
    .status.error { color: #ff9aa3; }
    .status.busy { color: #d8d2ff; }
    .btns { display: flex; align-items: center; gap: 2px; flex: 0 0 auto; }
    button {
      font: inherit; color: inherit; background: rgba(255,255,255,.06);
      border: 1px solid rgba(255,255,255,.08); border-radius: 9px;
      min-width: 30px; height: 30px; padding: 0 8px; cursor: pointer;
      transition: background .15s, transform .05s;
    }
    button:hover:not(:disabled) { background: rgba(124,108,255,.35); }
    button:active:not(:disabled) { transform: scale(.95); }
    button:disabled { opacity: .35; cursor: default; }
    .progress { height: 3px; background: rgba(255,255,255,.07); }
    .fill { height: 100%; width: 0; background: linear-gradient(90deg,#7c6cff,#b39dff); transition: width .2s; }
    .settings { padding: 10px 12px 12px; border-top: 1px solid rgba(255,255,255,.07); display: grid; gap: 8px; }
    .settings.hidden { display: none; }
    .row { display: flex; align-items: center; gap: 8px; color: #d6d8ea; }
    .row > span { flex: 0 0 54px; color: #a9accc; }
    .row input[type="checkbox"] { width: 15px; height: 15px; accent-color: #7c6cff; }
    .row select, .row input[type="number"] {
      font: inherit; color: #eef0ff; background: #26263a;
      border: 1px solid rgba(255,255,255,.12); border-radius: 8px; padding: 4px 6px; flex: 1 1 auto; min-width: 0;
    }
    .row input[type="range"] { flex: 1 1 auto; accent-color: #7c6cff; }
    .speedval { flex: 0 0 42px; text-align: right; color: #c9c2ff; font-variant-numeric: tabular-nums; }
    .hint { color: #8f92b3; font-size: 11.5px; line-height: 1.4; }
    .hint b { color: #c9c2ff; }
    .row button { height: 26px; min-width: 0; padding: 0 10px; }
  `;

  function buildUI() {
    const host = document.createElement("div");
    host.id = "kokoro-reader-host";
    host.style.cssText =
      "position:fixed;right:0;bottom:0;width:0;height:0;z-index:2147483647;";
    document.documentElement.appendChild(host);
    const shadow = host.attachShadow({ mode: "open" });

    const style = document.createElement("style");
    style.textContent = UI_CSS;

    const panel = document.createElement("div");
    panel.className = "panel";
    panel.innerHTML = `
      <div class="bar">
        <span class="dot"></span>
        <span class="brand">Paradox</span>
        <span class="status">Starting…</span>
        <div class="btns">
          <button data-act="prev" title="Previous chapter">⏮</button>
          <button data-act="play" title="Play / Pause">▶</button>
          <button data-act="stop" title="Stop">■</button>
          <button data-act="next" title="Next chapter">⏭</button>
          <button data-act="gear" title="Settings">⚙</button>
        </div>
      </div>
      <div class="progress"><div class="fill"></div></div>
      <div class="settings hidden">
        <label class="row"><input type="checkbox" data-set="enabled"> Enabled</label>
        <label class="row"><input type="checkbox" data-set="autoRead"> Read when a chapter opens</label>
        <label class="row"><input type="checkbox" data-set="autoNext"> Continue to the next chapter</label>
        <label class="row"><input type="checkbox" data-set="seamless"> Switch chapters without reloading</label>
        <label class="row"><span>Voice</span><select data-set="voice"></select></label>
        <label class="row"><span>Speed</span><input type="range" min="0.5" max="2" step="0.05" data-set="speed"><b class="speedval">1.0x</b></label>
        <div class="row"><span>Server</span><input type="number" min="1" max="65535" data-set="port"><button data-act="check">Check</button></div>
        <div class="hint">Audio comes from the local Paradox server. If it is offline, run <b>Start server.bat</b> in the Paradox folder.</div>
      </div>
    `;

    shadow.append(style, panel);

    els = {
      host,
      shadow,
      panel,
      dot: shadow.querySelector(".dot"),
      status: shadow.querySelector(".status"),
      fill: shadow.querySelector(".fill"),
      settings: shadow.querySelector(".settings"),
      prev: shadow.querySelector('[data-act="prev"]'),
      play: shadow.querySelector('[data-act="play"]'),
      stop: shadow.querySelector('[data-act="stop"]'),
      next: shadow.querySelector('[data-act="next"]'),
      gear: shadow.querySelector('[data-act="gear"]'),
      check: shadow.querySelector('[data-act="check"]'),
      voice: shadow.querySelector('[data-set="voice"]'),
      speedval: shadow.querySelector(".speedval"),
    };

    els.play.addEventListener("click", togglePlay);
    els.stop.addEventListener("click", () => {
      stopAudio();
      setProgress(0);
      setStatus("Stopped.", "");
    });
    els.prev.addEventListener("click", () => {
      const url = navHref(document, "prev", location.href);
      if (url) goTo(url);
    });
    els.next.addEventListener("click", () => {
      const url = navHref(document, "next", location.href);
      if (url) goTo(url);
    });
    els.gear.addEventListener("click", () => els.settings.classList.toggle("hidden"));
    els.check.addEventListener("click", async () => {
      setStatus("Checking server…", "busy");
      const info = await checkServer();
      if (info && info.model_ready) {
        setStatus(`Server ready (${(info.device || "?").toUpperCase()})`, "ok");
        loadVoices();
      } else if (info) {
        setStatus("Server reachable, model still loading…", "warn");
      } else {
        setStatus("Server offline - run Start server.bat", "error");
      }
    });

    panel.addEventListener("keydown", (e) => e.stopPropagation());
    panel.addEventListener("keypress", (e) => e.stopPropagation());
  }

  // --------------------------------------------------------------- settings #
  function applySettingsToUI() {
    if (!els.settings) return;
    const s = state.settings;
    els.settings.querySelectorAll("[data-set]").forEach((input) => {
      const key = input.dataset.set;
      if (input.type === "checkbox") input.checked = !!s[key];
      else if (key === "speed") {
        input.value = s[key];
        if (els.speedval) els.speedval.textContent = `${Number(s[key]).toFixed(1)}x`;
      } else if (key === "voice") {
        input.value = s[key];
      } else {
        input.value = s[key];
      }
    });
  }

  function applySideEffect(key, value) {
    if (key === "enabled") {
      if (value) {
        checkServer();
        startReading();
      } else {
        stopAudio();
        setStatus("Reader off.", "");
      }
    }
    if (key === "port") {
      checkServer();
      loadVoices();
    }
  }

  async function saveSetting(key, value) {
    state.settings[key] = value;
    try {
      await chrome.storage.sync.set({ [key]: value });
    } catch (_) {
      // If sync is unavailable, still apply the change to this page.
      applySideEffect(key, value);
    }
  }

  function bindSettings() {
    els.settings.querySelectorAll("[data-set]").forEach((input) => {
      const handler = () => {
        const key = input.dataset.set;
        let value;
        if (input.type === "checkbox") value = input.checked;
        else if (input.type === "range" || input.type === "number") value = Number(input.value);
        else value = input.value;
        if (key === "speed" && els.speedval) {
          els.speedval.textContent = `${Number(value).toFixed(1)}x`;
        }
        saveSetting(key, value);
      };
      input.addEventListener("change", handler);
      if (input.type === "range") {
        input.addEventListener("input", () => {
          els.speedval.textContent = `${Number(input.value).toFixed(1)}x`;
        });
      }
    });
  }

  async function loadSettings() {
    try {
      state.settings = { ...DEFAULTS, ...(await chrome.storage.sync.get(DEFAULTS)) };
    } catch (_) {
      state.settings = { ...DEFAULTS };
    }
  }

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "sync") return;
    let touched = false;
    for (const key of Object.keys(changes)) {
      if (key in DEFAULTS) {
        state.settings[key] = changes[key].newValue;
        touched = true;
        applySideEffect(key, changes[key].newValue);
      }
    }
    if (touched) applySettingsToUI();
  });

  // ---------------------------------------------------------- chapter clicks #
  document.addEventListener(
    "click",
    (event) => {
      if (!state.settings.enabled || !state.settings.seamless) return;
      const link = event.target.closest ? event.target.closest("a") : null;
      if (!link) return;
      const href = link.getAttribute("href") || "";
      if (!href || href.startsWith("javascript")) return;
      const isNav = link.matches(
        '[data-chapter-nav="next"],[data-chapter-nav="prev"],.nextchap,.prevchap,.chnav.next,.chnav.prev'
      );
      if (!isNav) return;
      try {
        if (!/\/novel\/.+\/chapter/i.test(new URL(href, location.href).pathname)) return;
      } catch (_) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      goTo(href);
    },
    true
  );

  window.addEventListener("popstate", () => {
    if (state.settings.enabled && state.settings.seamless) {
      goTo(location.href, { push: false });
    }
  });

  window.addEventListener("beforeunload", () => {
    try {
      stopAudio();
    } catch (_) {}
  });

  // ------------------------------------------------------------------- boot #
  async function boot() {
    await loadSettings();
    buildUI();
    applySettingsToUI();
    bindSettings();

    checkServer().then((info) => {
      if (info && info.model_ready) {
        setStatus(`Ready (${(info.device || "?").toUpperCase()}) - press ▶ or open a chapter`, "ok");
      } else if (info) {
        setStatus("Server up, model loading…", "busy");
      } else {
        setStatus("Server offline - run Start server.bat", "error");
      }
    });
    loadVoices();

    const isChapterUrl = /\/novel\/.+\/chapter/i.test(location.pathname);
    const found = await waitFor(
      () => document.querySelector("#content"),
      isChapterUrl ? 12000 : 2500
    );
    updateNav();

    if (!found) {
      setStatus("Open a chapter page to listen.", "");
      return;
    }

    if (state.settings.enabled && state.settings.autoRead) {
      startReading();
    } else if (state.settings.enabled) {
      setStatus("Press ▶ to listen to this chapter.", "");
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();