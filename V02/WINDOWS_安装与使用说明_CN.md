# 34401A NVRAM Viewer v0.2：Windows 安装与使用

这是 **只读分析工具**。它不会连接 RS232，不会发送 SCPI，也不会写 EEPROM。

## 1. 安装 Python（只需要一次）

1. 打开官方 Python 下载页：`https://www.python.org/downloads/`
2. 安装 Python Install Manager。
3. 安装完成后，按 Windows 键，输入 `cmd`，打开“命令提示符”。
4. 输入：

   ```text
   py install 3.13
   ```

5. 等待安装完成，再输入：

   ```text
   py -3.13 --version
   ```

   看到类似 `Python 3.13.x` 就表示完成。

> 本工具只使用 Python 自带的 tkinter 图形界面，不需要额外安装任何 Python 库。

## 2. 运行程序

1. 解压本 ZIP 到一个固定文件夹，例如：

   ```text
   C:\34401A_NVRAM_Viewer
   ```

2. 双击：

   ```text
   Launch_34401A_NVRAM_Viewer.bat
   ```

3. 程序打开后，点击左上角：

   ```text
   打开 512-byte dump
   ```

4. 选择你的任意 `.bin` 文件，例如：

   ```text
   old.bin
   caldump_08-05-02.bin
   my_34401_backup.bin
   ```

文件名没有要求。程序只检查文件是否为 **512 bytes**。

## 3. 最值得看的页面

### 总览

- secure / unsecured 状态
- GPIB 地址、settings、calibration count
- 正确解码的 calibration string
- 9 个 block checksum 是否全部 PASS

### Block 校验

逐块显示 stored checksum 与 calculated checksum。

### 可读校准表（候选映射）

显示为人类容易理解的格式：

- Gain raw：EEPROM 中的 signed Int16
- Gain factor：`1 + Gain_raw / 8388608`
- Gain ppm：增益偏差，单位 ppm
- Offset raw：EEPROM 中的 signed Int16
- Offset / FS：`Offset_raw / 8388608`
- Offset（按量程）：按照对应满量程换算的 V / A / ohm

重要：范围到 EEPROM word 的具体对应关系仍标为 **Candidate mapping**。
只有 B4–B8 block 的物理边界、checksum 算法和 Q23 计算公式已经验证。
后续可通过一次正式校准的“写前/写后物理 dump”把某一个 range 的 word 对逐项证实。

### 校准原始数据 B4–B8

显示所有 raw words，适合做严格 diff。

### 对比

可加载第二个 `.bin`，只显示有变化的 word。

## 4. 可选：直接传入文件名启动

普通使用不需要做这个。若将来习惯命令行，可以在命令提示符进入本目录后输入：

```text
py -3.13 34401A_NVRAM_Viewer.pyw "C:\你的路径\old.bin"
```

程序会直接打开这个 dump。

## 5. 可选：制作不依赖 Python 的 EXE

在已经安装 Python 的电脑上，双击：

```text
Build_Windows_EXE.bat
```

第一次会下载 PyInstaller。完成后，在 `dist` 文件夹生成：

```text
34401A_NVRAM_Viewer.exe
```

之后运行这个 EXE 不需要再从命令行启动 Python。
