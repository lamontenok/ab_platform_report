# MVP AI-агент для отчёта по A/B Testing новостям

Ниже максимально простой путь для новичка.

## 1) Структура папки

```text
ab_platform_report/
├─ agent.py            # основной скрипт-агент
├─ requirements.txt    # зависимости Python
├─ .env.example        # пример переменных окружения
├─ README.md           # инструкция по запуску
└─ report_preview.txt  # появится после тестового dry-run
```

## 2) Установка библиотек

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3) Настройка переменных окружения

1. Скопируйте шаблон:

```bash
cp .env.example .env
```

2. Откройте `.env` и заполните значения:
- `RSS_FEEDS` — ваши RSS-источники через запятую.
- `OPENAI_API_KEY` — API-ключ OpenAI.
- `OPENAI_MODEL` — модель (можно оставить `gpt-4.1-mini`).
- `MAX_PER_FEED` — сколько новостей брать с одного RSS-источника.
- `EMAIL_TO` — куда отправлять отчёт.
- `EMAIL_FROM` — от кого отправлять (обычно тот же Gmail).
- `GMAIL_USER` — Gmail логин.
- `GMAIL_APP_PASSWORD` — пароль приложения Gmail (App Password).

> Важно: нужен именно **App Password**, обычный пароль Gmail не сработает.

---

## 4) Как протестировать функционал по шагам (рекомендуется)

### Шаг 1. Проверить, что код вообще запускается

```bash
python -m py_compile agent.py
```

### Шаг 2. Тест без OpenAI и без отправки письма (безопасный тест)

Этот режим позволит проверить RSS + разбиение на группы + сбор отчёта.

```bash
python agent.py --dry-run --skip-llm
```

Что произойдёт:
- скрипт прочитает RSS,
- разделит новости на `Россия` / `Мир`,
- сделает простой тестовый анализ (без OpenAI),
- сохранит отчёт в `report_preview.txt`,
- выведет отчёт в консоль,
- письмо отправлять не будет.

### Шаг 3. Тест с OpenAI, но всё ещё без отправки письма

Проверьте качество summary/insights от модели.

```bash
python agent.py --dry-run
```

### Шаг 4. Полный запуск с отправкой на email

```bash
python agent.py
```

---

## 5) Что нужно сделать, чтобы отчёт пришёл именно вам на почту

1. В `.env` укажите:
   - `EMAIL_TO=ваш_адрес@gmail.com`
2. Проверьте Gmail аккаунт отправителя:
   - включена 2FA,
   - создан App Password,
   - `GMAIL_USER` и `EMAIL_FROM` совпадают с этим Gmail.
3. Запустите полный сценарий:

```bash
python agent.py
```

4. Если письма нет во "Входящих", проверьте:
   - папку "Спам",
   - нет ли ошибки в терминале при логине SMTP,
   - правильный ли `GMAIL_APP_PASSWORD`.

---

## 6) Какие шаги A-G уже реализованы

- **A) Основной файл `agent.py`** — создан.
- **B) Парсинг RSS** — функция `parse_rss_feeds`.
- **C) Разделение Россия/Мир** — функция `split_news_by_region`.
- **D) Анализ через LLM (OpenAI API)** — функция `analyze_group_with_llm`.
- **E) Красивый текстовый отчёт** — функция `format_report`.
- **F) Отправка email через SMTP Gmail** — функция `send_email_report`.
- **G) Как запускать и что заполнить** — в этом `README` + `.env.example`.

---

## 7) Коротко про новые флаги запуска

- `--dry-run` — не отправлять email, только собрать и показать отчёт.
- `--skip-llm` — не вызывать OpenAI API, использовать простой анализ для теста.
- `--max-per-feed N` — временно взять `N` новостей на RSS-ленту.

Пример:

```bash
python agent.py --dry-run --skip-llm --max-per-feed 5
```
