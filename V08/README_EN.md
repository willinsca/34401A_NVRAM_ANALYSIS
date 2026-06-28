# 34401A NVRAM Viewer v0.8 English + Refined SCPI Console

## v0.8 improvements

### 1. `Cal String to Write` is hard-limited to 40 characters

The CAL:STR helper field is now named:

```text
Cal String to Write
```

It has a live counter:

```text
0 / 40 characters
```

The entry widget blocks:

- more than 40 characters;
- non-printable / non-ASCII characters;
- single quote `'`, because the helper creates a single-quoted SCPI literal.

The manual script editor remains fully editable. The 40-character restriction applies to the **CAL:STR helper field**, not to arbitrary manually typed SCPI script lines.

### 2. Clear update behavior after editing the string

The large script editor is intentionally editable. To prevent a helper-field edit from silently overwriting a manually edited script:

- when you change `Cal String to Write`, security code, or either security checkbox, the helper displays:

```text
Template inputs changed — click UPDATE TEMPLATE to replace the editor script.
```

- click:

```text
UPDATE TEMPLATE
```

to regenerate the CAL:STR command lines using the current helper inputs;
- pressing Enter while editing `Cal String to Write` also updates the template.

Example: after changing the field to `hello world`, click `UPDATE TEMPLATE` and the script becomes:

```text
CAL:SEC:STAT?
CAL:SEC:STAT OFF,HP034401
CAL:STR 'hello world'
CAL:STR?
SYST:ERR?
```

The **editor text** is still the exact script that `EXECUTE EDITOR SCRIPT` runs.

### 3. Security choices are independent, not mutually exclusive

The compact side-by-side options are:

```text
Unlock before write (OFF)
Re-secure after verify (ON)
```

They have this sequence logic:

| OFF | ON | Generated intent |
|---|---|---|
| checked | unchecked | Unsecure → write / verify → leave unsecured |
| unchecked | checked | Write / verify → secure; assumes the meter is already unsecured |
| checked | checked | Unsecure → write / verify → re-secure |
| unchecked | unchecked | Write / verify only; assumes the meter is already unsecured |

For the common “temporarily unsecure, then restore secure state” workflow, check **both** boxes.

### 4. Console Test `*IDN?` now shares the Dump Reader worker exactly

The `SCPI Command Console` Test `*IDN?` now calls the same shared `start_idn_test / idn_worker` transaction used by **Read dump from 34401A**:

```text
open COM port
9600 / 8N2 / DTR-DSR
send *IDN?
wait 300 ms
read CR-terminated reply
close COM port
```

The difference is only where the result is displayed: the Console test writes to the Console log and Console status line.

## Existing v0.7 capabilities retained

- 512-byte dump analysis.
- 256 × 16-bit little-endian word table.
- Nine physical NVRAM-block checksum checks.
- Correct LSB-first 7-bit calibration-string decode.
- Readable and raw B4–B8 Q23 views.
- Primary-vs-comparison dump word differences.
- CSV export.
- RS-232 dump reader using `DIAG:PEEK? -1,<word>,0`.
- COM-port scanning and dump reading.
- Default dump filename: `caldump.bin`.
- SCPI CAL Assistant with primary/compare dump Q23 model values.
- Unified editable SCPI Command Console.

## SCPI Command Console rules

- The editor is the source of truth: **exactly the non-comment lines in the editor are sent**.
- One SCPI command per line.
- Blank lines are ignored.
- Lines beginning `;`, `#`, or `//` are ignored.
- Commands ending in `?` wait for a reply and log it.
- Other lines are sent as write commands and use the configured post-write delay.
- Before the script begins, the app presents a confirmation dialog with the exact executable lines.
- Security code parameters are hidden in the Console log.

## First use

1. Extract the ZIP.
2. Install Python 3.9+.
3. Double-click:

```text
Launch_34401A_NVRAM_Viewer_EN.bat
```

The launcher installs `pyserial` automatically when needed.
