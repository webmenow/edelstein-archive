#!/usr/bin/env python3
import glob
import re
import os

print("Начинаем очистку тегов и удаление вшитых дат...")

file_list = glob.glob("/home/sergeishevchenko/edelstein-site/content/posts/*.md")

EN_MONTHS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december"
]
RU_MONTHS = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря"
]

all_months_regex = "|".join(EN_MONTHS + RU_MONTHS)

# Регулярное выражение для обнаружения строки даты ЖЖ (напр. October 20 2026, 11:26 или _20 октября 2026, 11:26_)
date_line_re = re.compile(
    rf'^\s*(?:<p[^>]*>)?\s*(?:[_*]|<em[^>]*>|<strong[^>]*>)?\s*'
    rf'((?:(?:{all_months_regex})\s+\d{{1,2}}[,\s]+\d{{4}}|\d{{1,2}}\s+(?:{all_months_regex})\s+\d{{4}})'
    rf'(?:[,\s-]+\d{{1,2}}:\d{{2}}(?::\d{{2}})?)?(?:\s*(?:UTC|GMT))?)'
    rf'\s*(?:[_*]|</em>|</strong>)?\s*(?:</p>)?\s*$',
    re.IGNORECASE
)

processed_files = 0
cleaned_dates = 0
global_tags = set()

for path in file_list:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if not content.startswith("---"):
        continue

    parts = content.split("---", 2)
    if len(parts) < 3:
        continue

    fm, body = parts[1], parts[2]

    # --- 1. Очистка и нормализация тегов ---
    fm_lines = fm.strip().split("\n")
    new_fm_lines = []
    in_tags = False
    post_tags = set()
    cleaned_post_tags = []

    for line in fm_lines:
        if line.startswith("tags:"):
            in_tags = True
            new_fm_lines.append("tags:")
        elif in_tags and line.strip().startswith("-"):
            m = re.match(r'^\s*-\s*["\']?(.*?)["\']?\s*$', line)
            if m:
                raw_tag = m.group(1).strip()
                if raw_tag:
                    # Приводим к стандарту: Первая буква заглавная, остальные строчные
                    norm_tag = raw_tag[0].upper() + raw_tag[1:].lower()
                    if norm_tag not in post_tags:
                        post_tags.add(norm_tag)
                        global_tags.add(norm_tag)
                        cleaned_post_tags.append(f'  - "{norm_tag}"')
        elif in_tags and re.match(r'^[a-zA-Z0-9_-]+:', line):
            in_tags = False
            new_fm_lines.extend(cleaned_post_tags)
            new_fm_lines.append(line)
        elif not in_tags:
            new_fm_lines.append(line)

    if in_tags:
        new_fm_lines.extend(cleaned_post_tags)

    fm_cleaned = "\n".join(new_fm_lines) + "\n"

    # --- 2. Поиск и удаление даты в начале текста ---
    body_lines = body.split("\n")
    new_body_lines = []
    date_removed_for_file = False
    
    # Проверяем первые 10 непустых строк тела поста
    checked_lines = 0
    i = 0
    while i < len(body_lines):
        line = body_lines[i]
        stripped = line.strip()

        # Пропускаем пустые строки в самом начале
        if not stripped and not date_removed_for_file and checked_lines == 0:
            i += 1
            continue

        if not date_removed_for_file and checked_lines < 8:
            checked_lines += 1
            if date_line_re.match(stripped):
                # Нашли строку с датой ЖЖ — удаляем её
                date_removed_for_file = True
                cleaned_dates += 1
                i += 1
                # Также пропускаем идущую сразу за ней пустую строку
                if i < len(body_lines) and not body_lines[i].strip():
                    i += 1
                continue

        new_body_lines.append(line)
        i += 1

    body_cleaned = "\n" + "\n".join(new_body_lines).lstrip("\n")

    # Перезаписываем файл
    new_content = f"---{fm_cleaned}---{body_cleaned}"
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)

    processed_files += 1

print(f"Готово! Обработано файлов: {processed_files}")
print(f"Удалено вшитых дат из текстов: {cleaned_dates}")
print(f"Всего уникальных нормализованных тегов на сайте: {len(global_tags)}")