"""Shared helpers for the retained-history tests."""


def clear_archive(*mirrors):
    """Empty these mirrors, so a test starts from nothing."""
    for mirror in mirrors:
        mirror.objects.all().delete()


class StubJobResult:
    """Stands in for the `JobResult` a running job reads its user from."""

    def __init__(self, user):
        self.user = user


class RecordingLogger:
    """Captures what the job would tell the operator, so messages can be asserted directly."""

    def __init__(self):
        self.records = []

    def _record(self, level, message, *args):
        self.records.append((level, message % args if args else message))

    def debug(self, message, *args, **kwargs):
        self._record("debug", message, *args)

    def info(self, message, *args, **kwargs):
        self._record("info", message, *args)

    def warning(self, message, *args, **kwargs):
        self._record("warning", message, *args)

    def error(self, message, *args, **kwargs):
        self._record("error", message, *args)

    def success(self, message, *args, **kwargs):
        self._record("success", message, *args)

    @property
    def messages(self):
        return [message for _level, message in self.records]

    def said(self, fragment):
        return any(fragment in message for message in self.messages)
