"""Tests for the validators module."""

import pytest
from src.openbmc_ft_poc.validators import (
    ValidationResult,
    validate_batch,
    validate_example,
)

GOOD_TROUBLESHOOT_OUTPUT = """\
**Assessment**
This appears to be a phosphor-logging service failure or startup issue.

**Likely OpenBMC area**
phosphor-logging / xyz.openbmc_project.Logging

**Likely components/services**
- xyz.openbmc_project.Logging.service
- phosphor-log-manager binary

**Why this is likely**
The empty event log after reboot is consistent with the logging service failing
to persist events, either due to a restart race or storage path issue.

**Suggested checks/commands**
```bash
systemctl status xyz.openbmc_project.Logging.service
journalctl -u xyz.openbmc_project.Logging.service --no-pager -n 50
ls -la /var/lib/phosphor-logging/
```

**Missing evidence**
- Full journalctl output for the logging service since boot
- Whether /var/lib/phosphor-logging/ is accessible

**Confidence**
Medium — pattern consistent with logging race, but need journal output to confirm.
"""

GOOD_INSTRUCTION = "After a host reboot, the event log is completely empty. phosphor-logging was working before the reboot. What should I check first?"

GOOD_EXPLAIN_OUTPUT = """\
**Explanation**
The xyz.openbmc_project.ObjectMapper is a D-Bus service that maintains
a registry of all D-Bus objects and interfaces exported by other services.
It allows any service to query "which service owns this object path?"

**Why it matters in practice**
Without ObjectMapper, services like bmcweb, ipmid, and phosphor-state-manager
cannot resolve D-Bus paths at runtime. A failed ObjectMapper causes cascading failures.

**Related OpenBMC area**
phosphor-mapper / phosphor-dbus-interfaces

**Common debug checks**
```bash
systemctl status xyz.openbmc_project.ObjectMapper.service
busctl tree xyz.openbmc_project.ObjectMapper
```

**Confidence**
High — ObjectMapper behavior is well documented.
"""


class TestValidateExample:
    def test_valid_troubleshoot_example(self):
        ex = {
            "instruction": GOOD_INSTRUCTION,
            "input": "",
            "output": GOOD_TROUBLESHOOT_OUTPUT,
            "metadata": {"pattern": "event_logging_debug"},
        }
        result = validate_example(ex)
        assert result.valid, f"Expected valid but got: {result.reasons}"

    def test_valid_explain_example(self):
        ex = {
            "instruction": "What is the xyz.openbmc_project.ObjectMapper service and why does it matter?",
            "input": "",
            "output": GOOD_EXPLAIN_OUTPUT,
            "metadata": {"pattern": "dbus_lookup_debug"},
        }
        result = validate_example(ex)
        assert result.valid, f"Expected valid but got: {result.reasons}"

    def test_missing_instruction(self):
        ex = {"instruction": "", "input": "", "output": GOOD_TROUBLESHOOT_OUTPUT}
        result = validate_example(ex)
        assert not result.valid
        assert any("missing_instruction" in r for r in result.reasons)

    def test_missing_output(self):
        ex = {"instruction": GOOD_INSTRUCTION, "input": "", "output": ""}
        result = validate_example(ex)
        assert not result.valid
        assert any("missing_output" in r for r in result.reasons)

    def test_output_too_short(self):
        ex = {
            "instruction": GOOD_INSTRUCTION,
            "input": "",
            "output": "Check systemctl.",  # way too short
        }
        result = validate_example(ex)
        assert not result.valid
        assert any("too_short" in r for r in result.reasons)

    def test_instruction_too_short(self):
        ex = {
            "instruction": "BMC?",  # too short
            "input": "",
            "output": GOOD_TROUBLESHOOT_OUTPUT,
        }
        result = validate_example(ex)
        assert not result.valid

    def test_no_commands_in_troubleshoot(self):
        no_commands_output = """\
**Assessment**
There might be a service issue with phosphor-logging.

**Likely OpenBMC area**
phosphor-logging area probably.

**Likely components/services**
- The logging service definitely.

**Why this is likely**
Because logging is involved in this scenario obviously.

**Suggested checks/commands**
You should check the service status and logs if possible.

**Missing evidence**
Need more information from the system logs maybe.

**Confidence**
Low — not enough info to say more.
"""
        ex = {
            "instruction": GOOD_INSTRUCTION,
            "input": "",
            "output": no_commands_output,
            "metadata": {"pattern": "event_logging_debug"},
        }
        result = validate_example(ex)
        assert not result.valid
        assert any("no_commands" in r for r in result.reasons)

    def test_missing_confidence(self):
        output_no_confidence = GOOD_TROUBLESHOOT_OUTPUT.replace(
            "**Confidence**\nMedium — pattern consistent with logging race, but need journal output to confirm.",
            ""
        )
        ex = {
            "instruction": GOOD_INSTRUCTION,
            "input": "",
            "output": output_no_confidence,
            "metadata": {"pattern": "event_logging_debug"},
        }
        result = validate_example(ex)
        assert not result.valid
        assert any("confidence" in r.lower() for r in result.reasons)

    def test_generic_output_rejected(self):
        generic_output = (
            "OpenBMC is an open source firmware project. "
            "There are many ways to debug issues. "
            "It depends on the situation. " * 5
            + "\n\n**Confidence**\nMedium"
        )
        ex = {
            "instruction": GOOD_INSTRUCTION,
            "input": "",
            "output": generic_output,
        }
        result = validate_example(ex)
        assert not result.valid


class TestValidateBatch:
    def test_batch_returns_two_lists(self):
        examples = [
            {
                "instruction": GOOD_INSTRUCTION,
                "input": "",
                "output": GOOD_TROUBLESHOOT_OUTPUT,
                "metadata": {"pattern": "event_logging_debug"},
            },
            {
                "instruction": "x",
                "input": "",
                "output": "short",
            },
        ]
        valid, rejected = validate_batch(examples)
        assert len(valid) + len(rejected) == len(examples)

    def test_rejected_have_reasons(self):
        examples = [
            {"instruction": "", "input": "", "output": ""},
        ]
        _, rejected = validate_batch(examples)
        assert len(rejected) == 1
        assert "rejection_reasons" in rejected[0]
        assert len(rejected[0]["rejection_reasons"]) > 0

    def test_empty_batch(self):
        valid, rejected = validate_batch([])
        assert valid == []
        assert rejected == []
