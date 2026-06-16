# Mac 全语言 OCR 预处理（校对工作流前置层）

把转曲/无文字层 PDF，在你 Mac 上用**六语种全质量 OCR** 转成可交叉核对的文本，
产物自动落到 Cowork 工作文件夹，校对会话直接读取。与 Cowork 沙盒英文兜底互补。

## 三个脚本

- `proofread_prep.sh` —— 引擎：单个 PDF → `<名>.ocr.pdf`（带文字层）+ `<名>.md`（结构化）。
- `proofread_watch.sh` —— 监听器：盯着「收件箱」文件夹，PDF 一落地就自动调用引擎。
- `setup_mac.command` —— 一次性设置：装语言包/监听工具 + 自检（**可双击运行**）。

## 一次性设置

双击 `setup_mac.command`（或在终端运行）。它会：
1. `brew install tesseract-lang fswatch`（全语言数据 + 文件夹监听）；
2. 给脚本加可执行权限；
3. 自检 ocrmypdf / opendataloader-pdf / java / 已装语言。

> 前提：`ocrmypdf`、`opendataloader-pdf`、`openjdk` 已装（本会话已完成）。
> 若 `opendataloader-pdf` 自检缺失：`pipx install opendataloader-pdf`。

## 用法 A · 单个文件（手动）

```
./proofread_prep.sh ~/Desktop/VCD20说明书.pdf ~/校对工作文件夹
```
产出 `VCD20说明书.ocr.pdf` 和 `VCD20说明书.md` 到 `~/校对工作文件夹`。

## 用法 B · 「发 PDF 即可」（自动监听）

开一个终端常驻运行：
```
./proofread_watch.sh ~/校对收件箱 ~/校对工作文件夹
```
之后**把任何 PDF 拖进 `~/校对收件箱`**，自动产出到 `~/校对工作文件夹`（即你连进 Cowork 的文件夹）。

### 可选 · 开机自动监听（launchd，彻底无人值守）
把下面存成 `~/Library/LaunchAgents/com.proofread.watch.plist`，改好两处路径后
`launchctl load ~/Library/LaunchAgents/com.proofread.watch.plist`：
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.proofread.watch</string>
  <key>ProgramArguments</key><array>
    <string>/绝对路径/mac_setup/proofread_watch.sh</string>
    <string>/Users/你/校对收件箱</string>
    <string>/Users/你/校对工作文件夹</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict></plist>
```

## 和 Cowork 怎么衔接

1. 把 `~/校对工作文件夹` 连进 Cowork 会话。
2. 粘贴接力包里的 `Claude_启动提示词.md`。
3. 智能体的「Step 0 预处理」会**优先读取 Mac 产出的 `<名>.md`**（六语种全质量）做交叉核对，
   并渲染 `<名>.ocr.pdf` 逐页图像做视觉终审；找不到 Mac 产出时才在沙盒跑英文兜底。

## 铁律不变

`.md` 仅作机械/交叉核对的**加速线索**（目录↔正文、表格标题↔接口数量、跨语言枚举、参数数值一致）。
OCR 疑似错字与截断按四条铁律标注、不猜补；最终文字以页面图像视觉识别为准。
