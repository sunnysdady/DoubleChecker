# ai_checks.py — AI 语义层（L2）· 跨语言对齐检查器
# 设计原则（见 doc 方案）：
#   1. AI 只做「带证据的候选生成」，不做终判；
#   2. 每条结论强制带逐字原文 quote —— 在源文本里逐字核验，对不上即丢弃（防幻觉）；
#   3. 模型可配置：DeepSeek（OpenAI 兼容）/ Claude（Anthropic），env 一行切换；
#   4. 优雅降级：没配 API key 时 enabled()=False，整层跳过，保持现有零-API 行为。
#
# 配置（环境变量）：
#   AI_PROVIDER   deepseek | claude | openai   （默认 deepseek）
#   AI_API_KEY    密钥（缺省则本层关闭）
#   AI_MODEL      模型名（默认随 provider：deepseek-chat / claude-sonnet-4-6）
#   AI_BASE_URL   OpenAI 兼容端点（默认 https://api.deepseek.com）
#   AI_MAX_CHUNKS 最多送检的分片数（默认 12，控成本）
#   AI_CHUNK_CHARS 每片字符数（默认 6000）
import os, re, json, urllib.request, urllib.error

ORDER = {"high": 0, "warn": 1, "low": 2}


def _env(k, d=""):
    return os.environ.get(k, d).strip()


def enabled() -> bool:
    return bool(_env("AI_API_KEY"))


def _provider():
    return (_env("AI_PROVIDER", "deepseek") or "deepseek").lower()


def _model():
    m = _env("AI_MODEL")
    if m:
        return m
    return "claude-sonnet-4-6" if _provider() == "claude" else "deepseek-chat"


# ---------------------------------------------------------------- LLM 调用（provider 抽象）
def _http_post(url, headers, payload, timeout=120):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _call_llm(system: str, user: str, timeout=120) -> str:
    """返回模型纯文本输出。DeepSeek/OpenAI 走 chat/completions；Claude 走 messages。"""
    key = _env("AI_API_KEY")
    prov = _provider()
    model = _model()
    if prov == "claude":
        url = (_env("AI_BASE_URL") or "https://api.anthropic.com") + "/v1/messages"
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01",
                   "content-type": "application/json"}
        payload = {"model": model, "max_tokens": 4096, "temperature": 0,
                   "system": system,
                   "messages": [{"role": "user", "content": user}]}
        resp = _http_post(url, headers, payload, timeout)
        parts = resp.get("content", [])
        return "".join(p.get("text", "") for p in parts if p.get("type") == "text")
    # deepseek / openai 兼容
    base = _env("AI_BASE_URL") or ("https://api.deepseek.com" if prov == "deepseek"
                                   else "https://api.openai.com/v1")
    url = base.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"model": model, "temperature": 0,
               "response_format": {"type": "json_object"},
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user}]}
    resp = _http_post(url, headers, payload, timeout)
    return resp["choices"][0]["message"]["content"]


# ---------------------------------------------------------------- JSON 解析（防御式）
def _extract_json(s: str):
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s).strip()
    try:
        obj = json.loads(s)
    except Exception:
        # 退而求其次：截取第一个 { ... } 或 [ ... ]
        m = re.search(r"\{.*\}|\[.*\]", s, re.S)
        if not m:
            return []
        try:
            obj = json.loads(m.group(0))
        except Exception:
            return []
    if isinstance(obj, dict):
        obj = obj.get("findings") or obj.get("issues") or []
    return obj if isinstance(obj, list) else []


# ---------------------------------------------------------------- 跨语言对齐检查
SYSTEM = (
    "你是多语种产品说明书的资深校对审查员。说明书含 EN/DE/FR/ES/IT/JP 等多语版本，"
    "文本由 OCR 得到、可能有错字。你只做『带证据的候选生成』，绝不臆测、绝不编造。\n"
    "只报你能在原文中逐字引用证据的问题，聚焦三类跨语言对齐缺陷：\n"
    "1) 跨语种数字/型号/规格不一致（如英文版 30W、德文版 33W）；\n"
    "2) 某语种缺失了其它语种存在的安全警告/关键信息（漏译）；\n"
    "3) 明显的意思偏移/误译（不是风格差异，是语义错误）。\n"
    "不要报单位空格、客套词、纯风格问题（另有规则负责）。\n"
    "严格输出 JSON：{\"findings\":[{\"severity\":\"high|warn|low\","
    "\"kind\":\"简短中文类型\",\"lang\":\"如 DE←EN\",\"quote\":\"原文中逐字出现的关键片段(<=120字)\","
    "\"reason\":\"中文说明为何可疑 + 建议\",\"confidence\":0.0~1.0}]} 。"
    "quote 必须是原文里能逐字搜到的字符串。没有可靠证据就返回空 findings。"
)


def _chunks(text):
    n = int(_env("AI_CHUNK_CHARS", "6000") or 6000)
    overlap = 400
    maxc = int(_env("AI_MAX_CHUNKS", "12") or 12)
    out, i = [], 0
    while i < len(text) and len(out) < maxc:
        out.append(text[i:i + n])
        i += max(1, n - overlap)
    return out


def check_cross_language(text: str) -> list:
    findings = []
    for chunk in _chunks(text):
        try:
            raw = _call_llm(SYSTEM, "待审查文本：\n\n" + chunk)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
            continue
        except Exception:
            continue
        for f in _extract_json(raw):
            if not isinstance(f, dict):
                continue
            quote = (f.get("quote") or "").strip()
            # 证据接地：quote 必须在源文本里逐字出现，否则视为幻觉丢弃。
            # 阈值放到 2，避免误丢 9V/33W 这类高价值短证据。
            if len(quote) < 2 or quote not in text:
                continue
            sev = f.get("severity")
            if sev not in ORDER:
                sev = "warn"
            try:
                conf = float(f.get("confidence", 0.6))
            except (TypeError, ValueError):
                conf = 0.6
            findings.append({
                "code": "AI-XLANG", "severity": sev,
                "kind": (f.get("kind") or "跨语言对齐").strip()[:24],
                "lang": (f.get("lang") or "—").strip()[:16],
                "line": _line_of(text, quote),
                "text": quote[:160],
                "note": f"AI·{_model()}（置信 {conf:.2f}，需人工确认）：{(f.get('reason') or '').strip()[:240]}",
                "confidence": conf, "source": f"ai:{_provider()}",
            })
    return _dedup(findings)


def _line_of(text, quote):
    idx = text.find(quote)
    if idx < 0:
        return None
    return text.count("\n", 0, idx) + 1


def _dedup(items):
    seen, out = set(), []
    for it in items:
        k = (it["kind"], it["text"][:60])
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


# ---------------------------------------------------------------- 对外入口 / 合并
def run_ai(text: str) -> dict:
    """跑 AI 语义层，返回 {'issues': [...]}。任何异常都返回空，绝不拖垮主流程。"""
    try:
        return {"issues": check_cross_language(text)}
    except Exception:
        return {"issues": []}


def _stats(issues):
    return {
        "total": len(issues),
        "high": sum(1 for i in issues if i["severity"] == "high"),
        "warn": sum(1 for i in issues if i["severity"] == "warn"),
        "low": sum(1 for i in issues if i["severity"] == "low"),
    }


def merge(base_result: dict, ai_issues: list) -> dict:
    """把 AI findings 合并进既有 result，重排 + 重算 stats。"""
    issues = list(ai_issues) + list(base_result.get("issues", []))
    issues.sort(key=lambda o: (ORDER.get(o.get("severity"), 9), o.get("code", "")))
    out = {"issues": issues, "stats": _stats(issues)}
    if base_result.get("audit_summary"):
        out["audit_summary"] = base_result["audit_summary"]
    return out


# ================================================================ L3 · 联网事实核查
# 对「可外部核实的事实类断言」（规格/认证/安规/品牌技术声明）联网找证据：
#   有检索佐证且矛盾 → 事实存疑(高)；查无佐证 → 待人工核实(中)；未配搜索 key → 仅抽清单(中)。
# 绝不在无引用时裸判真伪。搜索后端可插拔：SEARCH_PROVIDER=tavily|serper + SEARCH_API_KEY。
def factcheck_enabled() -> bool:
    return enabled() and _env("AI_FACTCHECK", "1") != "0"


def search_enabled() -> bool:
    return bool(_env("SEARCH_API_KEY"))


def _web_search(query: str, k: int = 4) -> list:
    key = _env("SEARCH_API_KEY")
    prov = (_env("SEARCH_PROVIDER", "tavily") or "tavily").lower()
    try:
        if prov == "serper":
            resp = _http_post("https://google.serper.dev/search",
                              {"X-API-KEY": key, "Content-Type": "application/json"},
                              {"q": query, "num": k}, timeout=30)
            return [{"title": r.get("title", ""), "url": r.get("link", ""),
                     "content": r.get("snippet", "")} for r in resp.get("organic", [])[:k]]
        resp = _http_post("https://api.tavily.com/search",
                          {"Content-Type": "application/json"},
                          {"api_key": key, "query": query, "max_results": k,
                           "search_depth": "basic"}, timeout=30)
        return [{"title": r.get("title", ""), "url": r.get("url", ""),
                 "content": r.get("content", "")} for r in resp.get("results", [])[:k]]
    except Exception:
        return []


CLAIM_SYS = (
    "你从多语种产品说明书文本中，抽取『可用公开资料外部核实』的事实类断言，"
    "聚焦：产品规格/参数能力、安规/认证编号、行业标准、品牌技术声明（如某芯片是否支持某操作）。"
    "不要抽内部一致性问题（数字前后矛盾另有检查）。OCR 可能有错字，只抽你能逐字引用的。"
    "严格输出 JSON：{\"claims\":[{\"quote\":\"原文逐字片段\","
    "\"query\":\"用于网络检索的英文查询语句\",\"claim\":\"中文转述该断言\"}]} 。无可核实断言则空。"
)

JUDGE_SYS = (
    "你是事实核查员。给你若干断言及其网络检索结果。对每条断言判定："
    "supported(检索证据支持) / contradicted(检索证据相矛盾) / unverified(证据不足以判定)。"
    "只有给得出具体引用 URL 时才可判 supported/contradicted；拿不准一律 unverified。"
    "严格输出 JSON：{\"verdicts\":[{\"i\":序号,\"verdict\":\"...\",\"citation\":\"URL或空\","
    "\"reason\":\"中文简述\"}]} 。"
)


def _extract_claims(text: str) -> list:
    maxf = int(_env("AI_MAX_FACTS", "8") or 8)
    claims = []
    for chunk in _chunks(text):
        if len(claims) >= maxf:
            break
        try:
            raw = _call_llm(CLAIM_SYS, "文本：\n\n" + chunk)
        except Exception:
            continue
        for c in _extract_json(raw):
            if not isinstance(c, dict):
                continue
            q = (c.get("quote") or "").strip()
            if len(q) < 4 or q not in text:
                continue
            claims.append({"quote": q, "query": (c.get("query") or q).strip(),
                           "claim": (c.get("claim") or "").strip()})
            if len(claims) >= maxf:
                break
    # 去重
    seen, out = set(), []
    for c in claims:
        if c["quote"][:60] in seen:
            continue
        seen.add(c["quote"][:60])
        out.append(c)
    return out


def check_facts_online(text: str) -> list:
    claims = _extract_claims(text)
    if not claims:
        return []
    # 未配搜索后端：只把待核实清单抛给人工，不做真伪判断
    if not search_enabled():
        return [{
            "code": "AI-FACT", "severity": "warn", "kind": "事实待核实·未联网",
            "lang": "—", "line": _line_of(text, c["quote"]), "text": c["quote"][:160],
            "note": f"AI 抽出的可核实断言（未配 SEARCH_API_KEY，需人工联网核实）：{c['claim'][:200]}",
            "source": "ai:factcheck",
        } for c in claims]
    # 联网检索 + 一次性判定
    enriched = []
    for i, c in enumerate(claims):
        hits = _web_search(c["query"])
        enriched.append({"i": i, "claim": c["claim"] or c["quote"],
                         "results": [{"url": h["url"], "content": h["content"][:300]} for h in hits]})
    try:
        raw = _call_llm(JUDGE_SYS, "断言与检索结果：\n" + json.dumps(enriched, ensure_ascii=False))
        verdicts = {v.get("i"): v for v in _extract_json(raw) if isinstance(v, dict)}
    except Exception:
        verdicts = {}
    out = []
    for i, c in enumerate(claims):
        v = verdicts.get(i, {})
        verdict = v.get("verdict")
        cite = (v.get("citation") or "").strip()
        reason = (v.get("reason") or "").strip()[:200]
        if verdict == "supported":
            continue  # 有据支持，不报问题
        if verdict == "contradicted" and cite:
            out.append({"code": "AI-FACT", "severity": "high", "kind": "事实存疑·与公开资料不符",
                        "lang": "—", "line": _line_of(text, c["quote"]), "text": c["quote"][:160],
                        "note": f"AI 联网核查（需人工确认）：{reason}　引用：{cite}",
                        "source": "ai:factcheck"})
        else:  # unverified 或无引用
            out.append({"code": "AI-FACT", "severity": "warn", "kind": "事实待核实",
                        "lang": "—", "line": _line_of(text, c["quote"]), "text": c["quote"][:160],
                        "note": f"AI 联网未获足够佐证，需人工核实：{c['claim'][:160]}"
                                + (f"　参考：{cite}" if cite else ""),
                        "source": "ai:factcheck"})
    return _dedup(out)


# ================================================================ L5 · 审计员闸门
# 交付前由独立「审计员」对整份报告把关：① 精度——逐条判可能的误报；
# ② 召回——指出明显遗漏（须带逐字证据）；③ 给整体全面性/准确性结论。
# 审计员不静默删条目（保留人工终审），只标注「疑似误报」并追加「审计补充」候选。
def audit_enabled() -> bool:
    return enabled() and _env("AI_AUDIT", "1") != "0"


AUDIT_SYS = (
    "你是多语种说明书校对报告的质量审计员。给你（可能截断的）原文，与一份自动+AI 检查产出的问题清单(JSON，每条带 index)。"
    "请：1) 逐条判断是否疑似误报(likely_false_positive)还是应保留(keep)，给理由；"
    "2) 指出清单明显遗漏、但你能在原文逐字引用证据的高把握问题(最多5条)；"
    "3) 用2~3句中文给出整体全面性与准确性结论。"
    "只基于原文证据，不臆测。严格输出 JSON：{\"reviews\":[{\"index\":n,\"verdict\":\"keep|likely_false_positive\",\"reason\":\"...\"}],"
    "\"missed\":[{\"severity\":\"high|warn|low\",\"kind\":\"...\",\"lang\":\"...\",\"quote\":\"原文逐字\",\"reason\":\"...\"}],"
    "\"summary\":\"整体结论\"}"
)


def audit(text: str, result: dict) -> dict:
    issues = list(result.get("issues", []))
    if not issues:
        return result
    budget = int(_env("AI_AUDIT_CHARS", "12000") or 12000)
    compact = [{"index": i, "code": it.get("code"), "severity": it.get("severity"),
                "kind": it.get("kind"), "lang": it.get("lang"), "text": it.get("text")}
               for i, it in enumerate(issues)]
    user = ("原文(可能截断)：\n" + text[:budget]
            + "\n\n问题清单：\n" + json.dumps(compact, ensure_ascii=False))
    try:
        raw = _call_llm(AUDIT_SYS, user, timeout=180)
        data = _extract_json(raw)
        data = data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else data
        if not isinstance(data, dict):
            data = {}
    except Exception:
        return result
    # ① 标注疑似误报
    for r in (data.get("reviews") or []):
        if not isinstance(r, dict):
            continue
        idx = r.get("index")
        if r.get("verdict") == "likely_false_positive" and isinstance(idx, int) and 0 <= idx < len(issues):
            issues[idx]["audit_flag"] = "fp"
            issues[idx]["note"] = (issues[idx].get("note", "") +
                                   f"　〔审计·疑似误报：{(r.get('reason') or '')[:140]}〕")
    # ② 追加审计补充（逐字证据接地）
    added = []
    for m in (data.get("missed") or []):
        if not isinstance(m, dict):
            continue
        q = (m.get("quote") or "").strip()
        if len(q) < 2 or q not in text:
            continue
        sev = m.get("severity") if m.get("severity") in ORDER else "warn"
        added.append({"code": "AI-AUDIT", "severity": sev,
                      "kind": (m.get("kind") or "审计补充").strip()[:24],
                      "lang": (m.get("lang") or "—").strip()[:16],
                      "line": _line_of(text, q), "text": q[:160],
                      "note": f"审计员补充（需人工确认）：{(m.get('reason') or '')[:200]}",
                      "source": "ai:audit"})
    issues = added + issues
    issues.sort(key=lambda o: (ORDER.get(o.get("severity"), 9), o.get("code", "")))
    out = {"issues": issues, "stats": _stats(issues)}
    summary = (data.get("summary") or "").strip()
    fp = sum(1 for it in issues if it.get("audit_flag") == "fp")
    out["audit_summary"] = (summary + (f"（审计标注疑似误报 {fp} 条、补充 {len(added)} 条）" if (fp or added) else "")) \
        if summary else (f"审计完成：标注疑似误报 {fp} 条、补充 {len(added)} 条。" if (fp or added) else "")
    return out


# ================================================================ 总编排
def run_pipeline(text: str, base_result: dict, progress=None) -> dict:
    """L2 跨语言对齐 → L3 联网事实核查 → 合并 → L5 审计员把关。失败逐层降级，绝不拖垮主流程。"""
    if not enabled():
        return base_result

    def _p(m):
        if progress:
            try:
                progress(m)
            except Exception:
                pass

    ai_issues = []
    try:
        _p("AI 跨语言对齐校验…")
        ai_issues += check_cross_language(text)
    except Exception:
        pass
    if factcheck_enabled():
        try:
            _p("AI 联网事实核查…")
            ai_issues += check_facts_online(text)
        except Exception:
            pass
    result = merge(base_result, ai_issues)
    if audit_enabled():
        try:
            _p("AI 审计员把关全面性与准确性…")
            result = audit(text, result)
        except Exception:
            pass
    return result
