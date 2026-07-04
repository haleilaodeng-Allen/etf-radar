"""ETF Radar 数据更新。

价格数据通过 AKShare 统一适配；宏观数据通过 FRED CSV。
价格更新与宏观更新分开：宏观暂时不可用时，仍保留ETF价格和均线，不再整页清空。
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
        raise ValueError(f"AKShare未返回足够的{symbol}日线")
    date_col = "日期"
    close_col = "收盘"
    dates = [str(x)[:10] for x in df[date_col].tolist()]
    closes = [float(x) for x in df[close_col].tolist()]
    return dates, closes


def pct_change(values: list[float], periods: int = 5) -> float:
    return (values[-1] / values[-1 - periods] - 1) * 100


def previous() -> dict:
    return json.loads(STATUS_FILE.read_text(encoding="utf-8"))[0]


def main() -> None:
    old = previous()
    try:
        dates, closes = etf_closes("159822")
        _, hstech = etf_closes("513180")
    except Exception as error:
        old.update({
            "as_of": "ETF价格更新失败：保留上一份状态",
            "alert_level": "价格数据不可用",
            "action_title": "不输出交易判断",
            "action": f"ETF日线未能更新，暂停判断。原因：{error}",
            "negative_signals": [f"价格数据保护触发：{error}"],
            "positive_signals": ["已有有效数据不会被空值覆盖。"]
        })
        STATUS_FILE.write_text(json.dumps([old], ensure_ascii=False, indent=2), encoding="utf-8")
        print(old["action"])
        return

    price, ma20, ma60 = closes[-1], statistics.mean(closes[-20:]), statistics.mean(closes[-60:])
    negatives, positives, risk = [], [], 0
    if price < ma20:
        negatives.append("场内价格低于20日线，短线趋势偏弱。")
        risk += 1
    else:
        positives.append("场内价格仍在20日线上方。")
    if price < ma60:
        negatives.append("场内价格低于60日线，中期趋势需要重新观察。")
        risk += 1
    else:
        positives.append("场内价格仍在60日线上方。")
    hstech_5d = pct_change(hstech)
    if hstech_5d < 0:
        negatives.append(f"恒生科技ETF代理近5日 {hstech_5d:.1f}% ，外部科技环境偏弱。")
        risk += 1
    else:
        positives.append(f"恒生科技ETF代理近5日 {hstech_5d:.1f}% ，提供外部支持。")

    macro_notes = []
    try:
        dgs10 = fred_series("DGS10")
        dollar = fred_series("DTWEXBGS")
        yield_bp = (dgs10[-1] - dgs10[-6]) * 100
        dollar_5d = pct_change(dollar)
        if yield_bp > 5:
            negatives.append(f"美国10年期收益率近5日上行 {yield_bp:.0f}bp，成长估值压力增加。")
            risk += 1
        elif yield_bp < -5:
            positives.append(f"美国10年期收益率近5日下行 {abs(yield_bp):.0f}bp，成长估值压力缓和。")
        if dollar_5d > 0.3:
            negatives.append(f"广义美元指数近5日上涨 {dollar_5d:.1f}% ，外部流动性压力增加。")
            risk += 1
        elif dollar_5d < -0.3:
            positives.append(f"广义美元指数近5日下跌 {abs(dollar_5d):.1f}% ，外部压力缓和。")
    except Exception as error:
        macro_notes.append(f"宏观数据暂未更新：{error}")

    if risk >= 4:
        level, title, action = "橙色预警", "多项领先变量转坏，先控制风险", "停止加仓；已有仓位重点看60日线和外部环境。"
    elif risk >= 2:
        level, title, action = "黄色预警", "上涨条件开始松动，先保护判断空间", "不追跌、不加仓；观察20日线与恒生科技能否改善。"
    else:
        level, title, action = "环境正常", "当前未出现集中转弱", "不代表可以买入；仍需结合位置、回踩和仓位管理判断。"
    if macro_notes:
        action += " 宏观部分暂未更新，因此预警仅基于ETF趋势与恒生科技代理。"
        positives.extend(macro_notes)

    status = {
        "code": "159822",
        "as_of": f"数据更新：场内价格 {dates[-1]}",
        "price": f"{price:.3f}",
        "ma20": f"{ma20:.3f}",
        "ma60": f"{ma60:.3f}",
        "relative_strength": f"恒科代理5日 {hstech_5d:+.1f}%",
        "alert_level": level,
        "action_title": title,
        "action": action,
        "logic_chain": ["美债/美元变化", "成长股估值压力", "恒生科技强弱", "ETF场内趋势", "新经济ETF环境"],
        "negative_signals": negatives or ["暂未发现本规则定义的集中转弱信号。"],
        "positive_signals": positives or ["暂未发现本规则定义的明显支持信号。"]
    }
    STATUS_FILE.write_text(json.dumps([status], ensure_ascii=False, indent=2), encoding="utf-8")
    print("ETF price data updated successfully.")


if __name__ == "__main__":
    main()
