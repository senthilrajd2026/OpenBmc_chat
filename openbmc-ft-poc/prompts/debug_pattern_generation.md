# Debug Pattern Generation Guidelines

## Overview

This file documents how to generate high-quality debug pattern examples
for each of the 12 debug patterns defined in `configs/dataset_rules.yaml`.

## Pattern: service_state_debug

**Target scenario**: A systemd service in OpenBMC is failed, inactive, or stuck.

**Instruction pattern**:
- "X service is not starting / crashed / stuck in activating"
- "I see 'Failed to start X' in the logs"
- "systemctl status shows X service as failed"

**Must include commands**:
- `systemctl status <service>` — check current state
- `journalctl -u <service> --no-pager -n 50` — check recent logs
- `systemctl list-dependencies <service>` — check dependencies

**Missing evidence to request**:
- Full journalctl output since boot
- `systemctl --failed` output
- Whether this is a first boot or regression

---

## Pattern: dbus_lookup_debug

**Target scenario**: ObjectMapper GetObject fails, D-Bus interface not found.

**Instruction pattern**:
- "busctl shows object path missing"
- "GetObject failed for /xyz/openbmc_project/..."
- "Service cannot find D-Bus interface"

**Must include commands**:
- `busctl tree <service>` — see what the service exports
- `busctl call xyz.openbmc_project.ObjectMapper ...GetObject sas <path> 0`
- `busctl introspect <service> <path>` — verify interface contents

**Missing evidence**:
- Exact D-Bus path being queried
- Which service should own the object
- Whether service is running at all

---

## Pattern: sensor_debug

**Target scenario**: Sensor not showing up, wrong value, stale reading.

**Instruction pattern**:
- "Temperature sensor shows 0 or -1"
- "Fan sensor not visible in ipmitool sensor list"
- "Voltage sensor disappeared after restart"

**Must include commands**:
- `busctl tree xyz.openbmc_project.HwmonTempSensor`
- `journalctl -u xyz.openbmc_project.EntityManager.service`
- `ls /sys/class/hwmon/` — check sysfs source
- `ipmitool sensor list | grep <name>`

**Missing evidence**:
- entity-manager JSON config for this sensor
- sysfs path for the hardware sensor
- Whether sensor existed before

---

## Pattern: host_state_debug

**Target scenario**: BMC cannot power on/off host, stuck state.

**Instruction pattern**:
- "Power on command has no effect"
- "Host stuck in On state even though host OS is down"
- "Can't get chassis power state via Redfish"

**Must include commands**:
- `busctl get-property xyz.openbmc_project.State.Host /xyz/openbmc_project/state/host0 xyz.openbmc_project.State.Host CurrentHostState`
- `systemctl status xyz.openbmc_project.State.Host.service`
- `journalctl -u xyz.openbmc_project.State.Host.service`

---

## Pattern: boot_progress_debug

**Target scenario**: Host is booting but progress stalls or regresses.

**Instruction pattern**:
- "Host stuck at POST"
- "BootProgress shows SystemInitComplete but OS never comes up"
- "Redfish shows 'OSRunning' incorrectly"

**Must include commands**:
- `busctl get-property xyz.openbmc_project.State.Host /xyz/openbmc_project/state/host0 xyz.openbmc_project.State.Host BootProgress`
- `ipmitool chassis status`
- `ipmitool sel list` — check for boot errors in SEL

---

## Pattern: insufficient_evidence

**Target scenario**: User asks a vague question without logs or context.

**Generation rule**: The model must NOT attempt to diagnose. It must:
1. Acknowledge the question is underspecified
2. List what evidence is specifically needed
3. Provide commands to gather that evidence
4. State Low confidence

**Examples of vague questions**:
- "My BMC isn't working"
- "IPMI is broken"
- "Sensors show wrong values"
- "The system won't boot"

**Model behavior to train**:
```
**Assessment**
The question does not provide enough context. [specific gap explained]

**Missing evidence**
- Exact error message or service name
- journalctl output from the affected service
- Platform/version information
- Last known working state

**Confidence**
Low — cannot diagnose without the above information
```
