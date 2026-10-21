import os
import re
import json
import shutil
from pathlib import Path
from html import escape, unescape
from collections import defaultdict
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.resolve()
DATA_DIR = PROJECT_ROOT / "data"
POSTS_DIR = DATA_DIR / "posts"
IMAGES_DIR = DATA_DIR / "images"
DIST_DIR = PROJECT_ROOT / "dist"
AUTHOR_HTML_FILE = DATA_DIR / "author.html"

RUSSIAN_MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12
}

MONTH_NAMES_RU = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
]

def render_navbar(active_item=""):
    def link_classes(name):
        base = "font-medium transition-colors px-2.5 py-1.5 rounded-lg text-xs sm:text-sm whitespace-nowrap"
        if active_item == name:
            return f"{base} text-emerald-900 bg-emerald-100 font-semibold"
        return f"{base} text-gray-600 hover:text-emerald-800 hover:bg-emerald-50"

    return f"""
  <header class="border-b border-gray-200 bg-white/95 backdrop-blur sticky top-0 z-40 shadow-xs">
    <div class="max-w-5xl mx-auto px-3 sm:px-4 py-2.5 sm:py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-4">
      <div class="flex items-center justify-between">
        <a href="/" class="font-title text-lg sm:text-xl font-bold tracking-tight text-gray-900 hover:text-emerald-800 transition truncate">
          о. Георгий Эдельштейн
        </a>
        <a href="https://g-edelstein.livejournal.com" target="_blank" rel="noopener" class="text-xs text-gray-400 hover:text-gray-700 sm:hidden font-sans-ui px-1.5 py-0.5">
          ЖЖ ↗
        </a>
      </div>
      <nav class="font-sans-ui flex items-center gap-1 sm:gap-2 overflow-x-auto no-scrollbar py-0.5">
        <a href="/" class="{link_classes('posts')}">Статьи</a>
        <a href="/search.html" class="{link_classes('search')}">Поиск и темы</a>
        <a href="/author.html" class="{link_classes('author')}">Об авторе</a>
        <a href="https://g-edelstein.livejournal.com" target="_blank" rel="noopener" class="text-xs text-gray-400 hover:text-gray-700 hidden sm:inline ml-1 font-sans-ui">
          ЖЖ ↗
        </a>
      </nav>
    </div>
  </header>
"""

def get_html_head(page_title):
    return f"""<!DOCTYPE html>
<html lang="ru" class="overflow-x-hidden">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0">
  <title>{escape(page_title)}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Lora:ital,wght@0,400;0,500;0,600;1,400&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    html, body {{
      overflow-x: hidden;
      width: 100%;
    }}
    body {{
      font-family: 'Lora', Georgia, serif;
      background-color: #fbfbfc;
      color: #1f2937;
      -webkit-font-smoothing: antialiased;
    }}
    .font-sans-ui {{ font-family: 'Inter', system-ui, -apple-system, sans-serif; }}
    .font-title {{ font-family: 'Cinzel', Georgia, serif; }}
    
    .no-scrollbar::-webkit-scrollbar {{
      display: none;
    }}
    .no-scrollbar {{
      -ms-overflow-style: none;
      scrollbar-width: none;
    }}

    .comment-entry {{
      transition: border-color 0.15s ease;
      word-break: break-word;
      overflow-wrap: break-word;
    }}
    .comment-entry:hover {{
      border-color: #a7f3d0;
    }}

    /* Защита от переполнения таблицами и цитатами на смартфонах */
    article img {{
      max-width: 100% !important;
      height: auto !important;
      border-radius: 0.5rem;
    }}
    article table {{
      display: block;
      max-width: 100%;
      overflow-x: auto;
    }}
    article pre, article code {{
      word-break: break-all;
      white-space: pre-wrap;
    }}
  </style>
</head>
<body class="min-h-screen flex flex-col bg-[#fbfbfc] text-gray-900 w-full overflow-x-hidden">
"""

HTML_FOOTER = """
</body>
</html>
"""

def clean_html_to_plain_text(html_text):
    text = re.sub(r'<[^>]+>', ' ', html_text)
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def parse_date_components(date_str):
    if not date_str:
        return None, None, None
    ds = date_str.lower()
    
    # 1. Формат: "December 28 2016, 22:11" или "28 декабря 2016"
    for month_name, m_num in RUSSIAN_MONTHS.items():
        if month_name in ds:
            # Ищем день и год
            m_day = re.search(r'\b([0-3]?[0-9])\b', ds)
            m_year = re.search(r'\b(20[0-2][0-9]|199[0-9])\b', ds)
            day = int(m_day.group(1)) if m_day else 1
            year = int(m_year.group(1)) if m_year else 2016
            return year, m_num, day

    # 2. Формат: "2016-12-28"
    m_iso = re.search(r'(\d{4})-(\d{2})-(\d{2})', ds)
    if m_iso:
        return int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))

    return None, None, None

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

    clean_body = re.sub(r'^\s*#\s+[^\n]+\n+', '', content.strip())
    clean_body = re.sub(r'^\s*_[^\n]+_\s*\n+', '', clean_body)

    comments_html = ""
    post_html = clean_body
    if '<section class="lj-comments-archive"' in clean_body:
        c_parts = clean_body.split('<section class="lj-comments-archive"', 1)
        post_html = c_parts[0]
        comments_html = '<section class="lj-comments-archive"' + c_parts[1]

    plain_content = clean_html_to_plain_text(post_html)
    has_images = bool(re.search(r'<img\s+', post_html, re.I))

    if len(plain_content) < 40 and not has_images:
        return None

    title = meta.get("title", "").strip()
    is_dummy_title = not title or bool(re.match(r'^Запись\s+\d+$', title, re.I)) or title.lower() in ["без темы", "(без темы)", "untitled"]

    if is_dummy_title:
        sentences = [s.strip() for s in re.split(r'[.\n!?]+', plain_content) if len(s.strip()) > 5]
        if sentences:
            candidate = sentences[0]
            if len(candidate) > 75:
                candidate = candidate[:72].rsplit(' ', 1)[0] + '...'
            title = candidate
        else:
            title = f"Запись от {meta.get('date', filepath.stem)}"

    comment_count = len(re.findall(r'<article class="comment-entry"', comments_html))
    snippet = plain_content[:180].rsplit(' ', 1)[0] + '...' if len(plain_content) > 180 else plain_content

    date_str = meta.get("date", "")
    y, m, d = parse_date_components(date_str)

    return {
        "id": meta.get("id", filepath.stem),
        "title": title,
        "snippet": snippet,
        "date": date_str,
        "year": y,
        "month": m,
        "day": d,
        "tags": meta.get("tags", []),
        "original_url": meta.get("original_url", f"https://g-edelstein.livejournal.com/{filepath.stem}.html"),
        "body_html": post_html.strip(),
        "comments_html": comments_html.strip(),
        "comment_count": comment_count
    }

def render_post_card(p):
    tags_str = " ".join(p["tags"])
    tags_chips = "".join([f'<span class="text-[11px] sm:text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded font-sans-ui whitespace-nowrap">{escape(t)}</span>' for t in p["tags"][:2]])
    comments_badge = f'<span class="text-[11px] sm:text-xs text-emerald-800 bg-emerald-50 border border-emerald-100 px-2 py-0.5 rounded font-semibold font-sans-ui whitespace-nowrap">💬 {p["comment_count"]}</span>' if p["comment_count"] > 0 else ''
    
    date_badge = f"{p['year']}-{p['month']:02d}" if (p['year'] and p['month']) else ""

    return f"""
    <a href="/{p['id']}.html" 
       class="post-card group block bg-white border border-gray-200 hover:border-emerald-500 hover:shadow-md active:bg-emerald-50/20 rounded-xl p-4 sm:p-5 transition-all duration-200 flex flex-col justify-between w-full"
       data-search="{escape(p['title'].lower())} {escape(p['snippet'].lower())} {escape(tags_str.lower())}"
       data-tags="{escape(','.join(p['tags']))}"
       data-date="{date_badge}">
      <div>
        <div class="flex items-center justify-between gap-2 mb-2">
          <span class="font-sans-ui text-xs text-gray-400 group-hover:text-emerald-700 transition font-medium truncate">{escape(p['date'])}</span>
          {comments_badge}
        </div>
        <h2 class="font-title text-base sm:text-lg font-bold text-gray-900 group-hover:text-emerald-800 transition mb-2 leading-snug break-words">
          {escape(p['title'])}
        </h2>
        {f'<p class="font-sans-ui text-xs sm:text-sm text-gray-500 line-clamp-2 leading-relaxed mb-4 break-words">{escape(p["snippet"])}</p>' if p.get("snippet") else ''}
      </div>
      <div class="flex items-center justify-between mt-auto pt-3 border-t border-gray-100 group-hover:border-emerald-100 transition gap-2">
        <div class="flex flex-wrap gap-1 overflow-hidden">
          {tags_chips}
        </div>
        <span class="font-sans-ui text-xs text-emerald-700 group-hover:text-emerald-800 transition font-semibold whitespace-nowrap">Читать →</span>
      </div>
    </a>
    """

def generate_post_page(post):
    tag_badges = "".join([f'<a href="/search.html?tag={escape(t)}" class="text-xs bg-emerald-50 hover:bg-emerald-100 text-emerald-800 px-2.5 py-1 rounded font-sans-ui transition">{escape(t)}</a>' for t in post["tags"]])
    
    article_html = f"""
    <div class="flex-1 py-6 sm:py-10 px-3 sm:px-4 w-full">
      <main class="max-w-3xl mx-auto bg-white border border-gray-200 rounded-xl p-4 sm:p-8 md:p-10 shadow-xs w-full overflow-hidden">
        <header class="border-b border-gray-200 pb-5 mb-6 sm:mb-8">
          <div class="font-sans-ui text-[11px] sm:text-xs uppercase tracking-widest text-emerald-800 font-semibold mb-2">Архив ЖЖ @g-edelstein</div>
          <h1 class="font-title text-xl sm:text-2xl md:text-3xl font-bold text-gray-900 leading-tight mb-3 sm:mb-4 break-words">{escape(post["title"])}</h1>
          <div class="font-sans-ui text-xs sm:text-sm text-gray-500 flex flex-wrap items-center gap-2 sm:gap-3">
            <time>{escape(post["date"])}</time>
            <span>•</span>
            <a href="{escape(post["original_url"])}" target="_blank" rel="noopener" class="hover:text-emerald-800 underline decoration-dotted">Оригинал в LiveJournal ↗</a>
            {f'<span>•</span><span>💬 {post["comment_count"]}</span>' if post["comment_count"] else ''}
          </div>
          {f'<div class="flex flex-wrap gap-1.5 mt-3 sm:mt-4">{tag_badges}</div>' if tag_badges else ''}
        </header>

        <article class="prose prose-sm sm:prose-base md:prose-lg max-w-none text-gray-800 leading-relaxed space-y-4 break-words">
          {post["body_html"]}
        </article>

        {post["comments_html"]}

        <div class="mt-10 sm:mt-12 pt-6 border-t border-gray-200 text-center font-sans-ui">
          <a href="/" class="inline-flex items-center gap-2 text-xs sm:text-sm text-gray-600 hover:text-emerald-800 font-medium transition py-2 px-3 rounded-lg hover:bg-emerald-50">
            ← Вернуться ко всем статьям
          </a>
        </div>
      </main>
    </div>
    """
    page = get_html_head(f"{post['title']} — о. Георгий Эдельштейн") + render_navbar(active_item="posts") + article_html + HTML_FOOTER
    out_path = DIST_DIR / f"{post['id']}.html"
    out_path.write_text(page, encoding="utf-8")

def generate_index_page(posts):
    sorted_posts = sorted(posts, key=lambda x: int(x["id"]) if x["id"].isdigit() else 0, reverse=True)
    cards = [render_post_card(p) for p in sorted_posts]

    index_html = f"""
    <div class="flex-1 py-6 sm:py-10 px-3 sm:px-4 w-full">
      <main class="max-w-5xl mx-auto w-full">
        <header class="text-center mb-6 sm:mb-10 px-2">
          <h1 class="font-title text-2xl sm:text-3xl md:text-4xl font-bold text-gray-900 mb-2 sm:mb-3 leading-snug break-words">
            Архив записей о. Георгия Эдельштейна
          </h1>
          <div class="font-sans-ui text-xs sm:text-sm text-gray-500">
            Каталог публикаций ({len(posts)} статей)
          </div>
        </header>

        <div class="grid gap-3 sm:gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 w-full">
          {"".join(cards)}
        </div>
      </main>
    </div>
    """
    
    page = get_html_head("Архив публикаций — о. Георгий Эдельштейн") + render_navbar(active_item="posts") + index_html + HTML_FOOTER
    (DIST_DIR / "index.html").write_text(page, encoding="utf-8")

def generate_search_page(posts):
    sorted_posts = sorted(posts, key=lambda x: int(x["id"]) if x["id"].isdigit() else 0, reverse=True)
    cards = [render_post_card(p) for p in sorted_posts]

    # Собираем теги со статистикой
    tag_counts = defaultdict(int)
    for p in posts:
        for t in p["tags"]:
            tag_counts[t] += 1
    sorted_tags = sorted(tag_counts.items(), key=lambda x: (-x[1], x[0]))

    # Собираем календарь (Годы и месяцы)
    calendar_data = defaultdict(lambda: defaultdict(int))
    for p in posts:
        if p["year"] and p["month"]:
            calendar_data[p["year"]][p["month"]] += 1

    years_sorted = sorted(calendar_data.keys(), reverse=True)

    # Генерация HTML тегов
    tag_buttons = []
    for tag_name, count in sorted_tags:
        btn = f"""<button type="button" class="tag-filter-btn px-2.5 py-1 rounded-full text-xs font-sans-ui font-medium bg-gray-100 text-gray-700 hover:bg-emerald-100 hover:text-emerald-800 transition whitespace-nowrap" data-tag="{escape(tag_name)}">{escape(tag_name)} <span class="text-gray-400 font-normal">({count})</span></button>"""
        tag_buttons.append(btn)

    # Генерация HTML календаря
    cal_html = []
    for y in years_sorted:
        months_btns = []
        for m_num in sorted(calendar_data[y].keys()):
            cnt = calendar_data[y][m_num]
            m_label = MONTH_NAMES_RU[m_num]
            m_key = f"{y}-{m_num:02d}"
            months_btns.append(
                f'<button type="button" class="date-filter-btn text-xs font-sans-ui px-2 py-1 rounded bg-white border border-gray-200 hover:border-emerald-500 hover:text-emerald-800 transition text-gray-600 whitespace-nowrap" data-date="{m_key}">{m_label} <span class="text-gray-400">({cnt})</span></button>'
            )
        year_row = f"""
        <div class="mb-3">
          <div class="font-sans-ui text-xs font-bold text-gray-700 mb-1.5 flex items-center gap-2">
            <span>{y} год</span>
            <span class="text-gray-400 font-normal text-xs">({sum(calendar_data[y].values())} зап.)</span>
          </div>
          <div class="flex flex-wrap gap-1.5">
            {"".join(months_btns)}
          </div>
        </div>
        """
        cal_html.append(year_row)

    search_html = f"""
    <div class="flex-1 py-6 sm:py-10 px-3 sm:px-4 w-full">
      <main class="max-w-5xl mx-auto w-full">
        <header class="text-center mb-6 sm:mb-8 px-2">
          <h1 class="font-title text-2xl sm:text-3xl font-bold text-gray-900 mb-2 leading-snug">Поиск по архиву</h1>
          <p class="font-sans-ui text-xs sm:text-sm text-gray-500 max-w-xl mx-auto">Находите статьи по ключевым словам, темам или датам публикаций в LiveJournal</p>
          
          <div class="mt-4 sm:mt-6 max-w-2xl mx-auto relative w-full">
            <input type="text" id="searchInput" placeholder="Поиск по статьям, фразам, темам..." 
                   class="w-full px-4 sm:px-5 py-3 sm:py-3.5 pl-10 sm:pl-11 rounded-xl border border-gray-300 focus:outline-none focus:ring-2 focus:ring-emerald-600 font-sans-ui text-sm sm:text-base shadow-xs transition">
            <svg class="w-4 h-4 sm:w-5 sm:h-5 text-gray-400 absolute left-3.5 top-3.5 sm:top-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
            </svg>
          </div>
        </header>

        <!-- Блок фильтрации (Теги + Календарь) -->
        <div class="bg-white border border-gray-200 rounded-xl p-4 sm:p-6 mb-6 sm:mb-8 shadow-xs font-sans-ui w-full overflow-hidden">
          <div class="flex items-center justify-between gap-2 border-b border-gray-100 pb-3 mb-4">
            <span class="text-xs sm:text-sm font-bold text-gray-900">Фильтры поиска</span>
            <button id="resetFiltersBtn" type="button" class="text-xs text-emerald-700 hover:text-emerald-900 hover:underline hidden font-medium">Сбросить всё ✕</button>
          </div>

          <div class="grid md:grid-cols-2 gap-4 sm:gap-6">
            <!-- Теги -->
            <div>
              <div class="text-[11px] sm:text-xs uppercase tracking-wider text-gray-400 font-bold mb-2">Метки и категории</div>
              <div class="flex flex-wrap gap-1.5 max-h-40 sm:max-h-48 overflow-y-auto pr-1">
                {"".join(tag_buttons)}
              </div>
            </div>

            <!-- Календарь -->
            <div class="border-t md:border-t-0 md:border-l border-gray-100 pt-4 md:pt-0 md:pl-6">
              <div class="text-[11px] sm:text-xs uppercase tracking-wider text-gray-400 font-bold mb-2">Календарь по датам</div>
              <div class="max-h-40 sm:max-h-48 overflow-y-auto pr-1">
                {"".join(cal_html)}
              </div>
            </div>
          </div>

          <div id="filterStatus" class="mt-4 pt-3 border-t border-gray-100 text-xs text-gray-500 flex items-center justify-between gap-2">
            <span>Найдено статей: <strong id="resultsCount" class="text-emerald-800 font-bold">{len(posts)}</strong></span>
            <span id="activeFilterBadge" class="hidden bg-emerald-50 text-emerald-800 px-2 py-0.5 rounded font-medium truncate max-w-[200px]"></span>
          </div>
        </div>

        <!-- Результаты поиска -->
        <div id="postsList" class="grid gap-3 sm:gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 w-full">
          {"".join(cards)}
        </div>

        <div id="noResults" class="hidden text-center py-12 sm:py-16 bg-white border border-gray-200 rounded-xl px-4">
          <p class="font-sans-ui text-sm sm:text-base text-gray-500 mb-2">По вашему запросу ничего не найдено</p>
          <button id="clearSearchBtn" class="font-sans-ui text-xs text-emerald-700 hover:underline font-semibold">Сбросить поисковый запрос</button>
        </div>

        <script>
          const searchInput = document.getElementById('searchInput');
          const cards = document.querySelectorAll('.post-card');
          const resultsCount = document.getElementById('resultsCount');
          const noResults = document.getElementById('noResults');
          const resetFiltersBtn = document.getElementById('resetFiltersBtn');
          const filterStatus = document.getElementById('filterStatus');
          const activeFilterBadge = document.getElementById('activeFilterBadge');
          const clearSearchBtn = document.getElementById('clearSearchBtn');

          let selectedTag = "";
          let selectedDate = "";

          function applyFilter() {
            const query = searchInput.value.toLowerCase().trim();
            let visibleCount = 0;

            cards.forEach(card => {
              const searchData = card.getAttribute('data-search') || '';
              const cardTags = (card.getAttribute('data-tags') || '').split(',');
              const cardDate = card.getAttribute('data-date') || '';

              const matchesQuery = !query || searchData.includes(query);
              const matchesTag = !selectedTag || cardTags.includes(selectedTag);
              const matchesDate = !selectedDate || cardDate === selectedDate;

              if (matchesQuery && matchesTag && matchesDate) {
                card.style.display = '';
                visibleCount++;
              } else {
                card.style.display = 'none';
              }
            });

            resultsCount.textContent = visibleCount;
            noResults.style.display = visibleCount === 0 ? 'block' : 'none';

            const hasActiveFilters = Boolean(query || selectedTag || selectedDate);
            resetFiltersBtn.classList.toggle('hidden', !hasActiveFilters);

            if (selectedTag) {
              activeFilterBadge.textContent = 'Метка: ' + selectedTag;
              activeFilterBadge.classList.remove('hidden');
            } else if (selectedDate) {
              activeFilterBadge.textContent = 'Месяц: ' + selectedDate;
              activeFilterBadge.classList.remove('hidden');
            } else {
              activeFilterBadge.classList.add('hidden');
            }
          }

          searchInput.addEventListener('input', applyFilter);

          document.querySelectorAll('.tag-filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
              const tag = btn.getAttribute('data-tag');
              if (selectedTag === tag) {
                selectedTag = "";
                btn.classList.remove('bg-emerald-600', 'text-white');
                btn.classList.add('bg-gray-100', 'text-gray-700');
              } else {
                document.querySelectorAll('.tag-filter-btn').forEach(b => {
                  b.classList.remove('bg-emerald-600', 'text-white');
                  b.classList.add('bg-gray-100', 'text-gray-700');
                });
                selectedTag = tag;
                selectedDate = "";
                btn.classList.remove('bg-gray-100', 'text-gray-700');
                btn.classList.add('bg-emerald-600', 'text-white');
              }
              applyFilter();
            });
          });

          document.querySelectorAll('.date-filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
              const dateVal = btn.getAttribute('data-date');
              if (selectedDate === dateVal) {
                selectedDate = "";
                btn.classList.remove('bg-emerald-600', 'text-white', 'border-emerald-600');
              } else {
                document.querySelectorAll('.date-filter-btn').forEach(b => {
                  b.classList.remove('bg-emerald-600', 'text-white', 'border-emerald-600');
                });
                selectedDate = dateVal;
                selectedTag = "";
                btn.classList.add('bg-emerald-600', 'text-white', 'border-emerald-600');
              }
              applyFilter();
            });
          });

          function resetAll() {
            searchInput.value = '';
            selectedTag = '';
            selectedDate = '';
            document.querySelectorAll('.tag-filter-btn').forEach(b => {
              b.classList.remove('bg-emerald-600', 'text-white');
              b.classList.add('bg-gray-100', 'text-gray-700');
            });
            document.querySelectorAll('.date-filter-btn').forEach(b => {
              b.classList.remove('bg-emerald-600', 'text-white', 'border-emerald-600');
            });
            applyFilter();
          }

          resetFiltersBtn.addEventListener('click', resetAll);
          if (clearSearchBtn) clearSearchBtn.addEventListener('click', resetAll);

          const urlParams = new URLSearchParams(window.location.search);
          const initialTag = urlParams.get('tag');
          if (initialTag) {
            const targetBtn = Array.from(document.querySelectorAll('.tag-filter-btn')).find(b => b.getAttribute('data-tag') === initialTag);
            if (targetBtn) targetBtn.click();
          }
        </script>
      </main>
    </div>
    """

    page = get_html_head("Поиск по статьям — о. Георгий Эдельштейн") + render_navbar(active_item="search") + search_html + HTML_FOOTER
    (DIST_DIR / "search.html").write_text(page, encoding="utf-8")

def generate_author_page():
    content = ""
    if AUTHOR_HTML_FILE.exists():
        raw_html = AUTHOR_HTML_FILE.read_text(encoding="utf-8")
        m = re.search(r'<main[^>]*>(.*?)</main>', raw_html, re.DOTALL)
        if m:
            content = m.group(1)
            content = re.sub(r'<footer[^>]*>.*?</footer>', '', content, flags=re.DOTALL)
        else:
            content = raw_html

    author_html = f"""
    <div class="flex-1 py-6 sm:py-10 px-3 sm:px-4 w-full">
      <main class="max-w-3xl mx-auto bg-white border border-gray-200 rounded-xl p-4 sm:p-8 md:p-12 shadow-xs w-full overflow-hidden">
        {content}
      </main>
    </div>
    """

    page = get_html_head("Об авторе — протоиерей Георгий Эдельштейн") + render_navbar(active_item="author") + author_html + HTML_FOOTER
    (DIST_DIR / "author.html").write_text(page, encoding="utf-8")

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

    generate_search_page(posts)
    print(f"[✔] Страница поиска dist/search.html с тегами и календарем готова!")

    generate_author_page()
    print(f"[✔] Страница об авторе dist/author.html готова!")

if __name__ == "__main__":
    build()