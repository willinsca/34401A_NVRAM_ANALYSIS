# 34401A NVRAM Viewer v0.7 English + SCPI Command Console

## v0.7 changes

### 1. The SCPI Command Console replaces the separate live CAL:STR executor

The new **SCPI Command Console** combines:

- the CAL:STR template helper;
- an editable terminal-style command script;
- a local COM-port `*IDN?` test;
- a manual SCPI runner.

The large editor is the source of truth:

```text
Whatever text is in the editable SCPI command script is what Execute sends.
```

You can:

- generate a CAL:STR block from the helper;
- click **Load CAL Assistant block** to copy the current block from the SCPI CAL Assistant tab;
- paste any command block from PuTTY;
- type your own one-command-per-line script;
- edit the generated text before running it;
- click **EXECUTE EDITOR SCRIPT**.

Blank lines and lines beginning with `;`, `#`, or `//` are ignored. All other nonblank lines are sent in order.

Query commands that end in `?` wait for and log a reply. Non-query commands are sent and then use the configured write delay.

Before execution, the app shows a confirmation dialog containing the exact executable command lines.

### 2. Console Test *IDN? now uses the Dump Reader transaction path

The **Test *IDN?** button inside SCPI Command Console has its own local log and status display. It uses the same underlying transaction as the working `Read dump from 34401A` test:

```text
Open selected COM port
9600 baud / 8 data bits / no parity / 2 stop bits / DTR-DSR
Send *IDN? using selected line ending
Wait 300 ms
Read CR-terminated reply
Close port
```

It does not write any calibration data.

### 3. CAL:STR helper remains available

For example, with:

```text
TEST -34401 -RS232
```

click **Load CAL:STR template** to put this editable script into the console:

```text
CAL:SEC:STAT?
CAL:SEC:STAT OFF,HP034401
CAL:STR 'TEST -34401 -RS232'
CAL:STR?
SYST:ERR?
```

You can edit this text, copy it, paste additional SCPI commands, or execute it directly.

## Existing features retained

- 512-byte dump analysis.
- 256 × 16-bit little-endian word table.
- Nine physical NVRAM-block checksum checks.
- Correct LSB-first 7-bit calibration-string decode.
- Readable and raw B4–B8 Q23 views.
- Primary-vs-comparison dump word differences.
- CSV export.
- RS-232 dump reader using `DIAG:PEEK? -1,<word>,0`.
- COM-port scanning and Dump Reader `*IDN?` test.
- Default dump filename: `caldump.bin`.
- SCPI CAL Assistant and dump-derived numeric Q23 model selection.
- Copy buttons / Ctrl+C / right-click copy.

## First use

1. Extract the ZIP.
2. Install Python 3.9+.
3. Double-click:

```text
Launch_34401A_NVRAM_Viewer_EN.bat
```

4. The launcher installs `pyserial` automatically if it is missing.

## Console use

1. Open **SCPI Command Console**.
2. Click **Refresh ports**.
3. Choose the correct COM port.
4. Click **Test *IDN?**. The result appears in the Console log, not the Dump Reader log.
5. Generate, paste, or edit the desired script.
6. Click **EXECUTE EDITOR SCRIPT**.
7. Review the confirmation dialog.
8. Inspect the command/reply log.

## Execution notes

- Security-code command parameters are hidden in the console log.
- The runner does not automatically insert commands beyond what is in the editor.
- It does not flash firmware, write raw EEPROM words, or alter dump files.
- `DIAG:PEEK?` dump reads and normal SCPI writes can be entered by the user as script lines.
