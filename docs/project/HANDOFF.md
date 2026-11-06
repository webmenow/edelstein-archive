# Передача текущей работы

**Обновлено:** 2026-11-06  
**Репозиторий:** webmenow/edelstein-archive  
**Основная ветка:** main  
**Базовый commit main:** f7b3e8e6fba4c8f4dfae2bd89847a7f726f67e5c  
**Ветка текущей документации:** docs/project-baseline

## Текущая точка

Исторические переписки из двух предыдущих чатов изучены и сопоставлены с GitHub. Создана документация проекта в отдельной ветке:

- AGENTS.md
- docs/project/PROJECT_STATUS.md
- docs/project/ARCHITECTURE.md
- docs/project/DECISIONS.md
- docs/project/HANDOFF.md

В main документация ещё не находится. Код сайта, контент, изображения, конфигурация Hugo и настройки Cloudflare не изменялись.

## Последнее архитектурное решение

Владелец решил отказаться от старого импортёра LiveJournal и его GitHub Actions workflow. Сохраняются Hugo, архивные публикации и Cloudflare Pages.

Это решение подготовлено в PR №3:
- PR: https://github.com/webmenow/edelstein-archive/pull/3
- ветка: maintenance/remove-legacy-importer
- head: 8290dca8c7567fb1374eacdc4f6514cf00fbee02
- статус: Draft, открыт, не слит
- изменения: удаление .github/workflows/sync_posts.yml и fetch_new_posts.py
- Cloudflare Preview сообщил об успешной сборке
- визуальная проверка Preview пользователем ещё не подтверждена

## Следующие действия

1. Открой Preview PR №3 в обычном браузере:
   - https://b08735cf.edelstein-archive.pages.dev/
   - https://maintenance-remove-legacy-im.edelstein-archive.pages.dev/
2. Проверь главную страницу и несколько публикаций, в том числе страницы с локальными изображениями и HTML/iframe-вставками.
3. Если результат приемлем, владелец может принять решение о слиянии PR №3. Не выполняй merge автоматически.
4. После слияния PR №3 удали GitHub Secret GEMINI_API_KEY вручную в Settings → Secrets and variables → Actions, если он ещё существует. Подключённый GitHub-инструмент не позволяет проверить или удалить secret.
5. Отдельно реши судьбу PR №1. Не сливай его как есть: он содержит старый импортёр, workflow и дополнительный файл публикации LiveJournal №38505 с тем же original_url и alias, что уже есть в main. PR №1 остаётся Draft и расходится с текущим main.
6. После удаления импортёра проведи отдельный аудит безопасности уже сохранённого HTML-контента: iframe, inline styles/scripts, внешние ресурсы и Goldmark unsafe.
7. Отдельно реши, что делать с tracked public/: он исключён в .gitignore, но уже отслеживается Git; обнаружено 141 сгенерированное пространство страниц публикаций против 147 исходных Markdown-файлов.
8. Проверь Cloudflare Pages build settings и classic branch protection через соответствующие интерфейсы. Текущий GitHub connector не смог прочитать classic branch protection.

## Важные ограничения для следующего агента

- Не запускать старый workflow Sync LJ Posts в main.
- Не редактировать main напрямую.
- Не удалять и не перезаписывать архивные публикации и изображения.
- Не отключать Goldmark unsafe и не включать строгую CSP без проверки существующих iframe, inline JavaScript/CSS и внешних доменов.
- Не редактировать public/ вручную.
- Не считать PR №3 слитым: он остаётся открытым Draft.
- Не считать GitHub Secret удалённым: это не проверено.
- Не заявлять о визуальной проверке Preview: Cloudflare build успешен, но Preview не удалось открыть через доступный веб-инструмент.

## Как продолжать в новом чате

1. Прочитать AGENTS.md, PROJECT_STATUS.md и этот файл.
2. Проверить актуальные refs и PR на GitHub; указанные SHA — снимок на дату обновления.
3. Перед любыми изменениями проверить текущую ветку и HEAD.
4. Выполнять следующую задачу отдельным небольшим этапом и фиксировать результат в Git.
