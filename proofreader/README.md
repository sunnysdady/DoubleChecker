# proofreader · Claude Code 最优校对工作流

在 **Claude Code（Cowork）** 里跑的多语种说明书校对包。把方案里的三道保证补齐：
**确定性算术走 Python（L1·100% 准）+ AI 走语义（L2/L3）+ 独立子代理做审计（L5）**。

## 用法（3 步）
1. 把要校对的 PDF 放进本目录（或仓库任意位置）。
2. 一次性装依赖（仅 Word 报告需要）：`pip install -r proofreader/requirements.txt`
3. 在 Claude Code 里说：
   > 按 `proofreader/WORKFLOW.md` 校对 `xxx.pdf`，语言：英德法西意日

Claude 会：读图提文 → 跑 `checks.py` 确定性检查 → AI 语义检查 → 联网事实核查 →
**开独立审计员子代理把关** → 生成 `work/report.html` + `work/report.docx` 交付。

## 文件
| 文件 | 作用 |
|---|---|
| `WORKFLOW.md` | 工作流指令（Claude 照此 8 步执行，含独立审计员 prompt） |
| `checks.py` | 确定性检查（功率算术 / 单位空格 / 禁用词）·纯 Python 零依赖·可独立跑 |
| `report.py` | 由 findings 生成自包含 HTML + Word(.docx) |
| `requirements.txt` | `python-docx`（仅 Word 报告需要；HTML 无依赖） |

## 单独跑确定性检查（不依赖 AI）
```bash
python3 proofreader/checks.py 文本文件.txt
```

## 为什么用 Claude Code 而不是普通 Project
普通 Project 不能跑代码、不能开独立子代理，会丢掉"确定性算术"和"独立审计"两道保证。
Claude Code 都能做到，所以这是逼近原方案全面/准确/审计三项的**最优路径**。
四条铁律不变：只校产品内容 / 禁止编造 / OCR 不纠错 / 截断不补全 —— 线索层，不替代视觉终审。
