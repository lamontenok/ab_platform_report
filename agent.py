"""
MVP AI-агент для новостей про A/B-тестирование и experimentation platforms.

Что делает скрипт:
1) Читает новости из RSS-лент.
2) Делит новости на группы: Россия и Мир.
3) Анализирует группы через OpenAI API (summary + insights).
4) Собирает итоговый текстовый отчёт.
5) Отправляет отчёт на email через Gmail SMTP.

Важно: это учебный MVP, поэтому код максимально простой и с подробными комментариями.
"""

from __future__ import annotations

import argparse
import os
import ssl
import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict

import feedparser
from dotenv import load_dotenv
from openai import OpenAI


# Загружаем переменные окружения из файла .env (если он есть)
load_dotenv()


@dataclass
class NewsItem:
    """Простая структура для одной новости."""

    title: str
    link: str
    source: str
    published: str
    summary: str


@dataclass
class Config:
    """Все настройки приложения в одном месте, чтобы было удобно."""

    rss_feeds: List[str]
    openai_api_key: str
    openai_model: str
    smtp_host: str
    smtp_port: int
    gmail_user: str
    gmail_app_password: str
    email_from: str
    email_to: str
    max_per_feed: int


def get_config() -> Config:
    """
    Читаем конфиг из переменных окружения.

    Почему так:
    - пароли и ключи не храним прямо в коде;
    - можно запускать один и тот же код в разных окружениях.
    """
    rss_raw = os.getenv("RSS_FEEDS", "")
    rss_feeds = [url.strip() for url in rss_raw.split(",") if url.strip()]

    return Config(
        rss_feeds=rss_feeds,
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        gmail_user=os.getenv("GMAIL_USER", ""),
        gmail_app_password=os.getenv("GMAIL_APP_PASSWORD", ""),
        email_from=os.getenv("EMAIL_FROM", os.getenv("GMAIL_USER", "")),
        email_to=os.getenv("EMAIL_TO", ""),
        max_per_feed=int(os.getenv("MAX_PER_FEED", "10")),
    )


def parse_rss_feeds(feed_urls: List[str], max_per_feed: int = 10) -> List[NewsItem]:
    """
    Парсим RSS-ленты и собираем новости в единый список.

    max_per_feed ограничивает количество новостей с одного источника,
    чтобы отчёт не был слишком большим.
    """
    all_news: List[NewsItem] = []

    for url in feed_urls:
        feed = feedparser.parse(url)

        # Если RSS-лента не читается, не падаем, а просто идём дальше.
        # Так один проблемный источник не ломает весь отчёт.
        if getattr(feed, "bozo", False):
            print(f"[WARN] Не удалось корректно прочитать RSS: {url}")

        source = feed.feed.get("title", url)

        for entry in feed.entries[:max_per_feed]:
            title = entry.get("title", "Без заголовка")
            link = entry.get("link", "")
            published = entry.get("published", "")
            summary = entry.get("summary", "")

            all_news.append(
                NewsItem(
                    title=title,
                    link=link,
                    source=source,
                    published=published,
                    summary=summary,
                )
            )

    return all_news


def split_news_by_region(news: List[NewsItem]) -> Dict[str, List[NewsItem]]:
    """
    Делим новости на 2 группы: Россия и Мир.

    Логика очень простая (MVP):
    если в заголовке/описании есть ключевые слова про РФ,
    относим в группу "Россия", иначе — "Мир".
    """
    ru_keywords = [
        "россия",
        "рф",
        "russia",
        "moscow",
        "москва",
        "yandex",
        "яндекс",
        "vk",
        "сбер",
        "тинькофф",
    ]

    groups = {"Россия": [], "Мир": []}

    for item in news:
        text = f"{item.title} {item.summary}".lower()
        is_russia = any(keyword in text for keyword in ru_keywords)

        if is_russia:
            groups["Россия"].append(item)
        else:
            groups["Мир"].append(item)

    return groups


def build_prompt(group_name: str, items: List[NewsItem]) -> str:
    """Готовим текст для LLM: список новостей + задача анализа."""
    lines = [
        f"Группа новостей: {group_name}",
        "Задача: сделай короткое summary и practical insights для команды experimentation.",
        "Формат ответа:",
        "1) Summary (5-8 пунктов)",
        "2) Insights (5-8 пунктов)",
        "3) Что проверить в своих A/B-тестах на этой неделе (3-5 пунктов)",
        "",
        "Новости:",
    ]

    for i, item in enumerate(items, start=1):
        lines.append(
            f"{i}. {item.title}\n"
            f"   Источник: {item.source}\n"
            f"   Дата: {item.published or 'не указана'}\n"
            f"   Ссылка: {item.link}\n"
            f"   Описание: {item.summary[:500]}"
        )

    return "\n".join(lines)


def analyze_group_with_llm(client: OpenAI, model: str, group_name: str, items: List[NewsItem]) -> str:
    """
    Отправляем группу новостей в OpenAI и получаем анализ.

    Если новостей нет, возвращаем понятный текст и не делаем API-запрос.
    """
    if not items:
        return f"В группе '{group_name}' новостей не найдено."

    prompt = build_prompt(group_name, items)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты аналитик в продуктовой команде. Пиши по-русски, "
                    "коротко, структурно, практично."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )

    return response.choices[0].message.content or "Не удалось получить анализ от модели."


def build_basic_analysis(group_name: str, items: List[NewsItem]) -> str:
    """
    Резервный анализ без LLM.

    Полезно для первого теста пайплайна, когда вы ещё не добавили OPENAI_API_KEY.
    """
    if not items:
        return f"В группе '{group_name}' новостей не найдено."

    top_sources: Dict[str, int] = {}
    for item in items:
        top_sources[item.source] = top_sources.get(item.source, 0) + 1

    sorted_sources = sorted(top_sources.items(), key=lambda x: x[1], reverse=True)
    source_lines = [f"- {name}: {count}" for name, count in sorted_sources[:5]]

    lines = [
        "LLM-анализ отключён (режим теста).",
        f"Всего новостей: {len(items)}",
        "Топ источников:",
        *source_lines,
        "",
        "Что проверить вручную:",
        "- Корректно ли новости попали в нужную группу (Россия/Мир).",
        "- Достаточно ли релевантны RSS-источники для темы experimentation.",
        "- Нужны ли дополнительные ключевые слова для группы Россия.",
    ]
    return "\n".join(lines)


def format_report(groups: Dict[str, List[NewsItem]], analyses: Dict[str, str]) -> str:
    """Собираем финальный текстовый отчёт для email."""
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    parts = [
        "A/B Testing & Experimentation News Report",
        f"Сформирован: {date_str}",
        "=" * 72,
        "",
    ]

    for group_name in ["Россия", "Мир"]:
        parts.append(f"\n{'#' * 10} {group_name} {'#' * 10}")
        parts.append(f"Новостей в группе: {len(groups.get(group_name, []))}")
        parts.append("")

        # Добавляем перечень новостей, чтобы в письме сразу видеть источники
        for idx, item in enumerate(groups.get(group_name, []), start=1):
            parts.append(f"{idx}. {item.title}")
            parts.append(f"   - Источник: {item.source}")
            parts.append(f"   - Ссылка: {item.link}")

        parts.append("")
        parts.append("Анализ LLM:")
        parts.append(analyses.get(group_name, "Анализ отсутствует."))
        parts.append("\n" + "-" * 72)

    return "\n".join(parts)


def send_email_report(config: Config, subject: str, body: str) -> None:
    """
    Отправляем отчёт через Gmail SMTP.

    Для Gmail нужен App Password (пароль приложения),
    обычный пароль от аккаунта не подойдёт.
    """
    msg = MIMEMultipart()
    msg["From"] = config.email_from
    msg["To"] = config.email_to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    context = ssl.create_default_context()

    with smtplib.SMTP(config.smtp_host, config.smtp_port) as server:
        server.starttls(context=context)
        server.login(config.gmail_user, config.gmail_app_password)
        server.sendmail(config.email_from, [config.email_to], msg.as_string())


def build_arg_parser() -> argparse.ArgumentParser:
    """Аргументы командной строки для удобного тестирования MVP."""
    parser = argparse.ArgumentParser(description="MVP AI-агент для RSS-новостей A/B testing")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Собрать отчёт, показать в консоли и сохранить в report_preview.txt, но НЕ отправлять email.",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Не вызывать OpenAI API. Использовать простой тестовый анализ.",
    )
    parser.add_argument(
        "--max-per-feed",
        type=int,
        default=None,
        help="Сколько новостей брать из одной RSS-ленты (переопределяет MAX_PER_FEED).",
    )
    return parser


def main() -> None:
    """Главный сценарий: загрузили -> обработали -> отправили."""
    parser = build_arg_parser()
    args = parser.parse_args()

    config = get_config()

    if not config.rss_feeds:
        raise ValueError("Не заполнен RSS_FEEDS. Добавьте URL-ы RSS через запятую в .env")

    if not args.dry_run and not config.email_to:
        raise ValueError("Не заполнен EMAIL_TO в .env")

    # 1) Получаем новости из RSS
    max_per_feed = args.max_per_feed if args.max_per_feed is not None else config.max_per_feed
    news = parse_rss_feeds(config.rss_feeds, max_per_feed=max_per_feed)

    # 2) Делим на Россия / Мир
    groups = split_news_by_region(news)

    # 3) Анализируем группы с помощью OpenAI
    if args.skip_llm:
        analyses = {
            "Россия": build_basic_analysis("Россия", groups["Россия"]),
            "Мир": build_basic_analysis("Мир", groups["Мир"]),
        }
    else:
        if not config.openai_api_key:
            raise ValueError("Не заполнен OPENAI_API_KEY в .env")

        client = OpenAI(api_key=config.openai_api_key)
        analyses = {
            "Россия": analyze_group_with_llm(client, config.openai_model, "Россия", groups["Россия"]),
            "Мир": analyze_group_with_llm(client, config.openai_model, "Мир", groups["Мир"]),
        }

    # 4) Формируем общий отчёт
    report = format_report(groups, analyses)

    # В dry-run режиме сохраняем и показываем отчёт, но письмо не отправляем.
    if args.dry_run:
        preview_path = "report_preview.txt"
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(report)

        print(report)
        print(f"\nГотово! Это тестовый запуск (dry-run), письмо НЕ отправляли.")
        print(f"Отчёт сохранён в файл: {preview_path}")
        return

    # 5) Отправляем email
    subject = f"[MVP] A/B Experimentation Report - {datetime.now().strftime('%Y-%m-%d')}"
    send_email_report(config, subject, report)

    print("Готово! Отчёт успешно отправлен на email.")


if __name__ == "__main__":
    main()
