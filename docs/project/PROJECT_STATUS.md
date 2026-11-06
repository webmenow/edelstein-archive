# Состояние проекта

**Дата проверки:** 2026-11-06  
**Репозиторий:** webmenow/edelstein-archive  
**Основная ветка:** main  
**Проверенный HEAD main:** f7b3e8e6fba4c8f4dfae2bd89847a7f726f67e5c  
**Ветка документации:** docs/project-baseline (создана от указанного HEAD)

## Кратко о проекте

Edelstein Archive — статический архив публикаций протоиерея Георгия Эдельштейна. Сайт построен на Hugo и публикуется через Cloudflare Pages с GitHub. Тексты и локальные изображения хранятся в репозитории; для сборки уже сохранённых публикаций импортёр LiveJournal не требуется.

Последнее подтверждённое архитектурное решение — отказаться от старого импортёра LiveJournal и его GitHub Actions workflow. Это решение подготовлено в PR №3, но ещё не слито.

## Состояние GitHub

Репозиторий публичный, не архивирован. Подключённый GitHub-доступ имеет права admin/push/pull. Default branch — main.

| Объект | Состояние на момент проверки |
|---|---|
| main | HEAD f7b3e8e; содержит опубликованную статью от 4 ноября 2026 |
| PR №1 — Умеренная переработка: безопасность импорта и CI | Открыт, Draft, не слит; ветка security/moderate-hardening отстаёт от main на 1 коммит и расходится с ним |
| PR №2 — Отключить расписание старого импортёра | Закрыт и слит; merge commit 79416b359966d85f92ba227e17cd37c9f6c3d248 |
| PR №3 — Remove legacy LiveJournal importer | Открыт, Draft, не слит; ветка maintenance/remove-legacy-importer основана на текущем main и опережает его на 2 коммита |
| docs/project-baseline | Ветка для документации; исходная точка — main f7b3e8e |

В PR №3 изменены только два файла: удаляются .github/workflows/sync_posts.yml и fetch_new_posts.py. Другие файлы не затронуты.

### Проверки PR №3

- Cloudflare Pages оставил комментарий об успешном Preview Deployment для commit 8290dca8c7567fb1374eacdc4f6514cf00fbee02.
- Preview URL: https://b08735cf.edelstein-archive.pages.dev/
- Branch Preview URL: https://maintenance-remove-legacy-im.edelstein-archive.pages.dev/
- Через доступный веб-инструмент открыть preview не удалось; визуальная проверка человеком не подтверждена.
- Для commit PR №3 GitHub connector не вернул статусов CI и workflow runs. Это не означает, что Cloudflare build не запускался: его успешный статус подтверждён отдельным комментарием Cloudflare.

### Состояние старой автоматизации

PR №2 удалил расписание раз в шесть часов, но оставил workflow_dispatch. Поэтому в текущем main старый workflow всё ещё можно запустить вручную. Он имеет permissions: contents: write, запускает fetch_new_posts.py и использует secret GEMINI_API_KEY. Не запускай его.

После слияния PR №3 workflow и импортёр будут удалены. GitHub Secret GEMINI_API_KEY потребуется удалить вручную в Settings → Secrets and variables → Actions. Состояние самого секрета через подключённый GitHub API не проверено; удаление секрета не выполнено.

## Сохранность публикаций и изображений

Подсчёты выполнены по Git tree main и PR №3:

| Путь | Файлов | Назначение / статус |
|---|---:|---|
| content/posts/ | 147 | Основные Markdown-публикации Hugo |
| data/posts/ | 143 | Отдельные сохранённые копии исходных публикаций |
| data/images/ | 4 | Архивные копии локальных изображений |
| static/images/ | 4 | Локальные изображения, используемые сайтом |
| public/ | 500 | Сгенерированные файлы, также закоммиченные в Git |

Все 4 пары изображений в data/images/ и static/images/ имеют одинаковые Git blob SHA. PR №3 не изменяет ни одну публикацию или изображение: его diff содержит только два удаления, указанных выше.

Число файлов data/posts/ меньше числа content/posts/ на четыре. Поэтому data/posts/ нельзя считать полным зеркалом всех 147 публикаций.

В content/posts/2016-05-19-open-letter-patriarch-part2.md обнаружено внешнее изображение из архивированного комментария: https://ic.pics.livejournal.com/errorzemlyan/76985471/2256/2256_300.jpg. Оно не локализовано в static/images/. В старых публикациях также встречаются внешние аватары LiveJournal.

Поиск по репозиторию не обнаружил ссылок на fetch_new_posts.py и GEMINI_API_KEY вне удаляемых workflow/скрипта. В шаблонах не обнаружены ссылки на data/posts/ или data/images/. Это подтверждает, что сохранённый сайт не использует импортёр как часть сборки.

## Текущая техническая картина

- Hugo-конфигурация находится в config.toml.
- Hugo Goldmark настроен с markup.goldmark.renderer.unsafe = true.
- layouts/_default/baseof.html загружает Tailwind через https://cdn.tailwindcss.com и шрифты через Google Fonts.
- layouts/search/single.html содержит inline JavaScript.
- В content/posts/ есть HTML-вставки iframe, в частности для внешних медиасервисов. Их нельзя удалять или блокировать без инвентаризации.
- static/_headers отсутствует.
- .gitignore исключает public/, но public/ уже отслеживается Git. В public/ обнаружено 141 сгенерированное пространство страниц публикаций против 147 Markdown-источников. Это несоответствие требует отдельной проверки; public/ не следует считать актуальным источником сайта.
- clean_tags_and_dates.py сохранён. Это отдельная утилита, не часть импортёра; в ней используется абсолютный локальный путь /home/sergeishevchenko/edelstein-site/content/posts/.
- В репозитории нет отдельного package.json, go.mod или Hugo module manifest.
- В репозитории нет static/_headers.
- Cloudflare build settings и настройки домена находятся вне GitHub-репозитория и не проверены напрямую.

## Настройки защиты GitHub

- Запрос списка repository rulesets вернул пустой массив.
- Чтение classic branch protection для main завершилось 403 Resource not accessible by integration. Поэтому состояние классической защиты ветки не подтверждено.
- Наличие или отсутствие обязательных проверок, CODEOWNERS и 2FA не следует считать подтверждённым этим аудитом.

## Приоритетные незавершённые вопросы

1. Просмотреть PR №3 Preview в обычном браузере и подтвердить визуальную корректность. После этого владелец может решить, сливать ли PR №3.
2. После слияния PR №3 вручную удалить GEMINI_API_KEY, если секрет ещё существует.
3. Не сливать PR №1 как есть: он содержит устаревший импортёр и вторую публикацию с тем же original_url/alias, что и запись в main. Решение о закрытии PR №1 ещё не принято.
4. Провести отдельную инвентаризацию HTML в content/posts/: iframe, inline-стили, разрешённые теги и атрибуты, внешние ресурсы.
5. Только после инвентаризации решать вопрос об отключении Goldmark unsafe, CSP и HTTP Security Headers.
6. Отдельно рассмотреть локальную сборку Tailwind и шрифтов, не смешивая эту работу с текущим удалением импортёра.
7. Проверить актуальность tracked public/ и решить, следует ли хранить generated output в Git.
8. Проверить настройки Cloudflare Pages и classic branch protection через интерфейсы, доступ к которым не предоставил текущий connector.

## Границы проверки

Это состояние подтверждено GitHub tree, файлами main, PR metadata/diff, Cloudflare-комментарием о Preview Deployment и двумя историческими переписками, предоставленными владельцем.

Не выполнялись:
- слияние PR №3;
- запуск GitHub Actions;
- локальная сборка Hugo;
- полный скан всех HTML-фрагментов на XSS;
- визуальная проверка Preview в браузере;
- чтение Cloudflare account settings;
- чтение classic branch protection;
- проверка/удаление GitHub Secret.
