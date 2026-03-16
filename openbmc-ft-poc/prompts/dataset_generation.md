# Dataset Generation Prompt Guidelines

## Purpose

This file documents the prompt engineering philosophy for openbmc-ft-poc SFT data generation.
It is a reference for customizing or extending generation prompts.

## Core Principle

Every generated example must teach debugging behavior, not factual recall.

The model being trained must learn **patterns of thought**, not **encyclopedic knowledge**.

## What Makes a Good Training Example

### Good instruction (symptom-focused)
```
"The phosphor-ipmi-host service is stuck in 'activating' state after boot.
IPMI commands are timing out. What should I check first?"
```

### Bad instruction (definition-focused)
```
"What is phosphor-ipmi-host?"
```

### Good output structure
1. Assessment of what area is likely involved
2. Named components/services (not vague "the daemon")
3. Concrete commands with purpose explained
4. Explicit missing evidence stated
5. Confidence with caveat

### Bad output structure
- Starts with "OpenBMC is an open-source project..."
- Lists 10 generic steps without prioritization
- Claims root cause without evidence
- No commands or only generic commands
- "It depends" without specifics

## Difficulty Levels

The generator should vary difficulty across three levels:

### Level 1 (Common)
Standard service failure, sensor missing, D-Bus not found.
Expected commands: systemctl, journalctl, busctl.
Confidence: Medium to High.

### Level 2 (Intermediate)
Cross-service dependency, startup race, partial functionality.
Multiple services involved.
Confidence: Low to Medium.

### Level 3 (Advanced)
Platform-specific regression, recipe conflict, cross-subsystem interaction.
Requires bisect or deep investigation.
Confidence: Low.

## Pattern Weights

Target distribution for the generated dataset:
- debugging_and_triage: 45%
- subsystem_classification: 25%
- command_recommendation: 15%
- architecture_explanation: 10%
- insufficient_evidence: 5%

## Forbidden Outputs

Never generate examples where:
- The output is a book-style summary of OpenBMC architecture
- The output claims confirmed root cause without evidence
- The output has no OpenBMC-specific commands (use real command names!)
- The instruction is a multiple-choice exam question
- The output is shorter than 60 words

## Answer Format (Troubleshoot)

```
**Assessment**
[1-3 sentences on what this symptom suggests]

**Likely OpenBMC area**
[subsystem name, e.g. phosphor-logging, bmcweb, entity-manager]

**Likely components/services**
- service1
- interface1
- config file path if relevant

**Why this is likely**
[reason this subsystem is suspect, based on the symptom]

**Suggested checks/commands**
```bash
# Command 1 with purpose
systemctl status <service>

# Command 2 with purpose
journalctl -u <service> --no-pager -n 50
```

**Missing evidence**
- What logs are still needed
- Which object paths or service names are unknown
- What version/platform info is needed

**Confidence**
Medium — reason for this confidence level
```

## Answer Format (Explain)

Only use this for genuine "what is" or "how does" questions.
Do NOT use for symptoms or debug scenarios.

```
**Explanation**
[clear, practical explanation focused on how this works in OpenBMC]

**Why it matters in practice**
[when engineers encounter this, what it means operationally]

**Related OpenBMC area**
[subsystem]

**Common debug checks**
```bash
# relevant commands
```

**Confidence**
High — well-documented behavior
```
