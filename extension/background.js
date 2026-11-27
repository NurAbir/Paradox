/* Paradox - background service worker.
 *
 * The content script normally talks to the local server directly. If the page's
 * CORS / private-network rules get in the way, it falls back to this worker,
 * which has host permission for 127.0.0.1 and can fetch without those limits.
 */

const DEFAULTS = {
  enabled: true,
  autoRead: true,
  autoNext: true,
  seamless: true,
  voice: "af_heart",
  speed: 1.0,
  port: 8756,
};

chrome.runtime.onInstalled.addListener(async () => {
  const current = await chrome.storage.sync.get(DEFAULTS);
  await chrome.storage.sync.set({ ...DEFAULTS, ...current });
});

function base(port) {
  return `http://127.0.0.1:${Number(port) || DEFAULTS.port}`;
}

async function health(port) {
  try {
    const res = await fetch(`${base(port)}/health`, { cache: "no-store" });
    if (!res.ok) return { ok: false, error: `HTTP ${res.status}` };
    return await res.json();
  } catch (err) {
    return { ok: false, error: String(err && err.message ? err.message : err) };
  }
}

async function voices(port) {
  try {
    const res = await fetch(`${base(port)}/voices`, { cache: "no-store" });
    if (!res.ok) return { ok: false, error: `HTTP ${res.status}` };
    return await res.json();
  } catch (err) {
    return { ok: false, error: String(err && err.message ? err.message : err) };
  }
}

function toBase64(bytes) {
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

async function synthesize({ text, voice, speed, format, port }) {
  try {
    const res = await fetch(`${base(port)}/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, voice, speed, format: format || "mp3" }),
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      return { ok: false, error: `server ${res.status}: ${detail.slice(0, 300)}` };
    }
    const bytes = new Uint8Array(await res.arrayBuffer());
    return {
      ok: true,
      base64: toBase64(bytes),
      mime: res.headers.get("Content-Type") || "audio/mpeg",
    };
  } catch (err) {
    return { ok: false, error: String(err && err.message ? err.message : err) };
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || typeof message !== "object") return undefined;

  if (message.type === "health") {
    health(message.port).then(sendResponse);
    return true;
  }
  if (message.type === "voices") {
    voices(message.port).then(sendResponse);
    return true;
  }
  if (message.type === "synth") {
    synthesize(message).then(sendResponse);
    return true;
  }
  return undefined;
});