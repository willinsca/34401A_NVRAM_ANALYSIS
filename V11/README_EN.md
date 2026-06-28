# 34401A NVRAM Viewer v0.11 English — Dual Layout + Command Builder

Windows source package for analysing 512-byte HP / Agilent / Keysight 34401A NVRAM dumps.

## v0.11 changes

### Automatic old/new NVRAM map detection

The viewer now tests both confirmed 9-block maps using the same checksum:

```text
checksum = (sum(data words) + number of data words) mod 65536
```

| Detected map | System-block checksum | CAL count / string | B4–B8 correction regions |
|---|---:|---:|---|
| **04/01/01 legacy** | `W[0A]` | `W[0B]`, packed text `W[0C]..W[24]`, checksum `W[25]` | B4..B8 through checksum `W[AC]` |
| **05/02/01+ extended** | `W[30]` | `W[31]`, packed text `W[32]..W[4A]`, checksum `W[4B]` | B4..B8 through checksum `W[D2]` |

The layout is marked as **CONFIRMED** only when its own nine checksums pass. If neither map validates completely, the program selects the best map provisionally and clearly marks failed blocks as unverified.

### Correct CAL:STR display for both maps

- **04/01/01:** packed CAL string begins at `W[0C]`, with a retained `HP034401` header followed by **4 NUL** separators. Remote `CAL:STR` payload begins at packed character **12**.
- **05/02/01+:** packed CAL string begins at `W[32]`, with the retained header followed by **5 NUL** separators. Remote payload begins at packed character **13**.

The Console default uses the preferred remote payload only; it does not concatenate the retained header.

### Layout-correct correction words

For legacy images, every B4–B8 candidate Q23 address is resolved at its true physical location:

```text
legacy physical word = 05/02/01+ candidate word − 0x26
```

This applies to the readable table, raw B4–B8 view, SCPI CAL Assistant dump-record reference, CSV export, and word descriptions.

### Upgrade / missing-data guidance

The Overview and CSV export now include migration guidance.

For a **04/01/01** image, the program states that the later extended B2 block (`W[0A]..W[2F]` with checksum `W[30]`) must be created by the target firmware / normal initialization. It is not treated as a set of proven per-meter calibration coefficients, and the viewer never invents or raw-copies it.

For checksum-failed or all-`FFFF` B3–B8 data blocks, the Q23 migration model is disabled. The table and CAL Assistant state that the affected function must be re-entered or verified after upgrade using the supported calibration procedure and a traceable external standard.

### Generic SCPI Command Builder

The old fixed `CAL:STR` helper is now a generic **Action / Data** builder:

- Click **Load CAL Assistant block** after setting a candidate and actual standard value in **SCPI CAL Assistant**.
- The Console changes to two synchronized fields, for example:

```text
Action / function:              Calibrate DCV 10 V
Actual applied standard value:  9.999999873
```

- Click **UPDATE SCRIPT** after changing the data field; the editable SCPI script below is regenerated from the same action and data.
- Click **Change CAL string** to return to `CAL:STR` mode. The `CAL:STR`-only security controls and `Use primary/compare CAL string` buttons are restored.

The editor remains editable; only the exact visible script is executed after a confirmation dialog.

## Safety / interpretation boundary

- This program reads NVRAM and can run a user-reviewed SCPI script through RS-232.
- It does **not** raw-write EEPROM, issue `DIAG:POKE`, flash an image, alter a dump file, or calculate/insert raw EEPROM checksums.
- Q23 record values are a migration / comparison display. They are not a certified `CAL:VAL` value.
- `CAL:VAL` must be the actual known value applied by the external standard at the meter terminals.

## Running from source on Windows

1. Install Python 3.9 or later.
2. Run `Install_Dependencies.bat` once, or let `Launch_34401A_NVRAM_Viewer_EN.bat` install `pyserial` automatically.
3. Run `Launch_34401A_NVRAM_Viewer_EN.bat`.
4. Open a 512-byte dump with **Open 512-byte dump**.

To build a single Windows executable, run `Build_Windows_EXE_EN.bat`. The generated executable will be in the `dist` folder.

## Copyright

```text
Copyright © 2026 Wei Wang
willinsca@gmail.com
```
