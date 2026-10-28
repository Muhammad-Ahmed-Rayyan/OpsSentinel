from datetime import datetime, timedelta

from opssentinel.schemas import NormalizedAlert


def fingerprint(alert: NormalizedAlert) -> str:
    """Alerts with the same source, name and target are the same problem."""
    return "|".join(
        [
            alert.source,
            alert.name,
            alert.service or "-",
            alert.host or "-",
            alert.environment or "-",
        ]
    )


class AlertDeduplicator:
    """Tracks open incidents by alert fingerprint. State is in memory, like the checkpointer."""

    def __init__(self, window_minutes: int = 30):
        if window_minutes <= 0:
            raise ValueError("window_minutes must be positive")
        self.window = timedelta(minutes=window_minutes)
        self._open: dict[str, tuple[str, datetime]] = {}

    def check(self, alert: NormalizedAlert, incident_id: str) -> str | None:
        """Return the id of the open incident this alert repeats, or None if it is new.

        A new alert is remembered as the opener of its incident. A repeat refreshes
        the window, so a continuing storm stays suppressed.
        """
        key = fingerprint(alert)
        previous = self._open.get(key)
        if previous is not None:
            original_id, last_seen = previous
            if abs(alert.triggered_at - last_seen) <= self.window:
                self._open[key] = (original_id, max(last_seen, alert.triggered_at))
                return original_id
        self._open[key] = (incident_id, alert.triggered_at)
        return None

    def release(self, incident_id: str) -> None:
        """Forget an incident once it is closed so a later repeat opens a new one."""
        self._open = {
            key: value for key, value in self._open.items() if value[0] != incident_id
        }