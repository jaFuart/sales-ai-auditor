"""All amounts/counts are calculated by code; narrative never creates a KPI."""
from copy import deepcopy
from datetime import timedelta
from .common import AuditorError, parse_time
from .demo import STAGES

MONTHS = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
FOLLOWUP = [("предложени", "Отправить предложение"), ("расчёт", "Подготовить расчёт"),
            ("договор", "Согласовать договор"), ("демо", "Провести демо")]


def task_issues(deal, as_of):
    """Only directly attached, unfinished lead tasks satisfy next-action coverage."""
    active = [task for task in deal.get("tasks", []) if not task.get("is_completed", False)
              and task.get("entity_type", "leads") == "leads"]
    issues = [] if active else ["no_task"]
    if any(parse_time(task["complete_till"]) < as_of for task in active):
        issues.append("overdue")
    return issues


def analyze_rules(call, deal):
    """A deliberately transparent baseline, not a simulated model response."""
    result = deepcopy(call)
    if call.get("analysis_mode") == "openai" and "evidence" in call:
        key = next((key for key, _ in FOLLOWUP if key in call.get("next_step", "").lower()), None)
        matching = any(not task.get("is_completed") and task.get("entity_type", "leads") == "leads"
                       and key and key in task.get("text", "").lower() for task in deal.get("tasks", []))
        result["followup_gap"] = bool(key and not matching)
        result["quality"] = "attention" if result["followup_gap"] else "good"
        return result
    transcript = call.get("transcript", [])
    evidence = []
    next_step = "Уточнить следующий шаг с клиентом"
    match_key = None
    for segment in transcript:
        lower = segment["text"].lower()
        if any(word in lower for word in ("пришлите", "подготовьте", "проведём", "проведем")):
            evidence.append(deepcopy(segment))
            for keyword, label in FOLLOWUP:
                if keyword in lower:
                    next_step, match_key = label, keyword
                    break
            if match_key:
                break
    matching = [task for task in deal.get("tasks", []) if not task.get("is_completed")
                and task.get("entity_type", "leads") == "leads"
                and match_key and match_key in task.get("text", "").lower()]
    gap = bool(match_key and not matching)
    text = " ".join(segment["text"] for segment in transcript).lower()
    objections = [label for word, label in [("бюджет", "Цена"), ("две недели", "Срок внедрения"),
                                           ("руководител", "Согласование с руководителем")] if word in text]
    result.update(quality="attention" if gap else "good", next_step=next_step,
                  followup_gap=gap, objections=objections, evidence=evidence,
                  summary=(f"Клиент обсуждает {deal['name'].lower()}. Следующий шаг: {next_step.lower()}."),
                  analysis_mode="demo_rules" if call.get("synthetic") else "local_rules")
    return result


def build_report(snapshot, days=30):
    if not isinstance(days, int) or not 1 <= days <= 365:
        raise AuditorError("Period must be an integer between 1 and 365 days.")
    now = parse_time(snapshot["as_of"])
    start = now - timedelta(days=days)
    in_period = lambda value: value is not None and start <= parse_time(value) < now
    deals = deepcopy(snapshot.get("deals", []))
    managers = deepcopy(snapshot.get("managers", []))
    manager_ids = {manager["id"] for manager in managers}
    for item in deals + snapshot.get("calls", []):
        if item["manager_id"] not in manager_ids:
            manager_id = item["manager_id"]
            managers.append({"id": manager_id, "name": f"Сотрудник {manager_id}", "initials": "СТ", "color": "#89a2c8"})
            manager_ids.add(manager_id)
    lookup = {deal["id"]: deal for deal in deals}
    # Rebuild links after CRM refresh, which does not overwrite imported call content.
    for deal in deals:
        deal["call_ids"] = []
    for call in snapshot.get("calls", []):
        deal = lookup.get(call["deal_id"])
        if deal and parse_time(call["occurred_at"]) < now:
            deal["call_ids"].append(call["id"])
            if parse_time(call["occurred_at"]) > parse_time(deal["last_activity_at"]):
                deal["last_activity_at"] = call["occurred_at"]
    warnings = list(snapshot.get("warnings", []))
    if not snapshot.get("complete", True):
        warnings.append("Неполная выгрузка: показатели предварительные; отсутствие задач не подтверждено.")
    calls = []
    for raw in snapshot.get("calls", []):
        if raw["deal_id"] not in lookup:
            warnings.append(f"Звонок {raw['id']}: сделка {raw['deal_id']} отсутствует в снимке.")
            continue
        if in_period(raw["occurred_at"]):
            calls.append(analyze_rules(raw, lookup[raw["deal_id"]]))
    calls.sort(key=lambda call: parse_time(call["occurred_at"]), reverse=True)
    current = [deal for deal in deals if deal["status"] not in ("won", "lost")]
    current_ids = {deal["id"] for deal in current}
    for deal in deals:
        deal["issues"] = task_issues(deal, now) if deal["id"] in current_ids else []
        if not snapshot.get("complete", True) and "no_task" in deal["issues"]:
            deal["issues"].remove("no_task")
        gaps = [call for call in calls if call["deal_id"] == deal["id"] and call["followup_gap"]]
        if gaps and deal["id"] in current_ids:
            deal["issues"].append("followup_gap")
        if deal["id"] in current_ids and (now - parse_time(deal["last_activity_at"])).days >= 14:
            deal["issues"].append("stale")
        if "overdue" in deal["issues"]:
            recommendation = "Проверить просроченную задачу и согласовать новый срок"
        elif "no_task" in deal["issues"]:
            recommendation = "Назначить следующий контакт и ответственного"
        elif gaps:
            recommendation = "Сверить обещание в звонке с задачами CRM"
        else:
            recommendation = "Следующее действие запланировано" if deal["id"] in current_ids else "Сделка закрыта"
        deal["recommendation"] = recommendation
    closed = [deal for deal in deals if deal["status"] in ("won", "lost") and in_period(deal["closed_at"])]
    won = [deal for deal in closed if deal["status"] == "won"]
    new = [deal for deal in deals if in_period(deal["created_at"])]
    no_task = [deal for deal in current if "no_task" in deal["issues"]]
    overdue = [deal for deal in current if "overdue" in deal["issues"]]
    gap_calls = [call for call in calls if call["followup_gap"]]
    metrics = {"new_leads": len(new), "won_count": len(won), "won_amount": sum(deal["amount"] for deal in won),
               "closed_count": len(closed), "win_rate": round(len(won) / len(closed) * 100, 1) if closed else 0,
               "open_count": len(current), "no_task_count": len(no_task), "overdue_count": len(overdue),
               "calls_count": len(calls), "followup_gap_count": len(gap_calls)}
    pipeline = []
    stage_ids = list(STAGES) if snapshot.get("mode") == "demo" else []
    for deal in current:
        if deal["status"] not in {stage[0] for stage in stage_ids}:
            stage_ids.append((deal["status"], deal["status_label"], "#89a2c8"))
    for status, label, color in stage_ids:
        bucket = [deal for deal in current if deal["status"] == status]
        pipeline.append({"id": status, "label": label, "count": len(bucket),
                         "amount": sum(deal["amount"] for deal in bucket), "color": color})
    series = []
    date = start.date()
    while date <= now.date():
        on_date = lambda value: parse_time(value).astimezone(now.tzinfo).date() == date
        series.append({"date": date.isoformat(), "label": f"{date.day} {MONTHS[date.month-1]}",
                       "won_amount": sum(deal["amount"] for deal in won if on_date(deal["closed_at"])),
                       "calls_count": sum(on_date(call["occurred_at"]) for call in calls),
                       "new_leads": sum(on_date(deal["created_at"]) for deal in new)})
        date += timedelta(days=1)
    manager_stats = []
    for manager in managers:
        belongs = lambda item: item["manager_id"] == manager["id"]
        manager_stats.append({"id": manager["id"], "name": manager["name"],
                              "won_count": sum(belongs(deal) for deal in won),
                              "won_amount": sum(deal["amount"] for deal in won if belongs(deal)),
                              "open_count": sum(belongs(deal) for deal in current),
                              "no_task_count": sum(belongs(deal) for deal in no_task),
                              "overdue_count": sum(belongs(deal) for deal in overdue),
                              "calls_count": sum(belongs(call) for call in calls)})
    recommendations = []
    groups = [("next-actions", "high", "Назначить следующие действия", no_task, [],
               "Открытые сделки без незавершённых задач. Подтвердите контакт с клиентом и назначьте срок."),
              ("overdue", "high", "Разобрать просроченные задачи", overdue, [],
               "Проверьте фактическое выполнение и причины задержки, затем согласуйте новый срок."),
              ("promises", "medium", "Сверить договорённости со звонков", [], gap_calls,
               "Для обещанного действия не найдена задача с совпадающим ключевым словом. Это повод для проверки руководителем."),
              ("stale", "medium", "Вернуть в работу зависшие сделки",
               [deal for deal in current if "stale" in deal["issues"]], [],
               "Зафиксированная активность по сделке старше 14 дней. Уточните актуальность проекта.")]
    for key, priority, title, items, related_calls, description in groups:
        if items or related_calls:
            recommendations.append({"id": key, "priority": priority, "title": title, "description": description,
                                    "deal_ids": sorted({deal["id"] for deal in items} | {call["deal_id"] for call in related_calls}),
                                    "call_ids": [call["id"] for call in related_calls], "requires_approval": True})
    modes = {call["analysis_mode"] for call in calls}
    analysis_mode = "openai" if modes == {"openai"} else "mixed" if "openai" in modes else "demo_rules" if snapshot.get("mode") == "demo" else "local_rules"
    if snapshot.get("mode") == "demo":
        warnings.append("Демонстрационные данные и синтетические расшифровки. Аудио не использовано.")
        if "openai" not in modes:
            warnings.append("Реальный вызов модели не использован: анализ выполняют локальные правила.")
    else:
        warnings.append("Снимок актуальных статусов: исторические переходы и ответственные на момент закрытия не восстановлены.")
    warnings.append("Выигранная сумма — бюджеты успешно закрытых сделок, а не оплаченная выручка.")
    amount_label = f"{metrics['won_amount']:,}".replace(",", " ")
    summary = (f"За {days} дней создано {len(new)} сделок, успешно закрыто {len(won)} из {len(closed)} закрытых "
               f"({metrics['win_rate']}%). Сумма выигранных сделок — {amount_label} ₽. "
               f"В текущем портфеле {len(current)} открытых сделок: {len(no_task)} без активных задач, "
               f"{len(overdue)} с просроченными. Из {len(calls)} звонков за период {len(gap_calls)} требуют "
               "сверки договорённостей с CRM. Рекомендации требуют проверки руководителем.")
    deals.sort(key=lambda deal: (-len(deal["issues"]), -deal["amount"], deal["id"]))
    return {"meta": {"as_of": snapshot["as_of"], "period_days": days, "from": start.isoformat(),
                     "to": now.isoformat(), "mode": snapshot.get("mode", "live"), "analysis_mode": analysis_mode,
                     "warnings": list(dict.fromkeys(warnings)), "complete": snapshot.get("complete", True),
                     "period_semantics": "[from,to); pipeline and task checks are current account snapshot"},
            "managers": managers, "metrics": metrics, "pipeline": pipeline, "series": series,
            "manager_stats": manager_stats, "deals": deals, "calls": calls,
            "recommendations": recommendations, "summary": summary}
