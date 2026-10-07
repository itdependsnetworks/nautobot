"""Shared helpers for the retained-history tests."""


def clear_archive(*mirrors):
    """Empty these mirrors, so a test starts from nothing."""
    for mirror in mirrors:
        mirror.objects.all().delete()
