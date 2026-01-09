import json, os, re, shutil
from pathlib import Path
from html import escape
from collections import defaultdict

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
    keys = sorted(title_to_url.keys(), key=len, reverse=True)
    if not keys:
        return escape(text)

    safe = escape(text)
    for k in keys:
        url = title_to_url[k]
        safe = safe.replace(escape(k), f'<a href="{url}">{escape(k)}</a>')
    return safe

def render_page(title, sidebar_html, categories_sidebar_html, body_html):
    html = TPL.replace("{{TITLE}}", escape(title))
    # 兼容兩種模板：若模板只有 {{SIDEBAR}}，我們也會把分類塞到 sidebar_html
    html = html.replace("{{SIDEBAR}}", sidebar_html)
    html = html.replace("{{CATEGORIES_SIDEBAR}}", categories_sidebar_html)
    html = html.replace("{{CONTENT}}", body_html)
    return html

def build():
    entries = json.loads(DATA.read_text(encoding="utf-8"))

    # URL map
    title_to_slug = {e["title"]: slugify(e["title"]) for e in entries}
    title_to_url = {t: f"/pages/{s}/" for t, s in title_to_slug.items()}

    # --- Categories ---
    # categories 欄位：允許字串（單一分類）或陣列（多分類）
    cat_to_titles = defaultdict(list)
    for e in entries:
        cats = e.get("categories") or "未分類"
        if isinstance(cats, str):
            cats = [cats]
        cats = [str(c).strip() for c in cats if c and str(c).strip()]
        if not cats:
            cats = ["未分類"]
        for c in cats:
            cat_to_titles[c].append(e["title"])

    categories_sorted = sorted(cat_to_titles.keys())
    for c in categories_sorted:
        cat_to_titles[c] = sorted(cat_to_titles[c])

    cat_to_url = {c: f"/categories/{slugify(c)}/" for c in categories_sorted}

    categories_sidebar_html = "\n".join(
        f'<div class="side-item"><a href="{cat_to_url[c]}">{escape(c)}</a> '
        f'<span class="muted">({len(cat_to_titles[c])})</span></div>'
        for c in categories_sorted
    )

    # Sidebar：只顯示分類
    # 若你的模板只使用 {{SIDEBAR}}，也能顯示分類；若用 {{CATEGORIES_SIDEBAR}}，則 {{SIDEBAR}} 會是空的
    sidebar_html = ""

    # 清 dist
    if DIST.exists():
        shutil.rmtree(DIST)
    ensure_dir(DIST)

    # copy static
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
    (DIST / "search-index.json").write_text(
        json.dumps(search_index, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # 詞條頁
    for e in entries:
        slug = title_to_slug[e["title"]]
        out_dir = DIST / "pages" / slug
        ensure_dir(out_dir)

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

        # 單一分類顯示（你已要求每條只屬於一個分類）
        cat = e.get("categories") or "未分類"
        if isinstance(cat, list):
            cat = cat[0] if cat else "未分類"
        cat = str(cat).strip() or "未分類"
        cat_link = f'<a href="{cat_to_url.get(cat, "/categories/")}">{escape(cat)}</a>'
        cat_block = "<h2>分類</h2><p>" + cat_link + "</p>"

        body = "\n".join([h1, summary, alias, "<h2>內容</h2>", content_html, see, cat_block])
        page = render_page(e["title"], sidebar_html, categories_sidebar_html, body)
        (out_dir / "index.html").write_text(page, encoding="utf-8")

    # 分類頁
    cat_root = DIST / "categories"
    ensure_dir(cat_root)

    cat_list_items = []
    for c in categories_sorted:
        cat_list_items.append(
            f'<li><a href="{cat_to_url[c]}">{escape(c)}</a> — '
            f'<span class="muted">{len(cat_to_titles[c])} 條</span></li>'
        )

    cat_index_body = (
        "<h1>分類</h1>"
        "<p class='muted'>按分類瀏覽詞條。</p>"
        "<ul>" + "\n".join(cat_list_items) + "</ul>"
    )
    (cat_root / "index.html").write_text(
        render_page("分類", sidebar_html, categories_sidebar_html, cat_index_body),
        encoding="utf-8"
    )

    for c in categories_sorted:
        out_dir = cat_root / slugify(c)
        ensure_dir(out_dir)

        # Special formatting for 人物：先列出偶像團體成員並按團體分組
        if c == "人物":
            def is_group_member(text: str, group: str) -> bool:
                # 盡量避免把「經理人/負責」等角色誤判為成員
                # 需要同時出現團體名與「成員」字樣（相距不遠）
                return re.search(rf"{group}.{{0,12}}成員|{group}.{{0,12}}團成員|{group}.{{0,12}}女團成員|{group}.{{0,12}}男團成員", text) is not None

            # 建立 title -> entry text 快取
            title_to_text = {}
            for e in entries:
                if e.get("title") in cat_to_titles[c]:
                    title_to_text[e["title"]] = " ".join([e.get("summary","")] + (e.get("content") or []))

            groups = ["Virgo", "Virtus"]
            grouped = {g: [] for g in groups}
            others = []

            for t in cat_to_titles[c]:
                txt = title_to_text.get(t, "")
                placed = False
                for g in groups:
                    if is_group_member(txt, g):
                        grouped[g].append(t)
                        placed = True
                        break
                if not placed:
                    others.append(t)

            # sort within groups
            for g in groups:
                grouped[g] = sorted(grouped[g])
            others = sorted(others)

            parts = [f"<h1>分類：{escape(c)}</h1>",
                     f"<p class='muted'>共 {len(cat_to_titles[c])} 條</p>"]

            # group sections
            for g in groups:
                if grouped[g]:
                    parts.append(f"<h2>{escape(g)}</h2>")
                    parts.append("<ul>" + "
".join(
                        f'<li><a href="{title_to_url[t]}">{escape(t)}</a></li>' for t in grouped[g]
                    ) + "</ul>")

            if others:
                parts.append("<h2>其他人物</h2>")
                parts.append("<ul>" + "
".join(
                    f'<li><a href="{title_to_url[t]}">{escape(t)}</a></li>' for t in others
                ) + "</ul>")

            body = "
".join(parts)

        else:
            items = []
            for t in cat_to_titles[c]:
                items.append(f'<li><a href="{title_to_url[t]}">{escape(t)}</a></li>')

            body = (
                f"<h1>分類：{escape(c)}</h1>"
                f"<p class='muted'>共 {len(cat_to_titles[c])} 條</p>"
                "<h2>詞條</h2>"
                "<ul>" + "
".join(items) + "</ul>"
            )

        (out_dir / "index.html").write_text(
            render_page(f"分類：{c}", sidebar_html, categories_sidebar_html, body),
            encoding="utf-8"
        )
    # 首頁
    home_list = []
    entries_sorted = sorted(entries, key=lambda x: x["title"])
    for e in entries_sorted:
        home_list.append(
            f'<li><a href="{title_to_url[e["title"]]}">{escape(e["title"])}</a> — {escape(e.get("summary",""))}</li>'
        )

    home_body = (
        "<h1>佩洛瑪百科</h1>"
        "<p class='muted'>Wikipedia 風格的世界觀資料庫（靜態站點，可部署至 Netlify）</p>"
        "<p><a href='/categories/'>→ 瀏覽分類</a></p>"
        "<h2>詞條列表</h2>"
        "<ul>" + "\n".join(home_list) + "</ul>"
    )

    (DIST / "index.html").write_text(
        render_page("佩洛瑪百科", sidebar_html, categories_sidebar_html, home_body),
        encoding="utf-8"
    )

    print("Build complete -> dist/")

if __name__ == "__main__":
    build()
