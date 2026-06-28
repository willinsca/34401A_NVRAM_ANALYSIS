# Windows Quick Start — v0.7 SCPI Command Console

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

The first run installs `pyserial` automatically if needed.

## Test the local console COM port

1. Open **SCPI Command Console**.
2. Click **Refresh ports**.
3. Select the COM port used by the 34401A.
4. Click **Test *IDN?**.
5. Read the result in the **Console log** at the bottom of that same tab.

This test uses the same serial logic as the working Dump Reader test.

## Generate and run a CAL:STR test

1. In **CAL:STR template helper**, enter:

```text
TEST -34401 -RS232
```

2. Click:

```text
Load CAL:STR template
```

3. The editable script becomes:

```text
CAL:SEC:STAT?
CAL:SEC:STAT OFF,HP034401
CAL:STR 'TEST -34401 -RS232'
CAL:STR?
SYST:ERR?
```

4. Edit the script if needed.
5. Click:

```text
EXECUTE EDITOR SCRIPT
```

6. Review the confirmation dialog. It shows the exact executable lines.
7. The console log records every command and every query response.

## Run SCPI CAL Assistant commands

1. Configure the desired function/range in **SCPI CAL Assistant**.
2. Generate the command block there.
3. Open **SCPI Command Console**.
4. Click:

```text
Load CAL Assistant block
```

5. Review or edit the text.
6. Click **EXECUTE EDITOR SCRIPT**.

You can also paste any manual SCPI command block into the editor.

## Script rules

- One command per line.
- Blank lines are ignored.
- Lines starting with `;`, `#`, or `//` are ignored.
- Commands ending in `?` wait for a reply.
- Other commands are sent as writes.
- You can set the delay after write and choose whether to stop on first error/timeout.
