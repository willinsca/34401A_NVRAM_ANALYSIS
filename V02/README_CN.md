# 34401A NVRAM Viewer v0.2（只读分析版）

这是一个 Windows 图形界面工具，用于分析 **512-byte HP / Agilent / Keysight 34401A EEPROM/NVRAM dump**。

## 本版用途

- 打开 `.bin` 文件并验证其是否为 512 bytes。
- 按 **256 × 16-bit little-endian words** 显示数据。
- 验证 9 个 NVRAM block 的 checksum：

  ```text
  checksum = (所有数据 word 的和 + 本 block 数据 word 数量) mod 65536
  ```

- 显示核心设置、calibration count 和 calibration string。
- 正确解码 calibration string：

  ```text
  W[0x32] 起始 bit 0
  每个 word LSB-first
  连续 7-bit LSB-first 字符
  ```

- 显示 B4–B8 的校准区域 raw word、signed Int16、`raw / 2^23`。
- 对比两份 dump，列出变化的 word。
- 导出 CSV。

## 安全边界

本版是 **只读** 工具：

- 不连接 RS232；
- 不发送任何 SCPI；
- 不包含 `DIAG:POKE / PEEK`；
- 不改写 dump；
- 不改 checksum；
- 不写 EEPROM。

这样先把“读、比对、验证、解释数据”做稳，再单独设计写入功能。

## Windows 使用方式

### 方式 1：已安装 Python

建议 Windows 安装 Python 3.9 或更新版本，并在安装时勾选 “Add Python to PATH”。

双击：

```text
Launch_34401A_NVRAM_Viewer.bat
```

或双击：

```text
34401A_NVRAM_Viewer.pyw
```

### 方式 2：制作独立 EXE

在本文件夹空白处右键“在终端中打开”，运行：

```text
Build_Windows_EXE.bat
```

它会用 PyInstaller 在 `dist` 文件夹生成单文件 Windows EXE。

## 数据解释提醒

- 9 个 block 的物理边界和 checksum 规则，已由三份 dump 交叉验证。
- B4–B8 是校准相关区域；raw `Int16` 与 Q23 解读是主要观察目标。
- 程序中标记为 “Provisional / 候选”的每量程语义标签，是为了导航而保留的候选映射；并不代表每个 word 的物理含义已经完全由受控实验验证。
- 写入新 NVRAM 或通过 RS232 提交校准数据前，应先做：
  1. 原始 EEPROM dump；
  2. 写前/写后 diff；
  3. 9 block checksum 验证；
  4. 断电重启后的第二次 dump。



## v0.2 新增

- 新增“可读校准表（候选映射）”：显示 gain factor、gain ppm、offset fraction 和按满量程换算的物理 offset。
- 所有每量程对应关系均明确标示为 Candidate mapping，避免把未完成验证的推定当成事实。
