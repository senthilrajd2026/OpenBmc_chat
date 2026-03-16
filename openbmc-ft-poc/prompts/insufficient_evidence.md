# Insufficient Evidence Training Guidelines

## Purpose

One of the most important behaviors to train is knowing when to ask
for more information rather than guessing.

A senior engineer does NOT say "the problem might be X" when they have no evidence.
A senior engineer says: "I need these specific pieces of information before I can diagnose."

## When to Trigger Insufficient Evidence Pattern

Generate insufficient-evidence examples when:
1. The instruction provides no service name, component, or log output
2. The symptom is extremely vague ("it's not working", "broken")
3. No platform, version, or context is provided
4. The question is a bare one-liner with no details

## What the Model Should Do

The model trained on these examples should:

1. **Acknowledge the gap** — state specifically what information is missing
2. **Not guess** — never say "the problem is probably X" without basis
3. **Provide gathering commands** — give specific commands to collect evidence
4. **Explain why those commands** — briefly explain what each will reveal
5. **State Low confidence** — be explicit that diagnosis cannot proceed

## Example Vague Questions to Generate

```
- "My BMC isn't responding to IPMI commands. How do I fix it?"
- "Sensors are showing wrong values on our system."
- "OpenBMC is not booting after our last update."
- "Redfish API is returning errors. What's wrong?"
- "The host won't power on. What should I check?"
- "Fan control is behaving strangely."
- "Event logs are missing after a power cycle."
- "Network on the BMC stopped working."
```

## Required Output Structure

```
**Assessment**
The question lacks sufficient context to diagnose the issue. [Why: specific gap]

**Likely OpenBMC area**
Cannot determine without more information.

**Likely components/services**
Cannot determine without more information.

**Why this is likely**
N/A — insufficient evidence to narrow the area.

**Suggested checks/commands**
To proceed with diagnosis, run the following and share the output:
```bash
# Identify any failed services
systemctl --failed

# Recent BMC system log
journalctl -n 100 --no-pager

# Check BMC state via D-Bus
busctl get-property xyz.openbmc_project.State.BMC \
  /xyz/openbmc_project/state/bmc0 \
  xyz.openbmc_project.State.BMC CurrentBMCState

# For IPMI issues also:
systemctl status phosphor-ipmi-host.service
journalctl -u phosphor-ipmi-host.service --no-pager -n 50
```

**Missing evidence**
Specifically, I need:
- Exact error message, log output, or command that is failing
- Which subsystem or function is affected (IPMI, Redfish, sensors, host state, etc.)
- OpenBMC version or commit hash
- Platform type (AST2600, POWER9, etc.)
- Whether this is a new regression or first-time setup
- Last known working state (if any)

**Confidence**
Low — cannot form a meaningful hypothesis without the above information.
Providing the systemctl and journalctl output above will immediately narrow the diagnosis.
```

## Key Quality Signals for This Pattern

A good insufficient-evidence example:
- Does NOT attempt to diagnose
- Provides 3-5 specific evidence-gathering commands
- Lists exactly what information is needed (not vague "more info")
- Explains why each piece of evidence matters
- Has a brief "Confidence: Low" explanation
