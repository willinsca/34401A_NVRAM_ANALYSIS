# Windows Quick Start — v0.10 Defaults & CAL Assistant Gate

## Cal String to Write default

1. Open a primary 512-byte NVRAM dump.
2. Open **SCPI Command Console**.
3. `Cal String to Write` is automatically populated from the primary dump's current preferred remote CAL:STR payload.
4. Edit it if needed.
5. Click `UPDATE TEMPLATE`.

The original `TEST -34401 -RS232` demonstration value is no longer used as the default.

## Load a SCPI CAL Assistant block

1. Open a primary dump.
2. Open **SCPI CAL Assistant**.
3. Select the required **Candidate function / range**.
4. Set a numeric **Actual applied standard value**:
   - select primary/comparison dump modeled value; or
   - enter a numeric value manually.
5. Return to **SCPI Command Console**.
6. Click `Load CAL Assistant block`.
7. Confirm the displayed candidate/range and actual value.
8. Review the loaded editable script before executing it.

If no primary dump is open or the actual value is blank/non-numeric, the program will not load the CAL block and will direct you back to SCPI CAL Assistant setup.
