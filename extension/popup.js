const FIELDS = ["address", "rent", "bedrooms", "bathrooms", "size", "lat", "lon"];
const $ = (id) => document.getElementById(id);
let autoFields = new Set(); // fields the extractor filled

// Restore saved config.
chrome.storage.local.get(["apiBase", "profileId"], (cfg) => {
  $("apiBase").value = cfg.apiBase || "http://localhost:8000";
  $("profileId").value = cfg.profileId || "demo-seattle";
});
["apiBase", "profileId"].forEach((k) =>
  $(k).addEventListener("change", () => chrome.storage.local.set({ [k]: $(k).value })));

// Mark a field as user-edited (manual) when its value diverges from auto.
FIELDS.forEach((f) => {
  $(f).addEventListener("input", () => { autoFields.delete(f); paintBadges(); });
});

function paintBadges() {
  let filled = 0;
  FIELDS.forEach((f) => {
    const el = $(f);
    const badge = $("b-" + f);
    const hasVal = el.value !== "";
    if (hasVal) filled++;
    el.classList.remove("auto", "edited");
    if (autoFields.has(f)) { badge.textContent = "auto"; badge.className = "badge auto"; el.classList.add("auto"); }
    else if (hasVal) { badge.textContent = "manual"; badge.className = "badge manual"; el.classList.add("edited"); }
    else { badge.textContent = ""; badge.className = "badge"; }
  });
  const pct = Math.round((filled / FIELDS.length) * 100);
  $("barfill").style.width = pct + "%";
  return filled;
}

function fill(data) {
  autoFields = new Set(data._auto || []);
  FIELDS.forEach((f) => { if (data[f] != null) $(f).value = data[f]; });
  paintBadges();
}

async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

$("extract").addEventListener("click", async () => {
  setStatus("Extracting…");
  try {
    const tab = await activeTab();
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["parse.js", "extract.js"],
    });
    const res = results[results.length - 1];
    if (res && res.result) {
      fill(res.result);
      const r = res.result;
      const via = r.adapter ? r.adapter : "generic";
      const conf = Math.round((r._confidence || 0) * 100);
      $("meta").textContent = `Adapter: ${via} · auto-filled ${(r._auto || []).length}/${FIELDS.length} fields · confidence ${conf}%`;
      const any = (r._auto || []).length > 0;
      setStatus(any ? "Review the highlighted fields, edit as needed, then send." : "Nothing auto-detected — enter fields manually.", any ? "ok" : "err");
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
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
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
