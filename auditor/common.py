"""Small shared helpers; timestamps are always explicit and timezone-aware."""
from datetime import datetime, timezone
import json
from pathlib import Path


class AuditorError(Exception):
    """An actionable, credential-free error safe to print at the CLI boundary."""


def parse_time(value):
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return datetime.fromtimestamp(value, timezone.utc)
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError, OverflowError, OSError):
        raise AuditorError("Invalid timestamp; supply ISO 8601 with timezone or Unix seconds.") from None
    if result.tzinfo is None:
        raise AuditorError("Timestamp must include a timezone offset.")
    return result


def dump_json(path, value):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
