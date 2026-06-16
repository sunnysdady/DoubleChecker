# DoubleChecker

转曲 / 无文字层 PDF 的**多语种校对预处理工具**。把扫描/转曲的多语言说明书 PDF，
转成「可搜索 PDF + 结构化文本 + 自动校对报告(Word/Markdown)」，作为人工校对的**线索层**。

全本地、开源、**零 API / 零 key**：OCRmyPDF(Tesseract) + opendataloader-pdf(Java) + langdetect，
处理全在自己服务器/电脑上离线完成。

## 能做什么

- **多语种 OCR 加文字层**（EN/DE/FR/ES/IT/JP…），输出可搜索 PDF。
- **结构化抽取**：opendataloader 按阅读顺序抽出 Markdown，便于交叉核对。
- **自动校对检查**（机械"线索层"）：
  - 功率算术自洽（如 `9V×3A≠30W`）；
  - 事实触发（NVRAM 等需联网核实项）；
  - 跨语言**串版**疑似检测（高召回，需人工确认；ES/IT 易混对降置信）；
  - 单位空格、风格禁用词。
- **Word 校对报告**：套用既有报告排版（深红标题、蓝底表头、5 列问题表、分档小节）。

## 不做什么（边界）

不替代视觉终审。遵循四条铁律：只校产品内容 / 禁止编造 / OCR 不纠错 / 截断不补全。
OCR 会错字，数值/枚举类仅作定位；语义型交叉引用（标题↔机型）、纯视觉乱码、事实真伪判断需人工 + 联网。

## 目录结构

```
server/      FastAPI Web 服务（上传 PDF → 处理 → 网页下载 + 问题清单）
  app.py            服务与任务轮询
  checks.py         自动校对检查
  report_docx.py    Word 报告生成
  static/index.html 前端（拖拽上传 + 进度 + 结果）
  setup_server.sh   一次性装依赖（Ubuntu）
  run.sh            启动
  setup_domain.sh   绑域名（systemd + Nginx + HTTPS 指引）
  ocr-proofread.service  systemd 单元
mac_setup/   Mac 本地命令行版（全语种 OCR，可拖拽/监听文件夹）
```

## 快速开始（Ubuntu 服务器）

```bash
cd server
bash setup_server.sh          # 装 Tesseract 多语种 + Ghostscript + Java + Python 依赖
bash run.sh                   # http://<IP>:8000
# 绑域名 + 常驻 + 大文件上传：
sudo bash setup_domain.sh dc.example.com
```

## Mac 本地版

```bash
cd mac_setup
bash setup_mac.command        # 装全语种数据 + fswatch
./proofread_prep.sh 文件.pdf ~/输出目录
```

详见 `server/README_Server.md` 与 `mac_setup/README_Mac.md`。
