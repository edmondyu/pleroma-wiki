import json, os, re, shutil
from pathlib import Path
from html import escape

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "entries.json"
TPL = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
DIST = ROOT / "dist"
STATIC = ROOT / "static"

def slugify(title: str) -> str:
    # 保留中文，去掉危險字元，空白改成 -
    s = title.strip()
    s = re.sub(r"[\/\\\?\#\%\:\|\"<>\.]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def linkify(text: str, title_to_url: dict):
    # 依 title 長度由長到短，避免短詞先吃掉
    keys = sorted(title_to_url.keys(), key=len, reverse=True)
    if not keys:
        return escape(text)

    safe = escape(text)

    # 避免在已經有 <a ...> 的地方重複替換（這裡文本本來無 HTML，ok）
    for k in keys:
        url = title_to_url[k]
        # 只替換「純文字中出現的詞」，簡單做法：直接 replace
        safe = safe.replace(escape(k), f'<a href="{url}">{escape(k)}</a>')
    return safe

def render_page(title, sidebar_html, categories_sidebar_html, body_html):
    html = TPL.replace("{{TITLE}}", escape(title))
    html = html.replace("{{SIDEBAR}}", sidebar_html)
    html = html.replace("{{CATEGORIES_SIDEBAR}}", categories_sidebar_html)
    html = html.replace("{{CONTENT}}", body_html)
    return html


def build():
    entries = json.loads(DATA.read_text(encoding="utf-8"))

    # 建 url map
    title_to_slug = {e["title"]: slugify(e["title"]) for e in entries}
    title_to_url = {t: f"/pages/{s}/" for t, s in title_to_slug.items()}

    # sidebar：依字母/中文排序
    entries_sorted = sorted(entries, key=lambda x: x["title"])
    sidebar_items = []
    for e in entries_sorted:
        sidebar_items.append(f'<div class="side-item"><a href="{title_to_url[e["title"]]}">{escape(e["title"])}</a></div>')
    sidebar_html = "\n".join(sidebar_items)

    # 清 dist
    if DIST.exists():
        shutil.rmtree(DIST)
    ensure_dir(DIST)

    # 複製 static 到 dist 根目錄
    for f in STATIC.glob("*"):
        shutil.copy2(f, DIST / f.name)

    # search index
    search_index = []
    for e in entries:
        search_index.append({
            "title": e["title"],
            "title_lc": e["title"].lower(),
            "aliases": e.get("aliases", []),
            "aliases_lc": [a.lower() for a in e.get("aliases", [])],
            "summary": e.get("summary",""),
            "url": title_to_url[e["title"]],
        })
    (DIST / "search-index.json").write_text(json.dumps(search_index, ensure_ascii=False, indent=2), encoding="utf-8")

    # 產生每個詞條頁
    for e in entries:
        slug = title_to_slug[e["title"]]
        out_dir = DIST / "pages" / slug
        ensure_dir(out_dir)

        # 內容組裝
        h1 = f"<h1>{escape(e['title'])}</h1>"
        summary = f"<p class='muted'>{escape(e.get('summary',''))}</p>" if e.get("summary") else ""
        alias = ""
        if e.get("aliases"):
            alias = "<p><strong>別名：</strong> " + ", ".join(escape(a) for a in e["aliases"]) + "</p>"

        paras = []
        for p in e.get("content", []):
            paras.append(f"<p>{linkify(p, title_to_url)}</p>")
        content_html = "\n".join(paras) if paras else "<p class='muted'>（此詞條尚待補完）</p>"

        see = ""
        if e.get("see_also"):
            links = []
            for t in e["see_also"]:
                if t in title_to_url:
                    links.append(f'<a href="{title_to_url[t]}">{escape(t)}</a>')
                else:
                    links.append(escape(t))
            see = "<h2>參見</h2><p>" + " · ".join(links) + "</p>"

        body = "\n".join([h1, summary, alias, "<h2>內容</h2>", content_html, see])
        page = render_page(e["title"], sidebar_html, body)

        (out_dir / "index.html").write_text(page, encoding="utf-8")

    # 首頁 index：列出全部詞條
    home_list = []
    for e in entries_sorted:
        home_list.append(f'<li><a href="{title_to_url[e["title"]]}">{escape(e["title"])}</a> — {escape(e.get("summary",""))}</li>')
    home_body = (
        "<h1>佩洛瑪百科</h1>"
        "<p class='muted'>Wikipedia 風格的世界觀資料庫（靜態站點，可部署至 Netlify）</p>"
        "<h2>詞條列表</h2>"
        "<ul>" + "\n".join(home_list) + "</ul>"
    )
    (DIST / "index.html").write_text(render_page("佩洛瑪百科", sidebar_html, home_body), encoding="utf-8")

    print("Build complete -> dist/")

if __name__ == "__main__":
    build()
