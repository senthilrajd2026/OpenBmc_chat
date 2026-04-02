# EmbedAI Validator

An extensible embedded hardware validation platform for Linux-based boards.
Run automated peripheral tests, collect structured results, generate reports,
and receive rule-based diagnostic suggestions — all from the command line.

---

## Architecture Overview

```
embedai-validator/
├── cli/            Command-line interface (Typer)
├── core/           Orchestrator, scheduler, context, result models
├── board/          YAML loader, schemas, inventory, mapper
├── plugins/        Per-peripheral test plugins (I2C, GPIO, UART, Ethernet, System)
├── ai/             Rules engine + summary recommendations
├── reports/        JSON and HTML exporters, Jinja2 template
├── utils/          Logger, shell helpers, path utilities
├── boards/         Board YAML profiles
├── output/         Generated reports (gitignored)
└── tests/          pytest test suite
```

**Design principles:**

- **Plugin-first** – every test is a self-contained plugin; add new peripherals
  without touching core code.
- **Graceful degradation** – if a tool or device is absent the plugin returns
  `SKIP` or an informative result rather than crashing.
- **Mock-friendly** – pass `--mock` to run the full pipeline on any Linux host
  without physical hardware.
- **Structured results** – every test produces a typed `TestResult`; reports
  and rules are both driven from the same model.

---

## Setup

### Prerequisites

- Python 3.11+
- Linux (tested on Ubuntu 22.04 / 24.04)

### Install

```bash
git clone <repo>
cd embedai-validator

# Editable install with dev extras
pip install -e ".[dev]"

# Optional UART loopback support
pip install -e ".[dev,serial]"
```

---

## Usage

### Validate a board (mock mode – no hardware required)

```bash
embedai validate -b boards/sample_board.yaml --mock
```

### Validate with verbose logging

```bash
embedai validate -b boards/sample_board.yaml --mock --verbose
```

### Run smoke suite only

```bash
embedai validate -b boards/sample_board.yaml --mock --suite smoke
```

### Real hardware validation

```bash
embedai validate -b boards/sample_board.yaml
```

### System inventory only

```bash
embedai inventory -b boards/sample_board.yaml
```

### List all registered plugins

```bash
embedai plugins
```

### Re-render HTML from an existing JSON result

```bash
embedai report -i output/report_20240402_120000.json
```

---

## Board Profile Format

```yaml
board:
  name: My Board
  vendor: Acme
  soc: i.MX8
  os: ubuntu
  revision: C0

interfaces:
  i2c:
    - bus: 1
      devices:
        - name: eeprom
          address: "0x50"   # hex string or integer both accepted

  gpio:
    - line: 23
      name: reset_modem
      direction: out        # "in" or "out"

  uart:
    - port: /dev/ttyUSB0
      baudrate: 115200
      loopback_required: false

  ethernet:
    - name: eth0
      phy_expected: true
```

---

## How Plugins Work

Each plugin lives in `plugins/<name>/plugin.py` and:

1. Inherits from `BasePlugin`
2. Declares `name`, `test_type`, `description`, `suites` class attributes
3. Implements `supports(context)` → skip if the board has no relevant interfaces
4. Implements `run(context)` → returns a `list[TestResult]`
5. Optionally implements `precheck()` and `cleanup()`

Register the plugin by decorating the class with `@register`:

```python
from plugins.base import BasePlugin, register

@register
class MyPlugin(BasePlugin):
    name = "my_peripheral"
    test_type = "peripheral"
    ...
```

It will be auto-discovered via `plugins/base.py:load_all_plugins()`.

---

## Sample Output

```
Results – Sample Embedded Board
┌────────────────────────────┬────────┬──────────────────────────────┬──────┐
│ Test ID                    │ Status │ Message                      │   ms │
├────────────────────────────┼────────┼──────────────────────────────┼──────┤
│ system.uname               │ PASS   │ Kernel 6.1.0 on x86_64       │  0.3 │
│ system.network_interfaces  │ PASS   │ Interfaces collected          │  1.2 │
│ system.tool_inventory      │ PASS   │ Tool availability snapshot    │  0.1 │
│ ethernet.eth0.presence     │ PASS   │ [MOCK] eth0 assumed present   │  0.2 │
│ ethernet.eth0.link         │ PASS   │ [MOCK] eth0 link assumed UP   │  0.1 │
│ i2c.bus_1                  │ PASS   │ [MOCK] I2C bus 1 assumed OK   │  0.1 │
│ i2c.bus1.eeprom@0x50       │ PASS   │ [MOCK] eeprom detected        │  0.1 │
│ i2c.bus1.temp_sensor@0x48  │ PASS   │ [MOCK] temp_sensor detected   │  0.1 │
│ gpio.line23.reset_modem    │ PASS   │ [MOCK] GPIO reset_modem OK    │  0.1 │
│ uart._dev_ttyUSB0          │ PASS   │ [MOCK] UART /dev/ttyUSB0 OK   │  0.1 │
└────────────────────────────┴────────┴──────────────────────────────┴──────┘

Overall: PASS  PASS=10 FAIL=0 SKIP=0 ERROR=0
```

Report artifacts are saved to `output/` with timestamps:
- `output/report_YYYYMMDD_HHMMSS.json`
- `output/report_YYYYMMDD_HHMMSS.html`

---

## Running Tests

```bash
pytest
# or with coverage
pytest --cov=. --cov-report=term-missing
```

---

## MVP Limitations

- Sequential plugin execution only (no parallelism yet)
- No web UI or database backend
- UART loopback requires `pyserial` and a physical loopback jumper
- GPIO tests require `gpiod` tools or an exported sysfs GPIO
- I2C device detection requires `i2cdetect` (from `i2c-tools`)
- `ethtool` used as best-effort evidence only
- No authentication or multi-user support

---

## Roadmap

| Phase | Feature |
|-------|---------|
| v0.2  | Parallel plugin execution (asyncio / threadpool) |
| v0.2  | Plugin dependency graph (topological sort) |
| v0.3  | REST API layer (FastAPI) for CI/CD integration |
| v0.3  | Database result storage (SQLite → PostgreSQL) |
| v0.4  | Web dashboard (React / HTMX) |
| v0.5  | LLM-assisted diagnostics (replace rule stubs with Claude API) |
| v0.5  | Remote board agent over SSH |
| v1.0  | Plugin marketplace / community registry |

---

## License

MIT
