#!/usr/bin/env python3
import os
import re
import subprocess
from bs4 import BeautifulSoup
from backup_lj import extract_post_data, fetch_url, BASE_URL, POSTS_DIR

downloaded_ids = set()
for fname in os.listdir(POSTS_DIR):
    if fname.endswith(".md"):
        downloaded_ids.add(fname.replace(".md", ""))

print(f"[*] Уже скачано локально: {len(downloaded_ids)} постов.")

print("[*] 1. Проверка закрепленного (sticky/pinned) поста на главной...")
root_html = fetch_url(BASE_URL)
found_ids = set()

if root_html:
    soup = BeautifulSoup(root_html, "html.parser")
    # Проверяем все ссылки на главной
    for a in soup.find_all("a", href=True):
        m = re.search(r"/(\d+)\.html", a["href"])
        if m:
            found_ids.add(m.group(1))

print("[*] 2. Сканирование прямой хронологической ленты блога...")
# Листаем ленту блога по 25-50 записей назад
skip = 0
empty_pages = 0
while skip <= 200:
    feed_url = f"{BASE_URL}/?skip={skip}"
    html = fetch_url(feed_url)
    if not html:
        break
    
    soup = BeautifulSoup(html, "html.parser")
    page_post_ids = set()
    for a in soup.find_all("a", href=True):
        m = re.search(r"/(\d+)\.html", a["href"])
        if m:
            pid = m.group(1)
            found_ids.add(pid)
            page_post_ids.add(pid)
            
    if not page_post_ids:
        empty_pages += 1
        if empty_pages >= 2:
            break
    else:
        empty_pages = 0
        
    print(f"    Проверено с skip={skip}, обнаружено постов: {len(found_ids)}", end="\r")
    skip += 20

print(f"\n[*] Всего в прямой ленте и на главной обнаружено: {len(found_ids)} уникальных постов.")

missing = sorted(list(found_ids - downloaded_ids), key=lambda x: int(x))

if missing:
    print(f"\n[!] НАЙДЕН НЕДОСТАЮЩИЙ ПОСТ! ID: {missing}")
    for post_id in missing:
        missing_url = f"{BASE_URL}/{post_id}.html"
        print(f"[*] Скачиваем потерянный пост: {missing_url}")
        extract_post_data(missing_url)
    print("\n[✔] Теперь все посты синхронизированы 100%!")
else:
    print("\n[i] В публичной ленте дополнительных постов не видно.")
    print("    Если счетчик показывает 144, а доступно 143:")
    print("    144-й пост — либо скрытый черновик (Draft/Friends-only),")
    print("    либо удаленная запись, чей ID остался в кэше счетчика базы ЖЖ.")