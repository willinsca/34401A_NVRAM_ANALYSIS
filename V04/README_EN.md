# 34401A NVRAM Viewer v0.4 English + Dump Reader

## What it does

This Windows GUI combines:

- 512-byte 34401A dump analysis;
- 256 × 16-bit little-endian word display;
- all nine verified physical block checksum checks;
- correct LSB-first 7-bit calibration-string decode;
- readable signed-Int16 / Q23 correction views;
- primary-versus-compare dump differences;
- CSV export;
- copy buttons / Ctrl+C on all tables;
- copyable SCPI CAL templates;
- a GUI **read-only EEPROM dump reader** over RS-232.

## New: Read dump from 34401A

The **Read dump from 34401A** tab integrates the supplied HPAK34401ACalTool read workflow:

```text
Serial settings: 9600 baud, 8 data bits, no parity, 2 stop bits, DTR/DSR flow control
Command termination: LF by default
Optional entry: SYST:RWL
Read loop: DIAG:PEEK? -1,0,0 through DIAG:PEEK? -1,255,0
Cleanup: SYST:LOC
```

The GUI detects serial ports exposed by Windows and lets you choose one. It cannot know whether a detected port is currently occupied, so use **Test *IDN?** first. A valid 34401A reply has `34401A` as its model field.

The source command-line tool's default file is retained:

```text
current working directory\caldump.bin
```

When launched using the included `.bat`, the current working directory is normally the application folder.

### Dump safety behavior

- It reads all 256 words into memory first.
- It saves a 512-byte file only after all 256 reads complete.
- It then verifies all nine block checksums.
- A completed dump with a checksum failure is still saved and explicitly warned about; that may be valuable forensic evidence.
- An aborted/failed incomplete read does not overwrite the final output file.
- The program does **not** include flash mode or any EEPROM write command.
- The supplied source used display/beep progress commands. This GUI omits those cosmetic commands and uses its own progress bar/log; the core serial read transaction is retained.

## SCPI CAL Assistant: what dump data can and cannot do

The assistant has two separate concepts:

### 1. Actual external standard value — goes to `CAL:VAL`

For a formal 34401A calibration, `CAL:VAL` must be the actual, known external source value that is physically applied at that moment.

For example, if the DC source output has been independently verified as `9.999999873 V` on the 10 V range:

```text
CAL:SEC:STAT?
CAL:SEC:STAT OFF,HP034401
CONF:VOLT:DC 10
CAL:VAL 9.999999873
CAL?
SYST:ERR?
CAL:COUN?
```

### 2. Historical correction record from a loaded dump — never silently goes to `CAL:VAL`

A loaded primary dump and optional comparison dump provide a candidate raw correction record:

```text
Gain raw / gain factor / gain ppm
Offset raw / offset fraction of full scale / range-scaled offset
```

The assistant lets you select **Nominal full-scale template**, **Primary dump record**, or **Comparison dump record**.

- Choosing **Nominal** fills the nominal template (for example `10.000000000`).
- Choosing either dump option shows a copyable historical Q23 record for migration/comparison.
- The app deliberately does **not** insert a dump offset or gain into `CAL:VAL`.

Reason: the EEPROM record is an internal correction result. It does not contain the certified actual calibration-source output or the meter's uncorrected live reading; therefore no one-to-one, verified conversion to a formal `CAL:VAL` number exists yet.

## Important mapping boundary

- The physical B0–B8 block layout and the checksum formula are verified.
- The Q23 signed-Int16 treatment of correction data is the working model.
- Per-range word labels are displayed as **Candidate** mappings until proved with controlled before/after physical dumps for the relevant firmware.
- This app is an analysis, dump, and planning tool. It does not claim a proven raw RS-232 coefficient-import route.

## First-time Windows use

1. Extract this ZIP to a normal folder, for example:

```text
C:\34401A_NVRAM_Viewer
```

2. Install Python 3.9 or newer from the official Python Windows download page.
3. Double-click:

```text
Launch_34401A_NVRAM_Viewer_EN.bat
```

The first run installs `pyserial` automatically if needed. Internet access is required for that first dependency installation.

4. In the program:
   - use **Open 512-byte dump** for a saved `.bin`;
   - or open **Read dump from 34401A**, click **Refresh ports**, choose your COM port, click **Test *IDN?**, and then **Start 256-word dump**.

## Build a standalone EXE (optional)

Double-click:

```text
Build_Windows_EXE_EN.bat
```

It installs PyInstaller and produces:

```text
dist\34401A_NVRAM_Viewer_EN.exe
```

## Attribution

The serial dump transaction was implemented from the user-supplied source archive for **HPAK34401ACalTool 1.2** by `squad`, which uses the MIT License. This GUI is not a copy of that command-line application and does not include its flash-mode functionality.
