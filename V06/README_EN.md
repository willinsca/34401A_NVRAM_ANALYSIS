# 34401A NVRAM Viewer v0.6 English + Live CAL:STR

## v0.6 changes

### 1. Primary / Comparison dump selection now fills the numeric CAL:VAL field

In **SCPI CAL Assistant**, selecting:

- `Primary dump modeled value: ...`
- `Comparison dump modeled value: ...`

now immediately fills **Actual applied standard value** with the selected dump's calculated Q23 model:

```text
modeled value =
full_scale × (1 + Gain_raw / 2^23)
+ full_scale × (Offset_raw / 2^23)
```

The generated command block changes immediately, for example:

```text
CONF:VOLT:DC 10
CAL:VAL 9.99999912345678
CAL?
```

If a selected source has no usable dump record, the data field is cleared and the app reports that no value is available.

The application still labels this input as **dump-derived Q23 model** so it can be distinguished from a separately measured calibration-standard value. It does not substitute a placeholder when a numeric model exists.

### 2. Live CAL:STR write / verify through the selected COM port

The **SCPI CAL:STR Assistant** tab now has a live execution panel.

It shares the COM port, 9600 / 8N2 / DTR-DSR configuration, and line-ending selection used by the dump reader. Before changing the string, it displays a confirmation dialog.

The live workflow is:

```text
*IDN?
CAL:SEC:STAT?
CAL:SEC:STAT OFF,<security code>     only if the meter returns state 1
CAL:SEC:STAT?                        verify state 0
CAL:STR '<your string>'
CAL:STR?                             verify returned text
SYST:ERR?                            verify code 0
CAL:SEC:STAT ON,<security code>      optional
CAL:SEC:STAT?                        optional verify state 1
```

The execution log shows sent commands and replies. Security codes are hidden in the live log.

The program does not run raw EEPROM writes, flash mode, `DIAG:POKE`, or formal CAL coefficient writes.

## Existing features retained

- 512-byte dump analysis.
- 256 × 16-bit little-endian word table.
- 9 physical NVRAM block checksum checks.
- Correct LSB-first 7-bit calibration-string decode.
- Readable and raw B4–B8 Q23 views.
- Primary-vs-comparison dump word differences.
- CSV export.
- Copy buttons / Ctrl+C / right-click copy.
- Copyable SCPI CAL command templates.
- GUI RS-232 dump reader using the source-compatible `DIAG:PEEK? -1,<word>,0` loop.
- COM-port scanning and `*IDN?` test.
- Default dump filename: `caldump.bin`.

## First use

1. Extract the ZIP.
2. Install Python 3.9+.
3. Double-click:

```text
Launch_34401A_NVRAM_Viewer_EN.bat
```

4. The launcher installs `pyserial` automatically if it is missing.
5. In **Read dump from 34401A**, select your COM port and first run `Test *IDN?`.

## Live CAL:STR test

On **SCPI CAL:STR Assistant**:

1. Enter:

```text
TEST -34401 -RS232
```

2. Ensure the COM port is selected.
3. Click **EXECUTE CAL:STR WRITE + VERIFY**.
4. Review the confirmation dialog.
5. Read the execution log. A successful sequence ends with a success message after the returned string matches and `SYST:ERR?` reports zero.

The generated command text remains available for PuTTY use as well.

## Interpretation note for SCPI CAL Assistant

The dump-derived Q23 modeled value is intentionally shown as an actionable template because that is the selected workflow for firmware-migration experiments. It is still a model from candidate EEPROM mappings, so keep physical before/after dumps and validate all 9 block checksums after each experiment.
