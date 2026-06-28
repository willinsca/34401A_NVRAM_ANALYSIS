#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
34401A NVRAM Viewer v0.4 English
Viewer / verifier for 512-byte HP / Agilent / Keysight 34401A EEPROM dumps.

The program can perform a read-only serial dump using the supplied HPAK tool's
known working protocol. It intentionally does NOT:
- send SCPI calibration commands,
- write EEPROM,
- flash a dump file,
- modify a dump file,
- calculate or insert new calibration coefficients.

It can generate copyable SCPI CAL templates and can directly execute a confirmed CAL:STR write/verify workflow.
For a formal CAL command, the user must supply the actual value of the known
external calibration standard. That value cannot be proven from the EEPROM's
decoded offset/gain words alone.
"""

from __future__ import annotations

import csv
import os
import re
import struct
import sys
import threading
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tkinter as tk

try:
    import serial
    from serial.tools import list_ports
    PYSERIAL_AVAILABLE = True
    PYSERIAL_IMPORT_ERROR = ""
except Exception as exc:  # The viewer remains usable without pyserial.
    serial = None
    list_ports = None
    PYSERIAL_AVAILABLE = False
    PYSERIAL_IMPORT_ERROR = str(exc)
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText


APP_TITLE = "34401A NVRAM Viewer v0.6 English + Live CAL:STR"
SCALE_Q23 = 8_388_608

# Confirmed physical block boundaries from the three-dump checksum validation.
BLOCKS = [
    ("B0", "Secure state",                    0x00,  2, 0x02),
    ("B1", "GPIB / interface",                0x03,  2, 0x05),
    ("B2", "Internal data",                   0x06, 42, 0x30),
    ("B3", "Calibration text / count",        0x31, 26, 0x4B),
    ("B4", "DCV correction area",             0x4C, 24, 0x64),
    ("B5", "DCI correction area",             0x65, 18, 0x77),
    ("B6", "2-wire resistance correction area", 0x78, 26, 0x92),
    ("B7", "4-wire resistance correction area", 0x93, 28, 0xAF),
    ("B8", "AC / frequency correction area",  0xB0, 34, 0xD2),
]

# Core fields with stronger support than every individual calibration-record label.
CORE_DESCRIPTIONS: Dict[int, str] = {
    0x00: "Secure state: 0000 = unsecured, 8661 = secured",
    0x01: "Reserved / observed 0000",
    0x02: "B0 checksum",
    0x03: "GPIB address",
    0x04: "Reserved / observed 0000",
    0x05: "B1 checksum",
    0x06: "Settings word",
    0x07: "Continuity threshold + Hi-Z flag",
    0x08: "Feature-enable / hidden-menu-related bits",
    0x09: "Line-frequency trim count",
    0x0A: "Firmware layout flag; 0000 for new layout",
    0x1C: "ROM-initialized constant (often 8000)",
    0x1D: "Near-zero / variant field",
    0x1E: "Near-zero / variant field",
    0x1F: "Firmware constant (often 8000)",
    0x20: "Line-frequency correction",
    0x21: "Padding / observed 0000",
    0x22: "IEEE-754 template high word",
    0x23: "IEEE-754 template low word",
    0x30: "B2 checksum",
    0x31: "Calibration count",
    0x4B: "B3 checksum",
    0x64: "B4 checksum",
    0x76: "B5 sentinel / observed 0003",
    0x77: "B5 checksum",
    0x92: "B6 checksum",
    0xAE: "B7 sentinel / observed 000B",
    0xAF: "B7 checksum",
    0xCF: "B8 end sentinel / observed 956E",
    0xD0: "B8 padding / observed 0000",
    0xD1: "B8 padding / observed 0000",
    0xD2: "B8 checksum",
}

# Candidate labels are navigation aids only. They are never used for writing.
CANDIDATE_LABELS: Dict[int, str] = {
    0x4C: "Candidate: DCV 100 mV gain word",
    0x4D: "Candidate: DCV 100 mV offset word",
    0x50: "Candidate: DCV 1 V gain word",
    0x51: "Candidate: DCV 1 V offset word",
    0x54: "Candidate: DCV 10 V gain word",
    0x55: "Candidate: DCV 10 V offset word",
    0x58: "Candidate: DCV 100 V gain word",
    0x59: "Candidate: DCV 100 V offset word",
    0x5C: "Candidate: DCV 1000 V gain word",
    0x5D: "Candidate: DCV 1000 V offset word",
    0x60: "Candidate: DCV -10 V / 500 V gain word",
    0x62: "Candidate: DCV -10 V / 500 V offset word",
    0x65: "Candidate: DCI 10 mA gain word",
    0x66: "Candidate: DCI 10 mA offset word",
    0x69: "Candidate: DCI 100 mA gain word",
    0x6A: "Candidate: DCI 100 mA offset word",
    0x6D: "Candidate: DCI 1 A gain word",
    0x6E: "Candidate: DCI 1 A offset word",
    0x71: "Candidate: DCI 3 A gain word",
    0x72: "Candidate: DCI 3 A offset word",
    0x75: "Candidate: DCI / AC linearity term",
    0x78: "Candidate: RES 100 ohm gain word",
    0x79: "Candidate: RES 100 ohm offset word",
    0x7C: "Candidate: RES 1 kohm gain word",
    0x7D: "Candidate: RES 1 kohm offset word",
    0x80: "Candidate: RES 10 kohm gain word",
    0x81: "Candidate: RES 10 kohm offset word",
    0x84: "Candidate: RES 100 kohm gain word",
    0x85: "Candidate: RES 100 kohm offset word",
    0x88: "Candidate: RES 1 Mohm gain word",
    0x89: "Candidate: RES 1 Mohm offset word",
    0x8C: "Candidate: RES 10 Mohm gain word",
    0x8D: "Candidate: RES 10 Mohm offset word",
    0x90: "Candidate: extra resistance / continuity term",
}

for base, name in [
    (0x93, "FRES 100 ohm"), (0x95, "FRES 1 kohm"), (0x97, "FRES 10 kohm"),
    (0x99, "FRES 100 kohm"), (0x9B, "FRES 1 Mohm"), (0x9D, "FRES 10 Mohm"),
    (0x9F, "FRES extra 0"), (0xA1, "FRES extra 1"),
    (0xB0, "ACV 100 mV @ 1 kHz"), (0xB2, "ACV 100 mV @ 50 kHz"),
    (0xB4, "ACV 1 V"), (0xB6, "ACV 10 V"), (0xB8, "ACV 100 V"),
    (0xBA, "ACV 750 V"), (0xBC, "ACI 1 A"), (0xBE, "ACI 3 A"),
    (0xC0, "Frequency / extra"),
]:
    CANDIDATE_LABELS[base] = f"Candidate: {name} gain word"
    CANDIDATE_LABELS[base + 1] = f"Candidate: {name} offset word"


@dataclass(frozen=True)
class PairSpec:
    block: str
    label: str
    gain_index: int
    offset_index: int
    full_scale: float
    unit: str
    scpi_config: str
    source_note: str
    nominal_example: str


# Physical B4–B8 areas and Q23 conversion are verified.
# The logical range-to-word mapping remains explicitly "candidate" until each
# record is proved by a controlled pre/post formal calibration dump experiment.
PAIR_SPECS: List[PairSpec] = [
    PairSpec("B4", "DCV 100 mV", 0x4C, 0x4D, 0.1, "V", "CONF:VOLT:DC 0.1", "Apply a stable DC voltage near the selected range.", "0.100000000"),
    PairSpec("B4", "DCV 1 V", 0x50, 0x51, 1.0, "V", "CONF:VOLT:DC 1", "Apply a stable DC voltage near the selected range.", "1.000000000"),
    PairSpec("B4", "DCV 10 V", 0x54, 0x55, 10.0, "V", "CONF:VOLT:DC 10", "Apply a stable DC voltage near the selected range.", "10.000000000"),
    PairSpec("B4", "DCV 100 V", 0x58, 0x59, 100.0, "V", "CONF:VOLT:DC 100", "Apply a stable DC voltage near the selected range.", "100.000000000"),
    PairSpec("B4", "DCV 1000 V", 0x5C, 0x5D, 1000.0, "V", "CONF:VOLT:DC 1000", "Apply a stable DC voltage near the selected range. Observe all HV safety limits.", "1000.000000000"),
    PairSpec("B5", "DCI 10 mA", 0x65, 0x66, 0.01, "A", "CONF:CURR:DC 0.01", "Apply a stable DC current near the selected range.", "0.010000000"),
    PairSpec("B5", "DCI 100 mA", 0x69, 0x6A, 0.1, "A", "CONF:CURR:DC 0.1", "Apply a stable DC current near the selected range.", "0.100000000"),
    PairSpec("B5", "DCI 1 A", 0x6D, 0x6E, 1.0, "A", "CONF:CURR:DC 1", "Apply a stable DC current near the selected range.", "1.000000000"),
    PairSpec("B5", "DCI 3 A", 0x71, 0x72, 3.0, "A", "CONF:CURR:DC 3", "Apply a stable DC current near the selected range. Confirm fuse and leads.", "3.000000000"),
    PairSpec("B6", "RES 100 ohm", 0x78, 0x79, 100.0, "ohm", "CONF:RES 100", "Connect a stable, known resistance near the selected range.", "100.000000000"),
    PairSpec("B6", "RES 1 kohm", 0x7C, 0x7D, 1000.0, "ohm", "CONF:RES 1000", "Connect a stable, known resistance near the selected range.", "1000.000000000"),
    PairSpec("B6", "RES 10 kohm", 0x80, 0x81, 10000.0, "ohm", "CONF:RES 10000", "Connect a stable, known resistance near the selected range.", "10000.000000000"),
    PairSpec("B6", "RES 100 kohm", 0x84, 0x85, 100000.0, "ohm", "CONF:RES 100000", "Connect a stable, known resistance near the selected range.", "100000.000000000"),
    PairSpec("B6", "RES 1 Mohm", 0x88, 0x89, 1000000.0, "ohm", "CONF:RES 1000000", "Connect a stable, known resistance near the selected range.", "1000000.000000000"),
    PairSpec("B6", "RES 10 Mohm", 0x8C, 0x8D, 10000000.0, "ohm", "CONF:RES 10000000", "Connect a stable, known resistance near the selected range.", "10000000.000000000"),
    PairSpec("B7", "FRES 100 ohm", 0x93, 0x94, 100.0, "ohm", "CONF:FRES 100", "Connect a stable, known 4-wire resistance near the selected range.", "100.000000000"),
    PairSpec("B7", "FRES 1 kohm", 0x95, 0x96, 1000.0, "ohm", "CONF:FRES 1000", "Connect a stable, known 4-wire resistance near the selected range.", "1000.000000000"),
    PairSpec("B7", "FRES 10 kohm", 0x97, 0x98, 10000.0, "ohm", "CONF:FRES 10000", "Connect a stable, known 4-wire resistance near the selected range.", "10000.000000000"),
    PairSpec("B7", "FRES 100 kohm", 0x99, 0x9A, 100000.0, "ohm", "CONF:FRES 100000", "Connect a stable, known 4-wire resistance near the selected range.", "100000.000000000"),
    PairSpec("B7", "FRES 1 Mohm", 0x9B, 0x9C, 1000000.0, "ohm", "CONF:FRES 1000000", "Connect a stable, known 4-wire resistance near the selected range.", "1000000.000000000"),
    PairSpec("B7", "FRES 10 Mohm", 0x9D, 0x9E, 10000000.0, "ohm", "CONF:FRES 10000000", "Connect a stable, known 4-wire resistance near the selected range.", "10000000.000000000"),
    PairSpec("B8", "ACV 100 mV @ 1 kHz", 0xB0, 0xB1, 0.1, "V RMS", "CONF:VOLT:AC 0.1", "Apply the specified RMS voltage at 1 kHz.", "0.100000000"),
    PairSpec("B8", "ACV 100 mV @ 50 kHz", 0xB2, 0xB3, 0.1, "V RMS", "CONF:VOLT:AC 0.1", "Apply the specified RMS voltage at 50 kHz.", "0.100000000"),
    PairSpec("B8", "ACV 1 V", 0xB4, 0xB5, 1.0, "V RMS", "CONF:VOLT:AC 1", "Apply a stable RMS AC voltage near the selected range; use the required frequency for the intended procedure.", "1.000000000"),
    PairSpec("B8", "ACV 10 V", 0xB6, 0xB7, 10.0, "V RMS", "CONF:VOLT:AC 10", "Apply a stable RMS AC voltage near the selected range; use the required frequency for the intended procedure.", "10.000000000"),
    PairSpec("B8", "ACV 100 V", 0xB8, 0xB9, 100.0, "V RMS", "CONF:VOLT:AC 100", "Apply a stable RMS AC voltage near the selected range; use the required frequency for the intended procedure.", "100.000000000"),
    PairSpec("B8", "ACV 750 V", 0xBA, 0xBB, 750.0, "V RMS", "CONF:VOLT:AC 750", "Apply a stable RMS AC voltage near the selected range. Observe HV safety limits.", "750.000000000"),
    PairSpec("B8", "ACI 1 A", 0xBC, 0xBD, 1.0, "A RMS", "CONF:CURR:AC 1", "Apply a stable RMS AC current near the selected range; use the required frequency for the intended procedure.", "1.000000000"),
    PairSpec("B8", "ACI 3 A", 0xBE, 0xBF, 3.0, "A RMS", "CONF:CURR:AC 3", "Apply a stable RMS AC current near the selected range; use the required frequency for the intended procedure. Confirm fuse and leads.", "3.000000000"),
]


def signed16(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


def word_block(index: int) -> str:
    for block_id, _name, start, count, checksum_index in BLOCKS:
        if start <= index < start + count:
            return block_id
        if index == checksum_index:
            return f"{block_id} checksum"
    if 0xD3 <= index <= 0xFF:
        return "Unused / erased"
    return "Other"


def word_description(index: int) -> str:
    if index in CORE_DESCRIPTIONS:
        return CORE_DESCRIPTIONS[index]
    if index in CANDIDATE_LABELS:
        return CANDIDATE_LABELS[index]
    if 0x0B <= index <= 0x1B:
        return "ROM-initialized internal constant"
    if 0x24 <= index <= 0x2F:
        return "Additional internal correction / variant field"
    if 0x32 <= index <= 0x4A:
        return "Packed 7-bit calibration-text bitstream"
    if 0x4C <= index <= 0x63:
        return "DCV correction-area raw word; semantic role not fully proven"
    if 0x65 <= index <= 0x76:
        return "DCI correction-area raw word; semantic role not fully proven"
    if 0x78 <= index <= 0x91:
        return "2-wire resistance correction-area raw word; semantic role not fully proven"
    if 0x93 <= index <= 0xAD:
        return "4-wire resistance correction-area raw word; candidate Q23 term"
    if 0xB0 <= index <= 0xCE:
        return "AC / frequency correction-area raw word; candidate Q23 term"
    if 0xD3 <= index <= 0xFF:
        return "Unused EEPROM region; normally erased FFFF"
    return ""


def decode_cal_string(words: List[int]) -> Tuple[str, str]:
    """
    Observed / validated decode:
    W[0x32] bit 0 first; each 16-bit word LSB-first; 7-bit LSB-first characters.
    """
    bits: List[int] = []
    for word in words[0x32:0x4B]:
        bits.extend((word >> bit) & 1 for bit in range(16))

    chars: List[int] = []
    for base in range(0, len(bits) - 6, 7):
        chars.append(sum(bits[base + bit] << bit for bit in range(7)))

    visible: List[str] = []
    printable: List[str] = []
    for value in chars:
        if value == 0:
            visible.append("·")
        elif 32 <= value <= 126:
            visible.append(chr(value))
            printable.append(chr(value))
        else:
            visible.append(f"\\x{value:02X}")
    return "".join(visible).rstrip("·"), "".join(printable).strip()


def settings_summary(word: int) -> List[str]:
    return [
        f"Raw settings word: 0x{word:04X}",
        f"Interface bit b6: {'RS-232' if (word & 0x0040) else 'GPIB'}",
        f"10 mA AC bit b4: {'enabled' if (word & 0x0010) else 'disabled'}",
        f"Comma-decimal bit b1: {'enabled' if (word & 0x0002) else 'disabled'}",
        f"Beeper bit b0: {'enabled' if (word & 0x0001) else 'disabled'}",
        f"Format/tag high byte: 0x{(word >> 8) & 0xFF:02X}",
    ]


def format_physical(value: float, unit: str) -> str:
    return f"{value:+.12g} {unit}"


def q23_record_summary(image: Optional["NvramImage"], spec: PairSpec, source_name: str) -> str:
    """Return copyable dump-record information. Never treats it as a CAL:VAL source."""
    if image is None:
        return f"{source_name}: no dump loaded."
    gain_raw = signed16(image.words[spec.gain_index])
    offset_raw = signed16(image.words[spec.offset_index])
    gain_increment = gain_raw / SCALE_Q23
    gain_factor = 1.0 + gain_increment
    gain_ppm = gain_increment * 1_000_000
    offset_fraction = offset_raw / SCALE_Q23
    offset_physical = offset_fraction * spec.full_scale
    return (
        f"{source_name}: {spec.label}\n"
        f"  Gain: W[{spec.gain_index:02X}] raw {gain_raw:+d}; "
        f"factor {gain_factor:.12f}; {gain_ppm:+.3f} ppm\n"
        f"  Offset: W[{spec.offset_index:02X}] raw {offset_raw:+d}; "
        f"{offset_fraction:+.12f} FS; {format_physical(offset_physical, spec.unit)}\n"
        f"  Status: candidate range-to-word map; record data only, not a valid CAL:VAL source."
    )


def q23_modeled_fullscale_value(image: Optional["NvramImage"], spec: PairSpec) -> Optional[float]:
    """
    A mathematical display only:
        full_scale * (1 + gain_raw / 2^23) + full_scale * (offset_raw / 2^23)
    It is useful for comparing candidate EEPROM records. It is NOT proven to be an
    external standard value and must not be pasted into CAL:VAL automatically.
    """
    if image is None:
        return None
    gain_raw = signed16(image.words[spec.gain_index])
    offset_raw = signed16(image.words[spec.offset_index])
    gain_factor = 1.0 + gain_raw / SCALE_Q23
    offset_physical = (offset_raw / SCALE_Q23) * spec.full_scale
    return spec.full_scale * gain_factor + offset_physical


@dataclass
class NvramImage:
    path: Path
    data: bytes
    words: List[int]

    @classmethod
    def load(cls, path: str | Path) -> "NvramImage":
        path = Path(path)
        data = path.read_bytes()
        if len(data) != 512:
            raise ValueError(f"Expected exactly 512 bytes; got {len(data)} bytes.")
        words = list(struct.unpack("<256H", data))
        return cls(path=path, data=data, words=words)

    def checksum_rows(self) -> List[Tuple[str, str, int, int, int, bool]]:
        rows = []
        for block_id, name, start, count, checksum_index in BLOCKS:
            calculated = (sum(self.words[start:start + count]) + count) & 0xFFFF
            stored = self.words[checksum_index]
            rows.append((block_id, name, start, checksum_index, stored, calculated == stored))
        return rows

    def calculated_checksum(self, start: int, count: int) -> int:
        return (sum(self.words[start:start + count]) + count) & 0xFFFF

    def overview_text(self) -> str:
        checks = self.checksum_rows()
        passed = sum(1 for *_rest, ok in checks if ok)
        cal_visible, cal_printable = decode_cal_string(self.words)
        w = self.words

        security = (
            "UNSECURED (W[00] = 0000)"
            if w[0x00] == 0x0000
            else "SECURED magic present (W[00] = 8661)"
            if w[0x00] == 0x8661
            else f"UNRECOGNIZED secure-state value (W[00] = {w[0x00]:04X})"
        )

        lines = [
            "34401A NVRAM Viewer v0.6 English — ANALYSIS + SERIAL TOOLS",
            "=" * 68,
            f"File: {self.path}",
            f"Bytes: {len(self.data)} (expected 512)",
            f"Words: {len(self.words)} × 16-bit little-endian",
            "",
            "Validated physical layout",
            f"  Checksum result: {passed}/{len(checks)} blocks pass",
            "  Formula: checksum = (sum(data words) + number of data words) mod 65536",
            "  Note: this is a 16-bit additive checksum, not a CRC.",
            "",
            "Core information",
            f"  Secure state: {security}",
            f"  GPIB address W[03]: {w[0x03]}",
            f"  Continuity threshold W[07]: {w[0x07] & 0x7FFF} ohm",
            f"  Hi-Z continuity W[07].b15: {'ON' if (w[0x07] & 0x8000) else 'OFF'}",
            f"  Feature word W[08]: 0x{w[0x08]:04X}",
            f"  Line-frequency trim W[09]: {w[0x09]}",
            f"  Firmware layout flag W[0A]: 0x{w[0x0A]:04X}",
            f"  Calibration count W[31]: {w[0x31]}",
            "",
            "Settings W[06]",
            *[f"  {item}" for item in settings_summary(w[0x06])],
            "",
            "Calibration text — correct observed bit layout",
            "  Source: W[32]..W[4A], beginning at bit 0 of W[32], LSB-first 7-bit packing.",
            f"  NUL shown as · : {cal_visible}",
            f"  Printable text only: {cal_printable}",
            "",
            "Interpretation boundary",
            "  B4..B8 are physical correction areas. The app shows raw signed-Int16 values",
            "  and Q23 conversions. The range-to-word labels remain CANDIDATE mappings until",
            "  proven with controlled before/after calibration dumps for the relevant firmware.",
            "",
            "SCPI CAL Assistant boundary",
            "  CAL:VAL requires the actual known external calibration signal applied to the meter.",
            "  It does NOT accept EEPROM raw coefficients, gain ppm, offset/FS, or derived offset.",
            "  This viewer generates templates only; it never connects to or changes a meter.",
        ]
        return "\n".join(lines)


class NvramViewer(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1450x900")
        self.minsize(1120, 700)

        self.image: Optional[NvramImage] = None
        self.compare_image: Optional[NvramImage] = None

        self.assistant_record_var = tk.StringVar()
        self.assistant_actual_value_var = tk.StringVar()
        self.assistant_security_code_var = tk.StringVar(value="HP034401")
        self.assistant_unlock_var = tk.BooleanVar(value=True)
        self.assistant_resecure_var = tk.BooleanVar(value=False)
        self.assistant_current_info_var = tk.StringVar(value="Open a dump to display the selected candidate record.")
        self.assistant_warning_var = tk.StringVar(value="")
        self.record_by_label: Dict[str, PairSpec] = {item.label: item for item in PAIR_SPECS}

        # Dump-reader state. The reader follows the supplied HPAK tool's proven core:
        # 9600 8N2 DTR/DSR, LF termination, SYST:RWL, DIAG:PEEK? -1,<0..255>,0, SYST:LOC.
        self.dump_port_var = tk.StringVar()
        self.dump_output_var = tk.StringVar(value=str(Path.cwd() / "caldump.bin"))
        self.dump_line_ending_var = tk.StringVar(value="LF (source compatible)")
        self.dump_lock_front_panel_var = tk.BooleanVar(value=True)
        self.dump_open_after_var = tk.BooleanVar(value=True)
        self.dump_running = False
        self.dump_abort_event = threading.Event()
        self.dump_progress_var = tk.DoubleVar(value=0.0)
        self.dump_status_var = tk.StringVar(value="Refresh ports, choose the 34401A serial port, then use Test *IDN? or Start dump.")
        self.dump_port_lookup: Dict[str, str] = {}

        # CAL:STR assistant state. This tab only generates copyable text;
        # it deliberately does not transmit a write command over RS-232.
        self.calstr_text_var = tk.StringVar(value="TEST -34401 -RS232")
        self.calstr_security_code_var = tk.StringVar(value="HP034401")
        self.calstr_unlock_var = tk.BooleanVar(value=True)
        self.calstr_resecure_var = tk.BooleanVar(value=False)
        self.calstr_status_var = tk.StringVar(value="Enter a calibration string (1–40 printable ASCII characters).")
        self.calstr_source_var = tk.StringVar(value="Manual text")
        self.calstr_execute_status_var = tk.StringVar(
            value="Live execution is idle. Select a COM port and use Execute after reviewing the command block."
        )

        self._build_menu()
        self._build_toolbar()
        self._build_tabs()
        self._build_status()

        if len(sys.argv) > 1:
            try:
                self.load_image(sys.argv[1])
            except Exception as exc:
                messagebox.showerror("Unable to load startup file", str(exc))

    # ---------- App-wide helpers ----------

    def set_clipboard(self, text: str, status: str = "Copied to clipboard.") -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        self.status_var.set(status)

    def copy_tree_selection(self, tree: ttk.Treeview) -> None:
        selected = tree.selection()
        if not selected:
            self.status_var.set("Select one or more table rows first.")
            return
        columns = list(tree["columns"])
        rows = []
        for item_id in selected:
            values = tree.item(item_id, "values")
            rows.append("\t".join(str(value) for value in values[:len(columns)]))
        self.set_clipboard("\n".join(rows), f"Copied {len(rows)} selected table row(s) as tab-separated text.")

    def add_tree_copy_bindings(self, tree: ttk.Treeview) -> None:
        tree.bind("<Control-c>", lambda event, t=tree: (self.copy_tree_selection(t), "break")[1])
        tree.bind("<Command-c>", lambda event, t=tree: (self.copy_tree_selection(t), "break")[1])

        popup = tk.Menu(tree, tearoff=False)
        popup.add_command(label="Copy selected row(s)", command=lambda t=tree: self.copy_tree_selection(t))

        def show_popup(event: tk.Event) -> None:
            item = tree.identify_row(event.y)
            if item:
                if item not in tree.selection():
                    tree.selection_set(item)
                popup.tk_popup(event.x_root, event.y_root)
            popup.grab_release()

        tree.bind("<Button-3>", show_popup)

    @staticmethod
    def _clear_tree(tree: ttk.Treeview) -> None:
        for item in tree.get_children():
            tree.delete(item)

    # ---------- Menu and toolbar ----------

    def _build_menu(self) -> None:
        menu = tk.Menu(self)

        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Open NVRAM dump…", command=self.open_image)
        file_menu.add_command(label="Open comparison dump…", command=self.open_compare)
        file_menu.add_command(label="Clear comparison", command=self.clear_compare)
        file_menu.add_separator()
        file_menu.add_command(label="Export analysis CSV…", command=self.export_csv)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)
        menu.add_cascade(label="File", menu=file_menu)

        copy_menu = tk.Menu(menu, tearoff=False)
        copy_menu.add_command(label="Copy overview", command=self.copy_overview)
        copy_menu.add_command(label="Copy CAL command block", command=self.copy_assistant_commands)
        copy_menu.add_command(label="Copy CAL:STR command block", command=self.copy_calstr_commands)
        menu.add_cascade(label="Copy", menu=copy_menu)

        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="About / use notes", command=self.show_about)
        help_menu.add_command(label="Why offset is not CAL:VAL", command=self.show_cal_value_explanation)
        menu.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menu)

    def _build_toolbar(self) -> None:
        frame = ttk.Frame(self, padding=(8, 7))
        frame.pack(fill="x")

        ttk.Button(frame, text="Open 512-byte dump", command=self.open_image).pack(side="left")
        ttk.Button(frame, text="Open compare dump", command=self.open_compare).pack(side="left", padx=(6, 0))
        ttk.Button(frame, text="Clear compare", command=self.clear_compare).pack(side="left", padx=(6, 0))
        ttk.Button(frame, text="Export analysis CSV", command=self.export_csv).pack(side="left", padx=(6, 0))

        note = ttk.Label(
            frame,
            text="Viewer + serial tools: read-only dump plus live CAL:STR write/verify; no raw EEPROM write.",
        )
        note.pack(side="right")

    # ---------- Tab construction ----------

    def _build_tabs(self) -> None:
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.overview_tab = ttk.Frame(self.notebook)
        self.dump_tab = ttk.Frame(self.notebook)
        self.checksum_tab = ttk.Frame(self.notebook)
        self.readable_tab = ttk.Frame(self.notebook)
        self.cal_assistant_tab = ttk.Frame(self.notebook)
        self.calstr_tab = ttk.Frame(self.notebook)
        self.raw_cal_tab = ttk.Frame(self.notebook)
        self.words_tab = ttk.Frame(self.notebook)
        self.compare_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.overview_tab, text="Overview")
        self.notebook.add(self.dump_tab, text="Read dump from 34401A")
        self.notebook.add(self.checksum_tab, text="Block checksums")
        self.notebook.add(self.readable_tab, text="Readable calibration table")
        self.notebook.add(self.cal_assistant_tab, text="SCPI CAL Assistant")
        self.notebook.add(self.calstr_tab, text="SCPI CAL:STR Assistant")
        self.notebook.add(self.raw_cal_tab, text="Raw B4–B8 words")
        self.notebook.add(self.words_tab, text="All 256 words")
        self.notebook.add(self.compare_tab, text="Compare dumps")

        self._build_overview_tab()
        self._build_dump_tab()
        self._build_checksum_tab()
        self._build_readable_tab()
        self._build_cal_assistant_tab()
        self._build_calstr_tab()
        self._build_raw_cal_tab()
        self._build_all_words_tab()
        self._build_compare_tab()

    def _build_overview_tab(self) -> None:
        top = ttk.Frame(self.overview_tab, padding=(8, 8, 8, 0))
        top.pack(fill="x")
        ttk.Button(top, text="Copy overview", command=self.copy_overview).pack(side="left")
        ttk.Label(top, text="Text is selectable; Ctrl+C also works.").pack(side="left", padx=(10, 0))

        self.overview_text = ScrolledText(self.overview_tab, wrap="word", font=("Consolas", 10))
        self.overview_text.pack(fill="both", expand=True, padx=8, pady=8)
        self.overview_text.configure(state="disabled")

    def _build_dump_tab(self) -> None:
        intro = ttk.Label(
            self.dump_tab,
            text=(
                "Read a complete 512-byte calibration EEPROM image through the 34401A RS-232 diagnostic read path. "
                "Core protocol reproduced from the supplied HPAK34401ACalTool source: 9600 baud, 8 data bits, no parity, "
                "2 stop bits, DTR/DSR flow control, LF command termination, SYST:RWL, "
                "DIAG:PEEK? -1,<word>,0 for words 0..255, then SYST:LOC. "
                "The GUI does not implement flash/write mode."
            ),
            justify="left",
            padding=(10, 10, 10, 4),
            wraplength=1360,
        )
        intro.pack(fill="x")

        if not PYSERIAL_AVAILABLE:
            unavailable = ttk.Label(
                self.dump_tab,
                text=(
                    "pyserial is not installed, so the serial reader is unavailable. "
                    "Run Install_Dependencies.bat once, then restart the viewer.\n"
                    f"Import detail: {PYSERIAL_IMPORT_ERROR}"
                ),
                justify="left",
                padding=(10, 4, 10, 4),
            )
            unavailable.pack(fill="x")

        settings = ttk.LabelFrame(self.dump_tab, text="Serial reader settings", padding=10)
        settings.pack(fill="x", padx=8, pady=4)
        settings.columnconfigure(1, weight=1)

        ttk.Label(settings, text="Detected serial port:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        self.dump_port_combo = ttk.Combobox(settings, textvariable=self.dump_port_var, state="readonly", width=55)
        self.dump_port_combo.grid(row=0, column=1, sticky="w", pady=3)
        ttk.Button(settings, text="Refresh ports", command=self.refresh_serial_ports).grid(row=0, column=2, sticky="w", padx=(8, 0), pady=3)
        ttk.Button(settings, text="Test *IDN?", command=self.start_idn_test).grid(row=0, column=3, sticky="w", padx=(8, 0), pady=3)

        ttk.Label(settings, text="Source-compatible link:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Label(settings, text="9600 baud | 8 data bits | no parity | 2 stop bits | DTR/DSR flow control").grid(row=1, column=1, columnspan=3, sticky="w", pady=3)

        ttk.Label(settings, text="Command termination:").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=3)
        self.dump_line_combo = ttk.Combobox(
            settings,
            textvariable=self.dump_line_ending_var,
            state="readonly",
            values=("LF (source compatible)", "CRLF", "CR"),
            width=28,
        )
        self.dump_line_combo.grid(row=2, column=1, sticky="w", pady=3)

        ttk.Checkbutton(
            settings,
            text="Use SYST:RWL before reading and SYST:LOC when finished (source-compatible; temporarily returns panel control at end)",
            variable=self.dump_lock_front_panel_var,
        ).grid(row=3, column=1, columnspan=3, sticky="w", pady=3)

        output = ttk.LabelFrame(self.dump_tab, text="Output file", padding=10)
        output.pack(fill="x", padx=8, pady=4)
        output.columnconfigure(1, weight=1)

        ttk.Label(output, text="Dump file path:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(output, textvariable=self.dump_output_var, width=90).grid(row=0, column=1, sticky="ew", pady=3)
        ttk.Button(output, text="Browse…", command=self.choose_dump_output).grid(row=0, column=2, padx=(8, 0), pady=3)
        ttk.Button(output, text="Reset to caldump.bin", command=self.reset_dump_output).grid(row=1, column=2, padx=(8, 0), pady=3)
        ttk.Label(
            output,
            text="Default matches the supplied command-line tool: current working directory\\caldump.bin",
        ).grid(row=1, column=1, sticky="w", pady=3)
        ttk.Checkbutton(
            output,
            text="Open the finished dump in the viewer automatically",
            variable=self.dump_open_after_var,
        ).grid(row=2, column=1, sticky="w", pady=3)

        action = ttk.LabelFrame(self.dump_tab, text="Read operation", padding=10)
        action.pack(fill="x", padx=8, pady=4)
        ttk.Button(action, text="Start 256-word dump", command=self.start_dump).pack(side="left")
        ttk.Button(action, text="Abort after current word", command=self.abort_dump).pack(side="left", padx=(8, 0))
        self.dump_progress = ttk.Progressbar(action, variable=self.dump_progress_var, maximum=256, length=360)
        self.dump_progress.pack(side="left", padx=(18, 8))
        ttk.Label(action, textvariable=self.dump_status_var).pack(side="left", padx=(0, 6))

        log_frame = ttk.LabelFrame(self.dump_tab, text="Reader log", padding=8)
        log_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        log_actions = ttk.Frame(log_frame)
        log_actions.pack(fill="x")
        ttk.Button(log_actions, text="Copy log", command=self.copy_dump_log).pack(side="left")
        ttk.Button(log_actions, text="Clear log", command=self.clear_dump_log).pack(side="left", padx=(8, 0))
        self.dump_log_text = ScrolledText(log_frame, wrap="word", height=14, font=("Consolas", 9))
        self.dump_log_text.pack(fill="both", expand=True, pady=(6, 0))
        self.dump_log_text.bind("<Control-a>", self.select_all_text)

        self.refresh_serial_ports()

    def _build_checksum_tab(self) -> None:
        self.checksum_tree = self._make_tree(
            self.checksum_tab,
            ("block", "name", "data_range", "checksum_word", "stored", "calculated", "result"),
            ("Block", "Name", "Data word range", "Checksum word", "Stored", "Calculated", "Result"),
            (90, 300, 145, 130, 110, 120, 95),
        )

    def _build_readable_tab(self) -> None:
        note = ttk.Label(
            self.readable_tab,
            text=(
                "The app converts raw signed-Int16 values using the Q23 model into gain factor, gain ppm, "
                "offset fraction, and an offset scaled by the nominated full-scale range.\n"
                "Physical B4–B8 areas and the Q23 conversion are verified. Individual range-to-word assignments "
                "remain CANDIDATE mappings until each is confirmed by a controlled before/after formal-calibration dump."
            ),
            justify="left",
            padding=(8, 8, 8, 0),
        )
        note.pack(fill="x")

        self.readable_tree = self._make_tree(
            self.readable_tab,
            ("block", "range", "gain_w", "gain_raw", "gain_factor", "gain_ppm",
             "offset_w", "offset_raw", "offset_fraction", "offset_physical", "status"),
            ("Block", "Candidate function / range", "Gain W", "Gain raw", "Gain factor",
             "Gain ppm", "Offset W", "Offset raw", "Offset / FS", "Offset (range-scaled)", "Status"),
            (70, 220, 80, 100, 145, 110, 80, 100, 135, 185, 285),
            pady=(4, 8),
        )

    def _build_cal_assistant_tab(self) -> None:
        warning = ttk.Label(
            self.cal_assistant_tab,
            text=(
                "Important: CAL:VAL is the ACTUAL value of the known external calibration signal applied to the meter. "
                "It is NOT an EEPROM raw value, gain ppm, offset/FS, or decoded range-scaled offset. "
                "This tab only creates copyable text. It never connects to a meter."
            ),
            justify="left",
            padding=(10, 10, 10, 4),
            wraplength=1300,
        )
        warning.pack(fill="x")

        controls = ttk.LabelFrame(self.cal_assistant_tab, text="Template inputs", padding=10)
        controls.pack(fill="x", padx=8, pady=(4, 4))
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Candidate function / range:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        self.assistant_combo = ttk.Combobox(
            controls,
            textvariable=self.assistant_record_var,
            values=[record.label for record in PAIR_SPECS],
            state="readonly",
            width=38,
        )
        self.assistant_combo.grid(row=0, column=1, sticky="w", pady=3)
        self.assistant_combo.bind("<<ComboboxSelected>>", lambda event: self.on_assistant_record_changed())

        ttk.Label(controls, text="Actual applied standard value:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=3)
        value_frame = ttk.Frame(controls)
        value_frame.grid(row=1, column=1, sticky="ew", pady=3)
        value_frame.columnconfigure(0, weight=1)
        self.assistant_value_entry = ttk.Entry(value_frame, textvariable=self.assistant_actual_value_var, width=35)
        self.assistant_value_entry.grid(row=0, column=0, sticky="w")
        self.assistant_value_source_var = tk.StringVar()
        self.assistant_value_source_combo = ttk.Combobox(
            value_frame,
            textvariable=self.assistant_value_source_var,
            state="readonly",
            width=56,
        )
        self.assistant_value_source_combo.grid(row=0, column=1, padx=(8, 0), sticky="w")
        self.assistant_value_source_combo.bind("<<ComboboxSelected>>", lambda event: self.use_selected_value_option())
        ttk.Button(value_frame, text="Apply selected source", command=self.use_selected_value_option).grid(row=0, column=2, padx=(8, 0))
        ttk.Label(
            controls,
            text=(
                "Nominal template fills a numeric formatting example. Selecting a primary/compare dump inserts its "
                "Q23-modeled numeric value into the field and refreshes the generated command. The displayed source "
                "continues to identify whether the number came from a dump model or manual entry."
            ),
            wraplength=1000,
        ).grid(row=2, column=1, sticky="w", pady=(0, 6))

        ttk.Label(controls, text="Dump record source:").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=3)
        self.assistant_dump_source_var = tk.StringVar(value="Primary dump record (reference only)")
        self.assistant_dump_source_combo = ttk.Combobox(
            controls,
            textvariable=self.assistant_dump_source_var,
            state="readonly",
            width=44,
            values=(
                "Primary dump record (reference only)",
                "Comparison dump record (reference only)",
            ),
        )
        self.assistant_dump_source_combo.grid(row=3, column=1, sticky="w", pady=3)
        self.assistant_dump_source_combo.bind("<<ComboboxSelected>>", lambda event: self.refresh_dump_record_reference())

        ttk.Label(
            controls,
            text=(
                "A loaded dump supplies raw gain/offset history for the selected range. "
                "Those values are shown below and can be copied, but they cannot be converted into a truthful CAL:VAL number "
                "without the instrument's live calibration algorithm and a known external standard."
            ),
            wraplength=850,
        ).grid(row=4, column=1, sticky="w", pady=(0, 6))

        ttk.Label(controls, text="Security code (not stored):").grid(row=5, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(controls, textvariable=self.assistant_security_code_var, width=25, show="").grid(row=5, column=1, sticky="w", pady=3)
        ttk.Checkbutton(
            controls,
            text="Include CAL:SEC:STAT OFF command (factory default shown; replace if your code was changed)",
            variable=self.assistant_unlock_var,
        ).grid(row=6, column=1, sticky="w", pady=3)
        ttk.Checkbutton(
            controls,
            text="Append CAL:SEC:STAT ON command after the error query",
            variable=self.assistant_resecure_var,
        ).grid(row=7, column=1, sticky="w", pady=3)

        actions = ttk.Frame(controls)
        actions.grid(row=0, column=2, rowspan=8, sticky="ns", padx=(12, 0))
        ttk.Button(actions, text="Generate / refresh", command=self.generate_assistant_commands).pack(fill="x", pady=(0, 6))
        ttk.Button(actions, text="Copy command block", command=self.copy_assistant_commands).pack(fill="x", pady=6)
        ttk.Button(actions, text="Explain CAL:VAL", command=self.show_cal_value_explanation).pack(fill="x", pady=(6, 0))

        info_frame = ttk.LabelFrame(self.cal_assistant_tab, text="Selected candidate record from the open dump", padding=8)
        info_frame.pack(fill="x", padx=8, pady=4)
        self.assistant_info_label = ttk.Label(info_frame, textvariable=self.assistant_current_info_var, justify="left", wraplength=1320)
        self.assistant_info_label.pack(anchor="w")
        self.assistant_warning_label = ttk.Label(
            info_frame,
            textvariable=self.assistant_warning_var,
            justify="left",
            wraplength=1320,
        )
        self.assistant_warning_label.pack(anchor="w", pady=(5, 0))

        record_frame = ttk.LabelFrame(self.cal_assistant_tab, text="Copyable historical correction record (for migration / comparison only)", padding=8)
        record_frame.pack(fill="x", padx=8, pady=4)
        record_buttons = ttk.Frame(record_frame)
        record_buttons.pack(fill="x")
        ttk.Button(record_buttons, text="Refresh record reference", command=self.refresh_dump_record_reference).pack(side="left")
        ttk.Button(record_buttons, text="Copy record summary", command=self.copy_dump_record_reference).pack(side="left", padx=(8, 0))
        ttk.Label(
            record_buttons,
            text="This text is deliberately separate from CAL:VAL.",
        ).pack(side="left", padx=(12, 0))
        self.assistant_dump_record_text = ScrolledText(record_frame, wrap="word", height=6, font=("Consolas", 9))
        self.assistant_dump_record_text.pack(fill="x", pady=(6, 0))
        self.assistant_dump_record_text.bind("<Control-a>", self.select_all_text)

        output_frame = ttk.LabelFrame(self.cal_assistant_tab, text="Copyable PuTTY / terminal command block", padding=8)
        output_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        ttk.Label(
            output_frame,
            text=(
                "The command text below contains SCPI lines only—no explanatory comments. "
                "Send one line at a time with the line termination that your 34401A expects. "
                "Do not send a block containing <ENTER_ACTUAL_STANDARD_VALUE>."
            ),
            wraplength=1320,
        ).pack(anchor="w", pady=(0, 5))
        self.assistant_output = ScrolledText(output_frame, wrap="none", height=14, font=("Consolas", 10))
        self.assistant_output.pack(fill="both", expand=True)
        self.assistant_output.bind("<Control-a>", self.select_all_text)

        self.assistant_record_var.set(PAIR_SPECS[2].label)  # DCV 10 V
        self.on_assistant_record_changed()

    def _build_calstr_tab(self) -> None:
        intro = ttk.Label(
            self.calstr_tab,
            text=(
                "Create, copy, or directly execute a CAL:STR write / verify sequence. "
                "Live execution uses the same selected COM port and serial settings as the dump reader. "
                "It sends only the CAL:STR workflow shown in this tab; it does not use flash mode or raw EEPROM writes."
            ),
            justify="left",
            padding=(10, 10, 10, 4),
            wraplength=1360,
        )
        intro.pack(fill="x")

        controls = ttk.LabelFrame(self.calstr_tab, text="Calibration string workflow", padding=10)
        controls.pack(fill="x", padx=8, pady=4)
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="String to write:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        self.calstr_entry = ttk.Entry(controls, textvariable=self.calstr_text_var, width=70)
        self.calstr_entry.grid(row=0, column=1, sticky="w", pady=3)
        ttk.Button(controls, text="Use primary dump string", command=lambda: self.load_calstr_from_dump(False)).grid(row=0, column=2, padx=(8, 0), pady=3)
        ttk.Button(controls, text="Use comparison dump string", command=lambda: self.load_calstr_from_dump(True)).grid(row=0, column=3, padx=(8, 0), pady=3)

        ttk.Label(
            controls,
            text="34401A calibration string: printable ASCII only; maximum 40 characters. Single quote is not accepted by this assistant because it would break the generated SCPI literal.",
            wraplength=1080,
        ).grid(row=1, column=1, columnspan=3, sticky="w", pady=(0, 6))

        ttk.Label(controls, text="Security code (not stored):").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(controls, textvariable=self.calstr_security_code_var, width=28).grid(row=2, column=1, sticky="w", pady=3)

        ttk.Checkbutton(
            controls,
            text="Unsecure only when CAL:SEC:STAT? returns 1",
            variable=self.calstr_unlock_var,
        ).grid(row=3, column=1, sticky="w", pady=3)
        ttk.Checkbutton(
            controls,
            text="Re-secure after successful verification",
            variable=self.calstr_resecure_var,
        ).grid(row=4, column=1, sticky="w", pady=3)

        command_actions = ttk.Frame(controls)
        command_actions.grid(row=0, column=4, rowspan=5, sticky="ns", padx=(15, 0))
        ttk.Button(command_actions, text="Generate / refresh", command=self.generate_calstr_commands).pack(fill="x", pady=(0, 6))
        ttk.Button(command_actions, text="Copy command block", command=self.copy_calstr_commands).pack(fill="x")

        status_frame = ttk.LabelFrame(self.calstr_tab, text="String validation", padding=8)
        status_frame.pack(fill="x", padx=8, pady=4)
        ttk.Label(status_frame, textvariable=self.calstr_status_var, justify="left", wraplength=1320).pack(anchor="w")

        output_frame = ttk.LabelFrame(self.calstr_tab, text="Copyable PuTTY / terminal command block", padding=8)
        output_frame.pack(fill="both", expand=False, padx=8, pady=(4, 4))
        ttk.Label(
            output_frame,
            text="This output contains SCPI lines only. Send one line at a time using the line ending that your 34401A expects.",
            wraplength=1320,
        ).pack(anchor="w", pady=(0, 5))
        self.calstr_output = ScrolledText(output_frame, wrap="none", height=9, font=("Consolas", 10))
        self.calstr_output.pack(fill="both", expand=True)
        self.calstr_output.bind("<Control-a>", self.select_all_text)

        live_frame = ttk.LabelFrame(self.calstr_tab, text="Live serial execution", padding=10)
        live_frame.pack(fill="x", padx=8, pady=4)
        live_frame.columnconfigure(1, weight=1)

        ttk.Label(live_frame, text="COM port:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        self.calstr_port_combo = ttk.Combobox(
            live_frame,
            textvariable=self.dump_port_var,
            state="readonly",
            width=55,
        )
        self.calstr_port_combo.grid(row=0, column=1, sticky="w", pady=3)
        ttk.Button(live_frame, text="Refresh ports", command=self.refresh_serial_ports).grid(row=0, column=2, padx=(8, 0), pady=3)
        ttk.Button(live_frame, text="Test *IDN?", command=self.start_idn_test).grid(row=0, column=3, padx=(8, 0), pady=3)

        ttk.Label(live_frame, text="Line ending:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=3)
        self.calstr_line_combo = ttk.Combobox(
            live_frame,
            textvariable=self.dump_line_ending_var,
            state="readonly",
            values=("LF (source compatible)", "CRLF", "CR"),
            width=28,
        )
        self.calstr_line_combo.grid(row=1, column=1, sticky="w", pady=3)
        ttk.Label(live_frame, text="Link settings: 9600 baud | 8N2 | DTR/DSR").grid(row=1, column=2, columnspan=2, sticky="w", pady=3)

        ttk.Button(
            live_frame,
            text="EXECUTE CAL:STR WRITE + VERIFY",
            command=self.start_calstr_execute,
        ).grid(row=2, column=1, sticky="w", pady=(8, 3))
        ttk.Label(
            live_frame,
            text="The button opens a confirmation dialog before any command is transmitted.",
        ).grid(row=2, column=2, columnspan=2, sticky="w", padx=(12, 0), pady=(8, 3))
        ttk.Label(live_frame, textvariable=self.calstr_execute_status_var, justify="left", wraplength=1320).grid(
            row=3, column=0, columnspan=4, sticky="w", pady=(6, 0)
        )

        log_frame = ttk.LabelFrame(self.calstr_tab, text="Live execution log", padding=8)
        log_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        log_actions = ttk.Frame(log_frame)
        log_actions.pack(fill="x")
        ttk.Button(log_actions, text="Copy log", command=self.copy_calstr_log).pack(side="left")
        ttk.Button(log_actions, text="Clear log", command=self.clear_calstr_log).pack(side="left", padx=(8, 0))
        self.calstr_log_text = ScrolledText(log_frame, wrap="word", height=10, font=("Consolas", 9))
        self.calstr_log_text.pack(fill="both", expand=True, pady=(6, 0))
        self.calstr_log_text.bind("<Control-a>", self.select_all_text)

        self.generate_calstr_commands()
        self.refresh_serial_ports()

    def _build_raw_cal_tab(self) -> None:
        self.raw_cal_tree = self._make_tree(
            self.raw_cal_tab,
            ("block", "word", "byte", "raw", "signed", "q23", "candidate", "description"),
            ("Block", "Word", "Byte offset", "Raw hex", "Signed Int16", "raw / 2^23", "Candidate label", "Description"),
            (70, 80, 100, 95, 110, 145, 300, 540),
        )

    def _build_all_words_tab(self) -> None:
        self.words_tree = self._make_tree(
            self.words_tab,
            ("block", "word", "byte", "raw", "unsigned", "signed", "description"),
            ("Block", "Word", "Byte offset", "Raw hex", "Unsigned", "Signed Int16", "Description"),
            (125, 80, 100, 95, 105, 115, 700),
        )

    def _build_compare_tab(self) -> None:
        top = ttk.Frame(self.compare_tab, padding=(8, 8, 8, 0))
        top.pack(fill="x")
        self.compare_info = ttk.Label(top, text="Open a second 512-byte dump to list changed words.")
        self.compare_info.pack(anchor="w")

        self.compare_tree = self._make_tree(
            self.compare_tab,
            ("word", "byte", "block", "first", "second", "delta", "description"),
            ("Word", "Byte offset", "Block", "Primary dump", "Compare dump", "Signed delta", "Description"),
            (80, 100, 135, 120, 120, 120, 700),
            pady=(4, 8),
        )

    def _make_tree(
        self,
        parent: ttk.Frame,
        columns: Tuple[str, ...],
        headings: Tuple[str, ...],
        widths: Tuple[int, ...],
        pady: Tuple[int, int] = (8, 8),
    ) -> ttk.Treeview:
        outer = ttk.Frame(parent)
        outer.pack(fill="both", expand=True, padx=8, pady=pady)

        buttons = ttk.Frame(outer)
        buttons.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ttk.Button(buttons, text="Copy selected row(s)", command=lambda: self.copy_tree_selection(tree)).pack(side="left")
        ttk.Label(buttons, text="Tip: select rows and press Ctrl+C, or right-click.").pack(side="left", padx=(10, 0))

        holder = ttk.Frame(outer)
        holder.grid(row=1, column=0, sticky="nsew")
        outer.rowconfigure(1, weight=1)
        outer.columnconfigure(0, weight=1)

        tree = ttk.Treeview(holder, columns=columns, show="headings", selectmode="extended")
        yscroll = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
        xscroll = ttk.Scrollbar(holder, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        for col, heading, width in zip(columns, headings, widths):
            tree.heading(col, text=heading)
            tree.column(col, width=width, minwidth=50, anchor="w")
        tree.column(columns[0], anchor="center")

        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)

        self.add_tree_copy_bindings(tree)
        return tree

    def _build_status(self) -> None:
        self.status_var = tk.StringVar(value="Open a 512-byte EEPROM dump to begin.")
        ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(8, 5)).pack(fill="x", side="bottom")

    # ---------- CAL:STR command assistant ----------

    def validate_calstr_text(self, text: str) -> Optional[str]:
        if not text:
            return "String is empty. Enter 1–40 printable ASCII characters."
        if len(text) > 40:
            return f"String is {len(text)} characters. Maximum is 40."
        if "'" in text:
            return "Single quote is not allowed because this assistant emits a single-quoted SCPI string literal."
        for character in text:
            if not (32 <= ord(character) <= 126):
                return f"Unsupported non-printable or non-ASCII character: {character!r}"
        return None

    def load_calstr_from_dump(self, use_comparison: bool) -> None:
        image = self.compare_image if use_comparison else self.image
        label = "comparison" if use_comparison else "primary"
        if image is None:
            messagebox.showinfo("No dump available", f"No {label} dump is loaded.")
            return
        _visible, printable = decode_cal_string(image.words)
        self.calstr_text_var.set(printable)
        self.calstr_source_var.set(f"Loaded from {label} dump")
        self.generate_calstr_commands()
        self.status_var.set(f"Loaded calibration string from {label} dump.")

    def generate_calstr_commands(self) -> None:
        text = self.calstr_text_var.get()
        code_value = self.calstr_security_code_var.get().strip()
        error = self.validate_calstr_text(text)

        if error:
            self.calstr_status_var.set("Not ready: " + error)
            output = (
                "CAL:SEC:STAT?\n"
                "; Correct the string validation error above before generating a write command.\n"
            )
        else:
            self.calstr_status_var.set(
                f"Ready: {len(text)} / 40 printable ASCII characters. "
                f"Source: {self.calstr_source_var.get()}."
            )
            lines = ["CAL:SEC:STAT?"]
            if self.calstr_unlock_var.get():
                if code_value:
                    lines.append(f"CAL:SEC:STAT OFF,{code_value}")
                else:
                    lines.append("<ENTER_CALIBRATION_SECURITY_CODE>")
            lines.extend([
                f"CAL:STR '{text}'",
                "CAL:STR?",
                "SYST:ERR?",
            ])
            if self.calstr_resecure_var.get():
                if code_value:
                    lines.append(f"CAL:SEC:STAT ON,{code_value}")
                else:
                    lines.append("<ENTER_CALIBRATION_SECURITY_CODE>")
            output = "\n".join(lines) + "\n"

        self.calstr_output.delete("1.0", "end")
        self.calstr_output.insert("1.0", output)

    def copy_calstr_commands(self) -> None:
        self.generate_calstr_commands()
        self.set_clipboard(
            self.calstr_output.get("1.0", "end-1c"),
            "Copied CAL:STR write / verify command block to clipboard.",
        )

    # ---------- Live CAL:STR serial execution ----------

    def append_calstr_log(self, line: str) -> None:
        try:
            self.calstr_log_text.insert("end", line.rstrip() + "\n")
            self.calstr_log_text.see("end")
        except Exception:
            pass

    def clear_calstr_log(self) -> None:
        self.calstr_log_text.delete("1.0", "end")

    def copy_calstr_log(self) -> None:
        self.set_clipboard(self.calstr_log_text.get("1.0", "end-1c"), "Copied CAL:STR execution log to clipboard.")

    @staticmethod
    def format_command_for_log(command: str) -> str:
        upper = command.upper()
        if upper.startswith("CAL:SEC:STAT OFF,"):
            return "CAL:SEC:STAT OFF,<hidden>"
        if upper.startswith("CAL:SEC:STAT ON,"):
            return "CAL:SEC:STAT ON,<hidden>"
        return command

    @staticmethod
    def parse_first_int(reply: str) -> int:
        match = re.search(r"[-+]?\d+", reply)
        if not match:
            raise ValueError(f"No integer found in reply: {reply!r}")
        return int(match.group(0), 10)

    def calstr_send_query(self, handle, command: str, terminator: bytes, timeout: float = 2.0) -> str:
        self.after(0, self.append_calstr_log, ">> " + self.format_command_for_log(command))
        self.serial_send(handle, command, terminator)
        reply = self.serial_read_cr_line(handle, timeout)
        self.after(0, self.append_calstr_log, "<< " + reply)
        return reply

    def calstr_send_write(self, handle, command: str, terminator: bytes) -> None:
        self.after(0, self.append_calstr_log, ">> " + self.format_command_for_log(command))
        self.serial_send(handle, command, terminator)
        time.sleep(0.080)

    def start_calstr_execute(self) -> None:
        error = self.validate_calstr_text(self.calstr_text_var.get())
        if error:
            messagebox.showerror("Cannot execute CAL:STR", error)
            return
        if not PYSERIAL_AVAILABLE:
            messagebox.showerror("pyserial is missing", "Run Install_Dependencies.bat once, then restart the viewer.")
            return
        if self.dump_running:
            messagebox.showinfo("Serial port busy", "Wait for the current serial read/test operation to finish.")
            return

        device = self.selected_serial_device()
        if not device:
            messagebox.showerror("No COM port selected", "Choose a COM port in this tab or the Dump Reader tab first.")
            return

        text = self.calstr_text_var.get()
        security_code = self.calstr_security_code_var.get().strip()
        if self.calstr_unlock_var.get() and not security_code:
            messagebox.showerror("Security code missing", "Enter a security code, or uncheck automatic unsecure.")
            return
        if self.calstr_resecure_var.get() and not security_code:
            messagebox.showerror("Security code missing", "Enter a security code before selecting re-secure.")
            return

        self.generate_calstr_commands()
        confirm = messagebox.askyesno(
            "Execute CAL:STR write + verify?",
            (
                f"This will open {device} and send commands that change the 34401A calibration string.\n\n"
                f"String to write:\n{text!r}\n\n"
                "Sequence:\n"
                "1. *IDN? (must identify as 34401A)\n"
                "2. CAL:SEC:STAT?\n"
                "3. If secured and enabled: CAL:SEC:STAT OFF,<code>\n"
                "4. CAL:STR '<text>'\n"
                "5. CAL:STR? verification\n"
                "6. SYST:ERR? verification\n"
                "7. Optional CAL:SEC:STAT ON,<code>\n\n"
                "Proceed?"
            ),
            icon="warning",
        )
        if not confirm:
            self.calstr_execute_status_var.set("Live CAL:STR execution cancelled.")
            return

        terminator = self.selected_line_ending()
        unlock_enabled = bool(self.calstr_unlock_var.get())
        resecure_enabled = bool(self.calstr_resecure_var.get())

        self.dump_running = True
        self.dump_abort_event.clear()
        self.calstr_execute_status_var.set("Executing CAL:STR write / verify sequence…")
        self.append_calstr_log(
            f"[INFO] Starting live CAL:STR workflow on {device}; line ending={self.dump_line_ending_var.get()}."
        )
        threading.Thread(
            target=self.calstr_execute_worker,
            args=(device, terminator, text, security_code, unlock_enabled, resecure_enabled),
            daemon=True,
        ).start()

    def calstr_execute_worker(
        self,
        device: str,
        terminator: bytes,
        text: str,
        security_code: str,
        unlock_enabled: bool,
        resecure_enabled: bool,
    ) -> None:
        handle = None
        try:
            handle = self.serial_open(device)
            self.after(0, self.append_calstr_log, f"[INFO] Opened {device}: 9600 8N2 DTR/DSR")

            identity = self.calstr_send_query(handle, "*IDN?", terminator, 2.0)
            identity_parts = [part.strip() for part in identity.split(",")]
            model = identity_parts[1] if len(identity_parts) > 1 else ""
            if model != "34401A":
                raise RuntimeError(f"*IDN? did not identify a 34401A (reply: {identity!r}). No CAL:STR command was sent.")

            secure_reply = self.calstr_send_query(handle, "CAL:SEC:STAT?", terminator, 2.0)
            secure_state = self.parse_first_int(secure_reply)
            if secure_state not in (0, 1):
                raise RuntimeError(f"Unexpected CAL:SEC:STAT? reply: {secure_reply!r}")

            if secure_state == 1:
                if not unlock_enabled:
                    raise RuntimeError("Instrument reports secured state=1 and automatic unsecure is disabled. No CAL:STR command was sent.")
                self.calstr_send_write(handle, f"CAL:SEC:STAT OFF,{security_code}", terminator)
                secure_reply = self.calstr_send_query(handle, "CAL:SEC:STAT?", terminator, 2.0)
                secure_state = self.parse_first_int(secure_reply)
                if secure_state != 0:
                    raise RuntimeError(f"Unsecure verification failed; CAL:SEC:STAT? returned {secure_reply!r}. No CAL:STR command was sent.")
            else:
                self.after(0, self.append_calstr_log, "[INFO] Instrument is already unsecured; no OFF command required.")

            self.calstr_send_write(handle, f"CAL:STR '{text}'", terminator)
            returned_string = self.calstr_send_query(handle, "CAL:STR?", terminator, 2.0)
            if text not in returned_string:
                raise RuntimeError(
                    f"CAL:STR? verification did not contain the requested text. Expected {text!r}; got {returned_string!r}."
                )

            error_reply = self.calstr_send_query(handle, "SYST:ERR?", terminator, 2.0)
            error_code = self.parse_first_int(error_reply)
            if error_code != 0:
                raise RuntimeError(f"SYST:ERR? reported a non-zero instrument error: {error_reply!r}")

            if resecure_enabled:
                self.calstr_send_write(handle, f"CAL:SEC:STAT ON,{security_code}", terminator)
                resecure_reply = self.calstr_send_query(handle, "CAL:SEC:STAT?", terminator, 2.0)
                resecure_state = self.parse_first_int(resecure_reply)
                if resecure_state != 1:
                    raise RuntimeError(f"Re-secure verification failed; CAL:SEC:STAT? returned {resecure_reply!r}.")

            success = (
                f"SUCCESS: CAL:STR written and verified on {device}. "
                f"Returned string matched and SYST:ERR? was zero."
            )
            if resecure_enabled:
                success += " Instrument re-secured."
            else:
                success += " Instrument left in its current unsecured state."
            self.after(0, self.append_calstr_log, "[SUCCESS] " + success)
            self.after(0, self.set_calstr_execution_status, success)

        except Exception as exc:
            detail = f"CAL:STR execution failed: {exc}"
            self.after(0, self.append_calstr_log, "[ERROR] " + detail)
            self.after(0, self.set_calstr_execution_status, detail)
        finally:
            if handle is not None:
                try:
                    handle.close()
                    self.after(0, self.append_calstr_log, f"[INFO] Closed {device}.")
                except Exception:
                    pass
            self.after(0, self.finish_serial_operation)

    def set_calstr_execution_status(self, text: str) -> None:
        self.calstr_execute_status_var.set(text)

    # ---------- File operations ----------

    def open_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Open 34401A 512-byte NVRAM dump",
            filetypes=[("Binary dump", "*.bin *.BIN"), ("All files", "*.*")],
        )
        if path:
            self.load_image(path)

    def open_compare(self) -> None:
        if not self.image:
            messagebox.showinfo("Open primary dump first", "Open the primary 512-byte NVRAM dump before choosing a comparison file.")
            return
        path = filedialog.askopenfilename(
            title="Open comparison 34401A NVRAM dump",
            filetypes=[("Binary dump", "*.bin *.BIN"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.compare_image = NvramImage.load(path)
            self.refresh_compare()
            self.refresh_value_source_choices()
            self.refresh_dump_record_reference()
            if hasattr(self, "calstr_output"):
                self.generate_calstr_commands()
            self.status_var.set(f"Comparison dump opened: {self.compare_image.path.name}")
        except Exception as exc:
            messagebox.showerror("Unable to open comparison dump", str(exc))

    def clear_compare(self) -> None:
        self.compare_image = None
        self._clear_tree(self.compare_tree)
        self.compare_info.configure(text="Open a second 512-byte dump to list changed words.")
        self.refresh_value_source_choices()
        self.refresh_dump_record_reference()
        if hasattr(self, "calstr_output"):
            self.generate_calstr_commands()
        self.status_var.set("Comparison dump cleared.")

    def load_image(self, path: str) -> None:
        try:
            self.image = NvramImage.load(path)
            self.refresh_all()
            self.status_var.set(f"Loaded: {self.image.path.name} — 512 bytes / 256 words")
        except Exception as exc:
            messagebox.showerror("Unable to open NVRAM dump", str(exc))

    # ---------- Serial dump reader ----------

    def append_dump_log(self, line: str) -> None:
        """GUI-thread-safe when called through after()."""
        try:
            self.dump_log_text.insert("end", line.rstrip() + "\n")
            self.dump_log_text.see("end")
        except Exception:
            pass

    def clear_dump_log(self) -> None:
        self.dump_log_text.delete("1.0", "end")

    def copy_dump_log(self) -> None:
        self.set_clipboard(self.dump_log_text.get("1.0", "end-1c"), "Copied reader log to clipboard.")

    def reset_dump_output(self) -> None:
        self.dump_output_var.set(str(Path.cwd() / "caldump.bin"))

    def choose_dump_output(self) -> None:
        current = Path(self.dump_output_var.get() or (Path.cwd() / "caldump.bin"))
        path = filedialog.asksaveasfilename(
            title="Save 34401A calibration dump as",
            defaultextension=".bin",
            initialfile=current.name or "caldump.bin",
            initialdir=str(current.parent if current.parent.exists() else Path.cwd()),
            filetypes=[("Binary dump", "*.bin"), ("All files", "*.*")],
        )
        if path:
            self.dump_output_var.set(path)

    def refresh_serial_ports(self) -> None:
        if not PYSERIAL_AVAILABLE:
            self.dump_port_lookup = {}
            self.dump_port_combo.configure(values=())
            self.dump_status_var.set("pyserial unavailable. Run Install_Dependencies.bat, then restart.")
            return

        previous_device = self.selected_serial_device()
        values: List[str] = []
        lookup: Dict[str, str] = {}
        for port in list_ports.comports():
            description = port.description or "Serial port"
            label = f"{port.device} — {description}"
            values.append(label)
            lookup[label] = port.device

        self.dump_port_lookup = lookup
        self.dump_port_combo.configure(values=values)
        if hasattr(self, "calstr_port_combo"):
            self.calstr_port_combo.configure(values=values)
        if values:
            selected_label = next((label for label, device in lookup.items() if device == previous_device), values[0])
            self.dump_port_var.set(selected_label)
            self.dump_status_var.set(f"Detected {len(values)} serial port(s).")
        else:
            self.dump_port_var.set("")
            self.dump_status_var.set("No serial ports detected. Plug in the adapter, then click Refresh ports.")

    def selected_serial_device(self) -> str:
        selected = self.dump_port_var.get().strip()
        return self.dump_port_lookup.get(selected, selected.split(" — ")[0].strip() if selected else "")

    def selected_line_ending(self) -> bytes:
        choice = self.dump_line_ending_var.get()
        if choice == "CRLF":
            return b"\r\n"
        if choice == "CR":
            return b"\r"
        return b"\n"

    def validate_dump_request(self) -> Optional[Tuple[str, Path]]:
        if not PYSERIAL_AVAILABLE:
            messagebox.showerror("pyserial is missing", "Run Install_Dependencies.bat once, then restart the viewer.")
            return None
        if self.dump_running:
            messagebox.showinfo("Reader busy", "A serial operation is already running.")
            return None

        device = self.selected_serial_device()
        if not device:
            messagebox.showerror("No COM port selected", "Click Refresh ports and select the COM port connected to the 34401A.")
            return None

        raw_path = self.dump_output_var.get().strip()
        if not raw_path:
            raw_path = str(Path.cwd() / "caldump.bin")
            self.dump_output_var.set(raw_path)
        output_path = Path(raw_path).expanduser()
        if not output_path.suffix:
            output_path = output_path.with_suffix(".bin")
            self.dump_output_var.set(str(output_path))

        if output_path.exists():
            if not messagebox.askyesno(
                "Overwrite output?",
                f"The file already exists:\n{output_path}\n\nOverwrite it after a complete 256-word read?",
            ):
                return None
        return device, output_path

    def serial_open(self, device: str):
        # Exactly mirrors the supplied tool's link settings: 9600, 8N2, DTR/DSR.
        return serial.Serial(
            port=device,
            baudrate=9600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_TWO,
            timeout=0.10,
            write_timeout=1.0,
            xonxoff=False,
            rtscts=False,
            dsrdtr=True,
        )

    def serial_send(self, handle, command: str, terminator: bytes) -> None:
        wire = command.encode("ascii") + terminator
        handle.write(wire)
        handle.flush()
        # Supplied libhp34401A waits 20 ms after each send.
        time.sleep(0.020)

    def serial_read_cr_line(self, handle, timeout_seconds: float = 1.5) -> str:
        """Read a source-compatible CR-terminated response and consume optional LF."""
        deadline = time.monotonic() + timeout_seconds
        buffer = bytearray()
        while time.monotonic() < deadline:
            one = handle.read(1)
            if not one:
                continue
            if one == b"\r":
                # Most 34401A replies are CRLF. Consume the LF if it is already queued.
                time.sleep(0.005)
                if getattr(handle, "in_waiting", 0):
                    tail = handle.read(1)
                    if tail not in (b"", b"\n"):
                        # A non-LF byte should not occur in this protocol. It cannot be
                        # pushed back, so log it rather than silently calling it a response.
                        self.after(0, self.append_dump_log, f"[WARN] Unexpected byte after CR: {tail!r}")
                return buffer.decode("ascii", errors="replace").strip()
            if one != b"\n":
                buffer.extend(one)
        raise TimeoutError("No complete CR-terminated reply before timeout.")

    @staticmethod
    def parse_signed_word(reply: str) -> int:
        match = re.search(r"[-+]?\d+", reply)
        if not match:
            raise ValueError(f"No decimal integer found in reply: {reply!r}")
        value = int(match.group(0), 10)
        if not -32768 <= value <= 65535:
            raise ValueError(f"Reply is outside an expected 16-bit range: {value}")
        return value & 0xFFFF

    def start_idn_test(self) -> None:
        if not PYSERIAL_AVAILABLE:
            messagebox.showerror("pyserial is missing", "Run Install_Dependencies.bat once, then restart the viewer.")
            return
        if self.dump_running:
            messagebox.showinfo("Reader busy", "Wait for the current operation to finish.")
            return
        device = self.selected_serial_device()
        if not device:
            messagebox.showerror("No COM port selected", "Click Refresh ports and choose a serial port first.")
            return

        terminator = self.selected_line_ending()
        self.dump_running = True
        self.dump_abort_event.clear()
        self.dump_status_var.set("Testing *IDN?…")
        self.append_dump_log(f"[INFO] Testing {device} with *IDN?")
        threading.Thread(target=self.idn_worker, args=(device, terminator), daemon=True).start()

    def idn_worker(self, device: str, terminator: bytes) -> None:
        handle = None
        try:
            handle = self.serial_open(device)
            self.after(0, self.append_dump_log, f"[INFO] Opened {device}: 9600 8N2 DTR/DSR")
            self.serial_send(handle, "*IDN?", terminator)
            # The supplied library uses a 300 ms delay before reading *IDN?.
            time.sleep(0.300)
            reply = self.serial_read_cr_line(handle, 2.0)
            parts = [item.strip() for item in reply.split(",")]
            model = parts[1] if len(parts) > 1 else ""
            if model == "34401A":
                message = f"PASS: *IDN? returned {reply}"
            else:
                message = f"WARNING: *IDN? returned {reply!r}; model field was {model!r}, not exact '34401A'."
            self.after(0, self.append_dump_log, "[INFO] " + message)
            self.after(0, self.set_dump_status_from_worker, message)
        except Exception as exc:
            detail = f"IDN test failed: {exc}"
            self.after(0, self.append_dump_log, "[ERROR] " + detail)
            self.after(0, self.set_dump_status_from_worker, detail)
        finally:
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    pass
            self.after(0, self.finish_serial_operation)

    def start_dump(self) -> None:
        validated = self.validate_dump_request()
        if validated is None:
            return
        device, output_path = validated

        terminator = self.selected_line_ending()
        use_rwl = bool(self.dump_lock_front_panel_var.get())
        open_after = bool(self.dump_open_after_var.get())
        self.dump_running = True
        self.dump_abort_event.clear()
        self.dump_progress_var.set(0)
        self.dump_status_var.set("Preparing 256-word dump…")
        self.append_dump_log(f"[INFO] Dump requested: port={device}, output={output_path}")
        threading.Thread(
            target=self.dump_worker,
            args=(device, output_path, terminator, use_rwl, open_after),
            daemon=True,
        ).start()

    def abort_dump(self) -> None:
        if self.dump_running:
            self.dump_abort_event.set()
            self.dump_status_var.set("Abort requested; stopping after the current serial operation.")
            self.append_dump_log("[WARN] Abort requested by user.")

    def set_dump_progress_from_worker(self, count: int) -> None:
        self.dump_progress_var.set(count)
        self.dump_status_var.set(f"Reading EEPROM word {count}/256…")

    def set_dump_status_from_worker(self, status: str) -> None:
        self.dump_status_var.set(status)

    def dump_worker(
        self,
        device: str,
        output_path: Path,
        terminator: bytes,
        use_rwl: bool,
        open_after: bool,
    ) -> None:
        handle = None
        used_rwl = False
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            handle = self.serial_open(device)
            self.after(0, self.append_dump_log, f"[INFO] Opened {device}: 9600 8N2 DTR/DSR")

            if use_rwl:
                self.serial_send(handle, "SYST:RWL", terminator)
                used_rwl = True
                self.after(0, self.append_dump_log, "[INFO] Sent SYST:RWL (will send SYST:LOC in cleanup).")

            words: List[int] = []
            for index in range(256):
                if self.dump_abort_event.is_set():
                    raise RuntimeError("Dump aborted by user before completion.")

                self.serial_send(handle, f"DIAG:PEEK? -1,{index},0", terminator)
                # The supplied tool calls its read routine with no deliberate query delay;
                # use a longer timeout here for USB-to-RS232 adapters without changing command syntax.
                reply = self.serial_read_cr_line(handle, 1.5)
                words.append(self.parse_signed_word(reply))

                completed = index + 1
                self.after(0, self.set_dump_progress_from_worker, completed)
                if completed == 1 or completed % 16 == 0 or completed == 256:
                    self.after(0, self.append_dump_log, f"[INFO] Read {completed}/256 words.")

            data = struct.pack("<256H", *words)
            image = NvramImage(path=output_path, data=data, words=words)
            checksum_rows = image.checksum_rows()
            pass_count = sum(1 for *_rest, ok in checksum_rows if ok)

            temp_path = output_path.with_name(output_path.name + ".part")
            temp_path.write_bytes(data)
            os.replace(temp_path, output_path)

            block_result = f"{pass_count}/9 checksum blocks PASS"
            self.after(0, self.append_dump_log, f"[INFO] Saved complete 512-byte dump: {output_path}")
            self.after(0, self.append_dump_log, f"[INFO] Verification after read: {block_result}")
            if pass_count != 9:
                self.after(0, self.append_dump_log, "[WARN] All 256 words were saved, but one or more block checksums failed. Preserve this dump and investigate.")
            self.after(0, self.set_dump_status_from_worker, f"Finished: {output_path.name}; {block_result}")

            if open_after:
                self.after(0, self.load_image, str(output_path))

        except Exception as exc:
            detail = str(exc)
            self.after(0, self.append_dump_log, "[ERROR] " + detail)
            self.after(0, self.set_dump_status_from_worker, "Dump failed: " + detail)
        finally:
            if handle is not None:
                if used_rwl:
                    try:
                        self.serial_send(handle, "SYST:LOC", terminator)
                        self.after(0, self.append_dump_log, "[INFO] Sent SYST:LOC.")
                    except Exception as exc:
                        self.after(0, self.append_dump_log, f"[WARN] Could not send SYST:LOC during cleanup: {exc}")
                try:
                    handle.close()
                    self.after(0, self.append_dump_log, f"[INFO] Closed {device}.")
                except Exception:
                    pass
            self.after(0, self.finish_serial_operation)

    def finish_serial_operation(self) -> None:
        self.dump_running = False
        self.dump_abort_event.clear()

    # ---------- Refresh views ----------

    def refresh_all(self) -> None:
        if not self.image:
            return
        self.refresh_overview()
        self.refresh_checksums()
        self.refresh_readable_calibration()
        self.refresh_raw_calibration()
        self.refresh_all_words()
        self.refresh_compare()
        self.on_assistant_record_changed()
        self.refresh_dump_record_reference()
        if hasattr(self, "calstr_output"):
            self.generate_calstr_commands()

    def refresh_overview(self) -> None:
        assert self.image
        self.overview_text.configure(state="normal")
        self.overview_text.delete("1.0", "end")
        self.overview_text.insert("1.0", self.image.overview_text())
        self.overview_text.configure(state="disabled")

    def refresh_checksums(self) -> None:
        assert self.image
        self._clear_tree(self.checksum_tree)
        for block_id, name, start, checksum_index, stored, ok in self.image.checksum_rows():
            count = next(count for bid, _name, s, count, c in BLOCKS if bid == block_id)
            calculated = self.image.calculated_checksum(start, count)
            self.checksum_tree.insert(
                "",
                "end",
                values=(
                    block_id, name, f"W[{start:02X}]–W[{start + count - 1:02X}]",
                    f"W[{checksum_index:02X}]", f"{stored:04X}", f"{calculated:04X}",
                    "PASS" if ok else "FAIL",
                ),
            )

    def refresh_readable_calibration(self) -> None:
        assert self.image
        self._clear_tree(self.readable_tree)
        for spec in PAIR_SPECS:
            gain_raw = signed16(self.image.words[spec.gain_index])
            offset_raw = signed16(self.image.words[spec.offset_index])
            gain_increment = gain_raw / SCALE_Q23
            gain_factor = 1.0 + gain_increment
            gain_ppm = gain_increment * 1_000_000
            offset_fraction = offset_raw / SCALE_Q23
            offset_physical = offset_fraction * spec.full_scale

            self.readable_tree.insert(
                "",
                "end",
                values=(
                    spec.block,
                    spec.label,
                    f"W[{spec.gain_index:02X}]",
                    gain_raw,
                    f"{gain_factor:.12f}",
                    f"{gain_ppm:+.3f}",
                    f"W[{spec.offset_index:02X}]",
                    offset_raw,
                    f"{offset_fraction:+.12f}",
                    format_physical(offset_physical, spec.unit),
                    "Candidate mapping — needs controlled dump proof",
                ),
            )

    def refresh_raw_calibration(self) -> None:
        assert self.image
        self._clear_tree(self.raw_cal_tree)
        for block_id, _name, start, count, _checksum_index in BLOCKS:
            if block_id not in {"B4", "B5", "B6", "B7", "B8"}:
                continue
            for index in range(start, start + count):
                raw = self.image.words[index]
                value = signed16(raw)
                self.raw_cal_tree.insert(
                    "",
                    "end",
                    values=(
                        block_id, f"W[{index:02X}]", f"0x{index * 2:03X}", f"{raw:04X}",
                        value, f"{value / SCALE_Q23:+.9f}",
                        CANDIDATE_LABELS.get(index, ""), word_description(index),
                    ),
                )

    def refresh_all_words(self) -> None:
        assert self.image
        self._clear_tree(self.words_tree)
        for index, raw in enumerate(self.image.words):
            self.words_tree.insert(
                "",
                "end",
                values=(
                    word_block(index), f"W[{index:02X}]", f"0x{index * 2:03X}",
                    f"{raw:04X}", raw, signed16(raw), word_description(index),
                ),
            )

    def refresh_compare(self) -> None:
        self._clear_tree(self.compare_tree)
        if not self.image or not self.compare_image:
            self.compare_info.configure(text="Open a second 512-byte dump to list changed words.")
            return

        changed = []
        for index, (first, second) in enumerate(zip(self.image.words, self.compare_image.words)):
            if first != second:
                changed.append((index, first, second))

        pass_primary = sum(1 for *_rest, ok in self.image.checksum_rows() if ok)
        pass_compare = sum(1 for *_rest, ok in self.compare_image.checksum_rows() if ok)
        self.compare_info.configure(
            text=(
                f"Primary: {self.image.path.name}    Compare: {self.compare_image.path.name}    "
                f"Changed words: {len(changed)}    Checksums: {pass_primary}/9 vs {pass_compare}/9 PASS"
            )
        )

        for index, first, second in changed:
            self.compare_tree.insert(
                "",
                "end",
                values=(
                    f"W[{index:02X}]", f"0x{index * 2:03X}", word_block(index),
                    f"{first:04X}", f"{second:04X}", signed16(second) - signed16(first),
                    word_description(index),
                ),
            )

    # ---------- SCPI CAL Assistant ----------

    def selected_spec(self) -> PairSpec:
        return self.record_by_label[self.assistant_record_var.get()]

    def on_assistant_record_changed(self) -> None:
        spec = self.selected_spec()
        self.refresh_value_source_choices()
        if self.image:
            gain_raw = signed16(self.image.words[spec.gain_index])
            offset_raw = signed16(self.image.words[spec.offset_index])
            gain_ppm = gain_raw / SCALE_Q23 * 1_000_000
            offset_fraction = offset_raw / SCALE_Q23
            offset_physical = offset_fraction * spec.full_scale
            info = (
                f"Candidate record: {spec.label}  |  gain W[{spec.gain_index:02X}]={gain_raw:+d} "
                f"({gain_ppm:+.3f} ppm)  |  offset W[{spec.offset_index:02X}]={offset_raw:+d} "
                f"({offset_fraction:+.12f} FS = {format_physical(offset_physical, spec.unit)}).\n"
                f"Do NOT paste any of those decoded EEPROM values into CAL:VAL. "
                f"CAL:VAL must be the actual known signal applied from your standard."
            )
        else:
            info = (
                f"Candidate record: {spec.label}. Open a dump to see its raw/Q23 values. "
                f"CAL:VAL must be the actual known signal applied from your standard; "
                f"it cannot be calculated from the raw EEPROM offset."
            )
        self.assistant_current_info_var.set(
            info + f"\nExternal source requirement: {spec.source_note}"
        )
        self.refresh_dump_record_reference()
        self.generate_assistant_commands()

    def refresh_value_source_choices(self) -> None:
        """Populate source choices for the selected candidate range."""
        spec = self.selected_spec()
        primary_model = q23_modeled_fullscale_value(self.image, spec)
        primary_detail = (
            f"Primary dump modeled value: {primary_model:.15g} {spec.unit}"
            if primary_model is not None
            else "Primary dump modeled value: unavailable (no primary dump)"
        )
        choices = [
            f"Nominal full-scale template: {spec.nominal_example}",
            primary_detail,
        ]
        if self.compare_image is not None:
            compare_model = q23_modeled_fullscale_value(self.compare_image, spec)
            choices.append(
                f"Comparison dump modeled value: {compare_model:.15g} {spec.unit}"
                if compare_model is not None
                else "Comparison dump modeled value: unavailable"
            )
        self.assistant_value_source_combo.configure(values=choices)
        if self.assistant_value_source_var.get() not in choices:
            self.assistant_value_source_var.set(choices[0])

    def use_selected_value_option(self) -> None:
        choice = self.assistant_value_source_var.get()
        if choice.startswith("Nominal full-scale template:"):
            self.use_nominal_example()
            return

        if choice.startswith("Comparison dump"):
            self.assistant_dump_source_var.set("Comparison dump record (reference only)")
            source_name, image = "Comparison dump", self.compare_image
        else:
            self.assistant_dump_source_var.set("Primary dump record (reference only)")
            source_name, image = "Primary dump", self.image

        spec = self.selected_spec()
        modeled = q23_modeled_fullscale_value(image, spec)
        self.refresh_dump_record_reference()

        if modeled is None:
            self.assistant_actual_value_var.set("")
            self.assistant_warning_var.set(
                f"{source_name} has no usable candidate record for {spec.label}; no numeric value was inserted."
            )
            self.status_var.set(f"{source_name} selected, but no modeled value is available.")
        else:
            model_text = f"{modeled:.15g}"
            self.assistant_actual_value_var.set(model_text)
            self.assistant_warning_var.set(
                f"{source_name} Q23 modeled value inserted: {model_text} {spec.unit}. "
                "It is a dump-derived model; verify independently for precision work."
            )
            self.status_var.set(f"{source_name} selected. Inserted modeled value: {model_text} {spec.unit}.")
        self.generate_assistant_commands()

    def use_nominal_example(self) -> None:
        spec = self.selected_spec()
        self.assistant_actual_value_var.set(spec.nominal_example)
        self.generate_assistant_commands()
        self.status_var.set(
            "Inserted a nominal example only. Replace it with the certified / independently measured actual value before calibration."
        )

    @staticmethod
    def valid_decimal_text(text: str) -> bool:
        try:
            Decimal(text.strip())
            return True
        except (InvalidOperation, ValueError):
            return False

    def generate_assistant_commands(self) -> None:
        spec = self.selected_spec()
        actual_text = self.assistant_actual_value_var.get().strip()
        code = self.assistant_security_code_var.get().strip()

        source_choice = self.assistant_value_source_var.get()
        using_dump_model = (
            source_choice.startswith("Primary dump modeled value:")
            or source_choice.startswith("Comparison dump modeled value:")
        )

        if actual_text and not self.valid_decimal_text(actual_text):
            self.assistant_warning_var.set("The actual standard value is not a valid numeric value.")
            value_for_command = "<ENTER_ACTUAL_STANDARD_VALUE>"
        elif actual_text:
            value_for_command = actual_text
            if using_dump_model:
                self.assistant_warning_var.set(
                    f"Command uses the selected dump's Q23 modeled value: {actual_text}. "
                    "Verify independently for precision work."
                )
            else:
                self.assistant_warning_var.set("")
        else:
            self.assistant_warning_var.set("No numeric value is available for the selected source. The generated block contains a placeholder.")
            value_for_command = "<ENTER_ACTUAL_STANDARD_VALUE>"

        # This output intentionally contains SCPI command lines only.
        # Do not put explanatory comments into a PuTTY paste block because the
        # 34401A may interpret them as invalid command text.
        lines = [
            "CAL:SEC:STAT?",
        ]

        if self.assistant_unlock_var.get():
            if code:
                lines.append(f"CAL:SEC:STAT OFF,{code}")
            else:
                lines.append("; SECURITY CODE EMPTY — enter the correct code before sending an unsecure command.")

        lines.extend([
            spec.scpi_config,
            f"CAL:VAL {value_for_command}",
            "CAL?",
            "SYST:ERR?",
            "CAL:COUN?",
        ])

        if self.assistant_resecure_var.get():
            if code:
                lines.append(f"CAL:SEC:STAT ON,{code}")
            else:
                lines.append("; SECURITY CODE EMPTY — cannot append a secure command.")

        self.assistant_output.delete("1.0", "end")
        self.assistant_output.insert("1.0", "\n".join(lines) + "\n")

    def copy_assistant_commands(self) -> None:
        text = self.assistant_output.get("1.0", "end-1c")
        if not text.strip():
            self.generate_assistant_commands()
            text = self.assistant_output.get("1.0", "end-1c")
        self.set_clipboard(text, "Copied SCPI CAL Assistant text to clipboard.")

    def copy_overview(self) -> None:
        if not self.image:
            self.status_var.set("Open a dump first.")
            return
        self.set_clipboard(self.image.overview_text(), "Copied overview text to clipboard.")

    def select_all_text(self, event: tk.Event) -> str:
        event.widget.tag_add("sel", "1.0", "end-1c")
        event.widget.mark_set("insert", "1.0")
        event.widget.see("insert")
        return "break"

    # ---------- Dump record reference (kept separate from CAL:VAL) ----------

    def selected_dump_record_image(self) -> Tuple[str, Optional[NvramImage]]:
        choice = getattr(self, "assistant_dump_source_var", tk.StringVar(value="Primary dump record (reference only)")).get()
        if choice.startswith("Comparison"):
            return "Comparison dump", self.compare_image
        return "Primary dump", self.image

    def refresh_dump_record_reference(self) -> None:
        if not hasattr(self, "assistant_dump_record_text"):
            return
        spec = self.selected_spec()
        source_name, image = self.selected_dump_record_image()
        text = q23_record_summary(image, spec, source_name)

        other_name = "Comparison dump" if source_name == "Primary dump" else "Primary dump"
        other_image = self.compare_image if source_name == "Primary dump" else self.image
        if other_image is not None:
            text += "\n\n" + q23_record_summary(other_image, spec, other_name)

        modeled = q23_modeled_fullscale_value(image, spec)
        if modeled is not None:
            text += (
                "\n\nQ23 modeled full-scale value used by the assistant when this source is selected:\n"
                f"  {modeled:.15g} {spec.unit}\n"
                "Formula: full_scale × (1 + Gain_raw / 2^23) + Offset_raw / 2^23 × full_scale"
            )
        else:
            text += "\n\nNo modeled value is available for this source."
        text += (
            "\n\nInterpretation note:\n"
            "This is a dump-derived Q23 migration model. When selected in v0.6 it populates "
            "the Actual applied standard field and CAL:VAL template. It remains distinct from "
            "an independently measured calibration-source value."
        )
        self.assistant_dump_record_text.delete("1.0", "end")
        self.assistant_dump_record_text.insert("1.0", text)

    def copy_dump_record_reference(self) -> None:
        if not hasattr(self, "assistant_dump_record_text"):
            return
        self.set_clipboard(
            self.assistant_dump_record_text.get("1.0", "end-1c"),
            "Copied historical correction-record summary to clipboard.",
        )

    # ---------- Export ----------

    def export_csv(self) -> None:
        if not self.image:
            messagebox.showinfo("No data", "Open a 512-byte NVRAM dump first.")
            return

        default = self.image.path.with_name(self.image.path.stem + "_analysis.csv")
        path = filedialog.asksaveasfilename(
            title="Export NVRAM analysis CSV",
            defaultextension=".csv",
            initialfile=default.name,
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(["34401A NVRAM Viewer v0.6 English — ANALYSIS + SERIAL TOOLS export"])
                writer.writerow(["Source file", str(self.image.path)])
                writer.writerow([])
                writer.writerow(["Checksum validation"])
                writer.writerow(["Block", "Name", "Data start", "Data count", "Checksum word", "Stored", "Calculated", "Result"])
                for block_id, name, start, checksum_index, stored, ok in self.image.checksum_rows():
                    count = next(count for bid, _name, s, count, c in BLOCKS if bid == block_id)
                    writer.writerow([
                        block_id, name, f"W[{start:02X}]", count, f"W[{checksum_index:02X}]",
                        f"{stored:04X}", f"{self.image.calculated_checksum(start, count):04X}",
                        "PASS" if ok else "FAIL",
                    ])

                writer.writerow([])
                writer.writerow(["Readable candidate calibration records"])
                writer.writerow([
                    "Block", "Candidate range", "Gain word", "Gain raw", "Gain factor", "Gain ppm",
                    "Offset word", "Offset raw", "Offset / FS", "Offset (range-scaled)", "Status",
                ])
                for spec in PAIR_SPECS:
                    gain_raw = signed16(self.image.words[spec.gain_index])
                    offset_raw = signed16(self.image.words[spec.offset_index])
                    gain_inc = gain_raw / SCALE_Q23
                    offset_frac = offset_raw / SCALE_Q23
                    writer.writerow([
                        spec.block, spec.label, f"W[{spec.gain_index:02X}]", gain_raw,
                        f"{1.0 + gain_inc:.12f}", f"{gain_inc * 1_000_000:+.6f}",
                        f"W[{spec.offset_index:02X}]", offset_raw, f"{offset_frac:+.12f}",
                        format_physical(offset_frac * spec.full_scale, spec.unit),
                        "Candidate mapping — needs controlled dump proof",
                    ])

                writer.writerow([])
                writer.writerow(["All 256 physical words"])
                writer.writerow(["Block", "Word", "Byte offset", "Raw hex", "Unsigned", "Signed Int16", "Q23 fraction", "Description"])
                for index, raw in enumerate(self.image.words):
                    value = signed16(raw)
                    writer.writerow([
                        word_block(index), f"W[{index:02X}]", f"0x{index * 2:03X}", f"{raw:04X}",
                        raw, value, f"{value / SCALE_Q23:+.12f}", word_description(index),
                    ])

            self.status_var.set(f"Exported: {Path(path).name}")
            messagebox.showinfo("Export complete", f"CSV saved:\n{path}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    # ---------- Help ----------

    def show_cal_value_explanation(self) -> None:
        messagebox.showinfo(
            "Why decoded offset is not CAL:VAL",
            "Example: DCV 10 V\n\n"
            "Suppose the readable table shows:\n"
            "  Offset / FS = -0.002012729645\n"
            "  Range-scaled offset = -0.02012729645 V\n\n"
            "Do NOT enter either value into CAL:VAL.\n"
            "Do NOT enter 10 V + offset or 10 V - offset merely from this table.\n\n"
            "CAL:VAL must contain the actual, known signal that your external standard "
            "is applying to the 34401A at that moment. For example:\n\n"
            "  actual standard output = 9.999999873 V\n"
            "  command              = CAL:VAL 9.999999873\n\n"
            "The 34401A then measures that applied signal and calculates its own new "
            "calibration constants. The existing EEPROM gain/offset words cannot by "
            "themselves tell you what the external standard actually output."
        )

    def show_about(self) -> None:
        messagebox.showinfo(
            f"About {APP_TITLE}",
            "Purpose: inspect, compare, and validate 512-byte 34401A EEPROM dumps.\n\n"
            "Implemented:\n"
            "• 256 little-endian 16-bit words\n"
            "• 9 physical-block 16-bit additive checksum validation\n"
            "• Correct calibration-string LSB-first 7-bit decoding\n"
            "• Raw B4–B8 signed-Int16 / Q23 view\n"
            "• Readable candidate gain / offset table\n"
            "• Two-dump word-by-word comparison\n"
            "• CSV export\n"
            "• Copy buttons, Ctrl+C table copy, and a copyable SCPI CAL template generator\n"
            "• Copyable and live-executable CAL:STR write / verify workflow\n"
            "• GUI serial dump reader using source-compatible DIAG:PEEK? -1,<word>,0 reads\n\n"
            "Implemented serial action:\n"
            "• Read-only 256-word EEPROM dump through RS-232; no flash/write mode\n\n"
            "Intentionally NOT implemented:\n"
            "• Direct formal CALibration coefficient transmission\n"
            "• DIAG:POKE or EEPROM write commands\n"
            "• EEPROM or dump writing\n"
            "• Automatic checksum modification\n"
            "• Treating decoded EEPROM corrections as a proven CAL:VAL value\n\n"
            "The SCPI CAL Assistant only makes text templates. The dump reader performs diagnostic reads only; "
            "it temporarily uses SYST:RWL/SYST:LOC when that source-compatible option is enabled."
        )


if __name__ == "__main__":
    NvramViewer().mainloop()
