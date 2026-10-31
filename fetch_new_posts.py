#!/usr/bin/env python3
import os
import re
import sys
import time
import json
import subprocess
import requests
import socket
import ipaddress
import html
import yaml
import nh3
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil import parser as date_parser

# Определяем корневую папку проекта (работает и из корня, и из папки scripts/)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(SCRIPT_DIR) == "scripts":
    PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
else:
    PROJECT_ROOT = SCRIPT_DIR

POSTS_DIR = os.path.join(PROJECT_ROOT, "content", "posts")
STATIC_IMAGES_DIR = os.path.join(PROJECT_ROOT, "static", "images")

os.makedirs(POSTS_DIR, exist_ok=True)
os.makedirs(STATIC_IMAGES_DIR, exist_ok=True)

# 1. Автоматическая подгрузка GEMINI_API_KEY из .env или ~/.bashrc
def load_api_key():
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"].strip()

    env_paths = [
        os.path.join(PROJECT_ROOT, ".env"),
        os.path.expanduser("~/.env"),
        os.path.expanduser("~/.bashrc")
    ]
    for path in env_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        m = re.search(r'(?:export\s+)?GEMINI_API_KEY\s*=\s*["\']?([^"\'\s]+)["\']?', line)
                        if m and m.group(1):
                            os.environ["GEMINI_API_KEY"] = m.group(1)
                            return m.group(1)
            except Exception:
                pass
    return ""

API_KEY = load_api_key()
MODEL_NAME = "gemini-3.5-flash-lite"
USERNAME = "g-edelstein"
BASE_URL = f"https://{USERNAME}.livejournal.com"

# Порог даты: скачиваем новые посты начиная со вчерашнего дня (29 октября 2026)
MIN_DATE_FILTER = datetime(2026, 10, 29, 0, 0, 0)

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}

MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_IMAGE_REDIRECTS = 3
ALLOWED_IMAGE_HOST_SUFFIXES = (".livejournal.com", ".livejournal.net")

# Внешний HTML считается недоверенным. Список сохраняет основные элементы
# разметки, но запрещает скрипты, SVG, iframe, обработчики событий и CSS.
POST_HTML_CLEANER = nh3.Cleaner(
    tags={
        "a", "p", "br", "hr", "b", "strong", "i", "em", "u", "s",
        "blockquote", "pre", "code", "ul", "ol", "li",
        "h2", "h3", "h4", "h5", "div", "span",
        "img", "figure", "figcaption",
        "table", "thead", "tbody", "tr", "th", "td",
        "sup", "sub", "center",
    },
    attributes={
        "a": {"href", "title", "target", "rel", "name", "id", "class"},
        "img": {"src", "alt", "title", "width", "height", "class"},
        "p": {"class", "id"}, "div": {"class", "id"}, "span": {"class", "id"},
        "blockquote": {"class"}, "pre": {"class"}, "code": {"class"},
        "ul": {"class"}, "ol": {"class"}, "li": {"class"},
        "table": {"class"}, "thead": {"class"}, "tbody": {"class"},
        "tr": {"class"}, "th": {"colspan", "rowspan", "class"},
        "td": {"colspan", "rowspan", "class"},
        "figure": {"class"}, "figcaption": {"class"},
        "h2": {"class", "id"}, "h3": {"class", "id"},
        "h4": {"class", "id"}, "h5": {"class", "id"},
    },
    url_schemes={"http", "https", "mailto"},
    link_rel="noopener noreferrer",
    strip_comments=True,
)


def sanitize_untrusted_html(value):
    if not isinstance(value, str):
        return ""
    return POST_HTML_CLEANER.clean(value)


def safe_metadata_text(value, max_length=500):
    if not isinstance(value, str):
        return ""
    value = re.sub(r"[\x00-\x1f\x7f]", " ", value)
    return " ".join(value.split())[:max_length]


def build_front_matter(post_data, title, summary, slug, tags):
    data = {
        "title": title,
        "date": post_data["dt"].strftime("%Y-%m-%dT%H:%M:%S"),
        "summary": summary,
        "slug": slug,
        "tags": tags,
        "aliases": [f'/{post_data["id"]}.html'],
        "original_url": post_data["url"],
    }
    return yaml.safe_dump(
        data, allow_unicode=True, sort_keys=False, default_flow_style=False
    )


def _is_allowed_image_host(host):
    if not host:
        return False
    host = host.rstrip(".").lower()
    return host == "livejournal.com" or host.endswith(ALLOWED_IMAGE_HOST_SUFFIXES)


def _is_public_image_host(host):
    try:
        records = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        addresses = {record[4][0] for record in records}
        return bool(addresses) and all(
            ipaddress.ip_address(address).is_global for address in addresses
        )
    except (OSError, ValueError):
        return False


def _image_type(data):
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data.startswith(b"BM"):
        return ".bmp"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return ".tiff"
    return None


RUSSIAN_MONTHS = {
    "january": "января", "february": "февраля", "march": "марта",
    "april": "апреля", "may": "мая", "june": "июня",
    "july": "июля", "august": "августа", "september": "сентября",
    "october": "октября", "november": "ноября", "december": "декабря"
}


# =====================================================================
# 1. СЕТЕВЫЕ ЗАПРОСЫ И СКАЧИВАНИЕ КАРТИНОК (из download_begin.py)
# =====================================================================

def fetch_url(url, is_binary=False):
    """Выполняет запрос через системный curl (стабильно работает в penguin)."""
    cmd = [
        "curl",
        "-sSL",
        "--connect-timeout", "15",
        "--max-time", "45",
        "-A", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "-e", BASE_URL,
        url
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
        if is_binary:
            return res.stdout
        return res.stdout.decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [!] Ошибка curl {url}: {e}")
        return None


def download_image(target_url, post_id, img_index):
    """Безопасно скачивает изображения только с доменов LiveJournal."""
    try:
        if not re.fullmatch(r"\d+", str(post_id)):
            return None

        current_url = target_url
        data = None

        for redirect_count in range(MAX_IMAGE_REDIRECTS + 1):
            parsed = urlparse(current_url)
            host = parsed.hostname
            if (
                parsed.scheme not in {"http", "https"}
                or not _is_allowed_image_host(host)
                or parsed.username
                or parsed.password
                or parsed.port not in (None, 443, 80)
            ):
                return None

            if parsed.scheme == "http":
                parsed = parsed._replace(scheme="https")
                current_url = parsed.geturl()

            if not _is_public_image_host(host):
                return None

            response = requests.get(
                current_url,
                headers={"User-Agent": "EdelsteinArchive/1.0"},
                timeout=(10, 20),
                allow_redirects=False,
                stream=True,
            )

            if response.is_redirect or response.is_permanent_redirect:
                location = response.headers.get("Location")
                response.close()
                if not location or redirect_count >= MAX_IMAGE_REDIRECTS:
                    return None
                current_url = urljoin(current_url, location)
                continue

            if response.status_code != 200:
                response.close()
                return None

            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > MAX_IMAGE_BYTES:
                        response.close()
                        return None
                except ValueError:
                    response.close()
                    return None

            chunks = bytearray()
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if chunk:
                    chunks.extend(chunk)
                    if len(chunks) > MAX_IMAGE_BYTES:
                        response.close()
                        return None
            response.close()
            data = bytes(chunks)
            break

        if not data or len(data) < 200:
            return None
        ext = _image_type(data)
        if not ext:
            return None

        filename = f"{post_id}_{img_index:02d}{ext}"
        filepath = os.path.join(STATIC_IMAGES_DIR, filename)
        if not os.path.exists(filepath):
            temp_path = filepath + ".part"
            with open(temp_path, "wb") as image_file:
                image_file.write(data)
            os.replace(temp_path, filepath)
        return f"/images/{filename}"
    except (requests.RequestException, OSError, ValueError):
        return None

def process_images_in_content(body_elem, post_id, post_url):
    """Заменяет внешние ссылки картинок ЖЖ на локальные /images/..."""
    img_tags = body_elem.find_all("img")
    valid_counter = 1

    for img in img_tags:
        src = img.get("src")
        if not src:
            continue

        raw_url = urljoin(post_url, src)
        if any(bad in raw_url for bad in ["l-stat.livejournal.net", "clear.gif", "userinfo.gif", "userinfo_v8"]):
            continue

        target_url = raw_url
        parent_a = img.find_parent("a")
        if parent_a and parent_a.get("href"):
            href = urljoin(post_url, parent_a["href"])
            href_path = urlparse(href).path.lower()
            href_ext = os.path.splitext(href_path)[1]
            if href_ext in IMAGE_EXTENSIONS or "pics.livejournal.com" in href:
                target_url = href

        local_path = download_image(target_url, post_id, valid_counter)
        if local_path:
            img["src"] = local_path
            if parent_a and parent_a.get("href"):
                parent_a["href"] = local_path
            valid_counter += 1


# =====================================================================
# 2. ОЧИСТКА ТЕКСТА И КАНОНИЧЕСКАЯ ТИПОГРАФИКА
# =====================================================================

def clean_and_format_body(body_html):
    """
    Удаляет визуальный мусор ЖЖ, вшитые даты, приводит кавычки к «ёлочкам»
    и расставляет пробелы в инициалах и церковных сокращениях.
    """
    # 1. Удаляем мусорные теги и inline-стили ЖЖ
    body = re.sub(r'</?font[^>]*>', '', body_html, flags=re.IGNORECASE)
    body = re.sub(r'\sstyle="[^"]*"', '', body, flags=re.IGNORECASE)
    body = re.sub(r"\sstyle='[^']*'", '', body, flags=re.IGNORECASE)
    body = re.sub(r'\s(size|face|color)="[^"]*"', '', body, flags=re.IGNORECASE)
    body = re.sub(r"\s(size|face|color)='[^']*'", '', body, flags=re.IGNORECASE)
    body = re.sub(r'<span>(.*?)</span>', r'\1', body, flags=re.IGNORECASE | re.DOTALL)
    body = re.sub(r'<a\s+name="cutid\d+[^"]*"></a>', '', body, flags=re.IGNORECASE)

    # 2. Вычищаем табуляции и цепочки &nbsp; в начале строк
    body = re.sub(r'^[ \t]+', '', body, flags=re.MULTILINE)
    body = re.sub(r'^(?:&nbsp;|\s)+', '', body, flags=re.MULTILINE)

    # 3. Точечная обработка текста вне HTML-тегов
    parts = re.split(r'(<[^>]+>)', body)
    for i in range(0, len(parts), 2):
        if not parts[i]:
            continue
        txt = parts[i]
        txt = txt.replace('&nbsp;', ' ').replace('&mdash;', '—').replace('&laquo;', '«').replace('&raquo;', '»')

        # Парные кавычки "..." -> «...»
        txt = re.sub(r'"([^"]*?)"', r'«\1»', txt)

        # Пробелы в инициалах (А.С. Пушкин -> А. С. Пушкин)
        txt = re.sub(r'([А-ЯЁ])\.\s*([А-ЯЁ])\.\s*([А-ЯЁ][а-яё]+)', r'\1. \2. \3', txt)
        txt = re.sub(r'([А-ЯЁ])\.\s*([А-ЯЁ][а-яё]+)', r'\1. \2', txt)

        # Пробелы после церковных титулов (о.Георгий -> о. Георгий, прот.Александр -> прот. Александр)
        txt = re.sub(r'\b(о|прот|еп|архиеп|митр)\.([А-ЯЁа-яё])', r'\1. \2', txt)
        txt = re.sub(r'\b(архимандрит|игумен|иером|диак)\.?([А-ЯЁа-яё])', r'\1 \2', txt)

        parts[i] = txt

    body = "".join(parts)

    # 4. Удаление вшитой даты в начале поста (если она продублирована в первых строках)
    all_months_regex = "|".join(list(RUSSIAN_MONTHS.keys()) + list(RUSSIAN_MONTHS.values()))
    date_line_re = re.compile(
        rf'^\s*(?:<p[^>]*>)?\s*(?:[_*]|<em[^>]*>|<strong[^>]*>)?\s*'
        rf'((?:(?:{all_months_regex})\s+\d{{1,2}}[,\s]+\d{{4}}|\d{{1,2}}\s+(?:{all_months_regex})\s+\d{{4}})'
        rf'(?:[,\s-]+\d{{1,2}}:\d{{2}}(?::\d{{2}})?)?(?:\s*(?:UTC|GMT))?)'
        rf'\s*(?:[_*]|</em>|</strong>)?\s*(?:</p>)?\s*$',
        re.IGNORECASE
    )

    lines = body.split("\n")
    new_lines = []
    date_removed = False
    checked = 0

    for line in lines:
        stripped = line.strip()
        if not stripped and not date_removed and checked == 0:
            continue
        if not date_removed and checked < 8:
            checked += 1
            if date_line_re.match(stripped):
                date_removed = True
                continue
        new_lines.append(line)

    return sanitize_untrusted_html("\n".join(new_lines).strip())


# =====================================================================
# 3. ВЫГРУЗКА И ДЕРЕВО КОММЕНТАРИЕВ (из comments.py + fix_comments.py)
# =====================================================================

def format_date_to_ru(date_str):
    if not date_str:
        return ""
    res = re.sub(r'\s*(?:UTC|GMT)\s*', '', date_str, flags=re.IGNORECASE)
    for en_m, ru_m in RUSSIAN_MONTHS.items():
        if re.search(rf'\b{en_m}\b', res, re.IGNORECASE):
            m = re.search(rf'([A-Za-z]+)\s+([0-3]?[0-9])\s+(\d{{4}})(?:,\s*([0-9:]+))?', res, re.IGNORECASE)
            if m:
                month_word, day, year, time_part = m.groups()
                ru_month = RUSSIAN_MONTHS.get(month_word.lower(), month_word)
                # Убираем секунды для аккуратности, если они есть (19:52:48 -> 19:52)
                if time_part and len(time_part.split(":")) == 3:
                    time_part = ":".join(time_part.split(":")[:2])
                return f"{int(day)} {ru_month} {year}, {time_part}" if time_part else f"{int(day)} {ru_month} {year}"
            res = re.sub(rf'\b{en_m}\b', ru_m, res, flags=re.IGNORECASE)
            break
    return res.strip()


def clean_comment_body(html_text):
    if not html_text:
        return ""
    cleaned = re.sub(r'<p>\s*<a href="[^"]*#(?:reply|t\d+)"[^>]*>.*?</a>\s*</p>', '', html_text, flags=re.IGNORECASE)
    cleaned = re.sub(r'<div class="item-actions"[^>]*>.*?</div>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<p>\s*</p>', '', cleaned)
    return sanitize_untrusted_html(cleaned.strip())


def extract_comments_from_html(html):
    if not html:
        return []
    marker = '"comments":['
    idx = html.find(marker)
    if idx == -1:
        marker = "'comments':["
        idx = html.find(marker)
        if idx == -1:
            return []

    start = idx + len(marker) - 1
    try:
        decoder = json.JSONDecoder()
        comments_raw, _ = decoder.raw_decode(html[start:])
    except Exception:
        return []

    comments = []
    for item in comments_raw:
        if not isinstance(item, dict):
            continue
        author = item.get("uname") or item.get("dname") or "Аноним"
        if not author and item.get("username"):
            u_info = item.get("username")
            if isinstance(u_info, list) and len(u_info) > 0 and isinstance(u_info[0], dict):
                author = u_info[0].get("username") or "Аноним"

        raw_date = item.get("ctime") or item.get("stime") or ""
        date_str = format_date_to_ru(raw_date)
        body = clean_comment_body(item.get("article") or item.get("body") or "")

        subject = item.get("subject") or ""
        if subject.lower().startswith("re:"):
            subject = re.sub(r'^(?:re:\s*)+', 'Ответ: ', subject, flags=re.IGNORECASE)

        thread_id = item.get("thread") or item.get("dtalkid") or item.get("talkid") or 0
        parent_id = item.get("parent") or 0

        if not body and item.get("deleted"):
            body = "<em>(Комментарий удален)</em>"
        if not body:
            continue

        comments.append({
            "id": int(thread_id),
            "parent_id": int(parent_id) if parent_id else 0,
            "author": author,
            "date": date_str,
            "subject": subject,
            "body": body,
            "depth": 0
        })
    return comments


def sort_comments_into_tree(comments):
    if not comments:
        return []
    by_id = {c["id"]: c for c in comments}
    children = {}
    for c in comments:
        pid = c["parent_id"]
        if pid not in by_id or pid == c["id"]:
            pid = 0
        children.setdefault(pid, []).append(c)

    ordered = []
    def traverse(pid, depth):
        for node in children.get(pid, []):
            node_copy = dict(node)
            node_copy["depth"] = min(depth, 3)
            ordered.append(node_copy)
            traverse(node["id"], depth + 1)

    traverse(0, 0)
    seen = {c["id"] for c in ordered}
    for c in comments:
        if c["id"] not in seen:
            node_copy = dict(c)
            node_copy["depth"] = 0
            ordered.append(node_copy)
    return ordered


def render_comment_entry(comment, index):
    """Экранирует текстовые поля; тело комментария очищает как HTML."""
    author_raw = str(comment.get("author") or "Аноним")
    author = html.escape(author_raw)
    subject = html.escape(str(comment.get("subject") or ""))
    date_text = html.escape(str(comment.get("date") or ""))
    body = sanitize_untrusted_html(str(comment.get("body") or ""))
    depth = max(0, min(int(comment.get("depth", 0)), 3))
    is_author = "edelstein" in author_raw.lower()
    badge = (
        ' <span class="font-sans-ui" style="font-family: \'Inter\', system-ui, sans-serif; '
        'font-size: 0.7rem; background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; '
        'padding: 2px 7px; border-radius: 9999px; font-weight: 600; margin-left: 6px; '
        'letter-spacing: 0.02em;">автор</span>'
        if is_author else ""
    )
    margin_left = depth * 1.5
    subject_html = (
        f'<div class="font-sans-ui" style="font-family: \'Inter\', system-ui, sans-serif; '
        f'font-weight: 600; font-size: 0.95rem; margin-bottom: 0.35rem; '
        f'color: #111827;">{subject}</div>'
        if subject else ""
    )
    body_one_line = re.sub(r"\n+", " ", body).strip()
    return (
        f'<article class="comment-entry font-sans-ui" id="cmt-{index}" style="margin-left: {margin_left}rem; '
        f'margin-bottom: 1.1rem; padding: 0.95rem 1.15rem; background: #ffffff; border: 1px solid #e5e7eb; '
        f'border-left: 4px solid #059669; border-radius: 8px; font-size: 0.95rem;">'
        f'<header style="font-family: \'Inter\', system-ui, sans-serif; font-size: 0.85rem; color: #6b7280; '
        f'margin-bottom: 0.45rem; display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center;">'
        f'<strong style="color: #065f46; font-size: 0.95rem; font-weight: 600;">{author}</strong>{badge}'
        f'<time style="color: #9ca3af; font-size: 0.8rem;">{date_text}</time>'
        f'</header>{subject_html}'
        f'<div class="comment-body" style="line-height: 1.65; color: #374151; font-family: \'Lora\', Georgia, serif; '
        f'font-size: 0.975rem;">{body_one_line}</div>'
        f'</article>'
    )


def fetch_and_render_comments(post_id):
    all_comments = []
    seen_ids = set()
    page = 1

    while True:
        url = f"{BASE_URL}/{post_id}.html?view=flat&page={page}"
        html = fetch_url(url)
        page_comments = extract_comments_from_html(html)
        if not page_comments:
            break

        new_count = 0
        for c in page_comments:
            cid = c.get("id")
            if cid and cid in seen_ids:
                continue
            if cid:
                seen_ids.add(cid)
            all_comments.append(c)
            new_count += 1

        if new_count == 0 or len(page_comments) < 15:
            break
        page += 1
        time.sleep(0.1)

    if not all_comments:
        return ""

    ordered = sort_comments_into_tree(all_comments)
    total = len(ordered)

    # Формируем монолитный HTML без начальных пробелов и пустых строк (чтобы Hugo Goldmark не превращал его в код)
    html_lines = [
        f'<section class="lj-comments-archive" style="margin-top: 3.5rem; border-top: 2px solid #e5e7eb; padding-top: 2rem;">',
        f'<details style="background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 1.25rem 1.5rem;">',
        f'<summary style="cursor: pointer; font-family: \'Inter\', system-ui, sans-serif; font-weight: 600; font-size: 0.95rem; color: #374151; user-select: none;">💬 Архив комментариев ({total})</summary>',
        f'<div class="comments-list" style="margin-top: 1.5rem;">'
    ]

    for idx, comment in enumerate(ordered, 1):
        html_lines.append(render_comment_entry(comment, idx))

    html_lines.append('</div>\n</details>\n</section>')    html_lines.append('</div>\n</details>\n</section>')
    return "\n\n" + "\n".join(html_lines)


# =====================================================================
# 4. ГЕНЕРАЦИЯ КАНОНИЧЕСКИХ МЕТАДАННЫХ ЧЕРЕЗ GEMINI
# =====================================================================

def generate_metadata_with_gemini(raw_title, plain_text, raw_tags, post_id):
    """
    Обращается к Gemini для формирования осмысленного заголовка,
    однострочного TL;DR (summary), канонических тегов и уникального латинского slug.
    """
    global API_KEY
    if not API_KEY:
        try:
            print("\n[?] Переменная GEMINI_API_KEY не найдена в .env или окружении.")
            user_k = input("Введите ваш GEMINI_API_KEY (он будет автоматически сохранен в .env): ").strip()
            if user_k:
                API_KEY = user_k
                with open(os.path.join(PROJECT_ROOT, ".env"), "a", encoding="utf-8") as ef:
                    ef.write(f'\nGEMINI_API_KEY="{API_KEY}"\n')
                print("[+] Ключ успешно сохранен в файл .env! Больше вводить его не потребуется.")
        except (KeyboardInterrupt, EOFError):
            print("\nОтменено.")
            sys.exit(1)

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"

    prompt = (
        "Ты — главный редактор архива публикаций протоиерея Георгия Эдельштейна.\n"
        "Проанализируй новую запись из его Живого Журнала и сгенерируй метаданные строго по канону нашего сайта.\n\n"
        f"ИСХОДНЫЙ ЗАГОЛОВОК В ЖЖ: \"{raw_title}\"\n"
        f"ИСХОДНЫЕ МЕТКИ В ЖЖ: {', '.join(raw_tags) if raw_tags else 'нет'}\n"
        "ТЕКСТ ЗАПИСИ:\n"
        f"{plain_text[:4500]}\n\n"
        "СТРОГИЕ ТРЕБОВАНИЯ:\n"
        "1. final_title (Заголовок):\n"
        "   - Если исходный заголовок осмысленный (и это не техническая фраза вроде 'Запись 38266' или дата), сохрани его смысл, исправив регистр: Первое слово с заглавной буквы, остальные строчные (кроме имен собственных: Георгий, Россия, Христос и аббревиатур: РПЦ, МП, СССР, КГБ).\n"
        "   - Если в ЖЖ не было заголовка или он технический — сформулируй глубокий, точный, содержательный заголовок по сути самого текста (например: «О положении сельских приходов и церковной правде», «Ответы на вопросы читателей о вере и свободе»).\n"
        "   - КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНЫ пустые отписки вроде «Статья протоиерея Георгия Эдельштейна» или «Новая запись».\n"
        "   - Все кавычки внутри заголовка должны быть только «ёлочками».\n"
        "2. summary (Подзаголовок TL;DR для карточки):\n"
        "   - Одно емкое, информативное предложение (14–22 слова), передающее суть публикации.\n"
        "3. tags (Теги рубрик):\n"
        "   - От 2 до 4 содержательных тематических тегов на русском языке.\n"
        "   - Формат каждого тега: строго Первая буква заглавная, остальные строчные (например: \"Православие\", \"Церковная история\", \"Пастырство\", \"Воспоминания\", \"Публицистика\").\n"
        "   - Не используй бытовые ЖЖ-метки вроде «лытдыбр» или «без метки».\n"
        "4. slug (Латинское имя файла для URL):\n"
        "   - 2–4 английских слова через дефис, точно передающих тему конкретно этой статьи (например: letter-on-church-freedom, memory-of-fr-vsevolod).\n"
        "   - КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО использовать шаблонные слова вроде georgy-edelshtein-article или new-post.\n\n"
        "Верни ответ СТРОГО в формате JSON:\n"
        "{\n"
        '  "final_title": "...",\n'
        '  "summary": "...",\n'
        '  "tags": ["...", "..."],\n'
        '  "slug": "..."\n'
        "}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2
        }
    }

    for attempt in range(1, 4):
        try:
            resp = requests.post(api_url, json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                raw_json = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(raw_json)
            elif resp.status_code in (429, 503):
                print(f"  [Лимит API {resp.status_code}, ожидание 10 сек...]")
                time.sleep(10)
            else:
                print(f"  [!] Ошибка API Gemini ({resp.status_code}): {resp.text[:120]}")
                break
        except Exception as e:
            print(f"  [!] Сбой запроса к Gemini (попытка {attempt}/3): {e}")
            time.sleep(3)

    # Fallback, если API недоступен
    first_sentence = plain_text.split(".")[0][:80].strip() if plain_text else f"Публикация {post_id}"
    return {
        "final_title": raw_title if (raw_title and not raw_title.startswith("Запись")) else first_sentence,
        "summary": plain_text[:140].replace("\n", " ").strip() + "...",
        "tags": ["Православие", "Публицистика"],
        "slug": f"publication-{post_id}"
    }


# =====================================================================
# 5. ПОИСК И ОБРАБОТКА НОВЫХ ПОСТОВ НАЧИНАЯ СО ВЧЕРАШНЕГО ДНЯ
# =====================================================================

def cleanup_bad_files():
    """Удаляет пустые и шаблонные файлы от предыдущих тестовых запусков."""
    removed = 0
    for fname in os.listdir(POSTS_DIR):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(POSTS_DIR, fname)
        # Удаляем старые заглушки (размером менее 650 байт без текста или с шаблонными именами)
        if (
            "new-post" in fname
            or "georgy-edelshtein-article" in fname
            or re.search(r'post-\d{10}', fname)
            or os.path.getsize(fpath) < 650
        ):
            try:
                os.remove(fpath)
                removed += 1
            except Exception:
                pass
    if removed:
        print(f"[*] Очищено пустых/черновых файлов от прошлых запусков: {removed}")


def get_existing_post_map():
    """
    Сканирует content/posts/*.md и возвращает словарь:
    { "post_id": "filepath" }, а также множество всех уже занятых slug.
    """
    existing_map = {}
    used_slugs = set()

    for fname in os.listdir(POSTS_DIR):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(POSTS_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                head = f.read(1500)
            m_alias = re.search(r'-\s*["\']?/(\d+)\.html["\']?', head)
            if m_alias:
                existing_map[m_alias.group(1)] = fpath
            m_slug = re.search(r'^slug:\s*["\']?([^"\'\n]+)["\']?', head, re.MULTILINE)
            if m_slug:
                used_slugs.add(m_slug.group(1).strip())
        except Exception:
            pass

    return existing_map, used_slugs


def parse_lj_post_page(post_id):
    """
    Извлекает заголовок, точную дату, теги и полный текст статьи
    по проверенным селекторам темы ЖЖ из download_begin.py.
    """
    url = f"{BASE_URL}/{post_id}.html"
    html = fetch_url(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # 1. Заголовок поста (селекторы из download_begin.py)
    raw_title = ""
    title_elem = soup.find(class_=re.compile(r"aentry-post__title|entry-title|subj-text"))
    if not title_elem:
        title_elem = soup.find(["h1", "h2"], class_=re.compile(r"subj|title"))
    if title_elem:
        raw_title = title_elem.get_text(strip=True)
    else:
        head_title = soup.find("title")
        if head_title:
            t = head_title.get_text(strip=True)
            raw_title = t.split(":", 1)[1].strip() if ":" in t else t

    # 2. Дата публикации (селекторы из download_begin.py + парсинг)
    post_date_raw = ""
    dt_obj = None

    date_elem = soup.find(class_=re.compile(r"aentry-head__date"))
    if date_elem and date_elem.find("time"):
        time_tag = date_elem.find("time")
        post_date_raw = time_tag.get("datetime") or time_tag.get_text(strip=True)
    else:
        date_elem = soup.find(["time", "span", "div"], class_=re.compile(r"date|timestamp"))
        if date_elem:
            post_date_raw = date_elem.get("datetime") or date_elem.get_text(strip=True)

    if post_date_raw:
        # Очищаем строку даты от лишних слов для точного парсинга
        clean_dt_str = re.sub(r'(\d{4})\s+в\s+(\d{1,2}:\d{2})', r'\1 \2', post_date_raw)
        for ru_m, en_m in [(v, k) for k, v in RUSSIAN_MONTHS.items()]:
            clean_dt_str = re.sub(rf'\b{ru_m}\b', en_m, clean_dt_str, flags=re.IGNORECASE)
        try:
            dt_obj = date_parser.parse(clean_dt_str, fuzzy=True)
        except Exception:
            dt_obj = None

    if not dt_obj:
        dt_obj = datetime.now()

    # 3. Теги ЖЖ
    raw_tags = []
    for tag_link in soup.find_all("a", class_=re.compile(r"tag__link|ljtag")):
        t = tag_link.get_text(strip=True)
        if t and t not in raw_tags and t.lower() not in ["cancel", "отмена"]:
            raw_tags.append(t)

    # 4. Тело текста статьи (точные селекторы из download_begin.py: aentry-post__text)
    body_elem = soup.find("div", class_=re.compile(r"aentry-post__text"))
    if not body_elem:
        body_elem = soup.find("div", class_=re.compile(r"aentry-post__content"))
    if not body_elem:
        body_elem = soup.find(["article", "div"], class_=re.compile(r"entry-content|asset-body|post-text|b-singlepost-body"))

    if not body_elem:
        return None

    # Скачиваем изображения внутрь static/images/
    process_images_in_content(body_elem, post_id, url)

    plain_text = body_elem.get_text(separator=" ", strip=True)
    raw_body_html = body_elem.decode_contents()

    return {
        "id": post_id,
        "url": url,
        "raw_title": raw_title,
        "dt": dt_obj.replace(tzinfo=None),
        "raw_tags": raw_tags,
        "raw_body_html": raw_body_html,
        "plain_text": plain_text
    }


def sanitize_yaml_str(val):
    if not val:
        return ""
    # Приводим внутренние кавычки к ёлочкам и экранируем оставшиеся
    val = val.replace('\\"', '"')
    val = re.sub(r'"([^"]*?)"', r'«\1»', val)
    return val.replace("\\", "\\\\").replace('"', '\\"')


def main():
    print(f"[*] Запуск синхронизации сайта с Живым Журналом {BASE_URL}...")

    # 1. Удаляем пустые файлы-заглушки от предыдущих запусков
    cleanup_bad_files()

    # 2. Получаем карту уже существующих на сайте постов
    existing_map, used_slugs = get_existing_post_map()
    print(f"[*] В архиве сайта уже сохранено канонических постов: {len(existing_map)}")

    # 3. Сканируем главную страницу блога на свежие записи (как в __sync__.py)
    main_html = fetch_url(BASE_URL)
    if not main_html:
        print("[!] Не удалось загрузить главную страницу блога.")
        return

    soup = BeautifulSoup(main_html, "html.parser")
    remote_ids = []
    for a in soup.find_all("a", href=True):
        m = re.search(rf"{USERNAME}\.livejournal\.com/(\d+)\.html", a["href"]) or re.search(r"^/(\d+)\.html", a["href"])
        if m:
            pid = m.group(1)
            if pid not in remote_ids:
                remote_ids.append(pid)

    # Сортируем по убыванию ID (самые свежие первыми)
    remote_ids = sorted(remote_ids, key=lambda x: int(x), reverse=True)[:15]
    new_candidates = [pid for pid in remote_ids if pid not in existing_map]

    imported_count = 0

    for pid in new_candidates:
        post_data = parse_lj_post_page(pid)
        if not post_data:
            continue

        # Проверяем фильтр даты: берем строго записи начиная со вчерашнего дня (29 октября 2026)
        if post_data["dt"] < MIN_DATE_FILTER:
            continue

        if len(post_data["plain_text"]) < 20 and "<img" not in post_data["raw_body_html"]:
            print(f"[-] Пост {pid} пуст, пропускаем.")
            continue

        print(f"\n=======================================================")
        print(f"[+] Обработка новой записи #{pid} (дата: {post_data['dt'].strftime('%Y-%m-%d %H:%M')})")
        print(f"    Объем текста: {len(post_data['plain_text'])} симв.")

        # Очищаем верстку и применяем правила типографики
        cleaned_body = clean_and_format_body(post_data["raw_body_html"])

        # Генерируем канонический заголовок, TL;DR, нормализованные теги и slug через Gemini
        print("  -> Генерация заголовка, TL;DR, тегов и латинского имени через Gemini...")
        meta = generate_metadata_with_gemini(
            post_data["raw_title"],
            post_data["plain_text"],
            post_data["raw_tags"],
            pid
        )

        if not isinstance(meta, dict):
            meta = {}

        final_title = safe_metadata_text(
            meta.get("final_title") or post_data["raw_title"], 300
        ) or f"Публикация {pid}"
        summary = safe_metadata_text(meta.get("summary", ""), 500)

        # Gemini возвращает JSON, но его поля всё равно считаются недоверенными.
        norm_tags = []
        seen_t = set()
        model_tags = meta.get("tags", [])
        if isinstance(model_tags, list):
            for tag in model_tags[:10]:
                if not isinstance(tag, str):
                    continue
                t_clean = safe_metadata_text(tag, 80).strip().strip('"').strip("'")
                if not t_clean:
                    continue
                t_norm = t_clean[0].upper() + t_clean[1:].lower()
                if t_norm not in seen_t:
                    seen_t.add(t_norm)
                    norm_tags.append(t_norm)
        if not norm_tags:
            norm_tags = ["Православие"]

        model_slug = meta.get("slug", "")
        if not isinstance(model_slug, str):
            model_slug = ""
        raw_slug = re.sub(r'[^a-z0-9\-]+', '', model_slug.strip().lower()).strip("-")
        if not raw_slug or raw_slug in ("new-post", "article", "georgy-edelshtein-article"):
            raw_slug = f"journal-entry-{pid}"
        if raw_slug in used_slugs:
            raw_slug = f"{raw_slug}-{pid}"
        used_slugs.add(raw_slug)

        # Выгружаем комментарии
        print("  -> Проверка и выгрузка дерева комментариев...")
        comments_html = fetch_and_render_comments(pid)

        date_prefix = post_data["dt"].strftime("%Y-%m-%d")
        front_matter_yaml = build_front_matter(
            post_data, final_title, summary, raw_slug, norm_tags
        )
        md_content = (
            "---\n"
            + front_matter_yaml
            + "---\n\n"
            + cleaned_body
            + comments_html
            + "\n"
        )

        filename = f"{date_prefix}-{raw_slug}.md"
        filepath = os.path.join(POSTS_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)

        imported_count += 1
        print(f"  [✔] Сохранен канонический файл: content/posts/{filename}")
        print(f"      Заголовок: {final_title}")
        print(f"      TL;DR:     {summary}")
        print(f"      Теги:      {', '.join(norm_tags)}")
        time.sleep(2)

    print(f"\n=======================================================")
    print(f"[✔] Синхронизация завершена! Добавлено новых постов: {imported_count}")


if __name__ == "__main__":
    main()