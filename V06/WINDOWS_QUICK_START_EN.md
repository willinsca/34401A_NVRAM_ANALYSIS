# Windows Quick Start — v0.6

## Open or read a dump

- Run `Launch_34401A_NVRAM_Viewer_EN.bat`.
- Use **Open 512-byte dump** for an existing `.bin`.
- Or use **Read dump from 34401A**:
  1. Refresh ports.
  2. Choose the COM port.
  3. Click `Test *IDN?`.
  4. Leave `9600 / 8N2 / DTR-DSR / LF` at the source-compatible defaults.
  5. Click `Start 256-word dump`.

The default output filename remains:

```text
caldump.bin
```

## SCPI CAL Assistant

For a selected candidate range:

- **Nominal full-scale template** fills the nominal value.
- **Primary dump modeled value** fills the calculated numeric Q23 model from the primary dump.
- **Comparison dump modeled value** fills the calculated numeric Q23 model from the comparison dump.

When a dump model is selected, the numeric field and `CAL:VAL` line update immediately.

## Live CAL:STR write / verify

1. Open **SCPI CAL:STR Assistant**.
2. Enter the desired 1–40 character printable ASCII text.
3. Confirm the shared COM port and line ending.
4. Click:

```text
EXECUTE CAL:STR WRITE + VERIFY
```

5. Confirm the warning dialog.
6. The app performs IDN check, security query, conditional unsecure, string write, query verification, and error query.
7. Inspect the live execution log.

For the test string:

```text
TEST -34401 -RS232
```

the generated PuTTY block is:

```text
CAL:SEC:STAT?
CAL:SEC:STAT OFF,HP034401
CAL:STR 'TEST -34401 -RS232'
CAL:STR?
SYST:ERR?
```
