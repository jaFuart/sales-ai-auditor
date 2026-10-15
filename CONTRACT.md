# Shared implementation contract

Local Python standard-library service: `python3 -m auditor serve --port 8080`.
Build fixtures: `python3 -m auditor build-demo` writes `dist/data/report-{7,14,30}.json`.
CLI: `python3 -m auditor report --days 30 --output report.json`.
Frontend requests `/api/report?days=30`, falling back on HTTP 404 to `./data/report-30.json` on static hosting. It must show a visible demo-data label; no fictitious model execution.

Report schema (all listed fields required; additional fields okay):

```json
{
  "meta": {"as_of":"2026-10-14T18:00:00+03:00","period_days":30,"from":"2026-09-14T18:00:00+03:00","to":"2026-10-14T18:00:00+03:00","mode":"demo","analysis_mode":"demo_rules","warnings":[]},
  "managers":[{"id":101,"name":"Анна Волкова","initials":"АВ","color":"#b19af2"}],
  "metrics":{"new_leads":0,"won_count":0,"won_amount":0,"closed_count":0,"win_rate":0,"open_count":0,"no_task_count":0,"overdue_count":0,"calls_count":0,"followup_gap_count":0},
  "pipeline":[{"id":"new","label":"Новая заявка","count":0,"amount":0,"color":"#89a2c8"}],
  "series":[{"date":"2026-10-14","label":"14 окт","won_amount":0,"calls_count":0,"new_leads":0}],
  "manager_stats":[{"id":101,"name":"Анна Волкова","won_count":0,"won_amount":0,"open_count":0,"overdue_count":0,"no_task_count":0,"calls_count":0}],
  "deals":[{"id":1001,"name":"Внедрение CRM","company":"Орбита","amount":250000,"status":"proposal","status_label":"Предложение","manager_id":101,"created_at":"2026-10-01T12:00:00+03:00","closed_at":null,"last_activity_at":"2026-10-13T12:00:00+03:00","issues":["no_task"],"tasks":[],"call_ids":[2001],"recommendation":"Назначить следующий контакт","crm_url":null}],
  "calls":[{"id":2001,"deal_id":1001,"manager_id":101,"company":"Орбита","occurred_at":"2026-10-13T12:00:00+03:00","duration_seconds":240,"direction":"outgoing","quality":"attention","summary":"Клиент ждёт предложение","objections":["Цена"],"next_step":"Отправить предложение","followup_gap":true,"evidence":[{"start":35,"end":48,"speaker":"Клиент","text":"Пришлите предложение завтра."}],"transcript":[{"start":0,"end":10,"speaker":"Менеджер","text":"Добрый день."}],"audio_url":null,"analysis_mode":"demo_rules"}],
  "recommendations":[{"id":"r1","priority":"high","title":"Назначить следующие действия","description":"Проверить сделки без задач","deal_ids":[1001],"call_ids":[2001],"requires_approval":true}],
  "summary":"Текст итогового отчёта с числами, рассчитанными кодом."
}
```

Semantics: metrics of creation/closing/calls cover `[from,to)`; open pipeline and task violations are a current snapshot at `as_of` across all open deals, including old untouched deals. Won amount is the sum of CRM deal budgets, not cash revenue. `win_rate` is won/closed-in-period * 100. Task checks use directly attached unfinished lead tasks; no active tasks means `no_task`, any unfinished task before `as_of` means `overdue`. Contact-level tasks are not automatically attributed to deals. Matching promised follow-up is a review suggestion, not a proven breach. 7/14/30 reports must differ by genuine period calculations, not invented trend percentages. Deterministic fixtures have a fixed clock. No personal-history claims in docs.
