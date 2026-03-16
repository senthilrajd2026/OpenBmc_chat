"""
Prompt templates for SFT example generation.

These templates are used to instruct LLMs (or mock generators)
to produce engineer-style training examples grounded in OpenBMC context.
"""

from __future__ import annotations

from string import Template


# ------------------------------------------------------------------
# System instruction used for all generation calls
# ------------------------------------------------------------------
SYSTEM_INSTRUCTION = """\
You are a senior OpenBMC firmware engineer with 10+ years of experience
debugging OpenBMC systems, reviewing platform bring-ups, triaging service
failures, and guiding junior engineers through structured diagnosis.

Your answers must:
- State the most likely OpenBMC subsystem and components first
- Give a structured diagnosis sequence (not just a list of facts)
- Recommend specific commands with a brief rationale for each
- Explicitly state what evidence is still missing before confirming a root cause
- Separate facts from hypotheses clearly
- Never claim a root cause without supporting evidence
- Match the exact answer format provided in the instructions
- Avoid generic explanations; focus on practical diagnosis
- Use engineering vocabulary correctly (service names, D-Bus paths, unit names)
"""


# ------------------------------------------------------------------
# Generation prompt for document-based chunks
# ------------------------------------------------------------------
DOC_CHUNK_PROMPT = Template("""\
You are generating fine-tuning data for an OpenBMC engineering assistant.

## Context (from OpenBMC documentation)
Repo: $repo
File: $path
Section: $heading

Content:
$content

## Task
Generate ONE training example based on this OpenBMC documentation content.

The example must:
1. Have a realistic "instruction" that sounds like a question from an engineer
   debugging or triaging an OpenBMC system — NOT a study question or definition request.
2. Have an optional "input" with brief additional context (can be empty "").
3. Have an "output" in the following structured format:

For troubleshooting questions:
**Assessment**
...

**Likely OpenBMC area**
...

**Likely components/services**
...

**Why this is likely**
...

**Suggested checks/commands**
```
# include at least 2-3 concrete commands
```

**Missing evidence**
...

**Confidence**
Low | Medium | High — brief explanation

For explanation questions (use this ONLY if the question truly asks "what is" or "how does"):
**Explanation**
...

**Why it matters in practice**
...

**Related OpenBMC area**
...

**Common debug checks**
...

**Confidence**
Low | Medium | High — brief explanation

## Debug pattern (aim for this type)
Pattern: $pattern
Subsystem: $subsystem

## Output format (JSON only, no other text)
{
  "instruction": "...",
  "input": "...",
  "output": "...",
  "metadata": {
    "source_id": "$source_id",
    "source_type": "doc_chunk",
    "pattern": "$pattern",
    "subsystem": "$subsystem"
  }
}
""")


# ------------------------------------------------------------------
# Generation prompt for GitHub issues
# ------------------------------------------------------------------
ISSUE_PROMPT = Template("""\
You are generating fine-tuning data for an OpenBMC engineering assistant.

## Context (from GitHub issue)
Repo: $repo
Issue: #$issue_number — $title
Labels: $labels
State: $state

Issue body (truncated):
$body_snippet

$resolution_section

## Task
Generate ONE training example that teaches an engineer how to diagnose
this class of problem in OpenBMC.

Requirements:
- The "instruction" must describe a SYMPTOM or PROBLEM, not ask a definition question
- The "output" must follow the structured troubleshooting format exactly:
  **Assessment**, **Likely OpenBMC area**, **Likely components/services**,
  **Why this is likely**, **Suggested checks/commands**, **Missing evidence**, **Confidence**
- Include at least 2-3 concrete commands in "Suggested checks/commands"
- Do NOT claim a confirmed root cause unless the issue body provides clear resolution evidence
- If evidence is thin, say so in "Missing evidence" and keep Confidence at Low or Medium

## Output format (JSON only, no other text)
{
  "instruction": "...",
  "input": "...",
  "output": "...",
  "metadata": {
    "source_id": "$source_id",
    "source_type": "github_issue",
    "pattern": "$pattern",
    "subsystem": "$subsystem"
  }
}
""")


# ------------------------------------------------------------------
# Generation prompt for service unit metadata
# ------------------------------------------------------------------
SERVICE_PROMPT = Template("""\
You are generating fine-tuning data for an OpenBMC engineering assistant.

## Context (OpenBMC service unit)
Repo: $repo
Service: $service_name
Description: $description
ExecStart: $exec_start
Wants: $wants
After: $after

## Task
Generate ONE training example about this OpenBMC service.

Focus areas (pick the most appropriate):
1. What to check when this service fails to start
2. What D-Bus interfaces or paths this service owns
3. How this service interacts with other OpenBMC services
4. What logs to inspect when this service misbehaves

The output must use the troubleshooting format:
**Assessment**, **Likely OpenBMC area**, **Likely components/services**,
**Why this is likely**, **Suggested checks/commands**, **Missing evidence**, **Confidence**

## Output format (JSON only, no other text)
{
  "instruction": "...",
  "input": "...",
  "output": "...",
  "metadata": {
    "source_id": "$source_id",
    "source_type": "service_unit",
    "pattern": "service_state_debug",
    "subsystem": "$subsystem"
  }
}
""")


# ------------------------------------------------------------------
# Generation prompt for D-Bus interface strings
# ------------------------------------------------------------------
DBUS_PROMPT = Template("""\
You are generating fine-tuning data for an OpenBMC engineering assistant.

## Context
D-Bus interface: $dbus_value
Found in repo: $repo ($path)

## Task
Generate ONE training example about this D-Bus interface or object path.

Focus on:
- How to look up this interface with busctl
- What it represents in the OpenBMC object hierarchy
- Common failure modes when interacting with it
- How to confirm a service is correctly exporting it

Use the troubleshooting format:
**Assessment**, **Likely OpenBMC area**, **Likely components/services**,
**Why this is likely**, **Suggested checks/commands**, **Missing evidence**, **Confidence**

## Output format (JSON only, no other text)
{
  "instruction": "...",
  "input": "...",
  "output": "...",
  "metadata": {
    "source_id": "$source_id",
    "source_type": "dbus_interface",
    "pattern": "dbus_lookup_debug",
    "subsystem": "phosphor-dbus-interfaces"
  }
}
""")


# ------------------------------------------------------------------
# Generation prompt for insufficient-evidence scenarios
# ------------------------------------------------------------------
INSUFFICIENT_EVIDENCE_PROMPT = """\
You are generating fine-tuning data for an OpenBMC engineering assistant.

## Task
Generate ONE training example where an engineer asks a vague question
about an OpenBMC problem, and the model correctly identifies that it needs
more information before diagnosing.

The instruction should be realistic but deliberately underspecified:
- Vague symptom without specifying which service, platform, or error
- No log output provided
- Missing key context like OpenBMC version, IPMI channel, host type

The output MUST follow this format:
**Assessment**
Explain why the question lacks sufficient context.

**Likely OpenBMC area**
Cannot determine without more information.

**Likely components/services**
Cannot determine without more information.

**Why this is likely**
N/A — insufficient evidence.

**Suggested checks/commands**
Provide 3-4 commands the engineer SHOULD run to gather the missing evidence.

**Missing evidence**
List specifically what information is needed (exact service names, log output,
error messages, platform info, version, etc.)

**Confidence**
Low — explain why confidence is low.

## Output format (JSON only, no other text)
{
  "instruction": "...",
  "input": "",
  "output": "...",
  "metadata": {
    "source_id": "synthetic_insufficient_evidence",
    "source_type": "synthetic",
    "pattern": "insufficient_evidence",
    "subsystem": ""
  }
}
"""


def format_doc_chunk_prompt(
    chunk_dict: dict,
    pattern: str = "",
    subsystem: str = "",
) -> str:
    """Format a documentation chunk into a generation prompt."""
    return DOC_CHUNK_PROMPT.substitute(
        repo=chunk_dict.get("repo", ""),
        path=chunk_dict.get("path", ""),
        heading=chunk_dict.get("heading", ""),
        content=chunk_dict.get("content", "")[:800],
        pattern=pattern or chunk_dict.get("pattern_candidates", ["general"])[0:1][0] if chunk_dict.get("pattern_candidates") else "general",
        subsystem=subsystem or chunk_dict.get("subsystem", ""),
        source_id=chunk_dict.get("chunk_id", ""),
    )


def format_issue_prompt(signal: dict) -> str:
    """Format a GitHub issue signal into a generation prompt."""
    resolution = signal.get("resolution_hint", "")
    resolution_section = (
        f"Resolution (partial):\n{resolution[:400]}" if resolution else ""
    )
    patterns = signal.get("patterns", [])
    pattern = patterns[0] if patterns else "service_state_debug"

    return ISSUE_PROMPT.substitute(
        repo=signal.get("repo", ""),
        issue_number=signal.get("issue_number", ""),
        title=signal.get("title", ""),
        labels=", ".join(signal.get("labels", [])),
        state=signal.get("state", ""),
        body_snippet=signal.get("body_snippet", "")[:800],
        resolution_section=resolution_section,
        source_id=signal.get("source_id", ""),
        pattern=pattern,
        subsystem=signal.get("subsystem", ""),
    )


def format_service_prompt(service: dict, subsystem: str = "") -> str:
    """Format a service unit signal into a generation prompt."""
    return SERVICE_PROMPT.substitute(
        repo=service.get("repo", ""),
        service_name=service.get("service_name", ""),
        description=service.get("description", ""),
        exec_start=service.get("exec_start", ""),
        wants=" ".join(service.get("wants", [])),
        after=" ".join(service.get("after", [])),
        source_id=f"{service.get('repo', '')}::{service.get('service_name', '')}",
        subsystem=subsystem or "",
    )


def format_dbus_prompt(dbus: dict) -> str:
    """Format a D-Bus interface signal into a generation prompt."""
    return DBUS_PROMPT.substitute(
        dbus_value=dbus.get("value", ""),
        repo=dbus.get("repo", ""),
        path=dbus.get("path", ""),
        source_id=f"{dbus.get('repo', '')}::{dbus.get('value', '')}",
    )
