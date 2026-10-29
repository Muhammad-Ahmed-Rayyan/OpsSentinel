import json

import pytest

from opssentinel.notifier import (
    CompositeNotifier,
    OutboxNotifier,
    WebhookNotifier,
    build_notifier,
    format_message,
)

MESSAGE = {
    "kind": "approval",
    "incident_id": "INC-N1",
    "alert": "HighErrorRate: 5xx",
    "alternatives": ["option 2: restart_service", "option 3: clear_cache"],
}


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class RecordingOpener:
    def __init__(self):
        self.requests = []

    def __call__(self, request, timeout=None):
        self.requests.append((request, timeout))
        return FakeResponse()


def test_message_is_rendered_as_readable_text():
    text = format_message(MESSAGE)

    assert text.startswith("[APPROVAL] Incident INC-N1")
    assert "alert: HighErrorRate: 5xx" in text
    assert "  - option 2: restart_service" in text


def test_outbox_notifier_writes_one_file_per_message(tmp_path):
    notifier = OutboxNotifier(tmp_path)
    notifier.send(MESSAGE)
    notifier.send({**MESSAGE, "kind": "review"})

    names = sorted(path.name for path in tmp_path.iterdir())
    assert len(names) == 2
    assert any("approval-INC-N1" in name for name in names)
    assert any("review-INC-N1" in name for name in names)


def test_outbox_file_names_cannot_escape_the_folder(tmp_path):
    OutboxNotifier(tmp_path).send({**MESSAGE, "incident_id": "../evil"})

    (path,) = tmp_path.iterdir()
    assert path.parent == tmp_path


def test_webhook_posts_the_message_as_slack_text():
    opener = RecordingOpener()
    WebhookNotifier("https://hooks.example.com/abc", opener=opener).send(MESSAGE)

    request, timeout = opener.requests[0]
    assert request.full_url == "https://hooks.example.com/abc"
    assert json.loads(request.data)["text"].startswith("[APPROVAL]")
    assert timeout == 5.0


def test_webhook_refuses_a_non_https_url():
    with pytest.raises(ValueError):
        WebhookNotifier("file:///etc/passwd")


def test_webhook_errors_reach_the_caller():
    def failing(request, timeout=None):
        raise OSError("connection refused")

    with pytest.raises(OSError):
        WebhookNotifier("https://hooks.example.com/abc", opener=failing).send(MESSAGE)


def test_composite_delivers_to_working_channels_and_reports_the_broken_one(tmp_path):
    class Broken:
        def send(self, message):
            raise OSError("down")

    composite = CompositeNotifier([Broken(), OutboxNotifier(tmp_path)])

    with pytest.raises(RuntimeError, match="Broken"):
        composite.send(MESSAGE)
    assert len(list(tmp_path.iterdir())) == 1  # the working channel still delivered


def test_build_notifier_adds_the_webhook_only_when_configured(tmp_path):
    assert len(build_notifier(tmp_path).notifiers) == 1
    assert len(build_notifier(tmp_path, "https://hooks.example.com/abc").notifiers) == 2