const FIELDS = ["address", "rent", "bedrooms", "bathrooms", "size", "lat", "lon"];
const $ = (id) => document.getElementById(id);

// Restore saved config.
chrome.storage.local.get(["apiBase", "profileId"], (cfg) => {
  $("apiBase").value = cfg.apiBase || "http://localhost:8000";
  $("profileId").value = cfg.profileId || "demo-seattle";
});
["apiBase", "profileId"].forEach((k) =>
  $(k).addEventListener("change", () => chrome.storage.local.set({ [k]: $(k).value })));

function fill(data) {
  FIELDS.forEach((f) => { if (data[f] != null) $(f).value = data[f]; });
}

async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

$("extract").addEventListener("click", async () => {
  setStatus("Extracting…");
  try {
    const tab = await activeTab();
    // parse.js first (defines window.AFParse), then the orchestrator.
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["parse.js", "extract.js"],
    });
    const res = results[results.length - 1];
    if (res && res.result) {
      fill(res.result);
      const any = FIELDS.some((f) => res.result[f] != null);
      const via = res.result.adapter ? ` (via ${res.result.adapter} adapter)` : "";
      setStatus(any ? `Extracted${via}. Review and edit before sending.` : `Nothing detected${via} — enter fields manually.`, any ? "ok" : "err");
    } else {
      setStatus("Extraction failed — enter fields manually.", "err");
    }
  } catch (e) {
    setStatus("Cannot access this page. Enter fields manually.", "err");
  }
});

$("send").addEventListener("click", async () => {
  const base = $("apiBase").value.replace(/\/$/, "");
  const pid = $("profileId").value;
  if (!pid) return setStatus("Set a Profile ID first.", "err");
  const tab = await activeTab();
  const body = { source: "extension", source_url: tab?.url };
  FIELDS.forEach((f) => { if ($(f).value !== "") body[f] = $(f).value; });
  setStatus("Sending…");
  try {
    const r = await fetch(`${base}/api/profiles/${pid}/listings/extension`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(await r.text());
    const saved = await r.json();
    setStatus(`Sent ✓ (listing ${saved.id})`, "ok");
  } catch (e) {
    setStatus("Send failed: " + e.message, "err");
  }
});

function setStatus(msg, cls) {
  const el = $("status");
  el.textContent = msg;
  el.className = cls || "";
}
