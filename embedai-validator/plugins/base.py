"""Plugin base class and registry for EmbedAI Validator."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from core.context import ValidationContext
from core.result_model import TestResult
from utils.logger import get_logger

log = get_logger(__name__)


class BasePlugin(ABC):
    """All peripheral / system plugins inherit from this."""

    # Subclasses must define these class-level attributes.
    name: ClassVar[str] = ""
    test_type: ClassVar[str] = ""
    description: ClassVar[str] = ""

    # If a plugin declares suite tags, it will only run when --suite matches.
    suites: ClassVar[list[str]] = ["full", "smoke"]

    def supports(self, context: ValidationContext) -> bool:
        """Return True if this plugin has work to do for *context*."""
        return True

    def precheck(self, context: ValidationContext) -> list[str]:
        """Return a list of human-readable warnings before running.

        Return an empty list when all preconditions are met.
        """
        return []

    @abstractmethod
    def run(self, context: ValidationContext) -> list[TestResult]:
        """Execute tests and return structured results."""

    def cleanup(self, context: ValidationContext) -> None:
        """Optional cleanup after run; default is no-op."""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[BasePlugin]] = {}


def register(plugin_cls: type[BasePlugin]) -> type[BasePlugin]:
    """Decorator to register a plugin class."""
    if not plugin_cls.name:
        raise ValueError(f"Plugin {plugin_cls.__qualname__} must define a 'name'")
    _REGISTRY[plugin_cls.name] = plugin_cls
    log.debug("Registered plugin: %s", plugin_cls.name)
    return plugin_cls


def get_registry() -> dict[str, type[BasePlugin]]:
    return dict(_REGISTRY)


def get_plugin(name: str) -> type[BasePlugin] | None:
    return _REGISTRY.get(name)


def load_all_plugins() -> None:
    """Import every plugin sub-package so their @register decorators fire."""
    import plugins.system.plugin    # noqa: F401
    import plugins.i2c.plugin       # noqa: F401
    import plugins.gpio.plugin      # noqa: F401
    import plugins.uart.plugin      # noqa: F401
    import plugins.ethernet.plugin  # noqa: F401
