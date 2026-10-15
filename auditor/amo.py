"""Read-only amoCRM v4 connector, urllib only. Credentials never enter snapshots."""
from collections import defaultdict
from datetime import datetime, timezone
import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from .common import AuditorError, parse_time, utc_now


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not send a bearer credential to a redirect target.
        return None


class AmoClient:
    def __init__(self, subdomain, token, *, opener=None, sleep=time.sleep, timeout=25, retries=4):
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", subdomain or ""):
            raise AuditorError("AMO_SUBDOMAIN must be the account name only, not a URL.")
        if not token or any(character.isspace() for character in token):
            raise AuditorError("Set a valid AMO_ACCESS_TOKEN in the server environment.")
        self.base = f"https://{subdomain}.amocrm.ru"
        self.token, self.timeout, self.retries = token, timeout, retries
        self.opener = opener or build_opener(NoRedirect())
        self.sleep = sleep

    @classmethod
    def from_env(cls):
        return cls(os.environ.get("AMO_SUBDOMAIN", ""), os.environ.get("AMO_ACCESS_TOKEN", ""))

    def get(self, path, params=None):
        if not path.startswith("/api/v4/") or "?" in path or ".." in path:
            raise AuditorError("Unsupported amoCRM API path.")
        url = self.base + path + ("?" + urlencode(params) if params else "")
        request = Request(url, headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"}, method="GET")
        for attempt in range(self.retries + 1):
            try:
                with self.opener.open(request, timeout=self.timeout) as response:
                    if response.status == 204:
                        return None
                    payload = json.load(response)
                if not isinstance(payload, dict):
                    raise AuditorError("amoCRM returned an invalid object response.")
                self.sleep(0.17)  # Less than 7 requests/sec for this single worker.
                return payload
            except HTTPError as error:
                if error.code == 429 or 500 <= error.code <= 599:
                    if attempt < self.retries:
                        delay = min(2 ** attempt, 16)
                        retry_after = error.headers.get("Retry-After", "") if error.headers else ""
                        if retry_after.isdigit():
                            delay = min(max(delay, int(retry_after)), 60)
                        self.sleep(delay)
                        continue
                    raise AuditorError("amoCRM temporary error after retries; no partial snapshot stored.") from None
                if error.code in (401, 403):
                    raise AuditorError("amoCRM access denied; check token lifetime and account permissions.") from None
                raise AuditorError(f"amoCRM request failed (HTTP {error.code}); no partial snapshot stored.") from None
            except (URLError, TimeoutError, OSError):
                if attempt < self.retries:
                    self.sleep(min(2 ** attempt, 16))
                    continue
                raise AuditorError("amoCRM connection failed after retries; check network availability.") from None
            except (ValueError, UnicodeError):
                raise AuditorError("amoCRM returned malformed JSON; no partial snapshot stored.") from None

    def list_all(self, path, key, params=None):
        results, seen = [], set()
        for page in range(1, 10001):
            payload = self.get(path, {**(params or {}), "page": page, "limit": 250})
            if payload is None:
                return results
            items = payload.get("_embedded", {}).get(key)
            if not isinstance(items, list):
                raise AuditorError("amoCRM collection missing; cannot confirm snapshot completeness.")
            if not items:
                return results
            if any(not isinstance(item, dict) or "id" not in item for item in items):
                raise AuditorError("amoCRM collection contains malformed records.")
            fresh = [item for item in items if item["id"] not in seen]
            if not fresh:
                raise AuditorError("amoCRM repeated a page; cannot confirm snapshot completeness.")
            results.extend(fresh)
            seen.update(item["id"] for item in fresh)
            if not payload.get("_links", {}).get("next") and len(items) < 250:
                return results
        raise AuditorError("amoCRM pagination limit reached; no partial snapshot stored.")

    def snapshot(self):
        # All leads, including old ones, are needed for portfolio/task checks.
        leads = self.list_all("/api/v4/leads", "leads")
        tasks = self.list_all("/api/v4/tasks", "tasks")
        users = self.list_all("/api/v4/users", "users")
        pipelines = self.list_all("/api/v4/leads/pipelines", "pipelines")
        companies = self.list_all("/api/v4/companies", "companies")
        task_map = defaultdict(list)
        for task in tasks:
            if task.get("entity_type") != "leads":
                continue
            task_map[task["entity_id"]].append({"id": task["id"], "text": task.get("text", ""),
                                              "complete_till": parse_time(task["complete_till"]).isoformat(),
                                              "is_completed": bool(task["is_completed"]), "entity_type": "leads"})
        stages = {}
        for pipeline in pipelines:
            for status in pipeline.get("_embedded", {}).get("statuses", []):
                stages[(pipeline["id"], status["id"])] = status.get("name", "Этап CRM")
        company_names = {company["id"]: company.get("name", "Компания CRM") for company in companies}
        deals = []
        for lead in leads:
            if lead.get("is_deleted"):
                continue
            status_id = lead["status_id"]
            status = "won" if status_id == 142 else "lost" if status_id == 143 else f"stage_{lead['pipeline_id']}_{status_id}"
            company = lead.get("_embedded", {}).get("companies", [])
            deals.append({"id": lead["id"], "name": lead.get("name") or f"Сделка {lead['id']}",
                          "company": company_names.get(company[0]["id"], "Компания не указана") if company else "Компания не указана",
                          "amount": lead.get("price", 0), "status": status,
                          "status_label": stages.get((lead["pipeline_id"], status_id), "Успешно реализована" if status == "won" else "Закрыта без продажи" if status == "lost" else "Этап CRM"),
                          "manager_id": lead["responsible_user_id"], "created_at": parse_time(lead["created_at"]).isoformat(),
                          "closed_at": parse_time(lead["closed_at"]).isoformat() if lead.get("closed_at") else None,
                          "last_activity_at": parse_time(lead["updated_at"]).isoformat(),
                          "tasks": task_map[lead["id"]], "call_ids": [], "crm_url": f"{self.base}/leads/detail/{lead['id']}"})
        names = {user["id"]: user.get("name") or f"Пользователь {user['id']}" for user in users}
        colors = ["#b19af2", "#7fc9b3", "#e2ae77", "#89a2c8"]
        managers = []
        for index, manager_id in enumerate(sorted(set(names) | {deal["manager_id"] for deal in deals})):
            name = names.get(manager_id, f"Пользователь {manager_id}")
            managers.append({"id": manager_id, "name": name, "initials": "".join(part[0] for part in name.split()[:2]).upper(), "color": colors[index % len(colors)]})
        return {"as_of": utc_now(), "mode": "live", "complete": True, "managers": managers, "deals": deals,
                "calls": [], "warnings": ["API возвращает записи, доступные пользователю токена; полнота ограничена его правами.",
                                           "Выгрузка API не атомарная; параллельные изменения CRM могут повлиять на снимок.",
                                           "Последняя активность сделки — updated_at CRM; дата звонка учитывается после импорта."]}
