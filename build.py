import json, re, shutil
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
    """Replace entry titles with hyperlinks in plain text.

    Single-pass implementation to avoid nested <a> tags when one title is a
    substring of another (e.g. 胡亞尼 vs 胡亞尼（作者）).
    """
    keys = sorted(title_to_url.keys(), key=len, reverse=True)
    if not keys:
        return escape(text)

    pattern = re.compile("|".join(re.escape(k) for k in keys))

    out = []
    last = 0
    for m in pattern.finditer(text):
        out.append(escape(text[last:m.start()]))
        k = m.group(0)
        url = title_to_url.get(k)
        if url:
            out.append(f'<a href="{url}">{escape(k)}</a>')
        else:
            out.append(escape(k))
        last = m.end()

    out.append(escape(text[last:]))
    return "".join(out)


def render_page(title, sidebar_html, categories_sidebar_html, body_html):
    html = TPL.replace("{{TITLE}}", escape(title))
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

        # Custom category order (manual priority)
    CATEGORY_ORDER = [
        "創作背景",
        "人物",
        "團體",
        "精靈系統",
        "制度與舞台",
        "代幣經濟",
        "地點",
        "宗教與教派",
        "時間",
        "概念",
        "科技",
        "組織與勢力",
        "職業與角色",
        "能力與技術",
        "事件",
    ]
    order = {name: i for i, name in enumerate(CATEGORY_ORDER)}

    categories_sorted = sorted(cat_to_titles.keys(), key=lambda c: (order.get(c, 999), c))
    for c in categories_sorted:
        cat_to_titles[c] = sorted(cat_to_titles[c])

    cat_to_url = {c: f"/categories/{slugify(c)}/" for c in categories_sorted}

    categories_sidebar_html = "\n".join(
        f'<div class="side-item"><a href="{cat_to_url[c]}">{escape(c)}</a> '
        f'<span class="muted">({len(cat_to_titles[c])})</span></div>'
        for c in categories_sorted
    )

    # 右邊 sidebar：只顯示分類
    sidebar_html = ""

    # Clean dist
    if DIST.exists():
        shutil.rmtree(DIST)
    ensure_dir(DIST)
    # Copy static (recursive; supports subfolders like static/images/)
    if STATIC.exists():
        for p in STATIC.rglob("*"):
            rel = p.relative_to(STATIC)
            dest = DIST / rel
            if p.is_dir():
                ensure_dir(dest)
            else:
                ensure_dir(dest.parent)
                shutil.copy2(p, dest)

    # Search index
    search_index = []
    for e in entries:
        search_index.append({
            "title": e["title"],
            "title_lc": e["title"].lower(),
            "aliases": e.get("aliases", []),
            "aliases_lc": [a.lower() for a in e.get("aliases", [])],
            "summary": e.get("summary", ""),
            "url": title_to_url[e["title"]],
        })
    (DIST / "search-index.json").write_text(
        json.dumps(search_index, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # Entry pages
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
            p = (p or "").strip()
            if not p:
                continue
            if p.startswith("<"):
                # raw HTML block (e.g. infobox image)
                paras.append(p)
            else:
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

        cat = e.get("categories") or "未分類"
        if isinstance(cat, list):
            cat = cat[0] if cat else "未分類"
        cat = str(cat).strip() or "未分類"
        cat_link = f'<a href="{cat_to_url.get(cat, "/categories/")}">{escape(cat)}</a>'
        cat_block = "<h2>分類</h2><p>" + cat_link + "</p>"

        body = "\n".join([h1, summary, alias, "<h2>內容</h2>", content_html, see, cat_block])
        page = render_page(e["title"], sidebar_html, categories_sidebar_html, body)
        (out_dir / "index.html").write_text(page, encoding="utf-8")

    # Category pages
    cat_root = DIST / "categories"
    ensure_dir(cat_root)

    # categories index
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

    # 人物：偶像團體成員名單
    # 來源優先：從「Virgo」「Virtus」詞條內文解析「由A、B、C...和D組成」的名單；若解析失敗才回退到硬編碼。
    def parse_group_members(group_title: str):
        e = next((x for x in entries if x.get("title") == group_title), None)
        if not e:
            return None
        text = " ".join([e.get("summary","")] + (e.get("content") or []))
        m = re.search(r"由(.+?)組成", text)
        if not m:
            return None
        names_blob = m.group(1)
        # 統一分隔符：、 和 及
        names_blob = names_blob.replace("及", "、").replace("和", "、")
        # 去掉空白
        parts = [p.strip() for p in names_blob.split("、") if p.strip()]
        # 過濾掉明顯不是人名的詞（非常保守）
        parts = [p for p in parts if len(p) <= 6]
        return parts or None

    idol_groups = {}
    for g in ["Virgo", "Virtus"]:
        members = parse_group_members(g)
        if members:
            idol_groups[g] = members

    # fallback（保險）
    if "Virgo" not in idol_groups:
        idol_groups["Virgo"] = ["果真希", "桑敏智", "雲碩美", "伊澤愛", "香織善", "海允恕"]
    if "Virtus" not in idol_groups:
        idol_groups["Virtus"] = ["花愛誠", "摩維仁", "喬吉忠", "安貞勇", "角勝義", "占畢信"]


    for c in categories_sorted:
        out_dir = cat_root / slugify(c)
        ensure_dir(out_dir)
        if c == "人物":
            parts = [
                f"<h1>分類：{escape(c)}</h1>",
                f"<p class='muted'>共 {len(cat_to_titles[c])} 條</p>",
            ]

            # Explicit importance ordering (author-defined)
            virgo_order = ["果真希", "桑敏智", "雲碩美", "伊澤愛", "香織善", "海允恕"]
            virtus_order = ["花愛誠", "摩維仁", "喬吉忠", "安貞勇", "角勝義", "占畢信"]
            other_order = ["胡亞尼", "國真幾", "胡亞默", "真知子", "零智嚴", "間貫一", "牟兩儀", "郎三才"]

            titles = list(cat_to_titles.get(c, []))
            present = set(titles)

            # Use <div> rows instead of <ul><li> to avoid bullet points
            def row(t: str) -> str:
                return f'<div class="cat-row"><a href="{title_to_url[t]}">{escape(t)}</a></div>'

            used = set()

            # Virgo section
            virgo = [t for t in virgo_order if t in present]
            if virgo:
                used.update(virgo)
                parts.append("<h2>Virgo</h2>")
                parts.append('<div class="cat-list">')
                parts.append("\n".join(row(t) for t in virgo))
                parts.append("</div>")

            # Virtus section
            virtus = [t for t in virtus_order if t in present]
            if virtus:
                used.update(virtus)
                parts.append("<h2>Virtus</h2>")
                parts.append('<div class="cat-list">')
                parts.append("\n".join(row(t) for t in virtus))
                parts.append("</div>")

            # Others section: explicit importance order first, then remaining alphabetically
            others_main = [t for t in other_order if t in present and t not in used]
            used.update(others_main)
            others_rest = sorted([t for t in titles if t not in used])

            others = others_main + others_rest
            if others:
                parts.append("<h2>其他人物</h2>")
                parts.append('<div class="cat-list">')
                parts.append("\n".join(row(t) for t in others))
                parts.append("</div>")

            body = "\n".join(parts)

        else:

            items = [f'<li><a href="{title_to_url[t]}">{escape(t)}</a></li>' for t in cat_to_titles[c]]
            body = (
                f"<h1>分類：{escape(c)}</h1>"
                f"<p class='muted'>共 {len(cat_to_titles[c])} 條</p>"
                "<h2>詞條</h2>"
                "<ul>" + "\n".join(items) + "</ul>"
            )

        (out_dir / "index.html").write_text(
            render_page(f"分類：{c}", sidebar_html, categories_sidebar_html, body),
            encoding="utf-8"
        )

    # Home
    entries_sorted = sorted(entries, key=lambda x: x["title"])
    home_list = [
        f'<li><a href="{title_to_url[e["title"]]}">{escape(e["title"])}</a> — {escape(e.get("summary",""))}</li>'
        for e in entries_sorted
    ]
    home_body = (
        "<h1>佩洛瑪舞台：百科</h1>"
        "<p class='muted'>此網站內容全部源於《<a href='https://fictionpassion.com/' target='_blank' rel='noopener'>愛虛構 Fiction Passion</a>》，請訂閱支持創作。</p>"
        "<p><img class='hero-image' src='/images/pleroma-wiki.jpg' alt='佩洛瑪舞台：百科 主題圖' /></p>"
        "<p><a href='/categories/'>→ 瀏覽分類</a></p>"
        "<h2>詞條列表</h2>"
        "<ul>" + "\n".join(home_list) + "</ul>"
    )
    (DIST / "index.html").write_text(
        render_page("佩洛瑪舞台：百科", sidebar_html, categories_sidebar_html, home_body),
        encoding="utf-8"
    )

    print("Build complete -> dist/")

if __name__ == "__main__":
    build()
