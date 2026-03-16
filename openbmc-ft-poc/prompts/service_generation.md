# Service Unit Training Example Guidelines

## Philosophy

OpenBMC service unit files are a structured source of engineering knowledge:
- Service names (e.g., xyz.openbmc_project.Logging.service)
- Dependencies (Wants=, After=, Requires=)
- Executable paths (ExecStart=)

These map directly to the kinds of questions engineers ask:
- "This service failed, what do I check?"
- "What depends on this service?"
- "Where does this service log?"

## Generation Strategy

For each service unit, generate ONE of these question types:

### Type A: Service failure diagnosis
```
Instruction: "<service-name> is failing to start. What are the first checks?"
Output: [troubleshoot format with specific systemctl/journalctl commands]
```

### Type B: Dependency investigation
```
Instruction: "What services depend on / must start before <service-name>?"
Output: [explain format with relevant commands and explanation]
```

### Type C: D-Bus name ownership
```
Instruction: "How do I verify <service-name> has acquired its D-Bus name?"
Output: [troubleshoot format with busctl commands]
```

## Required Service Knowledge to Encode

For each service, the answer should teach:
1. The service's purpose (1 sentence, practical not theoretical)
2. Where its logs go (systemd journal, which unit name)
3. Its key D-Bus interfaces or names (if any)
4. Its systemd dependencies (what blocks it)
5. Common failure modes

## Example

**Service**: xyz.openbmc_project.ObjectMapper.service
**ExecStart**: /usr/bin/mapperx

**Good generated example**:
```
Instruction: "The xyz.openbmc_project.ObjectMapper service failed to start.
Several other services are now reporting D-Bus errors. How should I diagnose this?"

Output:
**Assessment**
ObjectMapper is a critical service — if it fails, all D-Bus object lookups via
GetObject/GetSubTree will fail, causing cascading errors in services that depend
on it (bmcweb, ipmid, phosphor-state-manager, etc.)

**Likely OpenBMC area**
xyz.openbmc_project.ObjectMapper / phosphor-mapper

**Likely components/services**
- xyz.openbmc_project.ObjectMapper.service
- mapperx binary (/usr/bin/mapperx)
- All services that use ObjectMapper for path resolution

**Why this is likely**
ObjectMapper startup failure is typically caused by:
1. Missing or corrupt mapperx binary
2. D-Bus system bus unavailable (dbus.service failure)
3. Permission error on the D-Bus configuration file
4. Conflict with another service claiming the same D-Bus name

**Suggested checks/commands**
```bash
# Check ObjectMapper service state
systemctl status xyz.openbmc_project.ObjectMapper.service

# Check full log since boot
journalctl -u xyz.openbmc_project.ObjectMapper.service --no-pager -n 80

# Verify D-Bus is running
systemctl status dbus.service

# Check if mapperx binary exists
ls -la /usr/bin/mapperx

# Try to call ObjectMapper directly (if it starts)
busctl call xyz.openbmc_project.ObjectMapper /xyz/openbmc_project/object_mapper \
  xyz.openbmc_project.ObjectMapper GetSubTreePaths sias "/" 0 0
```

**Missing evidence**
- Full journalctl output for ObjectMapper since last boot
- Whether dbus.service itself is healthy
- Error output from the journalctl -u command above

**Confidence**
Medium — ObjectMapper failure cascade is well-understood, but need journal output to identify exact root cause
```
