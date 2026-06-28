# Windows Quick Start — v0.9 CAL:STR field decoder

## Check a dump's current CAL:STR text

1. Open a 512-byte dump.
2. Open **Overview**.
3. In **Calibration text — physical packed region**, inspect:

```text
Layout
Raw field, NUL shown as ·
Retained header chars 0..7
Separator chars 8..12
Remote CAL:STR field chars 13..52
Preferred CAL:STR text
```

Use **Preferred CAL:STR text** as the current remote-written string. It excludes the retained `HP034401` header.

Example:

```text
Raw field:                 HP034401·····TEST -34401 -V08
Preferred CAL:STR text:    TEST -34401 -V08
```

## Generate a CAL:STR script

1. Open **SCPI Command Console**.
2. Enter up to 40 characters in `Cal String to Write`.
3. Click `UPDATE TEMPLATE`.
4. Review the editable script.
5. Execute only after confirming the exact command block.

## Copyright

Open:

```text
Help > Copyright
```

to view:

```text
Copyright © 2026 Wei Wang
willinsca@gmail.com
```
