# Sample Run – EmbedAI Validator (Mock Mode)

This example shows the expected console output when running on a developer
laptop without embedded hardware, using `--mock`.

## Command

```bash
cd embedai-validator
pip install -e ".[dev]"
embedai validate -b boards/sample_board.yaml --mock --verbose
```

## Console Output

```
──────────────── EmbedAI Validator ────────────────
INFO  Loaded board profile: Sample Embedded Board (rev A1)
INFO  Running 5 plugin(s) for board: Sample Embedded Board
INFO  → system
INFO      PASS   system.uname
INFO      PASS   system.network_interfaces
INFO      PASS   system.tool_inventory
INFO  → ethernet
INFO      PASS   ethernet.eth0.presence
INFO      PASS   ethernet.eth0.link
INFO  → gpio
INFO      PASS   gpio.line23.reset_modem
INFO  → i2c
INFO      PASS   i2c.bus_1
INFO      PASS   i2c.bus1.eeprom@0x50
INFO      PASS   i2c.bus1.temp_sensor@0x48
INFO  → uart
INFO      PASS   uart._dev_ttyUSB0

                   Results – Sample Embedded Board
┌──────────────────────────────────┬────────┬───────────────────────────┬──────┐
│ Test ID                          │ Status │ Message                   │   ms │
├──────────────────────────────────┼────────┼───────────────────────────┼──────┤
│ system.uname                     │ PASS   │ Kernel 6.x.y on x86_64   │  0.3 │
│ system.network_interfaces        │ PASS   │ Network interface list … │  1.2 │
│ system.tool_inventory            │ PASS   │ Tool availability …       │  0.1 │
│ ethernet.eth0.presence           │ PASS   │ [MOCK] eth0 assumed …     │  0.2 │
│ ethernet.eth0.link               │ PASS   │ [MOCK] eth0 link assumed  │  0.1 │
│ gpio.line23.reset_modem          │ PASS   │ [MOCK] GPIO reset_modem … │  0.1 │
│ i2c.bus_1                        │ PASS   │ [MOCK] I2C bus 1 assumed  │  0.1 │
│ i2c.bus1.eeprom@0x50             │ PASS   │ [MOCK] eeprom detected …  │  0.1 │
│ i2c.bus1.temp_sensor@0x48        │ PASS   │ [MOCK] temp_sensor …      │  0.1 │
│ uart._dev_ttyUSB0                │ PASS   │ [MOCK] UART /dev/ttyUSB0  │  0.1 │
└──────────────────────────────────┴────────┴───────────────────────────┴──────┘

Overall: PASS  PASS=10 FAIL=0 SKIP=0 ERROR=0

JSON: output/report_20240402_120000.json
HTML: output/report_20240402_120000.html
```

## Real Hardware Run (partial output with failures)

```
INFO  → i2c
INFO      PASS   i2c.bus_1
INFO      FAIL   i2c.bus1.eeprom@0x50
INFO      FAIL   i2c.bus1.temp_sensor@0x48
INFO  → ethernet
INFO      PASS   ethernet.eth0.presence
INFO      FAIL   ethernet.eth0.link

Overall: FAIL  PASS=5 FAIL=3 SKIP=1 ERROR=0

Suggestions for i2c.bus1.eeprom@0x50:
  • Verify device I2C address matches the YAML profile
  • Check pull-up resistors on SDA/SCL lines (typically 4.7 kΩ)
  • Confirm VCC/power sequencing to the device is correct

Suggestions for ethernet.eth0.link:
  • Verify the Ethernet cable is connected and the peer port is active
  • Bring the interface up: 'ip link set eth0 up'
```

## Other Commands

```bash
# System inventory only
embedai inventory -b boards/sample_board.yaml

# List registered plugins
embedai plugins

# Smoke suite only (fast)
embedai validate -b boards/sample_board.yaml --mock --suite smoke

# Re-render HTML from existing JSON
embedai report -i output/report_20240402_120000.json
```
