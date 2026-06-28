# Windows Quick Start — v0.8 Refined SCPI Console

## Test the Console COM port

1. Open **SCPI Command Console**.
2. Click **Refresh ports**.
3. Select the 34401A COM port.
4. Click **Test *IDN?**.
5. Read the result in the Console log.

This test uses the same serial transaction as the working Dump Reader test.

## CAL:STR helper

1. In **Cal String to Write**, enter a printable ASCII string of up to 40 characters.
2. The counter shows the current length, for example:

```text
11 / 40 characters
```

3. Click:

```text
UPDATE TEMPLATE
```

4. The editable script updates.

For `hello world`, with only `Unlock before write (OFF)` selected:

```text
CAL:SEC:STAT?
CAL:SEC:STAT OFF,HP034401
CAL:STR 'hello world'
CAL:STR?
SYST:ERR?
```

5. Review or edit the script.
6. Click:

```text
EXECUTE EDITOR SCRIPT
```

7. Read the confirmation dialog and proceed.
8. The Console log shows commands and query replies.

## Security checkbox logic

The two options are not alternatives:

```text
Unlock before write (OFF)
Re-secure after verify (ON)
```

To unlock for the string change and lock again afterward, check **both**.

## Run a CAL Assistant script

1. Configure the selected function/range in **SCPI CAL Assistant**.
2. Generate its command block.
3. Go to **SCPI Command Console**.
4. Click:

```text
Load CAL Assistant block
```

5. Review the script.
6. Click:

```text
EXECUTE EDITOR SCRIPT
```

You can also paste a PuTTY command block or type any SCPI lines directly into the editor.
