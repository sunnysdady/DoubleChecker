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


def merge(base_result: dict, ai_issues: list) -> dict:
    """把 AI findings 合并进既有 result，重排 + 重算 stats。"""
    issues = list(ai_issues) + list(base_result.get("issues", []))
    issues.sort(key=lambda o: (ORDER.get(o.get("severity"), 9), o.get("code", "")))
    stats = {
        "total": len(issues),
        "high": sum(1 for i in issues if i["severity"] == "high"),
        "warn": sum(1 for i in issues if i["severity"] == "warn"),
        "low": sum(1 for i in issues if i["severity"] == "low"),
    }
    return {"issues": issues, "stats": stats}
