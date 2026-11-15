// Web Reader — all state lives on this device (localStorage).
const store = {
  get(key, fallback) {
    try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; }
    catch { return fallback; }
  },
  set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch {} },
};

const read = new Set(store.get("read", []));
const saved = new Set(store.get("saved", []));
const prevVisit = store.get("lastVisit", null); // posts first seen after this are "New"
let posts = [];
let categories = [];
let filter = "All";
let query = "";

const $ = (id) => document.getElementById(id);

// A bright colour per filter / category
const FIXED = { All: "#4f46e5", Unread: "#ec4899", Saved: "#f59e0b" };
const PALETTE = ["#0ea5e9", "#10b981", "#8b5cf6", "#f97316", "#e11d48", "#14b8a6", "#6366f1", "#d946ef"];
function colorFor(name) {
  if (FIXED[name]) return FIXED[name];
  const i = categories.indexOf(name);
  if (i >= 0) return PALETTE[i % PALETTE.length];
  let h = 0; for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return PALETTE[h % PALETTE.length];
}
const fmtDate = (iso) => iso
  ? new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })
  : "";

function isNew(p) { return prevVisit && p.first_seen > prevVisit && !read.has(p.url); }

function visible() {
  const q = query.trim().toLowerCase();
  return posts.filter((p) => {
    if (filter === "Unread" && read.has(p.url)) return false;
    if (filter === "Saved" && !saved.has(p.url)) return false;
    if (!["All", "Unread", "Saved"].includes(filter) && !(p.categories || []).includes(filter)) return false;
    if (q && !`${p.title} ${p.description || ""} ${(p.categories || []).join(" ")}`.toLowerCase().includes(q)) return false;
    return true;
  });
}

function renderChips() {
  const counts = {
    All: posts.length,
    Unread: posts.filter((p) => !read.has(p.url)).length,
    Saved: posts.filter((p) => saved.has(p.url)).length,
  };
  for (const c of categories) counts[c] = posts.filter((p) => (p.categories || []).includes(c)).length;
  const names = ["All", "Unread", "Saved", ...categories.filter((c) => counts[c] > 0)];
  $("chips").replaceChildren(...names.map((name) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.style.setProperty("--c", colorFor(name));
    b.setAttribute("aria-pressed", String(name === filter));
    b.innerHTML = `${name}<span class="n">${counts[name]}</span>`;
    b.onclick = () => { filter = name; render(); };
    return b;
  }));
}

function renderList() {
  const items = visible();
  if (!items.length) {
    const msg = posts.length
      ? (filter === "Saved" ? "Nothing saved yet — tap ☆ on a post." : "No posts match.")
      : "No posts yet. Run the “Update posts” workflow once on GitHub.";
    $("list").innerHTML = `<p class="empty">${msg}</p>`;
    return;
  }
  const tpl = $("card");
  $("list").replaceChildren(...items.map((p) => {
    const node = tpl.content.firstElementChild.cloneNode(true);
    node.classList.add(read.has(p.url) ? "read" : "unread");
    node.style.setProperty("--c", colorFor((p.categories || [])[0] || "All"));
    if (!isNew(p)) node.querySelector(".badge").remove();
    const a = node.querySelector(".link");
    a.href = p.url;
    a.addEventListener("click", () => markRead(p.url));
    node.querySelector(".date").textContent = fmtDate(p.date);
    node.querySelector(".headline").textContent = p.title;
    node.querySelector(".desc").textContent = p.description || "";
    node.querySelector(".tags").replaceChildren(...(p.categories || []).map((c) => {
      const s = document.createElement("span"); s.textContent = c;
      s.style.setProperty("--tc", colorFor(c)); return s;
    }));
    const star = node.querySelector(".save");
    const paint = () => { star.textContent = saved.has(p.url) ? "★" : "☆"; star.classList.toggle("on", saved.has(p.url)); };
    paint();
    star.onclick = () => {
      saved.has(p.url) ? saved.delete(p.url) : saved.add(p.url);
      store.set("saved", [...saved]);
      paint(); renderChips();
    };
    return node;
  }));
}

function render() { renderChips(); renderList(); }

function markRead(url) {
  read.add(url);
  store.set("read", [...read]);
  setTimeout(render, 300); // after the article opens
}

$("markAll").onclick = () => {
  for (const p of visible()) read.add(p.url);
  store.set("read", [...read]);
  render();
};
$("search").addEventListener("input", (e) => { query = e.target.value; renderList(); });

async function load() {
  try {
    const res = await fetch("data/posts.json", { cache: "no-cache" });
    const data = await res.json();
    posts = data.posts || [];
    categories = data.categories || [];
    const fresh = posts.filter(isNew).length;
    const updated = data.updated ? new Date(data.updated).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "never";
    $("status").textContent = `${posts.length} posts · ${fresh ? fresh + " new · " : ""}checked ${updated}`;
  } catch {
    $("status").textContent = "Offline and nothing cached yet.";
  }
  render();
  store.set("lastVisit", new Date().toISOString());
}

// Refresh when the app comes back to the foreground
document.addEventListener("visibilitychange", () => { if (!document.hidden) load(); });

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
load();
