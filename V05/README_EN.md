# 34401A NVRAM Viewer v0.5 English + Dump Reader + CAL:STR Assistant

## v0.5 changes

### 1. Dump source now visibly affects the SCPI CAL Assistant

In **SCPI CAL Assistant**, the value-source drop-down now contains:

- `Nominal full-scale template: ...`
- `Primary dump modeled value: ... (reference only)`
- `Comparison dump modeled value: ... (reference only)` — when a compare dump is open.

For a selected candidate range, the program calculates and displays this **internal model reference**:

```text
modeled value = full_scale × (1 + Gain_raw / 2^23)
              + full_scale × (Offset_raw / 2^23)
```

Example purpose: compare a DC 10 V candidate record between old and new dump files, or record what the current candidate Q23 pair mathematically does at nominal full scale.

When you select Primary or Comparison dump:

- the historical record panel refreshes;
- the source selection visibly changes;
- the **Actual applied standard value** entry changes to:

```text
<DUMP_VALUE_IS_REFERENCE_ONLY>
```

- the copyable command becomes intentionally non-sendable:

```text
CAL:VAL <EXTERNAL_STANDARD_VALUE_REQUIRED>
```

This is deliberate. The modeled EEPROM value is a useful **migration/reference calculation**, but it is not proven to be the actual calibrated external source output. A formal `CAL:VAL` command still requires the real, known source value physically applied to the 34401A.

To make a live command block sendable, replace the placeholder with your certified external-standard value.

### 2. New SCPI CAL:STR Assistant

The new tab creates a copyable write/verify sequence such as:

```text
CAL:SEC:STAT?
CAL:SEC:STAT OFF,HP034401
CAL:STR 'TEST -34401 -RS232'
CAL:STR?
SYST:ERR?
```

Optional re-securing can be appended.

The tab also allows:

- manual entry;
- loading the current calibration string from the Primary dump;
- loading it from the Comparison dump;
- character validation: printable ASCII, 1–40 characters;
- copy command block.

This is a **command generator only**. It does not send the write command over RS-232.

## Existing v0.4 capabilities retained

- 512-byte dump analysis.
- 256 × 16-bit little-endian word view.
- Nine physical EEPROM block checksum checks.
- Correct packed calibration-string decode from `W[0x32] bit 0`, LSB-first 7-bit characters.
- Readable candidate gain / offset view for B4–B8.
- Raw B4–B8 word view.
- Dump comparison and CSV export.
- GUI RS-232 dump reader using the supplied HPAK source-compatible protocol.
- COM port discovery and `*IDN?` test.
- Default serial dump filename: `caldump.bin`.
- Copy buttons, Ctrl+C table copy, and right-click copy.

## Serial dump protocol

```text
9600 baud
8 data bits
no parity
2 stop bits
DTR/DSR flow control
LF command termination by default
SYST:RWL
DIAG:PEEK? -1,0,0 ... DIAG:PEEK? -1,255,0
SYST:LOC
```

The dump reader is read-only. There is no flash/write operation.

## Safety / interpretation boundaries

- B0–B8 physical block layout and the checksum formula are verified.
- Q23 signed-Int16 is the working correction-data model.
- Individual range-to-word assignments remain **Candidate** mappings until controlled before/after calibration dumps prove them for the firmware in question.
- The program will not quietly treat a dump-derived correction result as a true external CAL:VAL input.
- Keep before/after physical dumps and validate 9/9 block checksums after every experiment.
