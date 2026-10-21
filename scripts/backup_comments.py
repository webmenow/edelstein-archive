#!/usr/bin/env python3
import os
import re
import time
import json
import subprocess
from html import unescape

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
POSTS_DIR = os.path.join(DATA_DIR, "posts")

USERNAME = "g-edelstein"
BASE_URL = f"https://{USERNAME}.livejournal.com"


def fetch_url(url):
    """Выполняет запрос через curl с десктопным User-Agent."""
    cmd = [
        "curl",
        "-sSL",
        "--connect-timeout", "15",
        "--max-time", "45",
        "-A", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        url
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
        return res.stdout.decode("utf-8", errors="replace")
    except Exception as e:
        print(f"\n[!] Ошибка curl {url}: {e}")
        return None


def clean_comment_body(html_text):
    """Очищает HTML тела комментария от служебных тегов ЖЖ."""
    if not html_text:
        return ""
    cleaned = re.sub(r'<p>\s*<a href="[^"]*#(?:reply|t\d+)"[^>]*>.*?</a>\s*</p>', '', html_text, flags=re.IGNORECASE)
    cleaned = re.sub(r'<div class="item-actions"[^>]*>.*?</div>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<p>\s*</p>', '', cleaned)
    return cleaned.strip()


def extract_comments_from_html(html):
    """
    Извлекает массив комментариев из встроенного объекта Site.page десктопной темы post2017.
    """
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

        # Автор
        author = item.get("uname") or item.get("dname") or "Аноним"
        if not author and item.get("username"):
            u_info = item.get("username")
            if isinstance(u_info, list) and len(u_info) > 0 and isinstance(u_info[0], dict):
                author = u_info[0].get("username") or "Аноним"

        # Дата
        date_str = item.get("ctime") or item.get("stime") or ""

        # Текст
        body = item.get("article") or item.get("body") or ""
        body = clean_comment_body(body)

        # Тема / Subject комментария
        subject = item.get("subject") or ""

        thread_id = item.get("thread") or item.get("dtalkid") or item.get("talkid") or 0
        parent_id = item.get("parent") or 0

        # Если комментарий удален
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


def fetch_exact_parent_map(post_id, comments):
    """
    Извлекает реальную карту 'comment_id -> parent_id' из LiveJournal,
    опрашивая базовую страницу поста и треды дискуссий.
    """
    parent_map = {}

    def extract_pairs(html_content):
        if not html_content:
            return
        # Ищем все пары "thread": X ... "parent": Y через регулярное выражение
        # Это работает надежно и в JSON Site.page, и в ответах тредов
        pattern = re.compile(r'["\']thread["\']\s*:\s*(\d+).*?["\']parent["\']\s*:\s*(\d+)', re.DOTALL)
        for m in pattern.finditer(html_content):
            cid, pid = int(m.group(1)), int(m.group(2))
            if cid > 0 and pid > 0:
                parent_map[cid] = pid

        # Обратный порядок ключей parent/thread
        pattern_rev = re.compile(r'["\']parent["\']\s*:\s*(\d+).*?["\']thread["\']\s*:\s*(\d+)', re.DOTALL)
        for m in pattern_rev.finditer(html_content):
            pid, cid = int(m.group(1)), int(m.group(2))
            if cid > 0 and pid > 0:
                parent_map[cid] = pid

    # 1. Запрос базовой страницы поста (дерево первого экрана)
    base_html = fetch_url(f"{BASE_URL}/{post_id}.html")
    extract_pairs(base_html)

    # 2. Опрашиваем треды основных дискуссий (до 10 ключевых веток)
    # Корневыми являются комментарии первого уровня или с длинными ответами
    thread_ids = [c["id"] for c in comments if c.get("id")]
    for tid in thread_ids[:10]:
        t_html = fetch_url(f"{BASE_URL}/{post_id}.html?thread={tid}")
        extract_pairs(t_html)
        time.sleep(0.04)

    return parent_map


def reconstruct_conversational_tree(comments, post_id=None):
    """
    Восстанавливает естественное дерево диалогов:
    1. По серверной карте parent_id из ЖЖ.
    2. По семантическим цепочкам ответов.
    """
    if not comments:
        return []

    tree_comments = [dict(c) for c in comments]
    all_ids = {c["id"] for c in tree_comments}

    # 1. Получаем серверную карту связей
    exact_map = fetch_exact_parent_map(post_id, tree_comments) if post_id else {}

    for c in tree_comments:
        cid = c["id"]
        if cid in exact_map and exact_map[cid] in all_ids:
            c["parent_id"] = exact_map[cid]

    # 2. Семантические связи для случаев, когда родитель не был передан сервером
    for idx, c in enumerate(tree_comments):
        if c["parent_id"] != 0 and c["parent_id"] in all_ids:
            continue

        body = c.get("body", "").lower()
        assigned = 0

        # Ответы отца Георгия
        if "дорогой владимир" in body:
            for prev in tree_comments[:idx]:
                if "vladimir" in prev["author"].lower() or "владимир" in prev["author"].lower():
                    assigned = prev["id"]
        elif "спасибо, анна" in body:
            for prev in tree_comments[:idx]:
                if "анна" in prev["author"].lower() or "зуева" in prev["author"].lower() or "3774635" in prev["author"]:
                    assigned = prev["id"]
        elif "дорогая, марина" in body:
            for prev in tree_comments[:idx]:
                if "marina" in prev["author"].lower():
                    assigned = prev["id"]
        elif "дорогой afanasii1" in body:
            for prev in tree_comments[:idx]:
                if "afanasii1" in prev["author"].lower():
                    assigned = prev["id"]
        elif "уважаемый cui_bono_cui" in body:
            for prev in tree_comments[:idx]:
                if "cui_bono_cui" in prev["author"].lower():
                    assigned = prev["id"]
        elif "греко-католик" in body and "сибирь" in body:
            for prev in tree_comments[:idx]:
                if "eusevius" in prev["author"].lower():
                    assigned = prev["id"]
        elif "пересвет" in body and "осляб" in body:
            for prev in tree_comments[:idx]:
                if "пересвет" in prev.get("body", "").lower():
                    assigned = prev["id"]

        if assigned:
            c["parent_id"] = assigned

    return sort_comments_into_tree(tree_comments)


def sort_comments_into_tree(comments):
    """
    Выстраивает комментарии в дерево диалогов:
    Родитель -> Непосредственный ответ -> Ответ на ответ.
    Смещение: от 0 до 3 уровней (0, 1.5rem, 3.0rem, 4.5rem).
    """
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
            # Ограничиваем отступ максимум 3 уровнями (0.0, 1.5, 3.0, 4.5rem)
            node_copy["depth"] = min(depth, 3)
            ordered.append(node_copy)
            traverse(node["id"], depth + 1)

    traverse(0, 0)

    # Если какие-то узлы не попали в дерево
    seen = {c["id"] for c in ordered}
    for c in comments:
        if c["id"] not in seen:
            node_copy = dict(c)
            node_copy["depth"] = 0
            ordered.append(node_copy)

    return ordered


def fetch_all_comments_for_post(post_id):
    """
    Выкачивает ВСЕ страницы комментариев десктопного ЖЖ (?view=flat&page=N).
    """
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
        time.sleep(0.08)

    # Восстанавливаем дерево диалогов с учетом официальных серверных parent_id
    return reconstruct_conversational_tree(all_comments, post_id=post_id)


def render_comments_html(comments):
    """Рендерит чистый и аккуратный блок архивных комментариев с лесенкой веток."""
    if not comments:
        return ""

    total = len(comments)
    html = [
        f'\n\n<section class="lj-comments-archive" style="margin-top: 3.5rem; border-top: 2px solid #e5e7eb; padding-top: 2rem;">',
        f'  <details style="background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.25rem 1.5rem;">',
        f'    <summary style="cursor: pointer; font-weight: 600; font-size: 1.15rem; color: #111827; user-select: none;">💬 Архив комментариев из ЖЖ ({total})</summary>',
        f'    <div class="comments-list" style="margin-top: 1.5rem;">'
    ]

    for idx, c in enumerate(comments, 1):
        is_author = "edelstein" in c["author"].lower()
        border_color = "#b91c1c" if is_author else "#3b82f6"
        author_color = "#991b1b" if is_author else "#1e40af"
        bg_card = "#fffbfb" if is_author else "#ffffff"
        badge = ' <span style="font-size: 0.72rem; background: #fee2e2; color: #991b1b; padding: 2px 7px; border-radius: 4px; font-weight: 600; margin-left: 6px;">автор</span>' if is_author else ''
        margin_left = c.get("depth", 0) * 1.5

        subj_html = f'<div style="font-weight: 600; font-size: 0.95rem; margin-bottom: 0.35rem; color: #1f2937;">{unescape(c["subject"])}</div>' if c.get("subject") else ""

        entry = f'''      <article class="comment-entry" id="cmt-{idx}" style="margin-left: {margin_left}rem; margin-bottom: 1.1rem; padding: 0.9rem 1.1rem; background: {bg_card}; border: 1px solid #e5e7eb; border-left: 4px solid {border_color}; border-radius: 6px; font-size: 0.95rem;">
        <header style="font-size: 0.85rem; color: #6b7280; margin-bottom: 0.45rem; display: flex; flex-wrap: wrap; gap: 0.6rem; align-items: center;">
          <strong style="color: {author_color}; font-size: 0.95rem;">{c["author"]}</strong>{badge}
          <time style="color: #9ca3af; font-size: 0.8rem;">{c["date"]}</time>
        </header>
        {subj_html}
        <div class="comment-body" style="line-height: 1.6; color: #374151;">
          {c["body"]}
        </div>
      </article>'''
        html.append(entry)

    html.append('    </div>\n  </details>\n</section>\n')
    return "\n".join(html)


def process_post(md_filename):
    post_id = md_filename.replace(".md", "")
    md_path = os.path.join(POSTS_DIR, md_filename)

    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Очищаем старый блок комментариев, если он там уже был
    if '<section class="lj-comments-archive"' in content:
        content = re.sub(r'\n*<section class="lj-comments-archive".*?</section>\n*', '', content, flags=re.DOTALL)

    comments = fetch_all_comments_for_post(post_id)

    if comments:
        markup = render_comments_html(comments)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(content.strip() + markup)
        print(f"[+] Пост {post_id}: сохранено {len(comments)} коммент. (со всех страниц)")
    else:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")
        print(f"[-] Пост {post_id}: 0 комментариев.")


def main():
    md_files = sorted(
        [f for f in os.listdir(POSTS_DIR) if f.endswith(".md")],
        key=lambda x: int(x.replace(".md", ""))
    )
    total = len(md_files)
    print(f"[*] Точная выгрузка дерева комментариев (?view=flat) для {total} постов...")

    for i, md_f in enumerate(md_files, 1):
        print(f"[{i}/{total}] ", end="")
        process_post(md_f)
        time.sleep(0.15)

    print("\n[✔] Все посты успешно обновлены чистыми комментариями, реальными авторами и лесенкой веток!")


if __name__ == "__main__":
    main()