# 多语种说明书校对 · Claude Code 最优工作流
#
# 在 Claude Code（Cowork）里，把要校对的 PDF 放进本目录，对 Claude 说：
#   「按 proofreader/WORKFLOW.md 校对 <文件名>.pdf，语言：英德法西意日」
# Claude 将严格按下面 8 步执行。这套设计把方案里的三道保证补齐：
#   · 确定性算术走 Python（L1，100% 准）  · AI 走语义（L2/L3）  · 独立子代理做审计（L5）

## 四条铁律（贯穿全程）
1. 只校产品内容　2. 禁止编造（每条必有逐字证据，拿不准标"待人工确认"）
3. OCR 不纠错（读不准的标注，不替改）　4. 截断不补全
> 不替代视觉终审。事实真伪 / 纯视觉乱码 / 语义型交叉引用，需人工 + 联网最终确认。

---

## 执行步骤（Claude 必须逐步做，不可跳步）

### 第 1 步 · 取文（L0）—— 按所用模型二选一
**A. 有视觉的模型（Claude 等）**：直接逐页阅读 PDF，输出忠实纯文本到 `work/extracted.txt`：
- 每页以 `=== P{页码} ===` 起头，尽量保留行结构；
- 读不准的字/符号就地标 `〔读不准:猜测〕`，不擅自纠正（铁律 3）；多语种分栏按"语言块"顺序抄录。

**B. 无视觉的模型（DeepSeek 等，必须先 OCR，否则全是乱码）**：先跑 OCR 脚本，再用产出的文本：
```bash
bash proofreader/ocr.sh 你的文件.pdf eng+deu+fra+spa+ita+jpn
```
产出 `work/extracted.md`（结构化，优先）和 `work/extracted.txt`。后续步骤一律基于该文本。
> 转曲 PDF 必须 `--force-ocr`（脚本已带）；缺哪种语言包哪种就乱码，脚本会提示补装。
> 用哪些语言由实际说明书决定（日文务必装 `tesseract-ocr-jpn`）。

### 第 2 步 · 确定性检查（L1，走代码=100% 可复现）
运行：`python3 proofreader/checks.py work/extracted.txt > work/det.json`
这覆盖：功率算术自洽、单位空格、风格禁用词。**这层结论是 ground truth，后续 AI 不得推翻。**

### 第 3 步 · AI 语义检查（L2，你来做）
在 `extracted.txt` 上找以下问题，写入 `work/ai.json`（数组，字段见末尾 schema）：
- **跨语言数字/型号不一致**（如英版 30W / 德版 33W）→ high
- **漏译 / 缺关键安全信息**（某语种少了别版有的警告/步骤）→ high
- **明显误译 / 意思偏移**（语义错，非风格）→ warn
- **疑似串版**（整段某语言里混入一行别的语言；西/意接近时标低置信）→ warn
铁律：**每条必须带 `quote`——在 extracted.txt 中逐字搜得到**；对不上就不要写。

### 第 4 步 · 联网事实核查（L3）
对可外部核实的断言（规格 / 认证编号 / 品牌技术声明，如"NVRAM 重置""支持某操作"）：
- **用 web 搜索核实**；**找到引用且矛盾** → high，`note` 里附来源 URL；
- **查无足够佐证** → warn「事实待核实」，**绝不无引用裸判真伪**。
追加进 `work/ai.json`。

### 第 5 步 · 合并
把 `det.json` 与 `ai.json` 的 issues 合并为 `work/merged.json`，结构：
```json
{"meta":{"filename":"原文件名.pdf","product":"产品名 · 说明书","pages":"68 页",
         "langs":"EN / ES / DE / FR / IT / JP","lang_count":6,"date":"2026-06-16",
         "sections":{"EN":{"range":"01–10","status":"术语统一 ✓"},
                     "ES":{"range":"11–20","status":"USB 术语正确 ✓"}}},
 "issues":[...], "stats":{"total":N,"high":H,"warn":W,"low":L}}
```
`meta.sections[语言]`：该语种 `range` 内页范围 + `status` 状态徽标（绿勾结论，如「术语统一 ✓」「含 FCC ✓」），
用于报告里每个语言节的标题徽标，没有就留空。
报告会**套用 VCD 校对报告模板**（横向 A4·红黑灰·按语言分节），所以每条 issue 务必带：
- `section`：归属语言版本 `EN|ES|DE|FR|IT|JP`，或跨语言/结构性问题填 `结构性`（会进顶部高优先表）；
- `loc`：位置，如 `p05 Note` / `目录页`（没有就用 `L行号`）。

### 第 6 步 · 独立审计（L5）★关键，不能省★
**用 Task 工具开一个全新子代理**（独立上下文 = 消除"自己审自己"的确认偏误），
把下面〔审计员指令〕+ `extracted.txt` + `merged.json` 原样交给它，**不要把你第 3 步的推理过程给它**。

> 〔审计员指令〕你是独立质量审计员，之前没参与本报告。给你原文与一份校对问题清单(JSON)。
> 只依据原文证据，产出 JSON：
> `{"reviews":[{"index":n,"verdict":"keep|likely_false_positive","reason":"..."}],`
> `"missed":[{"severity":"high|warn|low","kind":"...","lang":"...","quote":"原文逐字","reason":"..."}],`
> `"summary":"2~3句：整体全面性与准确性结论"}`
> 要求：① 逐条判其证据是否成立（quote 对得上吗？事实类有引用吗？站不住→标 likely_false_positive）；
> ② 补你能逐字引用证据的明显漏报（最多5条）；③ 给整体结论。不臆测、不放过、不护短。

### 第 7 步 · 采纳审计结果
- `likely_false_positive` 的条目：降级或剔除，并在 note 注明审计意见；
- `missed` 的条目：`quote` 能在原文搜到的才采纳，追加进清单；
- 把 `summary` 写入 `merged.json` 的 `audit_summary` 字段。

### 第 8 步 · 出报告并交付
运行：`python3 proofreader/report.py work/merged.json work/`
产出 `work/report.html`（自包含，可离线/转发）+ `work/report.docx`（正式交付）。
把两份发给用户，并口头汇报：高优先几条、审计标注的误报/补充各几条、整体结论。

---

## finding 字段 schema（L1/L2/L3 统一）
```json
{"code":"AI-XLANG","severity":"high|warn|low","section":"EN|ES|DE|FR|IT|JP|结构性",
 "kind":"简短类型(进报告“类型”列)","lang":"如 DE←EN 或 —","loc":"p05 Note 或 L行号",
 "line":行号或null,"text":"原文逐字片段(<=160，进“问题”列)",
 "note":"理由+建议(进“修改建议”列)；事实类附URL；高/中类注明 需人工确认","confidence":0.0}
```
严重度：`high` 高优先（进顶部结构性表）/ `warn` 疑似·待确认 / `low` 低优先。
报告列映射：# ← 序号 · 位置 ← `loc` · 问题 ← `text` · 类型 ← `kind` · 修改建议 ← `note`。
