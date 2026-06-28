# Windows Quick Start — 34401A NVRAM Viewer v0.3 English

## Install Python once

1. Go to the official Python Windows download page:
   `https://www.python.org/downloads/windows/`
2. Install Python 3.9 or newer.
3. During installation, allow the Python launcher (`py`) and PATH option if offered.
4. Open **Command Prompt** and test:

```text
py --version
```

You should see a Python 3 version.

## Run the viewer

1. Extract the ZIP to a normal folder, for example:

```text
C:\34401A_NVRAM_Viewer
```

2. Double-click:

```text
Launch_34401A_NVRAM_Viewer_EN.bat
```

3. Click **Open 512-byte dump**.
4. Select any 512-byte `.bin` file.

The file can have any name. Examples:

```text
old.bin
before_upgrade.bin
my_34401_backup.bin
caldump11-5-2.bin
```

## Copy data

- In any table: select a row, press **Ctrl+C**, or click **Copy selected row(s)**.
- In **Overview**: click **Copy overview**.
- In **SCPI CAL Assistant**: click **Copy command block**.

## SCPI CAL Assistant

1. Select a candidate range, for example **DCV 10 V**.
2. Apply your real external calibration standard to the meter.
3. Type the **actual value of that source** into **Actual applied standard value**.
4. Click **Generate / refresh**.
5. Copy the text block and send one line at a time to PuTTY using your normal line-ending method.

The default nominal example is only a placeholder. Replace it with the certified or independently measured actual standard value.

Example:

```text
Actual applied standard value: 9.999999873
```

The generated commands use:

```text
CAL:VAL 9.999999873
```

Never substitute the decoded EEPROM offset or gain ppm into `CAL:VAL`.
