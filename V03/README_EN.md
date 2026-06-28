# 34401A NVRAM Viewer v0.3 English

## What this version preserves from v0.2

- 512-byte dump validation.
- 256 x 16-bit little-endian word display.
- Nine physical EEPROM block checksum checks.
- Correct packed calibration-string decode:
  - starts at `W[0x32] bit 0`;
  - word bits are read LSB first;
  - characters are 7-bit LSB-first.
- Core state/settings summary.
- Raw B4–B8 `signed Int16` / Q23 view.
- Readable candidate gain/offset table.
- Compare two dumps word by word.
- CSV export.

## New in v0.3

- Entire interface is English.
- Every table supports:
  - **Copy selected row(s)** button;
  - **Ctrl+C**;
  - right-click **Copy selected row(s)**.
- A new **SCPI CAL Assistant** tab:
  - selects a candidate function/range;
  - shows its decoded candidate EEPROM values from the open dump;
  - accepts the **actual applied calibration-standard value** entered by the user;
  - generates a copyable PuTTY/terminal command block;
  - does **not** connect to RS-232 or send anything.

## Critical CAL:VAL rule

`CAL:VAL` is **not** the EEPROM correction offset.

For a DCV 10 V example, if the readable table shows:

```text
Offset / FS = -0.002012729645
Offset      = -0.02012729645 V
```

then neither number is a CAL:VAL input. Do **not** enter:

```text
CAL:VAL -0.02012729645
```

and do **not** invent `10 V ± offset` from the decoded EEPROM word.

You must apply a real, known calibration standard and enter the value that standard actually produces. For example, when a calibrated source applies exactly `9.999999873 V`:

```text
CONF:VOLT:DC 10
CAL:VAL 9.999999873
CAL?
```

The meter measures the signal, then computes and stores its own new correction values. This program cannot derive the source's actual value from an old EEPROM coefficient.

## First-time Windows use

1. Extract this ZIP to a folder, for example `C:\34401A_NVRAM_Viewer`.
2. Install Python 3.9+.
3. Double-click:

```text
Launch_34401A_NVRAM_Viewer_EN.bat
```

4. Click **Open 512-byte dump** and select any `.bin` file. File names do not matter; the app checks only that the file is exactly 512 bytes.

## Optional command-line use

You may drag a `.bin` file onto `Launch_34401A_NVRAM_Viewer_EN.bat`, or run:

```text
py -3 34401A_NVRAM_Viewer_EN.pyw "C:\path\your_dump.bin"
```

## Optional EXE build

On your Windows computer, double-click:

```text
Build_Windows_EXE_EN.bat
```

This installs PyInstaller and creates a standalone `.exe` in the `dist` folder.

## Safety boundary

The program is intentionally **read-only**.

It does not:
- write EEPROM;
- modify `.bin` files;
- modify checksum words;
- open a serial port;
- send SCPI;
- run `DIAG:POKE` / `PEEK`;
- claim that each candidate calibration word is fully proven.

Before any calibration or firmware-migration experiment, retain:
1. an original physical EEPROM dump;
2. a before/after dump;
3. a 9-block checksum result;
4. a post-power-cycle dump;
5. a restoration path.
