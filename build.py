import os
import re
import json
import shutil
from pathlib import Path
from html import escape, unescape

PROJECT_ROOT = Path(__file__).parent.resolve()
DATA_DIR = PROJECT_ROOT / "data"
POSTS_DIR = DATA_DIR / "posts"
IMAGES_DIR = DATA_DIR / "images"
DIST_DIR = PROJECT_ROOT / "dist"

HTML_HEAD = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{page_title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Lora:ital,wght@0,400;0,500;0,600;1,400&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body {{
      font-family: 'Lora', Georgia, serif;
      background-color: #fbfbfc;
      color: #1f2937;
    }}
    .font-sans-ui {{ font-family: 'Inter', system-ui, -apple-system, sans-serif; }}
    .font-title {{ font-family: 'Cinzel', Georgia, serif; }}
    
    .comment-entry {{
      transition: border-color 0.15s ease;
    }}
    .comment-entry:hover {{
      border-color: #cbd5e1;
    }}
  </style>
</head>
<body class="min-h-screen flex flex-col">
  <nav class="border-b border-gray-200 bg-white/90 backdrop-blur sticky top-0 z-30">
    <div class="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
      <a href="/" class="font-title text-xl font-bold tracking-wide text-gray-900 hover:text-red-800 transition">
        о. Георгий Эдельштейн
      </a>
      <div class="font-sans-ui text-sm text-gray-500 flex items-center gap-4">
        <a href="/" class="hover:text-gray-900 font-medium transition">Все статьи</a>
        <a href="https://g-edelstein.livejournal.com" target="_blank" rel="noopener" class="text-red-700 hover:text-red-900 hover:underline">ЖЖ @g-edelstein ↗</a>
      </div>
    </div>
  </nav>
  <div class="flex-1 py-10 px-4">
"""

HTML_FOOTER = """
  </div>
  <footer class="border-t border-gray-200 bg-white py-8 text-center text-sm text-gray-500 font-sans-ui">
    <div class="max-w-4xl mx-auto px-4">
      <p class="font-medium text-gray-700">Архив публикаций и публичных диалогов о. Георгия Эдельштейна (1932–2026)</p>
      <p class="text-xs text-gray-400 mt-2">Священник Русской Православной Церкви, богослов, диссидент, член Московской Хельсинкской группы</p>
    </div>
  </footer>
</body>
</html>
"""

def clean_html_to_plain_text(html_text):
    """Удаляет все HTML-теги и лишние пробелы для анализа полезного текста."""
    text = re.sub(r'<[^>]+>', ' ', html_text)
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def parse_markdown_post(filepath):
    text = filepath.read_text(encoding="utf-8")
    meta = {}
    content = text
    
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            raw_meta = parts[1]
            content = parts[2]
            
            id_m = re.search(r"id:\s*(\d+)", raw_meta)
            if id_m: meta["id"] = id_m.group(1)
            
            title_m = re.search(r'title:\s*["\']?(.*?)["\']?\s*$', raw_meta, re.M)
            if title_m: meta["title"] = title_m.group(1).strip()
            
            date_m = re.search(r'date:\s*["\']?(.*?)["\']?\s*$', raw_meta, re.M)
            if date_m: meta["date"] = date_m.group(1).strip()
            
            url_m = re.search(r'original_url:\s*["\']?(.*?)["\']?\s*$', raw_meta, re.M)
            if url_m: meta["original_url"] = url_m.group(1).strip()

            tags_block = re.search(r'tags:\s*\n((?:\s*-\s*.*?\n)+)', raw_meta)
            tags = []
            if tags_block:
                for line in tags_block.group(1).strip().splitlines():
                    t = re.sub(r'^\s*-\s*["\']?(.*?)["\']?\s*$', r'\1', line).strip()
                    if t and t != "Без метки":
                        tags.append(t)
            meta["tags"] = tags

    # Удаляем дублирующиеся заголовки первого уровня из тела Markdown
    clean_body = re.sub(r'^\s*#\s+[^\n]+\n+', '', content.strip())
    clean_body = re.sub(r'^\s*_[^\n]+_\s*\n+', '', clean_body)

    comments_html = ""
    post_html = clean_body
    if '<section class="lj-comments-archive"' in clean_body:
        c_parts = clean_body.split('<section class="lj-comments-archive"', 1)
        post_html = c_parts[0]
        comments_html = '<section class="lj-comments-archive"' + c_parts[1]

    # Проверяем наличие полезного контента
    plain_content = clean_html_to_plain_text(post_html)
    has_images = bool(re.search(r'<img\s+', post_html, re.I))

    # ФИЛЬТРАЦИЯ ПУСТЫХ ЗАПИСЕЙ:
    # Если в статье меньше 40 символов осмысленного текста и нет картинок — считаем запись пустой
    if len(plain_content) < 40 and not has_images:
        return None

    # ИЗВЛЕЧЕНИЕ / УТОЧНЕНИЕ ЗАГОЛОВКА:
    title = meta.get("title", "").strip()
    is_dummy_title = not title or bool(re.match(r'^Запись\s+\d+$', title, re.I)) or title.lower() in ["без темы", "(без темы)", "untitled"]

    if is_dummy_title:
        # Пытаемся сформировать заголовок из первых слов первого абзаца
        sentences = [s.strip() for s in re.split(r'[.\n!?]+', plain_content) if len(s.strip()) > 5]
        if sentences:
            candidate = sentences[0]
            if len(candidate) > 75:
                candidate = candidate[:72].rsplit(' ', 1)[0] + '...'
            title = candidate
        else:
            title = f"Запись от {meta.get('date', filepath.stem)}"

    comment_count = len(re.findall(r'<article class="comment-entry"', comments_html))

    # Формируем короткое превью (сниппет) для карточки статьи
    snippet = plain_content[:180].rsplit(' ', 1)[0] + '...' if len(plain_content) > 180 else plain_content

    return {
        "id": meta.get("id", filepath.stem),
        "title": title,
        "snippet": snippet,
        "date": meta.get("date", ""),
        "tags": meta.get("tags", []),
        "original_url": meta.get("original_url", f"https://g-edelstein.livejournal.com/{filepath.stem}.html"),
        "body_html": post_html.strip(),
        "comments_html": comments_html.strip(),
        "comment_count": comment_count
    }

def generate_post_page(post):
    tag_badges = "".join([f'<span class="text-xs bg-gray-100 text-gray-700 px-2.5 py-1 rounded font-sans-ui">{escape(t)}</span>' for t in post["tags"]])
    
    article_html = f"""
    <main class="max-w-3xl mx-auto bg-white border border-gray-200 rounded-xl p-6 sm:p-10 shadow-sm">
      <header class="border-b border-gray-200 pb-6 mb-8">
        <div class="font-sans-ui text-xs uppercase tracking-widest text-red-800 font-semibold mb-2">Архив ЖЖ @g-edelstein</div>
        <h1 class="font-title text-2xl sm:text-3xl font-bold text-gray-900 leading-tight mb-4">{escape(post["title"])}</h1>
        <div class="font-sans-ui text-sm text-gray-500 flex flex-wrap items-center gap-3">
          <time>{escape(post["date"])}</time>
          <span>•</span>
          <a href="{escape(post["original_url"])}" target="_blank" rel="noopener" class="hover:text-red-700 underline decoration-dotted">Оригинал в LiveJournal ↗</a>
          {f'<span>•</span><span>💬 {post["comment_count"]}</span>' if post["comment_count"] else ''}
        </div>
        {f'<div class="flex flex-wrap gap-1.5 mt-4">{tag_badges}</div>' if tag_badges else ''}
      </header>

      <article class="prose prose-lg max-w-none text-gray-800 leading-relaxed space-y-4">
        {post["body_html"]}
      </article>

      {post["comments_html"]}

      <div class="mt-12 pt-6 border-t border-gray-200 text-center font-sans-ui">
        <a href="/" class="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-red-800 font-medium transition">
          ← Вернуться ко всем записям
        </a>
      </div>
    </main>
    """
    page = HTML_HEAD.format(page_title=f"{post['title']} — о. Георгий Эдельштейн") + article_html + HTML_FOOTER
    out_path = DIST_DIR / f"{post['id']}.html"
    out_path.write_text(page, encoding="utf-8")

def generate_index_page(posts):
    # Сортируем записи от самых новых к более старым
    sorted_posts = sorted(posts, key=lambda x: int(x["id"]) if x["id"].isdigit() else 0, reverse=True)
    
    posts_cards = []
    for p in sorted_posts:
        tags_str = " ".join(p["tags"])
        tags_chips = "".join([f'<span class="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{escape(t)}</span>' for t in p["tags"][:3]])
        comments_badge = f'<span class="text-xs text-blue-700 bg-blue-50 px-2 py-0.5 rounded font-medium">💬 {p["comment_count"]}</span>' if p["comment_count"] > 0 else ''
        
        # КЛИКАБЕЛЬНАЯ КАРТОЧКА ЦЕЛИКОМ:
        # Оборачиваем весь <article> в ссылку <a>, чтобы при клике в любое место открывалась статья
        card = f"""
        <a href="/{p['id']}.html" class="post-card group block bg-white border border-gray-200 hover:border-red-400 rounded-xl p-5 transition hover:shadow-md flex flex-col justify-between" data-search="{escape(p['title'].lower())} {escape(p['snippet'].lower())} {escape(tags_str.lower())}">
          <div>
            <div class="flex items-baseline justify-between gap-4 mb-2">
              <span class="font-sans-ui text-xs text-gray-400 group-hover:text-gray-500 transition">{escape(p['date'])}</span>
              {comments_badge}
            </div>
            <h2 class="font-title text-lg font-bold text-gray-900 group-hover:text-red-800 transition mb-2 leading-snug">
              {escape(p['title'])}
            </h2>
            {f'<p class="font-sans-ui text-xs text-gray-500 line-clamp-2 leading-relaxed mb-4">{escape(p["snippet"])}</p>' if p.get("snippet") else ''}
          </div>
          <div class="flex items-center justify-between mt-auto pt-3 border-t border-gray-100">
            <div class="flex flex-wrap gap-1">
              {tags_chips}
            </div>
            <span class="font-sans-ui text-xs text-red-700 group-hover:translate-x-0.5 transition font-medium">Читать →</span>
          </div>
        </a>
        """
        posts_cards.append(card)

    index_html = f"""
    <main class="max-w-4xl mx-auto">
      <header class="text-center mb-10">
        <h1 class="font-title text-3xl sm:text-4xl font-bold text-gray-900 mb-3">Архив записей о. Георгия Эдельштейна</h1>
        <p class="font-sans-ui text-gray-600 max-w-2xl mx-auto leading-relaxed">
          Священник Русской Православной Церкви, член Московской Хельсинкской группы, диссидент, богослов и публицист.
        </p>
        <div class="mt-6 max-w-md mx-auto">
          <input type="text" id="searchInput" placeholder="Поиск по статьям, темам и цитатам..." 
                 class="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-red-700 font-sans-ui text-sm shadow-sm transition">
        </div>
        <div class="font-sans-ui text-xs text-gray-400 mt-2">Каталог публикаций: {len(posts)} статей</div>
      </header>

      <div id="postsList" class="grid gap-4 sm:grid-cols-2">
        {"".join(posts_cards)}
      </div>

      <script>
        const input = document.getElementById('searchInput');
        const cards = document.querySelectorAll('.post-card');
        input.addEventListener('input', (e) => {{
          const q = e.target.value.toLowerCase().trim();
          cards.forEach(card => {{
            const searchData = card.getAttribute('data-search') || '';
            card.style.display = searchData.includes(q) ? '' : 'none';
          }});
        }});
      </script>
    </main>
    """
    
    page = HTML_HEAD.format(page_title="Архив публикаций — о. Георгий Эдельштейн") + index_html + HTML_FOOTER
    (DIST_DIR / "index.html").write_text(page, encoding="utf-8")

def build():
    print("[*] Запуск генерации сайта для Cloudflare Pages...")
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    if IMAGES_DIR.exists():
        dist_images = DIST_DIR / "images"
        shutil.copytree(IMAGES_DIR, dist_images)
        print(f"[+] Скопированы изображения в {dist_images}")

    posts = []
    skipped_count = 0
    md_files = sorted(list(POSTS_DIR.glob("*.md")))
    for md_f in md_files:
        post = parse_markdown_post(md_f)
        if post is None:
            skipped_count += 1
            continue
        posts.append(post)
        generate_post_page(post)

    print(f"[+] Отфильтровано пустых/битых записей: {skipped_count}")
    print(f"[+] Сгенерировано качественных статей: {len(posts)} в dist/")

    generate_index_page(posts)
    print(f"[✔] Главная страница dist/index.html готова!")

if __name__ == "__main__":
    build()