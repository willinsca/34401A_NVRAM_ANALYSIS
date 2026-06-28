# 34401A NVRAM Viewer v0.9 English + CAL:STR Decode Fix

## v0.9: Segmented CAL:STR decoding

### Why the old viewer appeared to duplicate `HP034401`

Your post-write dump shows this physical packed sequence:

```text
HP034401 ····· HP034401TEST -34401 -V08
```

where `·` represents a NUL character.

The physical field is segmented:

```text
packed characters 0..7   retained header             HP034401
packed characters 8..12  five NUL separators        ·····
packed characters 13..52 remote CAL:STR payload     HP034401TEST -34401 -V08
```

The old viewer rendered every printable character across the five-NUL separator and then removed NULs from its “Printable text only” summary. That visually concatenated the retained header and the remote payload:

```text
HP034401HP034401TEST -34401 -V08
```

This was a **viewer decoding/presentation issue**. It did not show that the firmware appended an old CAL:STR message.

All four existing validated dumps use the same segmented form:

```text
HP034401 ····· <remote CAL:STR payload>
```

For example, the older dump's preferred remote payload is:

```text
28 May 1999 CALIBRATED
```

### Practical consequence

The first `HP034401` is a retained header. It is not the remote CAL:STR payload.

Therefore, if you want the remote field to be:

```text
TEST -34401 -V08
```

send:

```text
CAL:STR 'TEST -34401 -V08'
```

Do not add the header to the input unless you deliberately want the **remote payload itself** to start with `HP034401`.

v0.9 detects the segmented layout and displays separately:

```text
Retained header chars 0..7
Separator chars 8..12
Remote CAL:STR field chars 13..52
Preferred CAL:STR text
```

When **Use primary** or **Use compare** is clicked in the CAL:STR helper, v0.9 uses the **Preferred CAL:STR text**. For a segmented dump that is the remote payload only; it excludes the retained header.

## CAL:STR helper

- Field label: `Cal String to Write`
- Maximum: 40 printable ASCII characters
- A live counter is shown.
- A single quote is rejected because the helper emits `CAL:STR '...'`.
- After editing the field, click `UPDATE TEMPLATE` or press Enter to replace the editable console script.

## Security options

The two options are independent:

```text
Unlock before write (OFF)
Re-secure after verify (ON)
```

With both selected, the generated sequence is:

```text
CAL:SEC:STAT?
CAL:SEC:STAT OFF,<code>
CAL:STR '<text>'
CAL:STR?
SYST:ERR?
CAL:SEC:STAT ON,<code>
CAL:SEC:STAT?
```

## Copyright

```text
Copyright © 2026 Wei Wang
willinsca@gmail.com
```

The same information appears under **Help > Copyright**.
