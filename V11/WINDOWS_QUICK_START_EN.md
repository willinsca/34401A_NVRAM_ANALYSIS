# Windows Quick Start — v0.11

1. Extract this folder to a normal writable location, such as `Documents\34401A_NVRAM_Viewer_v0.11`.
2. Double-click `Launch_34401A_NVRAM_Viewer_EN.bat`.
3. Open a 512-byte NVRAM dump.
4. Check the layout label in the top bar and Overview:
   - `04/01/01 legacy NVRAM layout`, or
   - `05/02/01+ extended NVRAM layout`.
5. Open **Block checksums**. A confirmed image shows 9/9 PASS on the selected map.
6. For a legacy image, use the displayed physical addresses; B4–B8 records are automatically translated by `-0x26` words from the modern map.
7. Before any firmware upgrade, save the original dump. After upgrade, capture a new dump, confirm the new map and all checksums, then re-enter or verify any required calibration using a traceable standard.

## Console workflow

- Use **SCPI CAL Assistant** to select a candidate range and enter the actual known standard value.
- In **SCPI Command Console**, click **Load CAL Assistant block**. The top builder will display the calibration action and its data value; click **UPDATE SCRIPT** after any data edit.
- To write only the calibration string, click **Change CAL string**, set the string and CAL:STR security options, then click **UPDATE SCRIPT**.
- Review the editable script carefully before selecting **EXECUTE EDITOR SCRIPT**.
