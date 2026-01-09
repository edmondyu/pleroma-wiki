async function loadIndex() {
  const res = await fetch("/search-index.json");
  return await res.json();
}

function escapeHtml(s) {
  return s.replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;");
}

(async function initSearch(){
  const box = document.getElementById("searchBox");
  const results = document.getElementById("searchResults");
  if (!box || !results) return;

  const index = await loadIndex();

  function render(list) {
    if (!list.length) { results.style.display = "none"; results.innerHTML = ""; return; }
    results.innerHTML = list.slice(0, 12).map(it =>
      `<a href="${it.url}"><strong>${escapeHtml(it.title)}</strong><div class="muted">${escapeHtml(it.summary || "")}</div></a>`
    ).join("");
    results.style.display = "block";
  }

  box.addEventListener("input", () => {
    const q = box.value.trim().toLowerCase();
    if (!q) { render([]); return; }
    const hits = index.filter(it =>
      it.title_lc.includes(q) || (it.aliases_lc && it.aliases_lc.some(a => a.includes(q)))
    );
    render(hits);
  });

  document.addEventListener("click", (e) => {
    if (!results.contains(e.target) && e.target !== box) {
      results.style.display = "none";
    }
  });
})();
