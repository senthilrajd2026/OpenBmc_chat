"""
SFT example generation for openbmc-ft-poc.

Implements an LLM provider abstraction with:
- mock/offline mode (deterministic, no API calls)
- openai provider
- anthropic provider
- local (Ollama/compatible) provider

All providers return the same schema: instruction, input, output, metadata.
"""

from __future__ import annotations

import json
import os
import random
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from .answer_formats import (
    INSUFFICIENT_EVIDENCE_EXAMPLE,
    TROUBLESHOOT_EXAMPLE,
)
from .logging_utils import get_logger

logger = get_logger(__name__)


# ------------------------------------------------------------------
# Schema
# ------------------------------------------------------------------

def make_example(
    instruction: str,
    input_text: str,
    output: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a canonical training example dict."""
    return {
        "instruction": instruction.strip(),
        "input": input_text.strip(),
        "output": output.strip(),
        "metadata": metadata or {},
    }


# ------------------------------------------------------------------
# Provider abstraction
# ------------------------------------------------------------------

class LLMProvider(ABC):
    """Abstract base for LLM generation providers."""

    @abstractmethod
    def generate(self, prompt: str, system: str = "") -> str | None:
        """Generate text from a prompt. Returns None on failure."""
        ...

    def parse_json_output(self, text: str) -> dict[str, Any] | None:
        """Parse JSON from LLM output, handling markdown fences."""
        if not text:
            return None
        # Strip markdown code fences if present
        text = re.sub(r"^```(?:json)?\n?", "", text.strip())
        text = re.sub(r"\n?```$", "", text.strip())
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON object from text
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
        logger.debug(f"Failed to parse JSON from LLM output: {text[:200]}")
        return None


class MockProvider(LLMProvider):
    """
    Offline mock provider for testing and offline dataset generation.

    Returns realistic-looking but pre-baked examples.
    Does NOT call any external API.
    Uses the source context to vary the output slightly.
    """

    def __init__(self, seed: int = 42) -> None:
        random.seed(seed)
        self._counter = 0

    def generate(self, prompt: str, system: str = "") -> str | None:
        """Return a mock structured example based on prompt content."""
        self._counter += 1

        # Detect source type from prompt to vary the output
        if "insufficient_evidence" in prompt.lower() or (
            "vague" in prompt.lower() and "underspecified" in prompt.lower()
        ):
            return self._mock_insufficient_evidence()

        if "service unit" in prompt.lower() or "ExecStart" in prompt:
            return self._mock_service_example(prompt)

        if "dbus interface" in prompt.lower() or "xyz.openbmc_project" in prompt:
            return self._mock_dbus_example(prompt)

        if "github issue" in prompt.lower() or "issue body" in prompt.lower():
            return self._mock_issue_example(prompt)

        return self._mock_doc_example(prompt)

    def _extract_context(self, prompt: str, key: str) -> str:
        """Extract a value from prompt text after a key pattern."""
        m = re.search(rf"{re.escape(key)}[:\s]+([^\n]+)", prompt, re.IGNORECASE)
        return m.group(1).strip() if m else ""

    def _mock_doc_example(self, prompt: str) -> str:
        repo = self._extract_context(prompt, "Repo") or "openbmc/openbmc"
        section = self._extract_context(prompt, "Section") or "OpenBMC subsystem"
        subsystem = self._extract_context(prompt, "Subsystem") or "phosphor-dbus-interfaces"

        variations = [
            {
                "instruction": f"A phosphor-logging service is failing to record events after a system reset on our {repo.split('/')[-1]} platform. The event log appears empty even though we know errors occurred. Where should we start debugging?",
                "input": "Platform: AST2600-based BMC. OpenBMC master branch from last week.",
                "output": f"""**Assessment**
This symptom points to phosphor-logging or its D-Bus event logging interface failing to persist or publish events. Most likely causes: the logging service crashed after reset, the persistent storage path has permission/mount issues, or the journal socket is not yet available when the log attempt is made.

**Likely OpenBMC area**
phosphor-logging / xyz.openbmc_project.Logging

**Likely components/services**
- xyz.openbmc_project.Logging.service (phosphor-log-manager)
- /var/lib/phosphor-logging/ (persistent storage)
- xyz.openbmc_project.Logging D-Bus interface

**Why this is likely**
Empty event log after reset with confirmed errors is almost always either:
1. phosphor-log-manager failing to start/restart after reset
2. The persistent log path being wiped or inaccessible after reset
3. A service trying to log before phosphor-log-manager finishes starting (race condition)

**Suggested checks/commands**
```bash
# Check if logging service is running
systemctl status xyz.openbmc_project.Logging.service

# Check recent journal output from the service
journalctl -u xyz.openbmc_project.Logging.service --no-pager -n 50

# Verify persistent log storage
ls -la /var/lib/phosphor-logging/

# Check D-Bus registration
busctl tree xyz.openbmc_project.Logging

# Attempt to read existing log entries via D-Bus
busctl call xyz.openbmc_project.Logging /xyz/openbmc_project/logging \\
  xyz.openbmc_project.Logging.Internal Manager GetAll s ""
```

**Missing evidence**
- `systemctl --failed` output after reset
- journalctl output from phosphor-log-manager around reset time
- Whether /var/lib/phosphor-logging/ is on tmpfs or persistent flash
- OpenBMC version/commit hash

**Confidence**
Medium — pattern consistent with logging service restart race or storage issue, but need log output to confirm."""
            },
            {
                "instruction": f"The xyz.openbmc_project.ObjectMapper service is returning 'object not found' for a sensor path after BMC reboot. The path was present before reboot. What should I check?",
                "input": "Error seen in bmcweb: GetObject failed for /xyz/openbmc_project/sensors/temperature/cpu_temp",
                "output": """**Assessment**
ObjectMapper 'object not found' after reboot almost always means the service that owns the object path has not yet registered it, or the service itself failed to start. This is a startup race condition or service failure.

**Likely OpenBMC area**
xyz.openbmc_project.ObjectMapper / phosphor-sensors / entity-manager

**Likely components/services**
- xyz.openbmc_project.ObjectMapper (mapper query layer)
- phosphor-virtual-sensor or phosphor-hwmon (sensor owner)
- entity-manager (sensor configuration)
- phosphor-sensor-aggregation-manager (if used)

**Why this is likely**
ObjectMapper returns 'not found' when no service has registered an object at the requested path. After reboot, sensor services initialize asynchronously. If the query arrives before initialization completes, the object appears missing even though it will appear later.

**Suggested checks/commands**
```bash
# Check if sensor service has registered the path
busctl tree xyz.openbmc_project.HwmonTempSensor 2>/dev/null || \\
  busctl tree xyz.openbmc_project.VirtualSensor 2>/dev/null

# Check entity-manager is running and has processed the config
systemctl status xyz.openbmc_project.EntityManager.service
journalctl -u xyz.openbmc_project.EntityManager.service --no-pager -n 30

# Check all services registered at /xyz/openbmc_project/sensors
busctl tree --list | grep sensors

# Check mapper registration for the path
busctl call xyz.openbmc_project.ObjectMapper \\
  /xyz/openbmc_project/object_mapper \\
  xyz.openbmc_project.ObjectMapper GetObject \\
  sas "/xyz/openbmc_project/sensors/temperature/cpu_temp" 0
```

**Missing evidence**
- Which service should own this sensor path (check entity-manager config)
- Whether the sensor appears after waiting 60+ seconds post-boot
- entity-manager configuration file for this sensor
- `systemctl --failed` output

**Confidence**
Medium-High — startup race is the most common cause; need the sensor service name to confirm."""
            }
        ]

        example = variations[self._counter % len(variations)]
        return json.dumps({
            "instruction": example["instruction"],
            "input": example["input"],
            "output": example["output"],
            "metadata": {
                "source_id": f"mock::{self._counter}",
                "source_type": "doc_chunk",
                "pattern": "dbus_lookup_debug",
                "subsystem": subsystem,
            }
        }, ensure_ascii=False)

    def _mock_service_example(self, prompt: str) -> str:
        service = self._extract_context(prompt, "Service") or "phosphor-ipmi-host"
        desc = self._extract_context(prompt, "Description") or "phosphor IPMI daemon"

        return json.dumps({
            "instruction": f"The {service} service is showing 'activating' but never reaches 'active'. IPMI commands are timing out. What is the diagnosis approach?",
            "input": f"BMC is accessible via Redfish. {service} description: {desc}",
            "output": f"""**Assessment**
A service stuck in 'activating' state typically means the main process is running but has not signaled systemd that it is ready, or a dependency is blocking startup. For {service}, this most often means the D-Bus name has not been acquired.

**Likely OpenBMC area**
phosphor-ipmi-host / ipmid / systemd service management

**Likely components/services**
- {service}
- xyz.openbmc_project.Ipmi.Host (D-Bus service name)
- IPMI provider shared libraries in /usr/lib/ipmid-providers/

**Why this is likely**
ipmid loads provider plugins dynamically at startup. If a plugin fails to load or a required D-Bus object is not available, the daemon may hang in initialization without signaling systemd.

**Suggested checks/commands**
```bash
# Check exact service state
systemctl status {service} --no-pager

# Look for startup errors in the service journal
journalctl -u {service} --no-pager -n 80

# Check if ipmid has acquired its D-Bus name
busctl list | grep -i ipmi

# Check for failed provider plugins
journalctl -u {service} | grep -i "error\\|failed\\|plugin\\|provider"

# Check socket activation if applicable
systemctl status {service.replace('.service', '.socket')} 2>/dev/null
```

**Missing evidence**
- Full journalctl output for {service} since last boot
- Whether this is a fresh install or regression
- OpenBMC platform and version
- `systemctl list-dependencies {service}` output

**Confidence**
Medium — stuck 'activating' for ipmid is consistent with plugin load failure or D-Bus dependency, but exact cause needs the journal output.""",
            "metadata": {
                "source_id": f"mock::service::{service}",
                "source_type": "service_unit",
                "pattern": "service_state_debug",
                "subsystem": "phosphor-ipmi",
            }
        }, ensure_ascii=False)

    def _mock_dbus_example(self, prompt: str) -> str:
        iface = self._extract_context(prompt, "D-Bus interface") or "xyz.openbmc_project.Sensor.Value"

        return json.dumps({
            "instruction": f"How do I verify that the {iface} interface is correctly exported by the expected service on a running BMC?",
            "input": "",
            "output": f"""**Explanation**
The {iface} interface should be exported by a specific service. To verify it, you need to check whether the D-Bus interface is visible on the system bus and that the correct service owns the object.

**Why it matters in practice**
If a client (like bmcweb or ipmid) queries this interface and it is absent or owned by the wrong service, all dependent features fail silently or with cryptic errors. Verifying the interface export is the first step in any D-Bus-related debug.

**Related OpenBMC area**
phosphor-dbus-interfaces / ObjectMapper

**Common debug checks**
```bash
# List all services and confirm which one exports this interface
busctl tree --list | grep <expected-service>

# Introspect the interface at the expected object path
busctl introspect <service-name> <object-path>

# Check the mapper knows about the interface
busctl call xyz.openbmc_project.ObjectMapper \\
  /xyz/openbmc_project/object_mapper \\
  xyz.openbmc_project.ObjectMapper GetSubTree \\
  sias "/" 0 1 "{iface}"

# Confirm the service is running and active
systemctl status <expected-service>
```

**Confidence**
High — these steps reliably verify interface export for any xyz.openbmc_project.* interface.""",
            "metadata": {
                "source_id": f"mock::dbus::{iface}",
                "source_type": "dbus_interface",
                "pattern": "dbus_lookup_debug",
                "subsystem": "phosphor-dbus-interfaces",
            }
        }, ensure_ascii=False)

    def _mock_issue_example(self, prompt: str) -> str:
        title = self._extract_context(prompt, "Issue:") or "sensor not appearing after boot"

        return json.dumps({
            "instruction": f"We're seeing '{title}' on a new platform bring-up. This appeared after switching to a newer OpenBMC build. How would you approach this?",
            "input": "Platform is AST2600-based. Issue was not present 3 builds ago.",
            "output": """**Assessment**
This is a regression on a new platform bring-up. The first step is to isolate whether the issue is a build/recipe change, a config change, or a hardware/driver difference. Start with a bisect or changelog review before diving into logs.

**Likely OpenBMC area**
entity-manager / phosphor-sensors / Yocto recipe layer

**Likely components/services**
- entity-manager (sensor configuration and inventory)
- phosphor-hwmon or phosphor-virtual-sensor (depending on sensor type)
- Machine config layer (meta-<platform>)

**Why this is likely**
Regressions after a build switch on new platform bring-ups are usually caused by:
1. An entity-manager configuration change or JSON config regression
2. A new hwmon driver kernel config missing from the platform layer
3. A recipe version bump breaking the sensor configuration format

**Suggested checks/commands**
```bash
# Check if entity-manager is processing the config correctly
journalctl -u xyz.openbmc_project.EntityManager.service --no-pager -n 60

# Look for sensor-related errors
journalctl | grep -i "sensor\\|hwmon\\|entity" | tail -40

# Check what sensors are currently present
busctl tree xyz.openbmc_project.HwmonTempSensor 2>/dev/null
busctl tree xyz.openbmc_project.VirtualSensor 2>/dev/null

# Compare entity-manager config between working and broken build
diff old-build/entity-manager-config/ new-build/entity-manager-config/

# Check sysfs for the underlying hardware
ls /sys/class/hwmon/
```

**Missing evidence**
- Which specific sensor type is missing (temperature, voltage, fan?)
- entity-manager configuration JSON for the affected sensor
- Diff of entity-manager recipe or config between builds
- Whether the sensor appears in sysfs (`/sys/class/hwmon/`)

**Confidence**
Medium — regression pattern is clear; need the config diff and journal output to pinpoint the exact cause.""",
            "metadata": {
                "source_id": "mock::issue::1",
                "source_type": "github_issue",
                "pattern": "sensor_debug",
                "subsystem": "phosphor-sensors",
            }
        }, ensure_ascii=False)

    def _mock_insufficient_evidence(self) -> str:
        questions = [
            "My BMC stopped responding to IPMI commands after a firmware update. How do I start diagnosing this?",
            "Sensors are showing incorrect values on our OpenBMC platform after reboot. Where do I begin?",
            "The Redfish API is returning HTTP 503 errors. We have not changed anything recently. What is the approach?",
            "OpenBMC is not completing the boot sequence after a recent change. How should I investigate this?",
            "Fan control is behaving erratically and fans are spinning at max speed. What could cause this?",
            "Event logs are completely empty after a host power cycle on our OpenBMC system. How do I debug this?",
            "Network connectivity to the BMC dropped intermittently. What is the correct diagnostic approach?",
        ]
        q = questions[self._counter % len(questions)]

        return json.dumps({
            "instruction": q,
            "input": "",
            "output": INSUFFICIENT_EVIDENCE_EXAMPLE,
            "metadata": {
                "source_id": f"mock::insufficient::{self._counter}",
                "source_type": "synthetic",
                "pattern": "insufficient_evidence",
                "subsystem": "",
            }
        }, ensure_ascii=False)


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self._api_key = api_key
        self._model = model

    def generate(self, prompt: str, system: str = "") -> str | None:
        try:
            import openai  # type: ignore
            client = openai.OpenAI(api_key=self._api_key)
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            resp = client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0.7,
                max_tokens=1024,
            )
            return resp.choices[0].message.content
        except Exception as exc:
            logger.error(f"OpenAI generation failed: {exc}")
            return None


class AnthropicProvider(LLMProvider):
    """Anthropic API provider."""

    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307") -> None:
        self._api_key = api_key
        self._model = model

    def generate(self, prompt: str, system: str = "") -> str | None:
        try:
            import anthropic  # type: ignore
            client = anthropic.Anthropic(api_key=self._api_key)
            resp = client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=system or "You are a helpful assistant.",
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text
        except Exception as exc:
            logger.error(f"Anthropic generation failed: {exc}")
            return None


class LocalProvider(LLMProvider):
    """Local LLM provider (Ollama or OpenAI-compatible endpoint)."""

    def __init__(self, url: str, model: str) -> None:
        self._url = url
        self._model = model

    def generate(self, prompt: str, system: str = "") -> str | None:
        try:
            import requests
            full_prompt = f"{system}\n\n{prompt}" if system else prompt
            resp = requests.post(
                self._url,
                json={"model": self._model, "prompt": full_prompt, "stream": False},
                timeout=120,
            )
            if resp.status_code == 200:
                return resp.json().get("response", "")
        except Exception as exc:
            logger.error(f"Local LLM generation failed: {exc}")
        return None


def get_provider(
    provider_name: str,
    **kwargs: Any,
) -> LLMProvider:
    """
    Factory: return the appropriate LLMProvider.

    Args:
        provider_name: "mock", "openai", "anthropic", "local"
        **kwargs: Provider-specific arguments (api_key, model, url, etc.)

    Returns:
        LLMProvider instance
    """
    name = provider_name.lower()

    if name == "mock":
        return MockProvider(seed=kwargs.get("seed", 42))

    if name == "openai":
        api_key = kwargs.get("api_key") or os.environ.get("OPENAI_API_KEY", "")
        model = kwargs.get("model") or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set; falling back to mock provider")
            return MockProvider()
        return OpenAIProvider(api_key=api_key, model=model)

    if name == "anthropic":
        api_key = kwargs.get("api_key") or os.environ.get("ANTHROPIC_API_KEY", "")
        model = kwargs.get("model") or os.environ.get("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set; falling back to mock provider")
            return MockProvider()
        return AnthropicProvider(api_key=api_key, model=model)

    if name == "local":
        url = kwargs.get("url") or os.environ.get("LOCAL_LLM_URL", "http://localhost:11434/api/generate")
        model = kwargs.get("model") or os.environ.get("LOCAL_LLM_MODEL", "mistral:7b")
        return LocalProvider(url=url, model=model)

    logger.warning(f"Unknown provider '{provider_name}'; using mock")
    return MockProvider()
