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

### 第 1 步 · 读图提文（L0）
逐页阅读 PDF，输出忠实的纯文本到 `work/extracted.txt`，要求：
- **每页以 `=== P{页码} ===` 起头**，尽量保留行结构；
- 读不准的字/符号就地标 `〔读不准:你的猜测〕`，**不要擅自纠正**（铁律 3）；
- 多语种分栏的，按"语言块"顺序抄录。

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
`{"meta":{...}, "issues":[...], "stats":{...}}`（meta 含 filename/product/langs/date）。

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
{"code":"AI-XLANG","severity":"high|warn|low","kind":"简短类型",
 "lang":"如 DE←EN 或 —","line":行号或null,"text":"原文逐字片段(<=160)",
 "note":"理由+建议；事实类附URL；高/中类注明 需人工确认","confidence":0.0}
```
严重度：`high` 高优先 / `warn` 疑似·待确认 / `low` 低优先。
