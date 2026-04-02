"""Scheduler – determines execution order and suite filtering.

MVP uses sequential execution.  Structure is in place to swap to
concurrent execution (asyncio / ThreadPoolExecutor) without touching
the orchestrator or plugins.
"""

from __future__ import annotations

from plugins.base import BasePlugin, get_registry
from core.context import ValidationContext
from utils.logger import get_logger

log = get_logger(__name__)


def select_plugins(context: ValidationContext) -> list[BasePlugin]:
    """Return instantiated, ordered plugins applicable to *context*."""
    registry = get_registry()
    selected: list[BasePlugin] = []

    for name, cls in registry.items():
        instance = cls()

        # Suite filtering
        if context.suite and context.suite not in instance.suites:
            log.debug("Skipping plugin '%s' (not in suite '%s')", name, context.suite)
            continue

        if not instance.supports(context):
            log.debug("Plugin '%s' reports it does not support this board", name)
            continue

        selected.append(instance)
        log.debug("Scheduled plugin: %s", name)

    # Stable ordering: system first, then alphabetical
    def sort_key(p: BasePlugin) -> tuple[int, str]:
        return (0 if p.name == "system" else 1, p.name)

    selected.sort(key=sort_key)
    return selected
