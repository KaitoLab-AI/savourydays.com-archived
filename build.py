#!/usr/bin/env python3
"""
Build static HTML site from Markdown content files.

Usage:
  python3 build.py          # build everything in site/content/
  python3 build.py --serve  # build then start local server on port 8080
"""

import argparse
import json
import re
import shutil
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

BASE_DIR = Path(__file__).parent
CONTENT_DIR = BASE_DIR / "content"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
PUBLIC_DIR = BASE_DIR / "docs"

BASE_PATH = "/savourydays.com-archived"
RECIPES_PER_PAGE = 24


def parse_md(path: Path) -> dict:
    """Parse a Markdown file with YAML frontmatter."""
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        _, fm, body = text.split("---", 2)
        meta = yaml.safe_load(fm) or {}
    else:
        meta, body = {}, text
    meta["body_html"] = body.strip()
    meta.setdefault("slug", path.stem)
    return meta


def load_all_recipes() -> list[dict]:
    recipes = []
    for p in sorted(CONTENT_DIR.glob("*.md")):
        try:
            recipes.append(parse_md(p))
        except Exception as e:
            print(f"  WARN: could not parse {p.name}: {e}")
    # Sort newest first
    recipes.sort(key=lambda r: r.get("date") or "", reverse=True)
    return recipes


def setup_templates() -> Environment:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,
    )


def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def fix_body_images(body_html: str) -> str:
    """Prefix /wp-content/ image srcs with BASE_PATH for GitHub Pages subpath hosting."""
    return body_html.replace('src="/wp-content/', f'src="{BASE_PATH}/wp-content/')


def build(recipes: list[dict], env: Environment):
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

    # Copy static assets
    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, PUBLIC_DIR / "static", dirs_exist_ok=True)

    # Write CSS inline (avoids needing a separate file for the demo)
    (PUBLIC_DIR / "style.css").write_text(CSS, encoding="utf-8")

    ctx = dict(site_name="Savoury Days", base=BASE_PATH)

    # Recipe pages
    recipe_tmpl = env.get_template("recipe.html")
    for recipe in recipes:
        r = dict(recipe)
        r["body_html"] = fix_body_images(r.get("body_html", ""))
        html = recipe_tmpl.render(recipe=r, **ctx)
        write(PUBLIC_DIR / recipe["slug"] / "index.html", html)

    # Homepage (paginated)
    index_tmpl = env.get_template("index.html")
    total_pages = max(1, (len(recipes) + RECIPES_PER_PAGE - 1) // RECIPES_PER_PAGE)
    for page_num in range(1, total_pages + 1):
        start = (page_num - 1) * RECIPES_PER_PAGE
        chunk = recipes[start : start + RECIPES_PER_PAGE]
        html = index_tmpl.render(recipes=chunk, page=page_num, total_pages=total_pages, **ctx)
        if page_num == 1:
            write(PUBLIC_DIR / "index.html", html)
        write(PUBLIC_DIR / "page" / str(page_num) / "index.html", html)

    # Category pages
    cats: dict[str, list] = {}
    for r in recipes:
        for c in r.get("categories") or []:
            cats.setdefault(c, []).append(r)

    cat_tmpl = env.get_template("category.html")
    for cat, cat_recipes in cats.items():
        slug = re.sub(r"[^\w]+", "-", cat.lower()).strip("-")
        html = cat_tmpl.render(category=cat, recipes=cat_recipes, **ctx)
        write(PUBLIC_DIR / "category" / slug / "index.html", html)

    # Search index
    index = [
        {"slug": r["slug"], "title": r["title"], "date": r.get("date", ""),
         "cats": r.get("categories") or []}
        for r in recipes
    ]
    (PUBLIC_DIR / "search.json").write_text(
        json.dumps(index, ensure_ascii=False), encoding="utf-8"
    )

    print(f"Built {len(recipes)} recipes → {PUBLIC_DIR}")
    if cats:
        print(f"Built {len(cats)} category pages")


# ── Minimal CSS ──────────────────────────────────────────────────────────────
CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', system-ui, sans-serif; color: #222; background: #fafaf8; line-height: 1.7; }
a { color: #b85c2c; text-decoration: none; }
a:hover { text-decoration: underline; }

/* Nav */
header { background: #fff; border-bottom: 2px solid #f0e6d6; padding: 0 1rem; position: sticky; top: 0; z-index: 10; }
nav { max-width: 900px; margin: 0 auto; display: flex; align-items: center; gap: 1.5rem; height: 56px; }
nav .site-title { font-size: 1.3rem; font-weight: 700; color: #222; }
nav .site-title span { color: #b85c2c; }
nav .spacer { flex: 1; }

/* Search */
#search-box { padding: .35rem .7rem; border: 1px solid #ddd; border-radius: 20px; font-size: .9rem; width: 200px; outline: none; }
#search-box:focus { border-color: #b85c2c; }
#no-results { display: none; text-align: center; padding: 2rem; color: #888; }

/* Layout */
.container { max-width: 900px; margin: 0 auto; padding: 2rem 1rem; }

/* Recipe grid */
.recipe-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 1.5rem; }
.recipe-card { background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 6px rgba(0,0,0,.09); transition: transform .15s, box-shadow .15s; display: flex; flex-direction: column; text-decoration: none; color: inherit; }
.recipe-card:hover { transform: translateY(-4px); box-shadow: 0 4px 16px rgba(0,0,0,.13); text-decoration: none; }
.recipe-card .thumb { width: 100%; aspect-ratio: 4/3; object-fit: cover; background: #f0e6d6; display: block; }
.recipe-card .thumb-placeholder { width: 100%; aspect-ratio: 4/3; background: linear-gradient(135deg, #f0e6d6 0%, #e8d5c0 100%); display: flex; align-items: center; justify-content: center; font-size: 2rem; }
.recipe-card .card-body { padding: .8rem; flex: 1; display: flex; flex-direction: column; gap: .25rem; }
.recipe-card h2 { font-size: .9rem; line-height: 1.4; color: #222; }
.recipe-card .date { font-size: .75rem; color: #aaa; }
.recipe-card .cats a { font-size: .72rem; color: #b85c2c; margin-right: .3rem; }

/* Recipe page */
.recipe-page h1 { font-size: 1.9rem; line-height: 1.3; margin-bottom: .5rem; }
.recipe-page .meta { color: #888; font-size: .85rem; margin-bottom: 1.5rem; border-bottom: 1px solid #f0e6d6; padding-bottom: .8rem; }
.recipe-page .meta a { color: #b85c2c; }
.recipe-page .featured-img { width: 100%; max-height: 460px; object-fit: cover; border-radius: 10px; margin-bottom: 1.8rem; }
.recipe-page .body { font-size: 1rem; }
.recipe-page .body img { max-width: 100%; border-radius: 8px; margin: .8rem auto; display: block; }
.recipe-page .body p { margin-bottom: 1rem; }
.recipe-page .body h2 { font-size: 1.2rem; margin: 1.6rem 0 .5rem; color: #b85c2c; }
.recipe-page .body h3 { font-size: 1.05rem; margin: 1.2rem 0 .4rem; }
.recipe-page .body ul, .recipe-page .body ol { margin: .5rem 0 1rem 1.5rem; }
.recipe-page .body ul li, .recipe-page .body ol li { margin-bottom: .25rem; }
.recipe-page .body strong { color: #333; }
.recipe-page .body table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
.recipe-page .body td, .recipe-page .body th { border: 1px solid #eee; padding: .4rem .7rem; }
.back-link { display: inline-block; margin-bottom: 1.5rem; color: #888; font-size: .9rem; }
.back-link:hover { color: #b85c2c; }

/* Pagination */
.pagination { display: flex; gap: .4rem; justify-content: center; margin-top: 2.5rem; flex-wrap: wrap; }
.pagination a, .pagination span { padding: .4rem .75rem; border: 1px solid #ddd; border-radius: 6px; color: #b85c2c; font-size: .9rem; }
.pagination a:hover { background: #f0e6d6; text-decoration: none; }
.pagination .current { background: #b85c2c; color: #fff; border-color: #b85c2c; }

/* Category pill */
.pill { display: inline-block; background: #f0e6d6; color: #b85c2c; border-radius: 20px; padding: .2rem .7rem; font-size: .78rem; margin: .2rem .2rem 0 0; }

/* Page heading row */
.index-header { display: flex; align-items: center; margin-bottom: 1.5rem; gap: 1rem; flex-wrap: wrap; }
.index-header h1 { flex: 1; font-size: 1.4rem; }

@media (max-width: 600px) {
  .recipe-grid { grid-template-columns: 1fr 1fr; gap: 1rem; }
  .recipe-page h1 { font-size: 1.4rem; }
  #search-box { width: 140px; }
}
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true", help="Serve after building")
    args = parser.parse_args()

    write_templates()

    recipes = load_all_recipes()
    if not recipes:
        print("No recipes found in site/content/. Run extract.py first.")
        return

    env = setup_templates()
    build(recipes, env)

    if args.serve:
        import http.server, os
        os.chdir(PUBLIC_DIR)
        print(f"\nServing at http://localhost:8080 — press Ctrl+C to stop")
        http.server.test(HandlerClass=http.server.SimpleHTTPRequestHandler, port=8080)


def write_templates():
    """Write Jinja2 templates to site/templates/ if they don't exist."""
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    (TEMPLATES_DIR / "base.html").write_text(BASE_HTML, encoding="utf-8")
    (TEMPLATES_DIR / "recipe.html").write_text(RECIPE_HTML, encoding="utf-8")
    (TEMPLATES_DIR / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (TEMPLATES_DIR / "category.html").write_text(CATEGORY_HTML, encoding="utf-8")


# ── Templates ────────────────────────────────────────────────────────────────
BASE_HTML = """\
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}{{ site_name }}{% endblock %}</title>
<link rel="stylesheet" href="{{ base }}/style.css">
</head>
<body>
<header>
  <nav>
    <a class="site-title" href="{{ base }}/"><span>Savoury</span> Days</a>
    <span class="spacer"></span>
    {% block nav_extra %}{% endblock %}
  </nav>
</header>
<main>{% block content %}{% endblock %}</main>
<footer style="text-align:center;padding:2rem;color:#aaa;font-size:.85rem;">
  © Savoury Days · Lưu trữ
</footer>
</body>
</html>
"""

RECIPE_HTML = """\
{% extends "base.html" %}
{% block title %}{{ recipe.title }} – {{ site_name }}{% endblock %}
{% block content %}
<div class="container recipe-page">
  <a class="back-link" href="{{ base }}/">← Tất cả công thức</a>
  <h1>{{ recipe.title }}</h1>
  <div class="meta">
    {% if recipe.date %}<span>{{ recipe.date[:10] }}</span>{% endif %}
    {% if recipe.categories %}
    <span> · </span>
    {% for cat in (recipe.categories or []) %}
      <a href="{{ base }}/category/{{ cat | lower | replace(' ', '-') }}/">{{ cat }}</a>{% if not loop.last %}, {% endif %}
    {% endfor %}
    {% endif %}
  </div>
  {% if recipe.image %}
  <img class="featured-img" src="{{ base }}{{ recipe.image }}" alt="{{ recipe.title }}" loading="lazy">
  {% endif %}
  <div class="body">{{ recipe.body_html }}</div>
  {% if recipe.tags %}
  <div style="margin-top:1.5rem;">
    {% for tag in recipe.tags %}<span class="pill">{{ tag }}</span>{% endfor %}
  </div>
  {% endif %}
</div>
{% endblock %}
"""

INDEX_HTML = """\
{% extends "base.html" %}
{% block title %}{{ site_name }} – Trang {{ page }}{% endblock %}
{% block nav_extra %}<input id="search-box" type="search" placeholder="Tìm công thức…" autocomplete="off">{% endblock %}
{% block content %}
<div class="container">
  <div class="index-header">
    <h1>Công thức nấu ăn</h1>
  </div>
  <div class="recipe-grid" id="recipe-grid">
    {% for r in recipes %}
    <a class="recipe-card" href="{{ base }}/{{ r.slug }}/" data-title="{{ r.title | lower }}">
      {% if r.image %}
      <img class="thumb" src="{{ base }}{{ r.image }}" alt="{{ r.title }}" loading="lazy">
      {% else %}
      <div class="thumb-placeholder">🍜</div>
      {% endif %}
      <div class="card-body">
        <h2>{{ r.title }}</h2>
        <div class="date">{{ r.date[:10] if r.date else '' }}</div>
        {% if r.categories %}
        <div class="cats">{% for c in r.categories[:2] %}<a href="{{ base }}/category/{{ c | lower | replace(' ','-') }}/">{{ c }}</a>{% endfor %}</div>
        {% endif %}
      </div>
    </a>
    {% endfor %}
  </div>
  <p id="no-results">Không tìm thấy công thức nào.</p>
  <div class="pagination" id="pagination">
    {% if page > 1 %}<a href="{{ base }}/page/{{ page - 1 }}/">«</a>{% endif %}
    {% for p in range(1, total_pages + 1) %}
      {% if p == page %}<span class="current">{{ p }}</span>
      {% else %}<a href="{{ base }}/page/{{ p }}/">{{ p }}</a>{% endif %}
    {% endfor %}
    {% if page < total_pages %}<a href="{{ base }}/page/{{ page + 1 }}/">»</a>{% endif %}
  </div>
</div>
<script>
(function(){
  const box = document.getElementById('search-box');
  const grid = document.getElementById('recipe-grid');
  const noRes = document.getElementById('no-results');
  const pagination = document.getElementById('pagination');
  if (!box) return;

  let allRecipes = null;
  const BASE = '{{ base }}';

  box.addEventListener('input', async function() {
    const q = this.value.trim().toLowerCase();
    if (!q) {
      if (allRecipes) { grid.innerHTML = originalHTML; }
      noRes.style.display = 'none';
      pagination.style.display = '';
      return;
    }
    if (!allRecipes) {
      const r = await fetch(BASE + '/search.json');
      allRecipes = await r.json();
    }
    const matches = allRecipes.filter(r => r.title.toLowerCase().includes(q));
    pagination.style.display = 'none';
    if (!matches.length) { grid.innerHTML = ''; noRes.style.display = 'block'; return; }
    noRes.style.display = 'none';
    grid.innerHTML = matches.map(r =>
      `<a class="recipe-card" href="${BASE}/${r.slug}/">
        <div class="thumb-placeholder">🍜</div>
        <div class="card-body"><h2>${r.title}</h2><div class="date">${r.date ? r.date.slice(0,10) : ''}</div></div>
      </a>`
    ).join('');
  });

  const originalHTML = grid.innerHTML;
})();
</script>
{% endblock %}
"""

CATEGORY_HTML = """\
{% extends "base.html" %}
{% block title %}{{ category }} – {{ site_name }}{% endblock %}
{% block content %}
<div class="container">
  <h1 style="margin-bottom:1.5rem;">{{ category }}</h1>
  <div class="recipe-grid">
    {% for r in recipes %}
    <a class="recipe-card" href="{{ base }}/{{ r.slug }}/">
      {% if r.image %}
      <img src="{{ base }}{{ r.image }}" alt="{{ r.title }}" loading="lazy">
      {% else %}
      <div style="height:160px;background:#f0e6d6;"></div>
      {% endif %}
      <div class="card-body">
        <h2>{{ r.title }}</h2>
        <div class="date">{{ r.date[:10] if r.date else '' }}</div>
      </div>
    </a>
    {% endfor %}
  </div>
</div>
{% endblock %}
"""


if __name__ == "__main__":
    main()
