# Архитектура Edelstein Archive

## Общая схема

Edelstein Archive — статический сайт. Репозиторий GitHub хранит исходные Markdown-публикации, шаблоны Hugo, локальные статические ресурсы и часть исторических архивных копий. Cloudflare Pages получает изменения из GitHub, собирает сайт Hugo и публикует результат.

Упрощённый поток:

GitHub repository → Cloudflare Pages / Hugo build → static HTML, CSS, JS and images → readers

Для предварительной проверки изменений Cloudflare Pages создаёт Preview Deployment для Pull Request. Это подтверждено успешным Preview PR №3 от 5 ноября 2026 года.

Серверная CMS, пользовательская база данных и отдельный backend в текущей структуре репозитория не обнаружены.

## Hugo

### Конфигурация

Основной конфигурационный файл: config.toml.

Подтверждённые параметры:

- baseURL: https://edelstein-archive.pages.dev/
- languageCode: ru-ru
- заголовок сайта: «о. Георгий Эдельштейн — Архив записей»
- размер страницы пагинации: 200
- permalink для публикаций: /posts/:slug/
- taxonomy tag использует поле tags
- Goldmark renderer: unsafe = true

Параметр unsafe позволяет Hugo пропускать HTML из Markdown в итоговые страницы. В архиве действительно есть HTML-разметка и iframe-вставки. Поэтому отключение unsafe — отдельная миграционная задача, а не безопасная однострочная настройка.

Текущая версия Hugo, установленная в Cloudflare Pages, по конфигурации Git не подтверждена. В старом tracked public/index.html присутствует meta generator Hugo 0.111.3, но это характеристика сохранённого HTML-снимка, а не доказательство текущей версии сборки.

### Шаблоны

В репозитории обнаружены следующие Hugo layouts:

- layouts/_default/baseof.html — общий HTML-каркас, шапка, поиск, навигация и подвал.
- layouts/_default/list.html — списки публикаций.
- layouts/_default/single.html — отдельная публикация.
- layouts/index.html — главная страница.
- layouts/page/single.html — обычные страницы.
- layouts/search/single.html — страница поиска с клиентским JavaScript.

В layouts/_default/baseof.html:
- подключается Tailwind через внешний JavaScript CDN https://cdn.tailwindcss.com;
- подключаются шрифты Inter и Lora с Google Fonts;
- присутствуют inline CSS-стили;
- общая структура сайта и навигация.

В layouts/search/single.html присутствует inline JavaScript для клиентского поиска.

Тема Hugo в виде отдельного подключённого theme/module в корне репозитория не обнаружена; используются собственные layouts.

## Содержание

### Основные источники

- content/posts/ — 147 Markdown-файлов публикаций на main f7b3e8e.
- content/author.md — страница об авторе.
- content/search.md — страница поиска.

Публикации содержат Front Matter и текст. В отдельных материалах сохранён исходный HTML, включая архивные комментарии и встроенные медиа.

### Архивные копии

- data/posts/ — 143 файла с сохранёнными копиями публикаций, в основном с именами по ID LiveJournal.
- data/images/ — 4 архивные копии изображений.

Эти каталоги не являются полным зеркалом основных публикаций. На момент проверки в content/posts/ было 147 файлов, а в data/posts/ — 143.

Поиск по шаблонам не обнаружил ссылок на data/posts/ или data/images/. Они выглядят как отдельный архив исходных материалов, а не обязательная часть текущей сборки Hugo.

### Изображения, используемые сайтом

- static/images/ — 4 локальных изображения.
- data/images/ — те же 4 изображения в архивной копии.

Git blob SHA всех четырёх пар совпадают. В Markdown локальные изображения используют пути вида /images/..., которые Hugo публикует из static/images/.

Обнаружено одно внешнее изображение в архивированном комментарии публикации content/posts/2016-05-19-open-letter-patriarch-part2.md:
https://ic.pics.livejournal.com/errorzemlyan/76985471/2256/2256_300.jpg

Также в HTML встречаются внешние SVG-аватары LiveJournal. Не следует считать, что все медиа полностью локализованы.

## Статические ресурсы

В static/ обнаружены:

- четыре локальных изображения;
- robots.txt;
- llms.txt;
- HTML-файл подтверждения Google;
- HTML-файл подтверждения Yandex.

Файл static/_headers отсутствует. Следовательно, собственный набор HTTP-заголовков Cloudflare Pages через этот файл сейчас не задан в репозитории.

## Generated output: public/

Каталог public/ содержит сгенерированный HTML и изображения, но уже отслеживается Git. При этом .gitignore содержит правило public/, которое предотвращает добавление новых неотслеживаемых файлов, но не удаляет ранее отслеживаемые.

На момент проверки:
- в public/ было 500 файлов;
- найдено 141 HTML-страница публикации;
- в content/posts/ было 147 Markdown-публикаций.

Это расхождение означает, что tracked public/ нельзя автоматически считать актуальным отражением всех исходников. Не редактируй public/ вручную. Нужно отдельно проверить, используется ли он в текущем Cloudflare build configuration и нужен ли в Git вообще.

## Старый импортёр LiveJournal

В main на момент проверки всё ещё находятся:

- fetch_new_posts.py;
- .github/workflows/sync_posts.yml.

PR №2 удалил расписание workflow, но сохранил ручной workflow_dispatch. Workflow имеет contents: write, запускает Python-скрипт и передаёт ему GitHub Secret GEMINI_API_KEY. Скрипт загружает записи LiveJournal, генерирует метаданные через Gemini, пишет Markdown в content/posts/ и изображения в static/images/.

PR №3 (ветка maintenance/remove-legacy-importer) удаляет только эти два файла. Сохранённые публикации, архивные копии, изображения, Hugo layouts и конфигурация не меняются. Cloudflare сообщил об успешной сборке Preview для PR №3.

Последнее принятое направление — отказаться от этого импортёра. Не считать его частью будущей архитектуры и не запускать оставшийся workflow из main.

## Вспомогательная утилита

clean_tags_and_dates.py остаётся в корне репозитория. Она не является частью импортёра LiveJournal и не вызывается шаблонами Hugo. В ней есть жёстко заданный абсолютный путь /home/sergeishevchenko/edelstein-site/content/posts/, поэтому перед запуском в другой среде путь нужно проверить.

## Cloudflare Pages и GitHub

GitHub является хранилищем исходников и истории изменений. Cloudflare Pages выполняет сборку и публикацию; для PR создаёт Preview Deployments.

Из GitHub repository не удалось установить:
- точную текущую версию Hugo в Cloudflare;
- build command и output directory проекта;
- настройки production/preview branches;
- настройки домена и HTTPS;
- значения переменных и секретов Cloudflare.

Эти параметры находятся в Cloudflare dashboard. Не выдумывай их и не выводи из старого public/ снимка.

На уровне GitHub:
- default branch — main;
- repository rulesets endpoint вернул пустой список;
- classic branch protection endpoint не удалось прочитать из-за 403 connector permission;
- поэтому фактические правила защиты main остаются непроверенными.

## Безопасность и границы доверия

Подтверждённые наблюдения:

1. Goldmark unsafe = true, поэтому HTML из Markdown может попадать в output.
2. В публикациях есть iframe-вставки сторонних медиасервисов.
3. Общий шаблон загружает внешний JavaScript Tailwind CDN и Google Fonts.
4. Search layout содержит inline JavaScript.
5. static/_headers отсутствует.
6. Одно внешнее изображение в архивированном комментарии не сохранено локально.

GitHub code search не нашёл буквальных совпадений по отдельным запросам onerror, onclick, onload и javascript:. Это предварительный поиск, а не полный аудит HTML и не доказательство отсутствия XSS.

До инвентаризации HTML нельзя безопасно включать строгую CSP или отключать unsafe: сначала нужно учесть iframe, inline-стили, inline-скрипт поиска и внешние ресурсы. Cloudflare Preview build подтверждает успешную сборку, но не заменяет security review.
