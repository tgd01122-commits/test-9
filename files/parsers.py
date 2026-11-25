import io
import re

import pandas as pd


STATEMENTS = {
    "재무상태표": dict(keys=["재무상태표"], sig=["자산총계"]),
    "손익계산서": dict(keys=["손익계산서"], sig=["영업이익", "당기순이익", "매출액"]),
    "현금흐름표": dict(keys=["현금흐름표"], sig=["영업활동"]),
    "자본변동표": dict(keys=["자본변동표"], sig=["기초"]),
}


ACCOUNTS = {
    "자산총계":   (["자산총계"], "재무상태표"),
    "부채총계":   (["부채총계"], "재무상태표"),
    "자본총계":   (["자본총계"], "재무상태표"),
    "유동자산":   (["유동자산"], "재무상태표"),
    "유동부채":   (["유동부채"], "재무상태표"),
    "매출액":     (["매출액", "영업수익", "수익(매출액)", "수익"], "손익계산서"),
    "영업이익":   (["영업이익(손실)", "영업이익", "영업손익", "영업손실"], "손익계산서"),
    "당기순이익": (["당기순이익(손실)", "당기순이익", "연결당기순이익", "분기순이익", "반기순이익", "당기순손익", "당기순손실", "분기순손실", "반기순손실"], "손익계산서"),
}

LOSS_ALIASES = {"영업손실", "당기순손실", "분기순손실", "반기순손실"}

_PREFIX = r"^\s*(?:[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩIVX\d]{1,4}[\.\)]\s*)?"
_NUM = re.compile(r"[\(△▲-]?\d[\d,\.]*\)?")


def to_num(x):
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return None if pd.isna(x) else float(x)
    s = str(x).strip().replace(",", "").replace(" ", "")
    if not s:
        return None
    neg = s.startswith("(") or s.startswith("△") or s.startswith("▲") or s.startswith("-")
    s = s.strip("()△▲-")
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def _label_regex(alias):
    body = r"\s*".join(re.escape(c) for c in alias)
    return re.compile(_PREFIX + body + r"(?![가-힣])")


def _apply_loss(alias, v):
    if alias in LOSS_ALIASES:
        return -abs(v)
    return v


def _pick_number(tokens, col=0):
    vals = []
    for t in tokens:
        digits = re.sub(r"\D", "", t)
        if "," in t or len(digits) >= 4:
            v = to_num(t)
            if v is not None:
                vals.append(v)
    if not vals:
        return None
    return vals[col] if len(vals) > col else vals[0]


def parse_excel(file_bytes):
    return pd.read_excel(io.BytesIO(file_bytes), sheet_name=None, header=None)


def sheet_title(name, df=None):
    if df is not None:
        try:
            t = str(df.iloc[1, 0])
            if t.startswith("["):
                return t
        except Exception:
            pass
    return str(name)


def classify_sheet(name, df=None):
    t = sheet_title(name, df).replace(" ", "")
    for key, cfg in STATEMENTS.items():
        if any(k in t for k in cfg["keys"]):
            return key
    return None


def sheet_label(name, df=None):
    t = re.sub(r"^\[[^\]]*\]\s*", "", sheet_title(name, df))
    kind = classify_sheet(name, df)
    if not kind:
        return str(name)
    base = "포괄손익계산서" if kind == "손익계산서" and "포괄" in t else kind
    scope = "연결" if "연결" in t else "별도" if "별도" in t else ""
    return f"{base} ({scope})" if scope else base


def sort_sheets(sheets):
    order = list(STATEMENTS.keys())

    def k(n):
        c = classify_sheet(n, sheets[n])
        t = sheet_title(n, sheets[n])
        return (order.index(c) if c else 99, 0 if "연결" in t else 1)

    return sorted(sheets.keys(), key=k)


def format_df(df):
    def f(x):
        if isinstance(x, bool):
            return str(x)
        if isinstance(x, (int, float)):
            if pd.isna(x):
                return ""
            return f"{int(x):,}" if float(x).is_integer() else f"{x:,.2f}"
        if x is None or (not isinstance(x, str) and pd.isna(x)):
            return ""
        return str(x)

    out = df.astype(object).apply(lambda col: col.map(f))
    out.columns = [" " * (i + 1) for i in range(out.shape[1])]
    return out


def _value_from_sheet(df, aliases):
    for alias in aliases:
        reg = _label_regex(alias)
        for _, row in df.iterrows():
            cells = list(row.values)
            for i, c in enumerate(cells[:3]):
                if isinstance(c, str) and reg.search(c):
                    nums = [to_num(x) for x in cells[i + 1:]]
                    nums = [n for n in nums if n is not None]
                    big = [n for n in nums if abs(n) >= 1000]
                    if big:
                        return _apply_loss(alias, big[0])
                    if nums:
                        return _apply_loss(alias, nums[0])
    return None


def extract_from_excel(sheets):
    out = {}
    names = sort_sheets(sheets)
    for acct, (aliases, stmt) in ACCOUNTS.items():
        same = [n for n in names if classify_sheet(n, sheets[n]) == stmt]
        targets = same + [n for n in names if n not in same]
        for n in targets:
            v = _value_from_sheet(sheets[n], aliases)
            if v is not None:
                out[acct] = v
                break
    return _fill_derived(out)


def parse_pdf(file_bytes):
    import pdfplumber

    pages, found = [], {k: [] for k in STATEMENTS}
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for p in pdf.pages:
            pages.append(p.extract_text() or "")
        for idx, text in enumerate(pages):
            flat = text.replace(" ", "")
            for name, cfg in STATEMENTS.items():
                if len(found[name]) >= 2:
                    continue
                if any(k in flat for k in cfg["keys"]) and any(s in flat for s in cfg["sig"]):
                    found[name].append(idx)
        statements = {}
        for name, idxs in found.items():
            items = []
            for i in idxs:
                dfs = []
                try:
                    for t in pdf.pages[i].extract_tables():
                        if t and len(t) > 1:
                            dfs.append(pd.DataFrame(t).fillna("").astype(str))
                except Exception:
                    pass
                items.append(dict(page=i + 1, text=pages[i], tables=dfs))
            if items:
                statements[name] = items
    return dict(pages=pages, statements=statements)


def _is_cumulative(text):
    flat = text.replace(" ", "")
    return "3개월" in flat and "누적" in flat


def _value_from_text(text, aliases, col=0):
    for alias in aliases:
        reg = _label_regex(alias)
        for line in text.splitlines():
            m = reg.search(line)
            if m:
                rest = re.sub(r"\(주[^)]*\)", "", line[m.end():])
                v = _pick_number(_NUM.findall(rest), col)
                if v is not None:
                    return _apply_loss(alias, v)
    return None


def _statement_text(parsed, stmt):
    pages = parsed["pages"]
    texts = []
    for item in parsed["statements"].get(stmt, []):
        texts.append(item["text"])
        nxt = item["page"]
        if nxt < len(pages):
            flat = pages[nxt].replace(" ", "")
            has_title = any(k in flat for cfg in STATEMENTS.values() for k in cfg["keys"])
            if not has_title:
                texts.append(pages[nxt])
    return "\n".join(texts)


def extract_from_pdf(parsed):
    out = {}
    income_col = 1 if _is_cumulative(_statement_text(parsed, "손익계산서")) else 0
    for acct, (aliases, stmt) in ACCOUNTS.items():
        col = income_col if stmt == "손익계산서" else 0
        stmt_text = _statement_text(parsed, stmt)
        v = _value_from_text(stmt_text, aliases, col) if stmt_text else None
        if v is None:
            v = _value_from_text("\n".join(parsed["pages"]), aliases, col)
        if v is not None:
            out[acct] = v
    return _fill_derived(out)


def _fill_derived(v):
    if "부채총계" not in v and "자산총계" in v and "자본총계" in v:
        v["부채총계"] = v["자산총계"] - v["자본총계"]
    return v
