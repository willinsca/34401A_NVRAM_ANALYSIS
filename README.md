34401A NVRAM Viewer v0.10 English + CAL Defaults & Gate
v0.10 changes
1. Cal String to Write defaults from the opened primary dump
The helper no longer starts with the old demonstration text.

At startup, the helper is blank until a primary 512-byte dump is opened.

Whenever a primary dump is opened—either through Open 512-byte dump or after a successful RS-232 dump read—the program decodes the current calibration-string layout and populates:

Cal String to Write

with the dump’s Preferred CAL:STR text.

For a segmented layout, it uses the remote CAL:STR payload only and excludes the retained HP034401 header.

Example:

Raw field:                  HP034401·····28 May 1999 CALIBRATED
Cal String to Write default: 28 May 1999 CALIBRATED

Opening a comparison dump does not overwrite the primary-dump default.

2. Load CAL Assistant block now requires SCPI CAL Assistant setup
Clicking Load CAL Assistant block no longer blindly copies a possibly incomplete template.

It now checks:

A primary NVRAM dump is open.
A Candidate function / range is selected in SCPI CAL Assistant.
Actual applied standard value is present and numeric.
If any item is missing, a dialog tells you to return to SCPI CAL Assistant and complete the setup.

When the setup is complete, a confirmation dialog states:

Candidate function / range
Actual applied standard value
Primary dump filename

Only after confirmation does the Console receive the regenerated command block.

This ensures the Console block comes from the currently selected SCPI CAL Assistant candidate/range and value rather than an old preview.

Existing v0.9 features retained
Current CAL:STR physical region decoder:
retained header;
five-NUL separator;
remote CAL:STR payload;
preferred user-facing payload.
Cal String to Write 40-character printable-ASCII helper limit.
UPDATE TEMPLATE behavior.
Independent Unlock before write (OFF) and Re-secure after verify (ON) flags.
Shared Dump Reader / Console *IDN? transport path.
Editable Console script runner.
NVRAM analysis, checksum verification, dump comparison, raw Q23 views, and CSV export.
Copyright
Copyright © 2026 Wei Wang
willinsca@gmail.com
