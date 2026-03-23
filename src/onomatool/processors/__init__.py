"""Processor package with plugin protocol and discovery.

SECURITY NOTE — Plugin Trust Boundary
======================================
Processor plugins run with the same privileges as OnomaTool itself.
Both discovery mechanisms execute arbitrary Python code:

1. **Entry-point plugins** (``onomatool.processors`` group) — loaded from
   installed packages. Any package in the environment can register a plugin.
2. **extra_processors** (config-driven) — loaded from ``module:ClassName``
   strings in ``~/.onomarc``. This is intentional code execution controlled
   by the config file owner.

Users should only install packages and configure extra_processors from
trusted sources. There is no sandboxing or capability restriction on plugins.
"""

import importlib
import logging
import sys
from typing import Protocol, runtime_checkable

from onomatool.models import ProcessingResult

logger = logging.getLogger(__name__)


@runtime_checkable
class ProcessorProtocol(Protocol):
    """Protocol that custom processors must implement."""

    def can_process(self, file_path: str) -> bool: ...
    def process(self, file_path: str) -> ProcessingResult | None: ...


def discover_entry_point_plugins() -> list[ProcessorProtocol]:
    """Discover processor plugins registered via entry_points."""
    plugins: list[ProcessorProtocol] = []

    if sys.version_info >= (3, 12):
        from importlib.metadata import entry_points

        eps = entry_points(group="onomatool.processors")
    else:
        from importlib.metadata import entry_points

        all_eps = entry_points()
        if isinstance(all_eps, dict):
            eps = all_eps.get("onomatool.processors", [])
        else:
            eps = all_eps.select(group="onomatool.processors")

    for ep in eps:
        try:
            plugin_cls = ep.load()
            plugin = plugin_cls()
            if isinstance(plugin, ProcessorProtocol):
                plugins.append(plugin)
                logger.debug("Loaded processor plugin: %s", ep.name)
            else:
                logger.warning(
                    "Plugin %s does not implement ProcessorProtocol, skipping",
                    ep.name,
                )
        except Exception as e:
            logger.warning("Failed to load processor plugin %s: %s", ep.name, e)

    return plugins


def load_extra_processors(module_paths: list[str]) -> list[ProcessorProtocol]:
    """Load processors from ad-hoc module paths specified in config.

    WARNING: This executes arbitrary code from the configured module paths.
    Only configure extra_processors with trusted modules.
    """
    plugins: list[ProcessorProtocol] = []

    for path in module_paths:
        logger.info("Loading extra processor (trusted code): %s", path)
        try:
            # path format: "my_package.module:ClassName"
            if ":" in path:
                module_path, class_name = path.rsplit(":", 1)
            else:
                logger.warning(
                    "extra_processors entry %r must use 'module:ClassName' format, skipping",
                    path,
                )
                continue

            module = importlib.import_module(module_path)
            plugin_cls = getattr(module, class_name)
            plugin = plugin_cls()
            if isinstance(plugin, ProcessorProtocol):
                plugins.append(plugin)
                logger.debug("Loaded extra processor: %s", path)
            else:
                logger.warning(
                    "Extra processor %s does not implement ProcessorProtocol, skipping",
                    path,
                )
        except Exception as e:
            logger.warning("Failed to load extra processor %s: %s", path, e)

    return plugins
