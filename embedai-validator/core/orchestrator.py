"""Orchestrator – drives the full validation lifecycle."""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from pathlib import Path

from board.inventory import collect_environment
from board.loader import load_board
from board.schemas import BoardProfile
from core.context import ValidationContext
from core.dependency import resolve_order
from core.result_model import RunResult, Status, TestResult
from core.scheduler import select_plugins
from plugins.base import BasePlugin, load_all_plugins
from ai.rules import apply_rules
from utils.logger import get_logger
from utils.paths import timestamped_path

log = get_logger(__name__)


class Orchestrator:
    """Coordinate board loading, plugin execution, diagnostics, and reporting."""

    def __init__(
        self,
        board_path: Path,
        mock_mode: bool = False,
        suite: str | None = None,
        output_dir: Path | None = None,
    ) -> None:
        self.board_path = board_path
        self.mock_mode = mock_mode
        self.suite = suite
        self.output_dir = output_dir or Path("output")

    def run(self) -> RunResult:
        """Execute a full validation run and return the populated RunResult."""
        run_id = str(uuid.uuid4())[:8]
        started_at = datetime.now()

        log.info("=== EmbedAI Validator – run %s ===", run_id)

        # 1. Load board profile
        profile = load_board(self.board_path)

        # 2. Collect environment
        env = collect_environment()

        # 3. Build context
        context = ValidationContext(
            profile=profile,
            run_id=run_id,
            mock_mode=self.mock_mode,
            suite=self.suite,
            output_dir=self.output_dir,
        )

        # 4. Discover plugins
        load_all_plugins()
        plugins = select_plugins(context)
        plugins = resolve_order(plugins)

        log.info("Running %d plugin(s) for board: %s", len(plugins), profile.board.name)

        # 5. Execute plugins sequentially
        all_results: list[TestResult] = []
        for plugin in plugins:
            log.info("→ [cyan]%s[/cyan]", plugin.name)
            warnings = plugin.precheck(context)
            for w in warnings:
                log.warning("  precheck: %s", w)

            t0 = time.monotonic()
            try:
                results = plugin.run(context)
            except Exception as exc:  # noqa: BLE001
                log.exception("Plugin '%s' raised an unhandled exception", plugin.name)
                from core.result_model import Evidence
                results = [
                    TestResult(
                        test_id=f"{plugin.name}.crash",
                        plugin_name=plugin.name,
                        status=Status.ERROR,
                        duration_ms=(time.monotonic() - t0) * 1000,
                        message=f"Plugin crashed: {exc}",
                        error_code="PLUGIN_CRASH",
                    )
                ]
            finally:
                try:
                    plugin.cleanup(context)
                except Exception:  # noqa: BLE001
                    pass

            for r in results:
                status_str = r.status.value
                log.info("    %s  %s", status_str.ljust(5), r.test_id)

            all_results.extend(results)

        # 6. Apply rules / diagnostics
        all_results = apply_rules(all_results)

        # 7. Assemble RunResult
        run_result = RunResult(
            run_id=run_id,
            board_name=profile.board.name,
            started_at=started_at,
            results=all_results,
            environment=env,
            mock_mode=self.mock_mode,
        )
        run_result.finalize()

        log.info(
            "Run complete – PASS=%d FAIL=%d SKIP=%d ERROR=%d",
            run_result.summary.passed,
            run_result.summary.failed,
            run_result.summary.skipped,
            run_result.summary.errors,
        )
        return run_result
