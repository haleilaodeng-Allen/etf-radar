"""ETF Radar 数据更新：单只详情 + 横向候选池。

候选池目前只展示“趋势事实”，不把不同赛道做成单一买入排名。
产品规模、成交额、折溢价、跟踪误差将在下一层加入后才启用产品质量门槛。
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


def etf_closes(symbol: str) -> tuple[list[str], list[float]]:
    df = ak.fund_etf_hist_em(symbol=symbol, period="daily", start_date="20250101", end_date="20301231", adjust="qfq")
    if df is None or len(df) < 65:
        raise ValueError(f"{symbol}日线不足")
    return [str(x)[:10] for x in df["日期"].tolist()], [float(x) for x in df["收盘"].tolist()]


def pct_change(values: list[float], periods: int = 5) -> float:
    return (values[-1] / values[-1 - periods] - 1) * 100


def trend_fact(price: float, ma20: float, ma60: float) -> str:
    if price > ma20 and price > ma60:
        return "价格在20日、60日线上方"
    if price < ma20 and price < ma60:
        return "价格低于20日、60日线"
    return "价格位于20日、60日线之间"


def build_candidate_item(code: str) -> dict:
    dates, closes = etf_closes(code)
    price, ma20, ma60 = closes[-1], statistics.mean(closes[-20:]), statistics.mean(closes[-60:])
    return {
        "code": code,
        "price": f"{price:.3f}",
        "ma20": f"{ma20:.3f}",
        "ma60": f"{ma60:.3f}",
        "trend": trend_fact(price, ma20, ma60),
        "environment": "待按该ETF专属影响链接入",
        "research": "可打开详情页研究" if price > ma20 else "先观察趋势是否修复",
        "date": dates[-1]
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
    payload = {
        "as_of": f"候选池价格数据：{as_of}",
        "method": "当前只完成趋势层：价格、20日线、60日线。产品质量与外部环境尚未接入，不据此选择或买入。",
        "items": items,
        "failures": failures
    }
    CANDIDATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return items, failures


def update_159822_detail() -> None:
    old = json.loads(STATUS_FILE.read_text(encoding="utf-8"))[0]
    try:
        dates, closes = etf_closes("159822")
        _, hstech = etf_closes("513180")
    except Exception as error:
        old.update({"as_of":"ETF价格更新失败：保留上一份状态","alert_level":"价格数据不可用","action_title":"不输出交易判断","action":f"ETF日线未能更新。原因：{error}","negative_signals":[f"价格数据保护触发：{error}"],"positive_signals":["已有有效数据不会被空值覆盖。"]})
        STATUS_FILE.write_text(json.dumps([old], ensure_ascii=False, indent=2), encoding="utf-8")
        return

    price, ma20, ma60 = closes[-1], statistics.mean(closes[-20:]), statistics.mean(closes[-60:])
    weak, strong = [], []
    if price < ma20: weak.append("场内价格低于20日线。")
    else: strong.append("场内价格仍在20日线上方。")
    if price < ma60: weak.append("场内价格低于60日线。")
    else: strong.append("场内价格仍在60日线上方。")
    hstech_5d = pct_change(hstech)
    (strong if hstech_5d >= 0 else weak).append(f"恒生科技ETF代理近5日 {hstech_5d:+.1f}% 。")
    macro_note = "宏观数据未更新，不纳入本页事实。"
    try:
        yield_change = (fred_series("DGS10")[-1] - fred_series("DGS10")[-6]) * 100
        dollar_change = pct_change(fred_series("DTWEXBGS"))
        macro_note = f"宏观：美债5日 {yield_change:+.0f}bp；广义美元5日 {dollar_change:+.1f}%。"
    except Exception:
        pass
    status = {
        "code":"159822","as_of":f"数据更新：场内价格 {dates[-1]}","price":f"{price:.3f}","ma20":f"{ma20:.3f}","ma60":f"{ma60:.3f}","relative_strength":f"恒科代理5日 {hstech_5d:+.1f}%","alert_level":"证据面板","action_title":"先看事实，再自己判断","action":macro_note,"logic_chain":["美债/美元变化","成长股估值压力","恒生科技强弱","ETF场内趋势","新经济ETF环境"],"negative_signals":weak or ["当前无趋势偏弱事实。"],"positive_signals":strong or ["当前无趋势偏强事实。"]}
    STATUS_FILE.write_text(json.dumps([status], ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    items, failures = update_candidate_pool()
    update_159822_detail()
    print(f"Candidate pool updated: {len(items)} items; failed: {len(failures)}")


if __name__ == "__main__":
    main()
