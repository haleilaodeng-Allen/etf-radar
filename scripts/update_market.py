"""ETF Radar 数据更新：单只详情 + 横向候选池。

价格数据优先使用 AKShare 的新浪历史接口；东方财富接口仅作回退。
候选池当前只展示趋势事实，不输出买卖结论。
"""
from __future__ import annotations

import csv
import io
import json
import statistics
from pathlib import Path
from urllib.request import Request, urlopen

import akshare as ak

ROOT = Path(__file__).resolve().parents[1]
STATUS_FILE = ROOT / "data" / "etf_status.json"
UNIVERSE_FILE = ROOT / "data" / "candidate_universe.json"
CANDIDATE_FILE = ROOT / "data" / "candidate_status.json"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def get_text(url: str) -> str:
    request = Request(url, headers=HEADERS)
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def fred_series(series: str) -> list[float]:
    rows = csv.DictReader(io.StringIO(get_text(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}")))
    values = [float(r[series]) for r in rows if r.get(series) not in (None, "", ".")]
    if len(values) < 10:
        raise ValueError(f"FRED {series} 数据不足")
    return values


def etf_closes(symbol: str) -> tuple[list[str], list[float], str]:
    """优先新浪ETF日线，失败后才回退东方财富。"""
    errors = []
    for exchange in ("sh", "sz"):
        try:
            df = ak.fund_etf_hist_sina(symbol=f"{exchange}{symbol}")
            if df is not None and len(df) >= 65:
                date_col = next(col for col in df.columns if str(col) in ("date", "日期"))
                close_col = next(col for col in df.columns if str(col).lower() in ("close", "收盘"))
                dates = [str(x)[:10] for x in df[date_col].tolist()]
                closes = [float(x) for x in df[close_col].tolist()]
                return dates, closes, "新浪历史日线"
        except Exception as error:
            errors.append(f"新浪{exchange}：{error}")
    try:
        df = ak.fund_etf_hist_em(symbol=symbol, period="daily", start_date="20250101", end_date="20301231", adjust="qfq")
        if df is not None and len(df) >= 65:
            return [str(x)[:10] for x in df["日期"].tolist()], [float(x) for x in df["收盘"].tolist()], "东方财富历史日线"
    except Exception as error:
        errors.append(f"东方财富：{error}")
    raise ValueError(f"{symbol}日线不可用；" + " | ".join(errors))


def pct_change(values: list[float], periods: int = 5) -> float:
    return (values[-1] / values[-1 - periods] - 1) * 100


def trend_fact(price: float, ma20: float, ma60: float) -> str:
    if price > ma20 and price > ma60:
        return "价格在20日、60日线上方"
    if price < ma20 and price < ma60:
        return "价格低于20日、60日线"
    return "价格位于20日、60日线之间"


def build_candidate_item(code: str) -> dict:
    dates, closes, source = etf_closes(code)
    price, ma20, ma60 = closes[-1], statistics.mean(closes[-20:]), statistics.mean(closes[-60:])
    return {
        "code": code,
        "price": f"{price:.3f}",
        "ma20": f"{ma20:.3f}",
        "ma60": f"{ma60:.3f}",
        "trend": trend_fact(price, ma20, ma60),
        "environment": "待按该ETF专属影响链接入",
        "research": "可打开详情页研究" if price > ma20 else "先观察趋势是否修复",
        "date": dates[-1],
        "source": source
    }


def update_candidate_pool() -> tuple[list[dict], list[str]]:
    universe = json.loads(UNIVERSE_FILE.read_text(encoding="utf-8"))
    items, failures = [], []
    for record in universe:
        try:
            items.append(build_candidate_item(record["code"]))
        except Exception as error:
            failures.append(f"{record['code']}：{error}")
    as_of = max((item["date"] for item in items), default="未更新")
    CANDIDATE_FILE.write_text(json.dumps({
        "as_of": f"候选池价格数据：{as_of}",
        "method": "当前只完成趋势层：价格、20日线、60日线。产品质量与外部环境尚未接入，不据此选择或买入。",
        "items": items,
        "failures": failures
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return items, failures


def update_159822_detail() -> None:
    old = json.loads(STATUS_FILE.read_text(encoding="utf-8"))[0]
    try:
        dates, closes, source = etf_closes("159822")
        _, hstech, hstech_source = etf_closes("513180")
    except Exception as error:
        old.update({"as_of":"ETF价格更新失败：保留上一份状态","alert_level":"价格数据不可用","action_title":"不输出交易判断","action":f"ETF日线未能更新。原因：{error}","negative_signals":[f"价格数据保护触发：{error}"],"positive_signals":["已有有效数据不会被空值覆盖。"]})
        STATUS_FILE.write_text(json.dumps([old], ensure_ascii=False, indent=2), encoding="utf-8")
        return
    price, ma20, ma60 = closes[-1], statistics.mean(closes[-20:]), statistics.mean(closes[-60:])
    weak, strong = [], []
    (weak if price < ma20 else strong).append("场内价格低于20日线。" if price < ma20 else "场内价格仍在20日线上方。")
    (weak if price < ma60 else strong).append("场内价格低于60日线。" if price < ma60 else "场内价格仍在60日线上方。")
    hstech_5d = pct_change(hstech)
    (strong if hstech_5d >= 0 else weak).append(f"恒生科技ETF代理近5日 {hstech_5d:+.1f}% 。")
    macro_note = "宏观数据未更新，不纳入本页事实。"
    try:
        yield_values, dollar_values = fred_series("DGS10"), fred_series("DTWEXBGS")
        macro_note = f"宏观：美债5日 {(yield_values[-1] - yield_values[-6]) * 100:+.0f}bp；广义美元5日 {pct_change(dollar_values):+.1f}%。"
    except Exception:
        pass
    STATUS_FILE.write_text(json.dumps([{
        "code":"159822","as_of":f"数据更新：场内价格 {dates[-1]} · 来源：{source}","price":f"{price:.3f}","ma20":f"{ma20:.3f}","ma60":f"{ma60:.3f}","relative_strength":f"恒科代理5日 {hstech_5d:+.1f}%","alert_level":"证据面板","action_title":"先看事实，再自己判断","action":macro_note,"logic_chain":["美债/美元变化","成长股估值压力","恒生科技强弱","ETF场内趋势","新经济ETF环境"],"negative_signals":weak or ["当前无趋势偏弱事实。"],"positive_signals":strong or ["当前无趋势偏强事实。"]
    }], ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    items, failures = update_candidate_pool()
    update_159822_detail()
    print(f"Candidate pool updated: {len(items)} items; failed: {len(failures)}")


if __name__ == "__main__":
    main()
