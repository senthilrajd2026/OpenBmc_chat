# Issue-Based Training Example Guidelines

## Philosophy

GitHub issues from OpenBMC repos are gold for debugging training data because:
1. They describe real symptoms engineers encountered
2. Closed issues often contain resolution hints
3. They include actual commands and log snippets
4. They represent the exact class of problems our model should handle

## How to Generate From Issues

### Step 1: Extract the symptom
Turn the issue title + body into a symptom statement.
Do NOT copy the issue title directly — rephrase as a question.

**Issue title**: "phosphor-logging crashes after host power cycle"
**Generated instruction**: "After a host power cycle, the event logging service
becomes unavailable and no new events are recorded. How would you diagnose this?"

### Step 2: Determine resolution availability
- If issue has a resolution comment: include it as supporting evidence in the answer
- If issue is closed without clear resolution: treat as partially resolved,
  focus on diagnosis sequence

### Step 3: Generate structured output
Follow the troubleshoot format exactly.
Do NOT copy the issue body as the output.

### Step 4: Calibrate confidence
- Issue clearly resolved with evidence: High confidence for that specific fix
- Issue closed without resolution: Low-Medium confidence

## What to Avoid

- DO NOT copy the issue body verbatim as the output
- DO NOT invent a resolution that wasn't in the issue
- DO NOT generate generic "here are 10 things to check" lists
- DO NOT omit the specific service names that appear in the issue

## Handling Issues With Command Output

If the issue body contains command outputs (journalctl, systemctl, busctl),
use them to make the example more concrete:

```
# Instruction: Include reference to the specific symptom
"We're seeing the following in journalctl for phosphor-logging:
  'Error opening file /var/lib/phosphor-logging/errors/...'
  'Failed to persist event log entry'
What does this indicate and how should we proceed?"

# Output: Reference the specific error and explain its meaning
```

## Handling Issues Without Commands

For issues that only describe symptoms without commands,
generate an output that teaches the reader which commands
would have been helpful:

```
"Suggested checks/commands:
# These commands would have identified the root cause
journalctl -u xyz.openbmc_project.Logging.service --no-pager -n 100
ls -la /var/lib/phosphor-logging/
df -h /var/lib/phosphor-logging/"
```
