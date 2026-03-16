"""
Answer format templates for openbmc-ft-poc.

Defines the structured answer formats that the fine-tuned model
should produce. These formats are used both in generation prompts
and in validation checks.
"""

from __future__ import annotations

from typing import Literal

AnswerType = Literal["troubleshoot", "explain"]


TROUBLESHOOT_TEMPLATE = """\
**Assessment**
{assessment}

**Likely OpenBMC area**
{area}

**Likely components/services**
{components}

**Why this is likely**
{reasoning}

**Suggested checks/commands**
{commands}

**Missing evidence**
{missing}

**Confidence**
{confidence}"""


EXPLAIN_TEMPLATE = """\
**Explanation**
{explanation}

**Why it matters in practice**
{practical}

**Related OpenBMC area**
{area}

**Common debug checks**
{debug_checks}

**Confidence**
{confidence}"""


TROUBLESHOOT_EXAMPLE = """\
**Assessment**
This looks like a D-Bus ObjectMapper lookup failure, likely because the service
that owns the object path hasn't finished initializing, or the service itself
has crashed/not started.

**Likely OpenBMC area**
phosphor-dbus-interfaces / xyz.openbmc_project.ObjectMapper

**Likely components/services**
- xyz.openbmc_project.ObjectMapper
- The service that should own the failing object path
- phosphor-ipmi-host or bmcweb (if the lookup comes from one of these)

**Why this is likely**
ObjectMapper errors during early boot are almost always either a race condition
(service not yet ready) or a service that failed to start. The "GetObject failed"
error indicates the mapper could not find any service registered for the requested path.

**Suggested checks/commands**
```
# Check if ObjectMapper itself is running
systemctl status xyz.openbmc_project.ObjectMapper.service

# Check what is registered at the path
busctl tree xyz.openbmc_project.ObjectMapper

# Check if the expected service is running
systemctl status <expected-service>
journalctl -u <expected-service> --no-pager -n 50

# See what paths are currently exported
busctl call xyz.openbmc_project.ObjectMapper /xyz/openbmc_project/object_mapper \
  xyz.openbmc_project.ObjectMapper GetSubTreePaths sias "/" 0 0
```

**Missing evidence**
- Exact object path being looked up
- Which service or daemon is making the GetObject call
- journalctl output from the calling service
- `systemctl --failed` output at the time of the error

**Confidence**
Medium — pattern matches ObjectMapper lookup failure, but without the exact path
and calling service logs, we cannot confirm whether this is a startup race or
a permanent missing object."""


INSUFFICIENT_EVIDENCE_EXAMPLE = """\
**Assessment**
The question does not provide enough context to diagnose the issue. The reported
symptom ("not working") is too broad. OpenBMC has many subsystems that could
match this description.

**Likely OpenBMC area**
Cannot determine without more information.

**Likely components/services**
Cannot determine without more information.

**Why this is likely**
N/A — insufficient evidence to narrow the area.

**Suggested checks/commands**
To help narrow the diagnosis, please run the following and share the output:
```
# Identify failing services
systemctl --failed

# Recent system log
journalctl -n 100 --no-pager

# BMC state
busctl get-property xyz.openbmc_project.State.BMC \
  /xyz/openbmc_project/state/bmc0 \
  xyz.openbmc_project.State.BMC CurrentBMCState

# Redfish availability
curl -sk https://localhost/redfish/v1 | python3 -m json.tool
```

**Missing evidence**
- Exact error message or log output
- Which subsystem or function is "not working" (IPMI, Redfish, sensors, boot, etc.)
- Platform / OpenBMC commit / version
- What was the last known working state

**Confidence**
Low — cannot proceed without the above evidence."""


def get_troubleshoot_sections() -> list[str]:
    """Return list of required section headers for troubleshoot format."""
    return [
        "Assessment",
        "Likely OpenBMC area",
        "Likely components",
        "Why this is likely",
        "Suggested checks",
        "Missing evidence",
        "Confidence",
    ]


def get_explain_sections() -> list[str]:
    """Return list of required section headers for explain format."""
    return [
        "Explanation",
        "Why it matters",
        "Related OpenBMC area",
        "Common debug",
        "Confidence",
    ]


def detect_answer_type(instruction: str) -> AnswerType:
    """
    Detect whether an instruction calls for troubleshoot or explain format.

    Heuristic: 'why', 'what is', 'explain', 'how does' → explain.
    Everything else (symptoms, errors, failures) → troubleshoot.
    """
    lower = instruction.lower()
    explain_triggers = [
        "what is", "what are", "explain", "how does", "describe",
        "what does", "define", "overview of", "purpose of",
    ]
    for trigger in explain_triggers:
        if trigger in lower:
            return "explain"
    return "troubleshoot"
