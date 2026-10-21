#!/usr/bin/env python3
import os
import re
import shutil
from pathlib import Path
from bs4 import BeautifulSoup

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
POSTS_DIR = DATA_DIR / "posts"
IMAGES_DIR = DATA_DIR / "images"
DIST_DIR = SCRIPT_DIR / "dist"
DIST_IMAGES_DIR = DIST_DIR / "images"

MONTH_NAMES_RU = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
]

RU_MONTHS_GENITIVE = [
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря"
]

RUSSIAN_MONTHS = {
    "january": ("января", 1), "february": ("февраля", 2), "march": ("марта", 3),
    "april": ("апреля", 4), "may": ("мая", 5), "june": ("июня", 6),
    "july": ("июля", 7), "august": ("августа", 8), "september": ("сентября", 9),
    "october": ("октября", 10), "november": ("ноября", 11), "december": ("декабря", 12)
}

def parse_date_components(date_str):
    """Извлекает (год, месяц, день) из строки даты."""
    if not date_str:
        return None, None, None
    for en_m, (ru_m, m_idx) in RUSSIAN_MONTHS.items():
        if en_m in date_str.lower():
            m = re.search(rf'{en_m}\s+([0-3]?[0-9])\s+(\d{{4}})', date_str, re.IGNORECASE)
            if m:
                return int(m.group(2)), m_idx, int(m.group(1))

    m_iso = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_str)
    if m_iso:
        return int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))

    m_year = re.search(r'\b(20[0-2][0-9])\b', date_str)
    year = int(m_year.group(1)) if m_year else None
    return year, None, None

def format_full_date_ru(raw_date):
    """Преобразует любую дату в аккуратный русский формат: 28 декабря 2016, 22:11."""
    if not raw_date:
        return ""
    d_clean = re.sub(r'\s*(?:UTC|GMT)\s*', '', raw_date, flags=re.IGNORECASE)
    y, m, d = parse_date_components(d_clean)
    if y and m and d:
        time_match = re.search(r'\b([0-2]?[0-9]:[0-5][0-9])\b', d_clean)
        time_str = f", {time_match.group(1)}" if time_match else ""
        return f"{d} {RU_MONTHS_GENITIVE[m]} {y}{time_str}"
    return d_clean

def render_navbar(active_item=""):
    """
    Фиксированная плавающая панель навигации (fixed top-0), 
    которая всегда остается на экране при скролле.
    Шрифт без засечек Inter, три основных раздела.
    """
    items = [
        {"id": "posts", "title": "Все статьи", "url": "/"},
        {"id": "search", "title": "Поиск", "url": "/search.html"},
        {"id": "author", "title": "Об авторе", "url": "/author.html"}
    ]
    
    links_html = []
    for item in items:
        if item["id"] == active_item:
            links_html.append(
                f'<a href="{item["url"]}" class="px-3 py-1.5 rounded-lg text-sm font-semibold tracking-normal bg-emerald-100 text-emerald-900 border border-emerald-200 transition-colors whitespace-nowrap font-sans">{item["title"]}</a>'
            )
        else:
            links_html.append(
                f'<a href="{item["url"]}" class="px-3 py-1.5 rounded-lg text-sm font-medium tracking-normal text-gray-600 hover:text-emerald-800 hover:bg-gray-100 transition-colors whitespace-nowrap font-sans">{item["title"]}</a>'
            )

    return f"""
    <header class="w-full bg-white/95 backdrop-blur-md border-b border-gray-200 fixed top-0 left-0 right-0 z-50 transition-all shadow-xs">
      <div class="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
        <a href="/" class="font-sans text-base sm:text-lg font-bold tracking-tight text-gray-900 hover:text-emerald-800 transition-colors whitespace-nowrap">
          о. Георгий Эдельштейн
        </a>
        <nav class="flex items-center gap-1 sm:gap-2 overflow-x-auto max-w-full font-sans">
          {''.join(links_html)}
        </nav>
      </div>
    </header>
    """

def render_footer():
    """Лаконичный подвал со ссылкой на Живой Журнал автора."""
    return """
    <footer class="w-full border-t border-gray-200 bg-white py-6 mt-16 font-sans">
      <div class="max-w-4xl mx-auto px-4 flex items-center justify-center text-sm text-gray-500">
        <a href="https://g-edelstein.livejournal.com" target="_blank" rel="noopener" class="hover:text-emerald-800 transition-colors inline-flex items-center gap-1">
          LiveJournal ↗
        </a>
      </div>
    </footer>
    """

GLOBAL_HEAD = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0">
  <title>{PAGE_TITLE}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Lora:ital,wght@0,400;0,500;0,600;1,400;1,500&display=swap" rel="stylesheet">
  <style>
    body {
      font-family: 'Lora', Georgia, serif;
      word-break: break-word;
      background-color: #f8fafc;
    }
    .font-sans, .font-sans-ui, nav, header, button, input {
      font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
    }
    h1, h2, h3, h4, h5, h6 {
      font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
    }
    .comment-entry {
      transition: border-color 0.15s ease;
      word-break: break-word;
      overflow-wrap: break-word;
      border-left: 4px solid #059669 !important;
      background: #ffffff !important;
    }
    article img {
      max-width: 100% !important;
      height: auto !important;
      border-radius: 8px;
      margin: 1.25rem auto;
      display: block;
    }
  </style>
</head>
<body class="bg-slate-50 text-gray-800 antialiased min-h-screen flex flex-col w-full pt-16">
"""

def parse_markdown_post(filepath):
    """Парсит markdown файл поста, вычищая технические даты и корректно доставая теги."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    meta = {"tags": []}
    body_content = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            raw_yaml = parts[1]
            body_content = parts[2]
            current_key = None
            for line in raw_yaml.strip().split("\n"):
                line_str = line.strip()
                if not line_str:
                    continue
                if ":" in line and not line_str.startswith("-"):
                    k, v = line.split(":", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    current_key = k
                    if k == "tags":
                        meta["tags"] = []
                    else:
                        meta[k] = v
                elif line_str.startswith("-") and current_key == "tags":
                    tag_val = line_str.lstrip("-").strip().strip('"').strip("'")
                    if tag_val and tag_val.lower() not in ["без метки", ""]:
                        meta["tags"].append(tag_val)

    comments_html = ""
    post_html = body_content
    if '<section class="lj-comments-archive"' in body_content:
        post_html, comments_html = body_content.split('<section class="lj-comments-archive"', 1)
        comments_html = '<section class="lj-comments-archive"' + comments_html

    title = meta.get("title", "").strip()
    h1_match = re.search(r'^#\s+(.+)$', post_html, re.MULTILINE)
    if h1_match:
        h1_val = h1_match.group(1).strip()
        if not title or title.startswith("Запись ") or title.startswith("_"):
            title = h1_val

    # Полная очистка тела поста от дублирующего H1, дат курсивом и меток
    post_html = re.sub(r'^#\s+.+$', '', post_html, count=1, flags=re.MULTILINE)
    post_html = re.sub(r'^\s*_[A-Za-z]+(?:\s+\d+)?[^_\n]*_\s*$', '', post_html, flags=re.MULTILINE)
    post_html = re.sub(r'^\s*_[0-9\s:,\.]*_\s*$', '', post_html, flags=re.MULTILINE)
    post_html = re.sub(r'<a\s+name="cutid\d+"></a>', '', post_html, flags=re.IGNORECASE)
    post_html = re.sub(r'<a\s+name="cutid\d+-end"></a>', '', post_html, flags=re.IGNORECASE)

    soup_text = BeautifulSoup(post_html, "html.parser")
    plain_content = soup_text.get_text(separator=" ", strip=True)

    # Вычищаем строки дат и мусора из начала контента
    cleaned_content = re.sub(r'^(?:_[A-Za-z0-9\s:,\.]+_\s*)+', '', plain_content).strip()
    cleaned_content = re.sub(r'^(?:(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+[^a-zA-Zа-яА-ЯёЁ]*)+', '', cleaned_content, flags=re.IGNORECASE).strip()

    # Если заголовок технический (начинается с даты или 'Запись') — достаем настоящую фразу
    if (not title or title.startswith("Запись ") or 
        re.match(r'^(?:_[A-Za-z0-9\s:,\.]+_\s*)$', title) or
        any(m_word in title.lower() for m_word in RUSSIAN_MONTHS)):
        
        lines = [ln.strip() for ln in cleaned_content.splitlines() if ln.strip()]
        first_meaningful = ""
        bad_words = ["январ", "феврал", "март", "апрел", "ма", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр"]
        for line in lines:
            if any(w in line.lower() for w in bad_words) and len(line) < 40:
                continue
            first_meaningful = line
            break

        if first_meaningful:
            if len(first_meaningful) > 75:
                title = first_meaningful[:75].rsplit(" ", 1)[0] + "..."
            else:
                title = first_meaningful
        else:
            title = f"Запись {filepath.stem}"

    title = title.strip().strip('_')

    if len(cleaned_content) < 30 and not soup_text.find("img"):
        return None

    comment_count = len(re.findall(r'<article class="comment-entry"', comments_html))
    snippet = cleaned_content[:180].rsplit(' ', 1)[0] + '...' if len(cleaned_content) > 180 else cleaned_content

    raw_date = meta.get("date", "")
    ru_date = format_full_date_ru(raw_date)
    y, m, d = parse_date_components(raw_date)

    if comments_html:
        comments_html = re.sub(r'border-left:\s*4px\s*solid\s*(?:#3b82f6|#b91c1c|#2563eb|#991b1b)', 'border-left: 4px solid #059669', comments_html)
        comments_html = re.sub(r'background:\s*#(?:fffbfb|fff5f5)', 'background: #ffffff', comments_html)
        comments_html = re.sub(r'color:\s*#(?:1e40af|991b1b|2563eb)', 'color: #065f46', comments_html)
        badge_replacement = '<span style="font-family: \'Inter\', system-ui, sans-serif; font-size: 0.7rem; background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; padding: 2px 7px; border-radius: 9999px; font-weight: 600; margin-left: 6px;">автор</span>'
        comments_html = re.sub(r'<span[^>]*style="[^"]*background:\s*#fee2e2[^"]*"[^>]*>.*?</span>', badge_replacement, comments_html)
        comments_html = re.sub(r'(>|\s)Re:\s*', r'\1Ответ: ', comments_html)
        # Уменьшаем шрифт заголовка архива комментариев
        comments_html = re.sub(r'font-size:\s*1\.15rem;', 'font-size: 0.95rem;', comments_html)
        for en_m, (ru_m, _) in RUSSIAN_MONTHS.items():
            pattern_dt = re.compile(rf'\b{en_m}\s+([0-3]?[0-9])\s+(\d{{4}})(?:,\s*([0-9:]+))?(?:\s*UTC|\s*GMT)?', re.IGNORECASE)
            comments_html = pattern_dt.sub(lambda m_obj: f"{m_obj.group(1)} {ru_m} {m_obj.group(2)}" + (f", {m_obj.group(3)}" if m_obj.group(3) else ""), comments_html)
        comments_html = re.sub(r'\s*(?:UTC|GMT)\b', '', comments_html)

    return {
        "id": meta.get("id", filepath.stem),
        "title": title,
        "snippet": snippet,
        "date": ru_date,
        "year": y,
        "month": m,
        "day": d,
        "tags": meta.get("tags", []),
        "original_url": meta.get("original_url", f"https://g-edelstein.livejournal.com/{filepath.stem}.html"),
        "body_html": post_html.strip(),
        "comments_html": comments_html.strip(),
        "comment_count": comment_count
    }

def generate_post_page(post):
    """Генерирует отдельную страницу статьи в виде белого листа с отступами и тенью."""
    tags_html = "".join([
        f'<a href="/search.html?tag={t}" class="inline-block bg-emerald-50 text-emerald-800 hover:bg-emerald-100 hover:text-emerald-900 border border-emerald-200/70 text-xs px-2.5 py-0.5 rounded-full font-medium transition-colors font-sans">{t}</a>'
        for t in post["tags"]
    ])

    head = GLOBAL_HEAD.replace("{PAGE_TITLE}", f"{post['title']} — о. Георгий Эдельштейн")
    navbar = render_navbar(active_item="posts")
    footer = render_footer()

    comments_block = f"""
    <section class="mt-12 sm:mt-16 pt-8 border-t border-gray-200 font-sans">
      {post['comments_html']}
    </section>
    """ if post["comments_html"] else ""

    # "Вид листа" на белом фоне с рамкой, тенью и скруглениями
    html = f"""{head}
  {navbar}
  <main class="max-w-3xl mx-auto px-4 py-8 sm:py-12 flex-grow w-full">
    
    <div class="mb-5">
      <a href="/" class="inline-flex items-center gap-1.5 text-xs sm:text-sm font-medium text-emerald-700 hover:text-emerald-900 transition-colors font-sans">
        ← Все публикации
      </a>
    </div>

    <!-- Белый лист статьи -->
    <div class="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 sm:p-10 md:p-12">
      <header class="mb-8 border-b border-gray-100 pb-6">
        <h1 class="font-sans text-2xl sm:text-3xl md:text-4xl font-bold tracking-tight text-gray-900 mb-3 leading-tight">
          {post['title']}
        </h1>
        <div class="flex flex-wrap items-center gap-3 text-xs sm:text-sm text-gray-500 font-sans">
          <time>{post['date']}</time>
          <span>•</span>
          <a href="{post['original_url']}" target="_blank" rel="noopener" class="text-gray-400 hover:text-gray-600 transition-colors underline decoration-dotted">
            Оригинал в LiveJournal ↗
          </a>
        </div>
        <div class="flex flex-wrap gap-1.5 mt-3">
          {tags_html}
        </div>
      </header>

      <article class="prose max-w-none text-base sm:text-lg leading-relaxed text-gray-800 space-y-4 font-serif">
        {post['body_html']}
      </article>

      {comments_block}
    </div>

  </main>
  {footer}
</body>
</html>
"""
    out_file = DIST_DIR / f"{post['id']}.html"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html)

def generate_index_page(posts):
    """Генерирует главную страницу каталога со спокойным заголовком."""
    head = GLOBAL_HEAD.replace("{PAGE_TITLE}", "Архив записей о. Георгия Эдельштейна")
    navbar = render_navbar(active_item="posts")
    footer = render_footer()

    cards_html = []
    for p in posts:
        comments_badge = f'<span class="text-xs text-gray-500 font-medium">💬 {p["comment_count"]}</span>' if p["comment_count"] > 0 else ""
        cards_html.append(f"""
        <a href="/{p['id']}.html" class="group block bg-white rounded-xl border border-gray-200 p-5 sm:p-6 shadow-xs hover:border-emerald-500 hover:shadow-md transition-all">
          <div class="flex items-center justify-between text-xs text-gray-500 font-sans mb-2">
            <time>{p['date']}</time>
            {comments_badge}
          </div>
          <h2 class="font-sans text-lg sm:text-xl font-bold tracking-tight text-gray-900 group-hover:text-emerald-800 transition-colors mb-2 leading-snug">
            {p['title']}
          </h2>
          <p class="text-sm sm:text-base text-gray-600 font-serif leading-relaxed line-clamp-2 mb-3">
            {p['snippet']}
          </p>
          <div class="inline-flex items-center text-xs font-semibold text-emerald-700 group-hover:text-emerald-900 font-sans">
            Читать полностью <span class="ml-1 group-hover:translate-x-1 transition-transform">→</span>
          </div>
        </a>
        """)

    html = f"""{head}
  {navbar}
  <main class="max-w-4xl mx-auto px-4 py-8 sm:py-12 flex-grow w-full">
    <div class="mb-8 sm:mb-10 text-left border-b border-gray-200 pb-6">
      <h1 class="font-sans text-2xl sm:text-3xl md:text-4xl font-normal tracking-tight text-gray-900 mb-2">
        Архив записей о. Георгия Эдельштейна
      </h1>
    </div>
    <div class="space-y-4">
      {''.join(cards_html)}
    </div>
  </main>
  {footer}
</body>
</html>
"""
    with open(DIST_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(html)

def generate_search_page(posts):
    """
    Генерирует страницу поиска с упорядоченными датами и тегами в точности как на скриншоте 1:
    - Метки и категории (счетчики в круглых чипах)
    - Календарь архива по датам (Год, количество записей, месяцы строго 1..12 по порядку)
    """
    head = GLOBAL_HEAD.replace("{PAGE_TITLE}", "Поиск по архиву — о. Георгий Эдельштейн")
    navbar = render_navbar(active_item="search")
    footer = render_footer()

    # Сбор и подсчет тегов
    tag_counts = {}
    for p in posts:
        for t in p.get("tags", []):
            if t:
                tag_counts[t] = tag_counts.get(t, 0) + 1

    sorted_tags = sorted(tag_counts.items(), key=lambda x: (-x[1], x[0]))
    tags_cloud_html = "".join([
        f'<button onclick="filterByTag(\'{tag}\')" class="tag-btn inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full border border-gray-200 bg-white text-gray-700 hover:border-emerald-500 hover:text-emerald-800 transition-colors font-sans shadow-2xs" data-tag="{tag}">'
        f'<span>{tag}</span> <span class="text-gray-400 font-normal">({cnt})</span>'
        f'</button>'
        for tag, cnt in sorted_tags
    ])

    # Сбор и группировка по годам и месяцам
    dates_tree = {}
    year_totals = {}
    for p in posts:
        y, m = p.get("year"), p.get("month")
        if y:
            dates_tree.setdefault(y, {}).setdefault(m or 0, 0)
            dates_tree[y][m or 0] += 1
            year_totals[y] = year_totals.get(y, 0) + 1

    dates_html = []
    # Сортируем года по убыванию (от новых к старым)
    for y in sorted(dates_tree.keys(), reverse=True):
        m_buttons = []
        # Внутри года месяцы сортируем строго ПО КАЛЕНДАРЮ: Январь (1), Февраль (2)...
        for m in sorted(dates_tree[y].keys()):
            if 1 <= m <= 12:
                m_name = MONTH_NAMES_RU[m]
                cnt = dates_tree[y][m]
                m_buttons.append(
                    f'<button onclick="filterByDate({y}, {m})" class="date-btn text-xs px-2.5 py-1 rounded-lg bg-gray-50 border border-gray-200 text-gray-700 hover:bg-emerald-50 hover:border-emerald-400 hover:text-emerald-900 transition-colors font-sans whitespace-nowrap" data-ym="{y}-{m}">{m_name} ({cnt})</button>'
                )
        dates_html.append(f"""
        <div class="py-2.5 border-b border-gray-100 last:border-0 font-sans">
          <div class="flex items-center gap-2 mb-1.5">
            <span class="font-bold text-xs sm:text-sm text-gray-900">{y} год</span>
            <span class="text-xs text-gray-400 font-normal">({year_totals[y]} зап.)</span>
          </div>
          <div class="flex flex-wrap gap-1.5">
            {''.join(m_buttons)}
          </div>
        </div>
        """)

    cards_json = []
    for p in posts:
        cards_json.append(f"""
        <article class="search-item group bg-white rounded-xl border border-gray-200 p-5 shadow-xs hover:border-emerald-500 hover:shadow-md transition-all" data-title="{p['title'].lower()}" data-snippet="{p['snippet'].lower()}" data-tags="{','.join(p.get('tags', [])).lower()}" data-year="{p.get('year') or ''}" data-month="{p.get('month') or ''}">
          <a href="/{p['id']}.html" class="block">
            <div class="flex items-center justify-between text-xs text-gray-500 font-sans mb-2">
              <time>{p['date']}</time>
            </div>
            <h2 class="font-sans text-lg sm:text-xl font-bold tracking-tight text-gray-900 group-hover:text-emerald-800 transition-colors mb-2 leading-snug">
              {p['title']}
            </h2>
            <p class="text-sm text-gray-600 font-serif line-clamp-2 leading-relaxed">
              {p['snippet']}
            </p>
          </a>
        </article>
        """)

    html = f"""{head}
  {navbar}
  <main class="max-w-4xl mx-auto px-4 py-8 sm:py-12 flex-grow w-full">
    
    <div class="mb-8 border-b border-gray-200 pb-6">
      <h1 class="font-sans text-2xl sm:text-3xl md:text-4xl font-normal tracking-tight text-gray-900 mb-2">
        поиск по архиву
      </h1>
      
      <!-- Поле поиска с бесцветной серой контурной лупой -->
      <div class="mt-4 relative">
        <input type="text" id="searchInput" placeholder="Введите слово или фразу для поиска..." 
               class="w-full px-4 py-3 pl-11 bg-white border border-gray-300 rounded-xl text-sm sm:text-base text-gray-900 placeholder-gray-400 focus:outline-hidden focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 font-sans transition-all shadow-xs">
        <svg class="absolute left-3.5 top-3.5 w-5 h-5 text-gray-400 pointer-events-none" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35m1.85-5.15a7 7 0 11-14 0 7 7 0 0114 0z"></path>
        </svg>
        <button id="clearBtn" class="hidden absolute right-3.5 top-3.5 text-gray-400 hover:text-gray-600 text-sm font-sans">✕ Сброс</button>
      </div>
    </div>

    <!-- Две колонки фильтрации: Теги и Даты -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8 font-sans">
      <!-- Блок тегов -->
      <section class="bg-white rounded-xl border border-gray-200 p-5 shadow-xs">
        <h2 class="text-xs font-bold uppercase tracking-wider text-gray-500 mb-3">
          теги
        </h2>
        <div class="flex flex-wrap gap-1.5 max-h-56 overflow-y-auto pr-1">
          {tags_cloud_html}
        </div>
      </section>

      <!-- Блок дат -->
      <section class="bg-white rounded-xl border border-gray-200 p-5 shadow-xs">
        <h2 class="text-xs font-bold uppercase tracking-wider text-gray-500 mb-3">
          даты
        </h2>
        <div class="space-y-1 max-h-56 overflow-y-auto pr-1">
          {''.join(dates_html)}
        </div>
      </section>
    </div>

    <!-- Индикатор фильтрации -->
    <div id="filterStatus" class="hidden items-center justify-between bg-emerald-50 border border-emerald-200 text-emerald-900 px-4 py-2.5 rounded-lg text-xs sm:text-sm font-sans mb-6">
      <span id="filterLabel"></span>
      <button onclick="resetAllFilters()" class="font-bold underline hover:text-emerald-950">Сбросить фильтр</button>
    </div>

    <!-- Счётчик результатов -->
    <div class="mb-4 text-xs sm:text-sm text-gray-500 font-sans">
      Найдено статей: <strong id="visibleCounter" class="text-emerald-800">{len(posts)}</strong>
    </div>

    <!-- Список результатов -->
    <div id="resultsList" class="space-y-4">
      {''.join(cards_json)}
    </div>
    <div id="noResults" class="hidden text-center py-12 text-gray-500 font-sans text-sm">
      Ничего не найдено. Попробуйте изменить запрос или сбросить фильтры.
    </div>

  </main>

  <script>
    const searchInput = document.getElementById('searchInput');
    const clearBtn = document.getElementById('clearBtn');
    const filterStatus = document.getElementById('filterStatus');
    const filterLabel = document.getElementById('filterLabel');
    const visibleCounter = document.getElementById('visibleCounter');
    const noResults = document.getElementById('noResults');
    const items = Array.from(document.querySelectorAll('.search-item'));

    let activeTag = null;
    let activeDate = null;

    function applyFilter() {{
      const query = searchInput.value.toLowerCase().trim();
      clearBtn.classList.toggle('hidden', query.length === 0 && !activeTag && !activeDate);

      let visibleCount = 0;

      items.forEach(item => {{
        const title = item.dataset.title || '';
        const snippet = item.dataset.snippet || '';
        const tags = item.dataset.tags || '';
        const year = item.dataset.year || '';
        const month = item.dataset.month || '';

        let matchQuery = true;
        if (query) {{
          matchQuery = title.includes(query) || snippet.includes(query) || tags.includes(query);
        }}

        let matchTag = true;
        if (activeTag) {{
          matchTag = tags.split(',').map(t => t.trim().toLowerCase()).includes(activeTag.toLowerCase());
        }}

        let matchDate = true;
        if (activeDate) {{
          matchDate = (year === String(activeDate.year)) && (!activeDate.month || month === String(activeDate.month));
        }}

        if (matchQuery && matchTag && matchDate) {{
          item.classList.remove('hidden');
          visibleCount++;
        }} else {{
          item.classList.add('hidden');
        }}
      }});

      visibleCounter.textContent = visibleCount;
      noResults.classList.toggle('hidden', visibleCount > 0);

      if (activeTag || activeDate || query) {{
        filterStatus.classList.remove('hidden');
        filterStatus.classList.add('flex');
        let parts = [];
        if (query) parts.push(`поиск: "${{query}}"`);
        if (activeTag) parts.push(`метка: #${{activeTag}}`);
        if (activeDate) parts.push(`период: ${{activeDate.year}}${{activeDate.month ? '/' + activeDate.month : ''}}`);
        filterLabel.textContent = `Найдено записей: ${{visibleCount}} (${{parts.join(', ')}})`;
      }} else {{
        filterStatus.classList.add('hidden');
        filterStatus.classList.remove('flex');
      }}
    }}

    function filterByTag(tag) {{
      // Взаимное переключение: при выборе тега сбрасываем дату и текстовый ввод
      activeDate = null;
      document.querySelectorAll('.date-btn').forEach(b => b.classList.remove('bg-emerald-600', 'text-white', 'border-emerald-600'));
      searchInput.value = '';

      activeTag = (activeTag === tag) ? null : tag;
      document.querySelectorAll('.tag-btn').forEach(btn => {{
        const isCurrent = btn.dataset.tag === activeTag;
        btn.classList.toggle('bg-emerald-600', isCurrent);
        btn.classList.toggle('text-white', isCurrent);
        btn.classList.toggle('border-emerald-600', isCurrent);
      }});
      applyFilter();
    }}

    function filterByDate(y, m) {{
      // Взаимное переключение: при выборе даты сбрасываем тег и текстовый ввод
      activeTag = null;
      document.querySelectorAll('.tag-btn').forEach(b => b.classList.remove('bg-emerald-600', 'text-white', 'border-emerald-600'));
      searchInput.value = '';

      if (activeDate && activeDate.year === y && activeDate.month === m) {{
        activeDate = null;
      }} else {{
        activeDate = {{ year: y, month: m }};
      }}
      document.querySelectorAll('.date-btn').forEach(btn => {{
        const isCurrent = activeDate && btn.dataset.ym === `${{activeDate.year}}-${{activeDate.month}}`;
        btn.classList.toggle('bg-emerald-600', isCurrent);
        btn.classList.toggle('text-white', isCurrent);
        btn.classList.toggle('border-emerald-600', isCurrent);
      }});
      applyFilter();
    }}

    function resetAllFilters() {{
      searchInput.value = '';
      activeTag = null;
      activeDate = null;
      document.querySelectorAll('.tag-btn').forEach(b => b.classList.remove('bg-emerald-600', 'text-white', 'border-emerald-600'));
      document.querySelectorAll('.date-btn').forEach(b => b.classList.remove('bg-emerald-600', 'text-white', 'border-emerald-600'));
      applyFilter();
    }}

    searchInput.addEventListener('input', () => {{
      // При ручном вводе текста в поиск сбрасываем фильтры кнопок, чтобы не конфликтовать
      if (activeTag || activeDate) {{
        activeTag = null;
        activeDate = null;
        document.querySelectorAll('.tag-btn').forEach(b => b.classList.remove('bg-emerald-600', 'text-white', 'border-emerald-600'));
        document.querySelectorAll('.date-btn').forEach(b => b.classList.remove('bg-emerald-600', 'text-white', 'border-emerald-600'));
      }}
      applyFilter();
    }});
    clearBtn.addEventListener('click', resetAllFilters);

    window.addEventListener('DOMContentLoaded', () => {{
      const params = new URLSearchParams(window.location.search);
      const tagParam = params.get('tag');
      if (tagParam) {{
        filterByTag(tagParam);
      }}
    }});
  </script>
  {footer}
</body>
</html>
"""
    with open(DIST_DIR / "search.html", "w", encoding="utf-8") as f:
        f.write(html)

def generate_author_page():
    """Генерирует страницу 'Об авторе' в виде белого листа."""
    head = GLOBAL_HEAD.replace("{PAGE_TITLE}", "Об авторе — Протоиерей Георгий Эдельштейн")
    navbar = render_navbar(active_item="author")
    footer = render_footer()

    author_html_path = DATA_DIR / "author.html"
    author_body = ""
    if author_html_path.exists():
        with open(author_html_path, "r", encoding="utf-8") as f:
            raw = f.read()
            m = re.search(r'<main[^>]*>(.*?)</main>', raw, re.DOTALL)
            author_body = m.group(1) if m else raw
    else:
        author_body = "<p>Информация об авторе формируется...</p>"

    html = f"""{head}
  {navbar}
  <main class="max-w-3xl mx-auto px-4 py-8 sm:py-12 flex-grow w-full">
    <div class="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 sm:p-10 md:p-12">
      {author_body}
    </div>
  </main>
  {footer}
</body>
</html>
"""
    with open(DIST_DIR / "author.html", "w", encoding="utf-8") as f:
        f.write(html)

def main():
    print("[*] Запуск генерации сайта с восстановленным утвержденным дизайном...")
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    DIST_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    if IMAGES_DIR.exists():
        for img_file in IMAGES_DIR.glob("*"):
            if img_file.is_file():
                shutil.copy2(img_file, DIST_IMAGES_DIR / img_file.name)
        print(f"[+] Скопированы изображения в {DIST_IMAGES_DIR}")

    posts = []
    for md_file in sorted(POSTS_DIR.glob("*.md"), key=lambda x: int(x.stem) if x.stem.isdigit() else 0, reverse=True):
        parsed = parse_markdown_post(md_file)
        if parsed:
            posts.append(parsed)
            generate_post_page(parsed)

    print(f"[+] Сгенерировано {len(posts)} страниц статей в dist/")

    generate_index_page(posts)
    generate_search_page(posts)
    generate_author_page()
    print("[✔] Генерация завершена: дизайн, навигация, календарь и теги полностью восстановлены!")

if __name__ == "__main__":
    main()