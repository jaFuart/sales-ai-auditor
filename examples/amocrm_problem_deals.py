"""Open deals without unfinished direct tasks or with overdue tasks (stdlib)."""
import json
import os
import re
import time
from collections import defaultdict
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

subdomain = os.environ.get("AMO_SUBDOMAIN", "").strip().lower()
token = os.environ.get("AMO_ACCESS_TOKEN", "").strip()
if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", subdomain) or not token:
    raise SystemExit("Set AMO_SUBDOMAIN (name only) and AMO_ACCESS_TOKEN")
base = f"https://{subdomain}.amocrm.ru/api/v4/"
as_of = int(time.time())

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None
def fetch_all(entity, filters=None):
    page, rows = 1, []
    while True:
        params = {"limit": 250, "page": page, "order[id]": "asc", **(filters or {})}
        request = Request(base + entity + "?" + urlencode(params), headers={
            "Authorization": f"Bearer {token}", "Accept": "application/hal+json"})
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            if response.status == 204:
                break
            payload = json.load(response)
        rows.extend(payload["_embedded"][entity])
        if not payload.get("_links", {}).get("next"):
            break
        page += 1
    return rows


tasks_by_lead = defaultdict(list)
for task in fetch_all("tasks", {"filter[entity_type]": "leads", "filter[is_completed]": 0}):
    if task["entity_type"] == "leads" and not task["is_completed"]:
        tasks_by_lead[task["entity_id"]].append(task)
problems = []
for lead in fetch_all("leads"):
    if lead["status_id"] in (142, 143):
        continue
    tasks = tasks_by_lead[lead["id"]]
    overdue = [t["id"] for t in tasks if t["complete_till"] < as_of]
    if not tasks or overdue:
        problems.append({"id": lead["id"], "name": lead["name"],
                         "no_task": not tasks, "overdue_task_ids": overdue})
print(json.dumps({"as_of": as_of, "deals": problems}, ensure_ascii=False, indent=2))
