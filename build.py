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


def build(recipes: list[dict], env: Environment):
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

    # Copy static assets
    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, PUBLIC_DIR / "static", dirs_exist_ok=True)

    # Write CSS inline (avoids needing a separate file for the demo)
    (PUBLIC_DIR / "style.css").write_text(CSS, encoding="utf-8")

    # Recipe pages
    recipe_tmpl = env.get_template("recipe.html")
    for recipe in recipes:
        html = recipe_tmpl.render(recipe=recipe, site_name="Savoury Days")
        write(PUBLIC_DIR / recipe["slug"] / "index.html", html)

    # Homepage (paginated)
    index_tmpl = env.get_template("index.html")
    total_pages = max(1, (len(recipes) + RECIPES_PER_PAGE - 1) // RECIPES_PER_PAGE)
    for page_num in range(1, total_pages + 1):
        start = (page_num - 1) * RECIPES_PER_PAGE
        chunk = recipes[start : start + RECIPES_PER_PAGE]
        html = index_tmpl.render(
            recipes=chunk,
            page=page_num,
            total_pages=total_pages,
            site_name="Savoury Days",
        )
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
        html = cat_tmpl.render(
            category=cat,
            recipes=cat_recipes,
            site_name="Savoury Days",
        )
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
header { background: #fff; border-bottom: 2px solid #f0e6d6; padding: 0 1rem; }
nav { max-width: 900px; margin: 0 auto; display: flex; align-items: center; gap: 1.5rem; height: 56px; }
nav .site-title { font-size: 1.3rem; font-weight: 700; color: #222; }
nav .site-title span { color: #b85c2c; }

/* Layout */
.container { max-width: 900px; margin: 0 auto; padding: 2rem 1rem; }

/* Recipe grid */
.recipe-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1.5rem; }
.recipe-card { background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.08); transition: transform .15s; }
.recipe-card:hover { transform: translateY(-3px); }
.recipe-card img { width: 100%; height: 160px; object-fit: cover; background: #f0e6d6; }
.recipe-card .card-body { padding: .8rem; }
.recipe-card h2 { font-size: .95rem; line-height: 1.4; }
.recipe-card .date { font-size: .78rem; color: #888; margin-top: .3rem; }
.recipe-card .cats a { font-size: .75rem; color: #b85c2c; margin-right: .4rem; }

/* Recipe page */
.recipe-page h1 { font-size: 1.8rem; line-height: 1.3; margin-bottom: .5rem; }
.recipe-page .meta { color: #888; font-size: .85rem; margin-bottom: 1.5rem; }
.recipe-page .meta a { color: #b85c2c; }
.recipe-page .featured-img { width: 100%; max-height: 420px; object-fit: cover; border-radius: 8px; margin-bottom: 1.5rem; }
.recipe-page .body img { max-width: 100%; border-radius: 6px; margin: .5rem 0; }
.recipe-page .body p { margin-bottom: 1rem; }
.recipe-page .body h2, .recipe-page .body h3 { margin: 1.2rem 0 .5rem; }
.recipe-page .body ul, .recipe-page .body ol { margin: .5rem 0 1rem 1.5rem; }

/* Pagination */
.pagination { display: flex; gap: .5rem; justify-content: center; margin-top: 2rem; }
.pagination a, .pagination span { padding: .4rem .8rem; border: 1px solid #ddd; border-radius: 4px; color: #b85c2c; }
.pagination .current { background: #b85c2c; color: #fff; border-color: #b85c2c; }

/* Category pill */
.pill { display: inline-block; background: #f0e6d6; color: #b85c2c; border-radius: 20px; padding: .2rem .7rem; font-size: .78rem; margin: .2rem .2rem 0 0; }

@media (max-width: 600px) {
  .recipe-grid { grid-template-columns: 1fr 1fr; }
  .recipe-page h1 { font-size: 1.4rem; }
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
<link rel="stylesheet" href="/style.css">
</head>
<body>
<header>
  <nav>
    <a class="site-title" href="/"><span>Savoury</span> Days</a>
    <a href="/">Trang chủ</a>
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
  <h1>{{ recipe.title }}</h1>
  <div class="meta">
    {% if recipe.date %}<span>{{ recipe.date[:10] }}</span> · {% endif %}
    {% for cat in (recipe.categories or []) %}
      <a href="/category/{{ cat | lower | replace(' ', '-') }}/">{{ cat }}</a>{% if not loop.last %}, {% endif %}
    {% endfor %}
  </div>
  {% if recipe.image %}
  <img class="featured-img" src="{{ recipe.image }}" alt="{{ recipe.title }}" loading="lazy">
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
{% block content %}
<div class="container">
  <h1 style="margin-bottom:1.5rem;">Công thức nấu ăn</h1>
  <div class="recipe-grid">
    {% for r in recipes %}
    <a class="recipe-card" href="/{{ r.slug }}/">
      {% if r.image %}
      <img src="{{ r.image }}" alt="{{ r.title }}" loading="lazy">
      {% else %}
      <div style="height:160px;background:#f0e6d6;"></div>
      {% endif %}
      <div class="card-body">
        <h2>{{ r.title }}</h2>
        <div class="date">{{ r.date[:10] if r.date else '' }}</div>
        {% if r.categories %}
        <div class="cats">{% for c in r.categories[:2] %}<a href="/category/{{ c | lower | replace(' ','-') }}/">{{ c }}</a>{% endfor %}</div>
        {% endif %}
      </div>
    </a>
    {% endfor %}
  </div>
  <div class="pagination">
    {% if page > 1 %}<a href="/page/{{ page - 1 }}/">«</a>{% endif %}
    {% for p in range(1, total_pages + 1) %}
      {% if p == page %}<span class="current">{{ p }}</span>
      {% else %}<a href="/page/{{ p }}/">{{ p }}</a>{% endif %}
    {% endfor %}
    {% if page < total_pages %}<a href="/page/{{ page + 1 }}/">»</a>{% endif %}
  </div>
</div>
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
    <a class="recipe-card" href="/{{ r.slug }}/">
      {% if r.image %}
      <img src="{{ r.image }}" alt="{{ r.title }}" loading="lazy">
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
