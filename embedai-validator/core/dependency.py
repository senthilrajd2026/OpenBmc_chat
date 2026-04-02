"""Dependency graph helpers (stub for MVP, ready for future expansion).

In a future release plugins will be able to declare dependencies on other
plugins via a ``depends_on`` class attribute.  This module will topologically
sort the execution order.  For the MVP we only export a no-op helper so the
orchestrator API stays stable.
"""

from __future__ import annotations

from plugins.base import BasePlugin


def resolve_order(plugins: list[BasePlugin]) -> list[BasePlugin]:
    """Return *plugins* in dependency-resolved execution order.

    MVP: identity function – plugins are already ordered by the scheduler.
    """
    return plugins
