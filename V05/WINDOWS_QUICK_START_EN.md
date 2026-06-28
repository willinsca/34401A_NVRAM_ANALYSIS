# Windows Quick Start — v0.5

## Start

1. Extract the ZIP to a normal folder, for example:

```text
C:\34401A_NVRAM_Viewer
```

2. Install Python 3.9+.
3. Double-click:

```text
Launch_34401A_NVRAM_Viewer_EN.bat
```

The launcher installs `pyserial` automatically if necessary.

## Read a dump

Open **Read dump from 34401A**:

1. Refresh ports.
2. Select the COM port.
3. Run **Test *IDN?**.
4. Leave `9600 / 8N2 / DTR-DSR / LF` at its source-compatible defaults.
5. Set an output name, or leave the default:

```text
caldump.bin
```

6. Start the 256-word dump.

## SCPI CAL Assistant source options

For a selected candidate range:

- **Nominal full-scale template** places the nominal number in the input field.
- **Primary dump modeled value** or **Comparison dump modeled value** refreshes the dump correction reference, changes the input field to a visible non-sendable marker, and produces:

```text
CAL:VAL <EXTERNAL_STANDARD_VALUE_REQUIRED>
```

This protects against treating an internal EEPROM correction as a known physical source output.

## Test CAL:STR manually through PuTTY

Open **SCPI CAL:STR Assistant**.

For a test string:

```text
TEST -34401 -RS232
```

the generated block is:

```text
CAL:SEC:STAT?
CAL:SEC:STAT OFF,HP034401
CAL:STR 'TEST -34401 -RS232'
CAL:STR?
SYST:ERR?
```

Send one line at a time using the serial line ending that works with your meter. The `CAL:STR?` reply should show the text you wrote; `SYST:ERR?` should report no error.

The app generates the text only. It does not send the write command itself.
