"""Provider-neutral import boundary. Export/provider adapters must supply deal IDs."""
import json
from pathlib import Path
from urllib.parse import urlsplit
from .common import AuditorError, parse_time


def validate_segments(segments, duration):
    if not isinstance(segments, list) or not segments:
        raise AuditorError("Each call needs a nonempty timestamped transcript list.")
    result = []
    last_start = -1
    for segment in segments:
        if not isinstance(segment, dict):
            raise AuditorError("Transcript segments must be objects.")
        start, end = segment.get("start"), segment.get("end")
        if (not isinstance(start, (int, float)) or isinstance(start, bool)
                or not isinstance(end, (int, float)) or isinstance(end, bool)
                or not 0 <= start < end <= duration or start < last_start):
            raise AuditorError("Transcript time bounds must be ordered and within call duration.")
        if not isinstance(segment.get("text"), str) or not segment["text"].strip():
            raise AuditorError("Transcript segment text must be nonempty.")
        speaker = segment.get("speaker", "Не определён")
        if not isinstance(speaker, str):
            raise AuditorError("Transcript speaker must be a string.")
        result.append({"start": start, "end": end, "text": segment["text"], "speaker": speaker})
        last_start = start
    return result


def import_calls(path, snapshot):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise AuditorError("Telephony import must be a readable normalized JSON file.") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("calls"), list):
        raise AuditorError("Telephony JSON must contain a calls array.")
    known_deals = {deal["id"]: deal for deal in snapshot["deals"]}
    output, seen = [], set()
    for raw in payload["calls"]:
        if not isinstance(raw, dict):
            raise AuditorError("Each telephony call must be an object.")
        for key in ("id", "deal_id", "manager_id", "duration_seconds"):
            if not isinstance(raw.get(key), int) or isinstance(raw[key], bool) or raw[key] <= 0:
                raise AuditorError("Call id, deal_id, manager_id and duration_seconds must be positive integers.")
        if raw["id"] in seen:
            raise AuditorError("Telephony file contains duplicate call IDs.")
        if raw["deal_id"] not in known_deals:
            raise AuditorError("Call references an unknown CRM deal; map it explicitly before import.")
        direction = raw.get("direction")
        if direction not in ("incoming", "outgoing"):
            raise AuditorError("Call direction must be incoming or outgoing.")
        occurred = parse_time(raw.get("occurred_at"))
        if occurred >= parse_time(snapshot["as_of"]):
            raise AuditorError("Call is outside the stored snapshot clock; refresh CRM before importing.")
        audio_url = raw.get("audio_url")
        if audio_url is not None:
            parsed = urlsplit(audio_url) if isinstance(audio_url, str) else None
            if parsed is None or parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
                raise AuditorError("audio_url must be null or an HTTPS URL without embedded credentials.")
        seen.add(raw["id"])
        deal = known_deals[raw["deal_id"]]
        output.append({key: raw[key] for key in ("id", "deal_id", "manager_id", "duration_seconds", "direction")})
        output[-1].update(company=deal["company"], occurred_at=occurred.isoformat(), audio_url=audio_url,
                          transcript=validate_segments(raw.get("transcript"), raw["duration_seconds"]),
                          analysis_mode="local_rules", synthetic=False)
    # Apply only after the entire file has validated.
    manager_ids = {manager["id"] for manager in snapshot["managers"]}
    for call in output:
        if call["manager_id"] not in manager_ids:
            manager_id = call["manager_id"]
            snapshot["managers"].append({"id": manager_id, "name": f"Сотрудник {manager_id}",
                                         "initials": "СТ", "color": "#89a2c8"})
            manager_ids.add(manager_id)
        deal = known_deals[call["deal_id"]]
        if call["id"] not in deal["call_ids"]:
            deal["call_ids"].append(call["id"])
        if parse_time(deal["last_activity_at"]) < parse_time(call["occurred_at"]):
            deal["last_activity_at"] = call["occurred_at"]
    return output
