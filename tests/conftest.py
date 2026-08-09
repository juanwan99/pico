"""Local py3.10 compat: datetime.UTC is 3.11+."""
import datetime

if not hasattr(datetime, "UTC"):
    datetime.UTC = datetime.timezone.utc  # type: ignore[attr-defined]
