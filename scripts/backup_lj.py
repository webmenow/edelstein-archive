#!/usr/bin/env python3
import os
import re
import time
import subprocess
import mimetypes
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
POSTS_DIR = os.path.join(DATA_DIR, "posts")
IMAGES_DIR = os.path.join(DATA_DIR, "images")

os.makedirs(POSTS_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

USERNAME = "g-edelstein"
BASE_URL = f"https://{USERNAME}.livejournal.com"

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}


def fetch_url(url, is_binary=False):
    """Выполняет запрос через системный curl, возвращает текст или байты."""
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
        print(f"\n[!] Ошибка curl {url}: {e}")
        return None


def sanitize_yaml(val):
    if not val:
        return ""
    return val.replace("\\", "\\\\").replace('"', '\\"')


def download_image(target_url, post_id, img_index):
    try:
        parsed = urlparse(target_url)
        ext = os.path.splitext(parsed.path)[1].lower()
        if not ext or ext not in IMAGE_EXTENSIONS:
            ext = ".jpg"

        filename = f"{post_id}_{img_index:02d}{ext}"
        filepath = os.path.join(IMAGES_DIR, filename)

        if not os.path.exists(filepath):
            data = fetch_url(target_url, is_binary=True)
            if not data or len(data) < 200:
                return None
            with open(filepath, "wb") as f:
                f.write(data)

        return f"/images/{filename}"
    except Exception:
        return None


def process_images_in_content(body_elem, post_id, post_url):
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


def get_all_post_urls():
    """Сбор ссылок на все 143 поста за всю историю блога."""
    print("[*] Поиск всех архивных годов блога...")
    calendar_html = fetch_url(f"{BASE_URL}/calendar/")
    if not calendar_html:
        print("[-] Не удалось получить корневой календарь.")
        return []

    soup = BeautifulSoup(calendar_html, "html.parser")
    
    year_links = set()
    for a in soup.find_all("a", href=True):
        m = re.search(r"/(\d{4})/?$", a["href"])
        if m:
            year_val = int(m.group(1))
            if 2007 <= year_val <= 2030:
                year_links.add(f"{BASE_URL}/{year_val}/")

    # Гарантируем охват 2008-2026
    for y in range(2008, 2027):
        year_links.add(f"{BASE_URL}/{y}/")

    month_links = set()
    print(f"[*] Сканирование годов (всего: {len(year_links)})...")
    for y_url in sorted(year_links):
        y_html = fetch_url(y_url)
        if not y_html:
            continue
        y_soup = BeautifulSoup(y_html, "html.parser")
        for a in y_soup.find_all("a", href=True):
            href = a["href"]
            if re.search(r"/\d{4}/\d{2}/?$", href):
                month_links.add(urljoin(BASE_URL, href))
        time.sleep(0.1)

    print(f"[*] Найдено активных месяцев: {len(month_links)}. Сбор прямых ссылок на статьи...")
    post_urls = set()
    for m_url in sorted(month_links):
        m_html = fetch_url(m_url)
        if not m_html:
            continue
        m_soup = BeautifulSoup(m_html, "html.parser")
        for a in m_soup.find_all("a", href=True):
            href = a["href"]
            match = re.search(rf"{USERNAME}\.livejournal\.com/(\d+)\.html", href)
            if match:
                post_id = match.group(1)
                post_urls.add(f"{BASE_URL}/{post_id}.html")
        time.sleep(0.1)

    print(f"\n[+] Всего уникальных записей найдено: {len(post_urls)}")
    return sorted(list(post_urls), key=lambda x: int(re.search(r"/(\d+)\.html", x).group(1)))


def extract_post_data(url):
    m = re.search(r"/(\d+)\.html", url)
    if not m:
        return
    post_id = m.group(1)
    md_file = os.path.join(POSTS_DIR, f"{post_id}.md")

    if os.path.exists(md_file):
        return

    html = fetch_url(url)
    if not html:
        return

    soup = BeautifulSoup(html, "html.parser")

    # 1. Заголовок поста
    title = f"Запись {post_id}"
    title_elem = soup.find(class_=re.compile(r"aentry-post__title|entry-title|subj-text"))
    if not title_elem:
        title_elem = soup.find(["h1", "h2"], class_=re.compile(r"subj|title"))
    if title_elem:
        title = title_elem.get_text(strip=True)
    else:
        head_title = soup.find("title")
        if head_title:
            t = head_title.get_text(strip=True)
            title = t.split(":", 1)[1].strip() if ":" in t else t

    # 2. Дата публикации
    date_elem = soup.find(class_=re.compile(r"aentry-head__date"))
    if date_elem and date_elem.find("time"):
        post_date_raw = date_elem.find("time").get_text(strip=True)
    else:
        date_elem = soup.find(["time", "span", "div"], class_=re.compile(r"date|timestamp"))
        post_date_raw = date_elem.get_text(strip=True) if date_elem else ""

    # 3. Теги и категории
    tags = []
    # Категории и теги в теме post2017
    for tag_link in soup.find_all("a", class_=re.compile(r"tag__link|ljtag")):
        t = tag_link.get_text(strip=True)
        if t and t not in tags and t.lower() not in ["cancel", "отмена"]:
            tags.append(t)

    # Резервный поиск по общим тегам ЖЖ
    if not tags:
        tag_block = soup.find(class_=re.compile(r"tag|entry-tags|ljtags"))
        if tag_block:
            for a in tag_block.find_all("a"):
                t = a.get_text(strip=True)
                if t and t.lower() not in ["tags", "метки", "теги"]:
                    tags.append(t)

    # 4. Тело текста статьи (на основе точной разметки)
    body_elem = soup.find("div", class_=re.compile(r"aentry-post__text"))
    if not body_elem:
        body_elem = soup.find("div", class_=re.compile(r"aentry-post__content"))
    if not body_elem:
        body_elem = soup.find(["article", "div"], class_=re.compile(r"entry-content|asset-body|post-text"))

    if not body_elem:
        print(f"[-] Не найден контент статьи {url}")
        return

    # Локализуем картинки
    process_images_in_content(body_elem, post_id, url)

    clean_title = sanitize_yaml(title)
    if tags:
        tag_lines = [f'  - "{sanitize_yaml(t)}"' for t in tags]
        tags_yaml = "\n".join(tag_lines)
    else:
        tags_yaml = '  - "Без метки"'

    md_content = f"""---
id: {post_id}
title: "{clean_title}"
date: "{post_date_raw}"
original_url: "{url}"
permalink: /{post_id}.html
tags:
{tags_yaml}
---

# {title}

_{post_date_raw}_

{body_elem.decode_contents()}
"""

    with open(md_file, "w", encoding="utf-8") as f:
        f.write(md_content)

    tag_preview = f" [теги: {', '.join(tags)}]" if tags else ""
    print(f"[+] Пост {post_id}: {title[:40]}...{tag_preview}")


def main():
    urls = get_all_post_urls()
    if not urls:
        print("[-] Список постов пуст.")
        return

    total = len(urls)
    print(f"\n[*] Начинаем скачивание {total} постов в data/posts/...")
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{total}] ", end="")
        extract_post_data(url)
        time.sleep(0.3)

    print("\n[✔] Выгрузка блога полностью завершена! Все посты сохранены в data/posts/.")


if __name__ == "__main__":
    main()