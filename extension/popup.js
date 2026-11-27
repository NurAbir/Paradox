/* Paradox - popup settings */

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

const el = (id) => document.getElementById(id);
const dot = el("dot");
const statusEl = el("status");
const voiceSel = el("voice");
const speedInput = el("speed");
const speedVal = el("speedVal");
const portInput = el("port");

let settings = { ...DEFAULTS };

function base(port) {
  return `http://127.0.0.1:${Number(port) || DEFAULTS.port}`;
}

function setDot(kind) {
  dot.className = `dot ${kind || ""}`;
}

async function loadSettings() {
  try {
    settings = { ...DEFAULTS, ...(await chrome.storage.sync.get(DEFAULTS)) };
  } catch (_) {
    settings = { ...DEFAULTS };
  }
  el("enabled").checked = !!settings.enabled;
  el("autoRead").checked = !!settings.autoRead;
  el("autoNext").checked = !!settings.autoNext;
  el("seamless").checked = !!settings.seamless;
  speedInput.value = settings.speed;
  speedVal.textContent = `${Number(settings.speed).toFixed(1)}x`;
  portInput.value = settings.port;
}

async function loadVoices() {
  let flat = FALLBACK_VOICES;
  try {
    const res = await fetch(`${base(settings.port)}/voices`, { cache: "no-store" });
    if (res.ok) {
      const info = await res.json();
      if (Array.isArray(info.flat) && info.flat.length) flat = info.flat;
    }
  } catch (_) {
    /* offline -> fallback list */
  }
  voiceSel.innerHTML = "";
  for (const name of flat) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    voiceSel.appendChild(opt);
  }
  voiceSel.value = flat.includes(settings.voice) ? settings.voice : flat[0] || "af_heart";
}

async function checkServer() {
  setDot("busy");
  statusEl.textContent = "Checking…";
  try {
    const res = await fetch(`${base(settings.port)}/health`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const info = await res.json();
    if (info.model_ready) {
      setDot("ok");
      statusEl.textContent = `Ready · ${(info.device || "?").toUpperCase()}`;
    } else {
      setDot("busy");
      statusEl.textContent = "Model loading…";
    }
    return info;
  } catch (_) {
    setDot("err");
    statusEl.textContent = "Server offline";
    return null;
  }
}

async function save(patch) {
  Object.assign(settings, patch);
  try {
    await chrome.storage.sync.set(patch);
  } catch (_) {}
}

function wire() {
  el("enabled").addEventListener("change", (e) => save({ enabled: e.target.checked }));
  el("autoRead").addEventListener("change", (e) => save({ autoRead: e.target.checked }));
  el("autoNext").addEventListener("change", (e) => save({ autoNext: e.target.checked }));
  el("seamless").addEventListener("change", (e) => save({ seamless: e.target.checked }));

  voiceSel.addEventListener("change", (e) => save({ voice: e.target.value }));

  speedInput.addEventListener("input", () => {
    speedVal.textContent = `${Number(speedInput.value).toFixed(1)}x`;
  });
  speedInput.addEventListener("change", () => save({ speed: Number(speedInput.value) }));

  portInput.addEventListener("change", async () => {
    const port = Number(portInput.value) || DEFAULTS.port;
    portInput.value = port;
    await save({ port });
    await Promise.all([checkServer(), loadVoices()]);
  });

  el("check").addEventListener("click", async () => {
    await Promise.all([checkServer(), loadVoices()]);
  });
}

(async function init() {
  await loadSettings();
  wire();
  await Promise.all([checkServer(), loadVoices()]);
})();