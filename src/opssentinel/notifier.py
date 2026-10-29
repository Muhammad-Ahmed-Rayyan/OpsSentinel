import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_OUTBOX_DIR = Path(__file__).resolve().parents[2] / "notifications"


def format_message(message: dict) -> str:
    """Render a notification as plain text suitable for chat or email."""
    lines = [
        f"[{str(message.get('kind', 'notice')).upper()}] "
        f"Incident {message.get('incident_id', 'unknown')}"
    ]
    for key, value in message.items():
        if key in ("kind", "incident_id"):
            continue
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines += [f"  - {item}" for item in value]
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


class OutboxNotifier:
    """Writes each notification to a file, standing in for an email or chat inbox."""

    def __init__(self, directory: Path = DEFAULT_OUTBOX_DIR):
        self.directory = Path(directory)

    def send(self, message: dict) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        incident = re.sub(r"[^A-Za-z0-9_.-]", "_", str(message.get("incident_id", "unknown")))
        kind = re.sub(r"[^A-Za-z0-9_.-]", "_", str(message.get("kind", "notice")))
        path = self.directory / f"{stamp}-{kind}-{incident}.txt"
        path.write_text(format_message(message), encoding="utf-8")


class WebhookNotifier:
    """Posts to a Slack-compatible incoming webhook."""

    def __init__(self, url: str, timeout: float = 5.0, opener=urllib.request.urlopen):
        if not url.startswith("https://"):
            raise ValueError("the webhook URL must start with https://")
        self.url = url
        self.timeout = timeout
        self.opener = opener

    def send(self, message: dict) -> None:
        body = json.dumps({"text": format_message(message)}).encode("utf-8")
        request = urllib.request.Request(
            self.url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        with self.opener(request, timeout=self.timeout) as response:
            status = getattr(response, "status", 200)
            if status >= 400:
                raise RuntimeError(f"webhook returned HTTP {status}")


class CompositeNotifier:
    """Sends to every channel. One broken channel never stops the others."""

    def __init__(self, notifiers: list):
        self.notifiers = list(notifiers)

    def send(self, message: dict) -> None:
        failures = []
        for notifier in self.notifiers:
            try:
                notifier.send(message)
            except Exception as exc:
                failures.append(f"{type(notifier).__name__}: {exc}")
        if failures:
            raise RuntimeError("; ".join(failures))


def build_notifier(outbox_dir: Path = DEFAULT_OUTBOX_DIR, webhook_url: str = "") -> CompositeNotifier:
    notifiers = [OutboxNotifier(outbox_dir)]
    if webhook_url:
        notifiers.append(WebhookNotifier(webhook_url))
    return CompositeNotifier(notifiers)