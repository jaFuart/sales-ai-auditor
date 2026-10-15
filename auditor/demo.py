"""A fixed synthetic account, generated without an API key or model execution."""
from datetime import datetime, timedelta
import random

AS_OF = "2026-10-14T18:00:00+03:00"
MANAGERS = [
    {"id": 101, "name": "Анна Волкова", "initials": "АВ", "color": "#b19af2"},
    {"id": 102, "name": "Михаил Соколов", "initials": "МС", "color": "#7fc9b3"},
    {"id": 103, "name": "Елена Миронова", "initials": "ЕМ", "color": "#e2ae77"},
]
STAGES = [
    ("new", "Новая заявка", "#89a2c8"),
    ("qualified", "Квалификация", "#b19af2"),
    ("demo", "Демонстрация", "#8dbbdb"),
    ("proposal", "Предложение", "#e2ae77"),
    ("negotiation", "Переговоры", "#7fc9b3"),
]
LABELS = dict((key, label) for key, label, _ in STAGES)
LABELS.update(won="Успешно реализована", lost="Закрыта без продажи")
COMPANIES = ["Орбита", "Север Трейд", "Атлас", "Меридиан", "Неон", "Вектор", "Гринлайн", "Лайтхаус", "Бюро 12", "Модуль", "Спектр", "Прайм", "Каскад", "Форма", "Точка роста", "Альта", "Ладога", "Аура", "Маяк", "Техносфера", "Линия", "Сфера", "Контур", "Нова", "Платформа", "Оптима"]
PRODUCTS = ["CRM для отдела продаж", "Интеграция телефонии", "Автоматизация воронки", "Аналитика продаж", "Поддержка CRM", "Обучение команды"]


def demo_snapshot():
    now = datetime.fromisoformat(AS_OF)
    rng = random.Random(481516)
    deals = []
    for index in range(78):
        status = (["proposal", "negotiation", "qualified", "demo", "new", "won", "won", "won", "lost", "lost"])[index % 10]
        age = rng.randint(2, 58)
        created = now - timedelta(days=age, hours=rng.randint(0, 12))
        closed = None
        if status in ("won", "lost"):
            closed = created + timedelta(days=rng.randint(1, min(age - 1, 25)), hours=1)
        activity = closed or now - timedelta(days=rng.randint(0, min(age, 22)), hours=2)
        deal = {
            "id": 1001 + index, "name": PRODUCTS[index % len(PRODUCTS)],
            "company": COMPANIES[index % len(COMPANIES)], "amount": rng.randrange(9, 85) * 10000,
            "status": status, "status_label": LABELS[status], "manager_id": 101 + index % 3,
            "created_at": created.isoformat(), "closed_at": closed.isoformat() if closed else None,
            "last_activity_at": activity.isoformat(), "tasks": [], "call_ids": [], "crm_url": None,
        }
        if status not in ("won", "lost"):
            variant = (index // 10 + index) % 5
            if variant in (1, 2):
                deal["tasks"].append(_task(index, now - timedelta(days=variant), False, "Отправить предложение"))
            elif variant == 3:
                deal["tasks"].append(_task(index, now + timedelta(days=2), False, "Согласовать следующий контакт"))
            elif variant == 4:
                deal["tasks"].append(_task(index, now - timedelta(days=4), True, "Отправить предложение"))
                deal["tasks"].append(_task(index + 100, now + timedelta(days=1), False, "Провести демо"))
        deals.append(deal)

    # An old untouched open deal stays visible in the CURRENT portfolio for every period.
    deals[0].update(company="Орбита", amount=640000, created_at=(now - timedelta(days=94)).isoformat(),
                    last_activity_at=(now - timedelta(days=38)).isoformat(), tasks=[])
    deals[1].update(company="Север Трейд", amount=480000)
    deals[1]["tasks"] = [_task(1, now - timedelta(days=3), False, "Отправить предложение")]
    calls = []
    open_deals = [deal for deal in deals[1:] if deal["status"] not in ("won", "lost")]
    for index in range(28):
        deal = open_deals[index % len(open_deals)]
        occurred = now - timedelta(days=(index * 5) % 37, hours=3 + index % 8)
        if datetime.fromisoformat(deal["created_at"]) > occurred:
            deal["created_at"] = (occurred - timedelta(days=4)).isoformat()
        if datetime.fromisoformat(deal["last_activity_at"]) < occurred:
            deal["last_activity_at"] = occurred.isoformat()
        action, objection, quote = [
            ("Отправить предложение", "Цена", "Цена выше нашего бюджета. Пришлите предложение завтра до обеда."),
            ("Подготовить расчёт", "Срок внедрения", "Нам важно уложиться в две недели. Подготовьте расчёт к пятнице."),
            ("Согласовать договор", "Согласование с руководителем", "Я покажу руководителю. Пришлите договор, чтобы согласовать условия."),
            ("Провести демо", "", "Нам подходит. Давайте проведём демо в четверг в 11:00."),
        ][index % 4]
        transcript = [
            {"start": 0, "end": 14, "speaker": "Менеджер", "text": "Добрый день! Обсудим внедрение и следующий шаг по вашему проекту."},
            {"start": 15, "end": 34, "speaker": "Клиент", "text": "Команда растёт, хотим видеть все обращения и договорённости в одной CRM."},
            {"start": 35, "end": 48, "speaker": "Клиент", "text": quote},
            {"start": 49, "end": 68, "speaker": "Менеджер", "text": "Договорились, я подготовлю материалы и свяжусь с вами."},
            {"start": 69, "end": 84, "speaker": "Клиент", "text": "Спасибо, будем ждать. До свидания!"},
        ]
        call = {"id": 2001 + index, "deal_id": deal["id"], "manager_id": deal["manager_id"],
                "company": deal["company"], "occurred_at": occurred.isoformat(), "duration_seconds": 84,
                "direction": "outgoing" if index % 3 else "incoming", "transcript": transcript,
                "audio_url": None, "analysis_mode": "demo_rules", "synthetic": True}
        calls.append(call)
        deal["call_ids"].append(call["id"])
    return {"as_of": AS_OF, "mode": "demo", "complete": True, "warnings": [],
            "managers": MANAGERS, "deals": deals, "calls": calls}


def _task(index, due, completed, text):
    return {"id": 3001 + index, "text": text, "complete_till": due.isoformat(),
            "is_completed": completed, "entity_type": "leads"}
