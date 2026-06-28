# Windows Quick Start — v0.4 English + Dump Reader

## A. Install / start

1. Extract the ZIP, for example to:

```text
C:\34401A_NVRAM_Viewer
```

2. Install Python 3.9+.
3. Double-click:

```text
Launch_34401A_NVRAM_Viewer_EN.bat
```

The launcher installs `pyserial` automatically if it is missing.

## B. Open an existing dump

1. Click **Open 512-byte dump**.
2. Select any `.bin` file. The filename does not matter; the application checks only that it is exactly 512 bytes.
3. Check **Block checksums**. A normal validated dump should show `9/9 PASS`.

## C. Read a new dump through RS-232

1. Confirm the 34401A is configured for RS-232 and the cable/adapter is connected.
2. Open **Read dump from 34401A**.
3. Click **Refresh ports**.
4. Choose the COM port that belongs to your adapter.
5. Leave the source-compatible link settings at:

```text
9600 / 8N2 / DTR-DSR / LF
```

6. Click **Test *IDN?**. A normal 34401A identification has `34401A` as the model field.
7. The default output is:

```text
caldump.bin
```

in the application working directory, just like the supplied command-line example. Change it with **Browse…** if needed.
8. Click **Start 256-word dump**.
9. The program saves a complete 512-byte dump, validates nine checksums, and opens the file automatically.

## D. SCPI CAL Assistant

- **Nominal full-scale template** fills a formatting example.
- **Primary dump record** and **Comparison dump record** show the existing candidate raw Q23 correction record and let you copy it.
- Do not use gain ppm, offset/FS, or the range-scaled offset as `CAL:VAL`.

`CAL:VAL` must be the actual known value of the external standard that is applied to the meter.
