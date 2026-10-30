#!/usr/bin/env python3
import glob
import re

print("Начинаем очистку тегов и удаление вшитых дат...")

file_list = glob.glob("/home/sergeishevchenko/edelstein-site/content/posts/*.md")

# Регулярное выражение для поиска английской даты в самом начале текста (с учетом курсива _ или *)
months = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
# Ищет строки вида: _September 23 2026, 19:45_ или *October 15, 2026*
date_pattern = re.compile(rf'^\s*(?:<[^>]+>|[_*])*\s*{months}\s+\d{{1,2}}[,\s]+\d{{4}}(?:,\s+\d{{2}}:\d{{2}}(?::\d{{2}})?)?\s*(?:<[^>]+>|[_*])*\s*', re.IGNORECASE)

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

    # 1. Очистка и дедупликация тегов
    lines = fm.strip().split('\n')
    new_lines = []
    in_tags = False
    post_tags = set()
    
    for line in lines:
        if line.startswith('tags:'):
            in_tags = True
            new_lines.append(line)
        elif in_tags and line.strip().startswith('-'):
            # Извлекаем сам тег
            m = re.match(r'^\s*-\s*["\']?(.*?)["\']?\s*$', line)
            if m:
                raw_tag = m.group(1).strip()
                if raw_tag:
                    # Нормализуем: первая буква заглавная, остальные строчные (богословие -> Богословие)
                    norm_tag = raw_tag[0].upper() + raw_tag[1:].lower()
                    if norm_tag not in post_tags:
                        post_tags.add(norm_tag)
                        global_tags.add(norm_tag)
                        new_lines.append(f'  - "{norm_tag}"')
        elif in_tags and re.match(r'^[a-zA-Z0-9_-]+:', line):
            in_tags = False
            new_lines.append(line)
        elif not in_tags:
            new_lines.append(line)

    fm_cleaned = '\n'.join(new_lines) + '\n'

    # 2. Удаление вшитой английской даты из самого начала статьи
    original_body = body
    body_cleaned = date_pattern.sub('', body, count=1)
    
    if original_body != body_cleaned:
        cleaned_dates += 1

    # Сохраняем файл
    new_content = f"---{fm_cleaned}---{body_cleaned}"
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
        
    processed_files += 1

print(f"Готово! Обработано файлов: {processed_files}")
print(f"Удалено вшитых дат из текстов: {cleaned_dates}")
print(f"Всего уникальных нормализованных тегов на сайте: {len(global_tags)}")