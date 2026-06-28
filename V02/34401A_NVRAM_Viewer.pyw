#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
34401A NVRAM Viewer v0.2
Read-only viewer / verifier for 512-byte HP/Agilent/Keysight 34401A EEPROM dumps.

This program intentionally contains NO serial-port, SCPI, or EEPROM-writing function.
It is designed to inspect physical 512-byte dumps safely before any calibration work.
"""

from __future__ import annotations

import csv
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText


SCALE_Q23 = 8_388_608

# Confirmed physical block boundaries from the three-dump validation.
BLOCKS = [
    ("B0", "Secure state",       0x00,  2, 0x02),
    ("B1", "GPIB / interface",  0x03,  2, 0x05),
    ("B2", "Internal data",     0x06, 42, 0x30),
    ("B3", "Calibration text",  0x31, 26, 0x4B),
    ("B4", "DCV correction area",  0x4C, 24, 0x64),
    ("B5", "DCI correction area",  0x65, 18, 0x77),
    ("B6", "2-wire resistance correction area", 0x78, 26, 0x92),
    ("B7", "4-wire resistance correction area", 0x93, 28, 0xAF),
    ("B8", "AC / frequency correction area", 0xB0, 34, 0xD2),
]

# Important core words with stronger support than the per-range correction mapping.
CORE_DESCRIPTIONS: Dict[int, str] = {
    0x00: "Secure state: 0000=unsecured, 8661=secured",
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

# Candidate labels are deliberately marked as PROVISIONAL. They help navigation
# but are not used to perform writes and do not claim full word-level proof.
CANDIDATE_LABELS: Dict[int, str] = {
    0x4C: "Provisional: DCV 100 mV gain word",
    0x4D: "Provisional: DCV 100 mV offset word",
    0x50: "Provisional: DCV 1 V gain word",
    0x51: "Provisional: DCV 1 V offset word",
    0x54: "Provisional: DCV 10 V gain word",
    0x55: "Provisional: DCV 10 V offset word",
    0x58: "Provisional: DCV 100 V gain word",
    0x59: "Provisional: DCV 100 V offset word",
    0x5C: "Provisional: DCV 1000 V gain word",
    0x5D: "Provisional: DCV 1000 V offset word",
    0x60: "Provisional: DCV -10 V / 500 V gain word",
    0x62: "Provisional: DCV -10 V / 500 V offset word",
    0x65: "Provisional: DCI 10 mA gain word",
    0x66: "Provisional: DCI 10 mA offset word",
    0x69: "Provisional: DCI 100 mA gain word",
    0x6A: "Provisional: DCI 100 mA offset word",
    0x6D: "Provisional: DCI 1 A gain word",
    0x6E: "Provisional: DCI 1 A offset word",
    0x71: "Provisional: DCI 3 A gain word",
    0x72: "Provisional: DCI 3 A offset word",
    0x75: "Provisional: DCI / AC linearity term",
    0x78: "Provisional: RES 100 ohm gain word",
    0x79: "Provisional: RES 100 ohm offset word",
    0x7C: "Provisional: RES 1 kohm gain word",
    0x7D: "Provisional: RES 1 kohm offset word",
    0x80: "Provisional: RES 10 kohm gain word",
    0x81: "Provisional: RES 10 kohm offset word",
    0x84: "Provisional: RES 100 kohm gain word",
    0x85: "Provisional: RES 100 kohm offset word",
    0x88: "Provisional: RES 1 Mohm gain word",
    0x89: "Provisional: RES 1 Mohm offset word",
    0x8C: "Provisional: RES 10 Mohm gain word",
    0x8D: "Provisional: RES 10 Mohm offset word",
    0x90: "Provisional: extra resistance / continuity term",
}

# B7 / B8 sequential records are a practical navigation aid. The physical block
# layout is verified; the semantic labels remain a candidate map until a controlled
# before/after calibration experiment proves every record.
for base, name in [
    (0x93, "FRES 100 ohm"), (0x95, "FRES 1 kohm"), (0x97, "FRES 10 kohm"),
    (0x99, "FRES 100 kohm"), (0x9B, "FRES 1 Mohm"), (0x9D, "FRES 10 Mohm"),
    (0x9F, "FRES extra 0"), (0xA1, "FRES extra 1"),
    (0xB0, "ACV 100 mV @ 1 kHz"), (0xB2, "ACV 100 mV @ 50 kHz"),
    (0xB4, "ACV 1 V"), (0xB6, "ACV 10 V"), (0xB8, "ACV 100 V"),
    (0xBA, "ACV 750 V"), (0xBC, "ACI 1 A"), (0xBE, "ACI 3 A"),
    (0xC0, "Frequency / extra"),
]:
    CANDIDATE_LABELS[base] = f"Provisional: {name} gain word"
    CANDIDATE_LABELS[base + 1] = f"Provisional: {name} offset word"


# Candidate calibration records for a human-readable display.
# Physical B4–B8 areas and Q23 conversion are verified. The range-to-word map below
# is intentionally labelled "candidate": it still needs controlled pre/post calibration
# dump experiments to prove every record on every firmware revision.
PAIR_SPECS = [
    ("B4", "DCV 100 mV", 0x4C, 0x4D, 0.1, "V"),
    ("B4", "DCV 1 V", 0x50, 0x51, 1.0, "V"),
    ("B4", "DCV 10 V", 0x54, 0x55, 10.0, "V"),
    ("B4", "DCV 100 V", 0x58, 0x59, 100.0, "V"),
    ("B4", "DCV 1000 V", 0x5C, 0x5D, 1000.0, "V"),
    ("B5", "DCI 10 mA", 0x65, 0x66, 0.01, "A"),
    ("B5", "DCI 100 mA", 0x69, 0x6A, 0.1, "A"),
    ("B5", "DCI 1 A", 0x6D, 0x6E, 1.0, "A"),
    ("B5", "DCI 3 A", 0x71, 0x72, 3.0, "A"),
    ("B6", "RES 100 ohm", 0x78, 0x79, 100.0, "ohm"),
    ("B6", "RES 1 kohm", 0x7C, 0x7D, 1000.0, "ohm"),
    ("B6", "RES 10 kohm", 0x80, 0x81, 10000.0, "ohm"),
    ("B6", "RES 100 kohm", 0x84, 0x85, 100000.0, "ohm"),
    ("B6", "RES 1 Mohm", 0x88, 0x89, 1000000.0, "ohm"),
    ("B6", "RES 10 Mohm", 0x8C, 0x8D, 10000000.0, "ohm"),
    ("B7", "FRES 100 ohm", 0x93, 0x94, 100.0, "ohm"),
    ("B7", "FRES 1 kohm", 0x95, 0x96, 1000.0, "ohm"),
    ("B7", "FRES 10 kohm", 0x97, 0x98, 10000.0, "ohm"),
    ("B7", "FRES 100 kohm", 0x99, 0x9A, 100000.0, "ohm"),
    ("B7", "FRES 1 Mohm", 0x9B, 0x9C, 1000000.0, "ohm"),
    ("B7", "FRES 10 Mohm", 0x9D, 0x9E, 10000000.0, "ohm"),
    ("B8", "ACV 100 mV @ 1 kHz", 0xB0, 0xB1, 0.1, "V"),
    ("B8", "ACV 100 mV @ 50 kHz", 0xB2, 0xB3, 0.1, "V"),
    ("B8", "ACV 1 V", 0xB4, 0xB5, 1.0, "V"),
    ("B8", "ACV 10 V", 0xB6, 0xB7, 10.0, "V"),
    ("B8", "ACV 100 V", 0xB8, 0xB9, 100.0, "V"),
    ("B8", "ACV 750 V", 0xBA, 0xBB, 750.0, "V"),
    ("B8", "ACI 1 A", 0xBC, 0xBD, 1.0, "A"),
    ("B8", "ACI 3 A", 0xBE, 0xBF, 3.0, "A"),
]


def signed16(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


def word_block(index: int) -> str:
    for block_id, _name, start, count, checksum_index in BLOCKS:
        if start <= index < start + count:
            return block_id
        if index == checksum_index:
            return block_id + " checksum"
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
    Correct observed decode method:
    starts at bit 0 of W[0x32], each 16-bit word LSB first, chunks of 7 bits LSB first.
    """
    bits: List[int] = []
    for word in words[0x32:0x4B]:
        bits.extend((word >> bit) & 1 for bit in range(16))

    chars: List[int] = []
    for base in range(0, len(bits) - 6, 7):
        value = sum(bits[base + bit] << bit for bit in range(7))
        chars.append(value)

    visible = []
    cleaned = []
    for value in chars:
        if value == 0:
            visible.append("·")
        elif 32 <= value <= 126:
            visible.append(chr(value))
            cleaned.append(chr(value))
        else:
            visible.append(f"\\x{value:02X}")
    return "".join(visible).rstrip("·"), "".join(cleaned).strip()


def settings_summary(word: int) -> List[str]:
    return [
        f"Raw settings word: 0x{word:04X}",
        f"Interface bit b6: {'RS-232' if (word & 0x0040) else 'GPIB'}",
        f"10 mA AC bit b4: {'enabled' if (word & 0x0010) else 'disabled'}",
        f"Comma-decimal bit b1: {'enabled' if (word & 0x0002) else 'disabled'}",
        f"Beeper bit b0: {'enabled' if (word & 0x0001) else 'disabled'}",
        f"Format/tag high byte: 0x{(word >> 8) & 0xFF:02X}",
    ]


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
            calculated = sum(self.words[start:start + count]) + count
            calculated &= 0xFFFF
            stored = self.words[checksum_index]
            rows.append((block_id, name, start, checksum_index, stored, calculated == stored))
        return rows

    def calculated_checksum(self, start: int, count: int) -> int:
        return (sum(self.words[start:start + count]) + count) & 0xFFFF

    def overview_text(self) -> str:
        checks = self.checksum_rows()
        passed = sum(1 for *_rest, ok in checks if ok)
        cal_visible, cal_clean = decode_cal_string(self.words)
        w = self.words

        security = (
            "UNSECURED (W[00] = 0000)"
            if w[0x00] == 0x0000
            else "SECURED magic present (W[00] = 8661)"
            if w[0x00] == 0x8661
            else f"UNRECOGNIZED secure-state value (W[00] = {w[0x00]:04X})"
        )

        lines = [
            "34401A NVRAM Viewer v0.2 — READ ONLY",
            "=" * 62,
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
            f"  Hi-Z continuity flag W[07].b15: {'ON' if (w[0x07] & 0x8000) else 'OFF'}",
            f"  Feature word W[08]: 0x{w[0x08]:04X}",
            f"  Line-frequency trim W[09]: {w[0x09]}",
            f"  Firmware layout flag W[0A]: 0x{w[0x0A]:04X}",
            f"  Calibration count W[31]: {w[0x31]}",
            "",
            "Settings W[06]",
            *[f"  {item}" for item in settings_summary(w[0x06])],
            "",
            "Calibration text — correct observed bit layout",
            "  Source: W[32]..W[4A], starting at bit 0 of W[32], LSB-first 7-bit packing.",
            f"  Display with NUL shown as · : {cal_visible}",
            f"  Printable text only: {cal_clean}",
            "",
            "Important interpretation boundary",
            "  B4..B8 are physical correction areas. Raw signed-Int16 values are shown in",
            "  the Calibration tab. The Q23 model is useful for candidate correction values:",
            "      gain = 1 + raw / 8388608",
            "      offset fraction of full-scale = raw / 8388608",
            "  However, the exact semantic assignment of every B4..B6 word is not yet proven.",
            "  This viewer never writes EEPROM, sends SCPI, or changes a meter.",
        ]
        return "\n".join(lines)


class NvramViewer(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("34401A NVRAM Viewer v0.2 — Read-only")
        self.geometry("1320x850")
        self.minsize(1080, 680)

        self.image: Optional[NvramImage] = None
        self.compare_image: Optional[NvramImage] = None

        self._build_menu()
        self._build_toolbar()
        self._build_tabs()
        self._build_status()

        if len(sys.argv) > 1:
            try:
                self.load_image(sys.argv[1])
            except Exception as exc:
                messagebox.showerror("Unable to load startup file", str(exc))

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="打开 NVRAM dump…", command=self.open_image)
        file_menu.add_command(label="打开对比 dump…", command=self.open_compare)
        file_menu.add_separator()
        file_menu.add_command(label="导出当前分析 CSV…", command=self.export_csv)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.destroy)
        menu.add_cascade(label="文件", menu=file_menu)

        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="关于 / 使用说明", command=self.show_about)
        menu.add_cascade(label="帮助", menu=help_menu)
        self.config(menu=menu)

    def _build_toolbar(self) -> None:
        frame = ttk.Frame(self, padding=(8, 7))
        frame.pack(fill="x")

        ttk.Button(frame, text="打开 512-byte dump", command=self.open_image).pack(side="left")
        ttk.Button(frame, text="打开对比 dump", command=self.open_compare).pack(side="left", padx=(6, 0))
        ttk.Button(frame, text="清除对比", command=self.clear_compare).pack(side="left", padx=(6, 0))
        ttk.Button(frame, text="导出分析 CSV", command=self.export_csv).pack(side="left", padx=(6, 0))

        note = ttk.Label(
            frame,
            text="只读版：不含串口、SCPI 或 EEPROM 写入功能。",
        )
        note.pack(side="right")

    def _build_tabs(self) -> None:
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.overview_tab = ttk.Frame(self.notebook)
        self.checksum_tab = ttk.Frame(self.notebook)
        self.cal_tab = ttk.Frame(self.notebook)
        self.human_cal_tab = ttk.Frame(self.notebook)
        self.words_tab = ttk.Frame(self.notebook)
        self.compare_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.overview_tab, text="总览")
        self.notebook.add(self.checksum_tab, text="Block 校验")
        self.notebook.add(self.human_cal_tab, text="可读校准表（候选映射）")
        self.notebook.add(self.cal_tab, text="校准原始数据 B4–B8")
        self.notebook.add(self.words_tab, text="全部 256 words")
        self.notebook.add(self.compare_tab, text="对比")

        self.overview_text = ScrolledText(self.overview_tab, wrap="word", font=("Consolas", 10))
        self.overview_text.pack(fill="both", expand=True, padx=8, pady=8)
        self.overview_text.configure(state="disabled")

        self.checksum_tree = self._make_tree(
            self.checksum_tab,
            ("block", "name", "range", "checksum_word", "stored", "calculated", "result"),
            ("Block", "名称", "数据 W 范围", "Checksum W", "Stored", "Calculated", "结果"),
            (90, 270, 130, 110, 110, 110, 90),
        )
        human_note = ttk.Label(
            self.human_cal_tab,
            text=(
                "本页把 raw signed-Int16 按 Q23 转为较易阅读的 gain factor、gain ppm、"
                "offset fraction 和按量程换算的 offset。\n"
                "注意：B4–B8 的物理 block 与 Q23 公式已经验证；各 range 对应的具体 word 仍是候选映射，"
                "必须用一次正式校准前/后 physical dump 才能逐项定案。"
            ),
            justify="left",
            padding=(8, 8, 8, 0),
        )
        human_note.pack(fill="x")
        self.human_cal_tree = self._make_tree(
            self.human_cal_tab,
            ("block", "range", "gain_w", "gain_raw", "gain_factor", "gain_ppm",
             "offset_w", "offset_raw", "offset_fraction", "offset_physical", "status"),
            ("Block", "候选功能/量程", "Gain W", "Gain raw", "Gain factor",
             "Gain ppm", "Offset W", "Offset raw", "Offset / FS", "Offset（按量程）", "状态"),
            (70, 205, 80, 100, 145, 110, 80, 100, 130, 170, 205),
            pady=(4, 8),
        )

        self.cal_tree = self._make_tree(
            self.cal_tab,
            ("block", "word", "byte", "raw", "signed", "q23", "candidate", "description"),
            ("Block", "Word", "Byte", "Raw hex", "Signed Int16", "raw / 2^23", "候选含义", "说明"),
            (70, 80, 80, 95, 105, 140, 280, 500),
        )
        self.words_tree = self._make_tree(
            self.words_tab,
            ("block", "word", "byte", "raw", "unsigned", "signed", "description"),
            ("Block", "Word", "Byte", "Raw hex", "Unsigned", "Signed Int16", "说明"),
            (115, 80, 80, 95, 105, 105, 600),
        )

        compare_top = ttk.Frame(self.compare_tab, padding=(8, 8, 8, 0))
        compare_top.pack(fill="x")
        self.compare_info = ttk.Label(compare_top, text="打开第二个 512-byte dump 后显示逐 word 差异。")
        self.compare_info.pack(anchor="w")
        self.compare_tree = self._make_tree(
            self.compare_tab,
            ("word", "byte", "block", "first", "second", "delta", "description"),
            ("Word", "Byte", "Block", "主文件", "对比文件", "Signed delta", "说明"),
            (80, 80, 130, 110, 110, 120, 650),
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
        holder = ttk.Frame(parent)
        holder.pack(fill="both", expand=True, padx=8, pady=pady)

        tree = ttk.Treeview(holder, columns=columns, show="headings")
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
        return tree

    def _build_status(self) -> None:
        self.status_var = tk.StringVar(value="打开一个 512-byte EEPROM dump 开始分析。")
        ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(8, 5)).pack(fill="x", side="bottom")

    def open_image(self) -> None:
        path = filedialog.askopenfilename(
            title="打开 34401A 512-byte NVRAM dump",
            filetypes=[("Binary dump", "*.bin *.BIN"), ("All files", "*.*")],
        )
        if path:
            self.load_image(path)

    def open_compare(self) -> None:
        if not self.image:
            messagebox.showinfo("先打开主文件", "请先打开主 NVRAM dump，再选择对比文件。")
            return
        path = filedialog.askopenfilename(
            title="打开对比 34401A NVRAM dump",
            filetypes=[("Binary dump", "*.bin *.BIN"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.compare_image = NvramImage.load(path)
            self.refresh_compare()
            self.status_var.set(f"已打开对比文件：{self.compare_image.path.name}")
        except Exception as exc:
            messagebox.showerror("无法打开对比文件", str(exc))

    def clear_compare(self) -> None:
        self.compare_image = None
        self._clear_tree(self.compare_tree)
        self.compare_info.configure(text="打开第二个 512-byte dump 后显示逐 word 差异。")
        self.status_var.set("已清除对比文件。")

    def load_image(self, path: str) -> None:
        try:
            self.image = NvramImage.load(path)
            self.refresh_all()
            self.status_var.set(f"已加载：{self.image.path.name} — 512 bytes / 256 words")
        except Exception as exc:
            messagebox.showerror("无法打开 NVRAM dump", str(exc))

    @staticmethod
    def _clear_tree(tree: ttk.Treeview) -> None:
        for item in tree.get_children():
            tree.delete(item)

    def refresh_all(self) -> None:
        if not self.image:
            return
        self.refresh_overview()
        self.refresh_checksums()
        self.refresh_human_calibration()
        self.refresh_calibration_words()
        self.refresh_all_words()
        self.refresh_compare()

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
            count = next(count for bid, _n, s, count, c in BLOCKS if bid == block_id)
            calculated = self.image.calculated_checksum(start, count)
            self.checksum_tree.insert(
                "",
                "end",
                values=(
                    block_id, name, f"{start:02X}–{start + count - 1:02X}",
                    f"W[{checksum_index:02X}]", f"{stored:04X}", f"{calculated:04X}",
                    "PASS" if ok else "FAIL",
                ),
            )

    def refresh_human_calibration(self) -> None:
        assert self.image
        self._clear_tree(self.human_cal_tree)

        for block_id, label, gain_index, offset_index, full_scale, unit in PAIR_SPECS:
            gain_raw = signed16(self.image.words[gain_index])
            offset_raw = signed16(self.image.words[offset_index])

            gain_increment = gain_raw / SCALE_Q23
            gain_factor = 1.0 + gain_increment
            gain_ppm = gain_increment * 1_000_000
            offset_fraction = offset_raw / SCALE_Q23
            offset_physical = offset_fraction * full_scale

            # Engineering notation without hiding sign.
            if unit == "ohm":
                physical_text = f"{offset_physical:+.9g} ohm"
            else:
                physical_text = f"{offset_physical:+.12g} {unit}"

            self.human_cal_tree.insert(
                "",
                "end",
                values=(
                    block_id,
                    label,
                    f"W[{gain_index:02X}]",
                    gain_raw,
                    f"{gain_factor:.12f}",
                    f"{gain_ppm:+.3f}",
                    f"W[{offset_index:02X}]",
                    offset_raw,
                    f"{offset_fraction:+.12f}",
                    physical_text,
                    "Candidate mapping — needs controlled dump proof",
                ),
            )

    def refresh_calibration_words(self) -> None:
        assert self.image
        self._clear_tree(self.cal_tree)
        for block_id, _name, start, count, _checksum_index in BLOCKS:
            if block_id not in {"B4", "B5", "B6", "B7", "B8"}:
                continue
            for index in range(start, start + count):
                raw = self.image.words[index]
                signed = signed16(raw)
                candidate = CANDIDATE_LABELS.get(index, "")
                desc = word_description(index)
                self.cal_tree.insert(
                    "",
                    "end",
                    values=(
                        block_id, f"W[{index:02X}]", f"0x{index * 2:03X}", f"{raw:04X}",
                        signed, f"{signed / SCALE_Q23:+.9f}", candidate, desc,
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
            self.compare_info.configure(text="打开第二个 512-byte dump 后显示逐 word 差异。")
            return

        changes = []
        for index, (first, second) in enumerate(zip(self.image.words, self.compare_image.words)):
            if first != second:
                changes.append((index, first, second))

        pass_a = sum(1 for *_rest, ok in self.image.checksum_rows() if ok)
        pass_b = sum(1 for *_rest, ok in self.compare_image.checksum_rows() if ok)
        self.compare_info.configure(
            text=(
                f"主文件：{self.image.path.name}；对比文件：{self.compare_image.path.name}。"
                f" 变化 word：{len(changes)}；checksums：{pass_a}/9 vs {pass_b}/9 PASS。"
            )
        )

        for index, first, second in changes:
            self.compare_tree.insert(
                "",
                "end",
                values=(
                    f"W[{index:02X}]", f"0x{index * 2:03X}", word_block(index),
                    f"{first:04X}", f"{second:04X}", signed16(second) - signed16(first),
                    word_description(index),
                ),
            )

    def export_csv(self) -> None:
        if not self.image:
            messagebox.showinfo("没有数据", "请先打开一个 512-byte NVRAM dump。")
            return

        default = self.image.path.with_name(self.image.path.stem + "_analysis.csv")
        path = filedialog.asksaveasfilename(
            title="导出 NVRAM 分析 CSV",
            defaultextension=".csv",
            initialfile=default.name,
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(["34401A NVRAM Viewer v0.2 — READ ONLY export"])
                writer.writerow(["Source file", str(self.image.path)])
                writer.writerow([])
                writer.writerow(["Checksum validation"])
                writer.writerow(["Block", "Name", "Data start", "Data count", "Checksum word", "Stored", "Calculated", "Result"])
                for block_id, name, start, checksum_index, stored, ok in self.image.checksum_rows():
                    count = next(count for bid, _n, s, count, c in BLOCKS if bid == block_id)
                    writer.writerow([
                        block_id, name, f"W[{start:02X}]", count, f"W[{checksum_index:02X}]",
                        f"{stored:04X}", f"{self.image.calculated_checksum(start, count):04X}",
                        "PASS" if ok else "FAIL",
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
            self.status_var.set(f"已导出：{Path(path).name}")
            messagebox.showinfo("导出完成", f"CSV 已保存：\n{path}")
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))

    def show_about(self) -> None:
        messagebox.showinfo(
            "关于 34401A NVRAM Viewer v0.2",
            "用途：读取、显示、比较和验证 512-byte 34401A EEPROM dumps。\n\n"
            "已实现：\n"
            "• 256 个 little-endian 16-bit words\n"
            "• 9 个物理 block 的 16-bit 加法 checksum 验证\n"
            "• 正确的 calibration-string LSB-first 7-bit 解码\n"
            "• B4–B8 raw signed-Int16 / Q23 观察视图\n"
            "• 可读的候选 gain / offset 表（明确标示为候选映射）\n"
            "• 两份 dump 的逐 word 比较\n\n"
            "未实现且刻意禁用：\n"
            "• RS-232 / SCPI\n"
            "• DIAG:POKE / PEEK\n"
            "• EEPROM 写入\n"
            "• 自动修改 checksum\n\n"
            "原因：本版本是安全的只读分析工具。"
        )


if __name__ == "__main__":
    NvramViewer().mainloop()
