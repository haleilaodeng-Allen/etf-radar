"""更新 159822 的第一批市场信号。

数据源：
- 东方财富：159822 日线
- Yahoo Finance 图表接口：恒生科技、美元指数历史日线
- FRED：美国 10 年期国债收益率 DGS10

原则：四项关键数据任一缺失，就只写“数据不完整”，不产生交易预警。
"""
from __future__ import annotations

import csv
import io
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
STATUS_FILE = ROOT / "data" / "etf_status.json"
HEADERS = {"User-Agent": "Mozilla/5.0 ETF-Radar/1.0"}


def get_json(url: str) -> dict:
    request = Request(url, headers=HEADERS)
    with urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def get_text(url: str) -> str:
    request = Request(url, headers=HEADERS)
    with urlopen(request, timeout=25) as response:
        return response.read().decode("utf-8")


def eastmoney_etf_closes() -> list[tuple[str, float]]:
    url = (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get?"
        "secid=0.159822&klt=101&fqt=1&lmt=140&"
        "fields1=f1,f2,f3,f4,f5,f6&"
        "fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
    )
    rows = get_json(url)["data"]["klines"]
    return [(row.split(",")[0], float(row.split(",")[2])) for row in rows if row.split(",")[2] != "-"]


def yahoo_closes(symbol: str) -> list[tuple[str, float]]:
    now = int(time.time())
    start = now - 180 * 86400
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={start}&period2={now}&interval=1d"
    result = get_json(url)["chart"]["result"][0]
    closes = result["indicators"]["quote"][0]["close"]
    timestamps = result["timestamp"]
    data = []
    for stamp, close in zip(timestamps, closes):
        if close is not None:
            day = datetime.fromtimestamp(stamp, tz=timezone.utc).date().isoformat()
            data.append((day, float(close)))
    return data


def fred_dgs10() -> list[tuple[str, float]]:
    text = get_text("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10")
    rows = csv.DictReader(io.StringIO(text))
    data = []
    for row in rows:
        value = row.get("DGS10", "")
        if value and value != ".":
            data.append((row["DATE"], float(value)))
    return data[-140:]


def pct_change(values: list[float], periods: int = 5) -> float:
    return (values[-1] / values[-1 - periods] - 1) * 100


def fmt(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def build_status() -> dict:
    etf = eastmoney_etf_closes()
    hstech = yahoo_closes("%5EHSTECH")
    dxy = yahoo_closes("DX-Y.NYB")
    dgs10 = fred_dgs10()

    if min(len(etf), len(hstech), len(dxy), len(dgs10)) < 25:
        raise ValueError("至少一项关键数据不足 25 个有效观测值")

    etf_dates, etf_values = zip(*etf)
    hstech_values = [x[1] for x in hstech]
    dxy_values = [x[1] for x in dxy]
    dgs_values = [x[1] for x in dgs10]
    price = etf_values[-1]
    ma20 = statistics.mean(etf_values[-20:])
    ma60 = statistics.mean(etf_values[-60:])
    hstech_5d = pct_change(hstech_values)
    dxy_5d = pct_change(dxy_values)
    dgs10_5d_bp = (dgs_values[-1] - dgs_values[-6]) * 100

    negatives, positives = [], []
    risk_count = 0
    if price < ma20:
        negatives.append("ETF收盘价低于20日线，短线趋势偏弱。")
        risk_count += 1
    else:
        positives.append("ETF仍在20日线上方，短线趋势尚未转弱。")
    if price < ma60:
        negatives.append("ETF收盘价低于60日线，中期趋势需要重新观察。")
        risk_count += 1
    else:
        positives.append("ETF仍在60日线上方，中期结构尚未确认走坏。")
    if hstech_5d < 0:
        negatives.append(f"恒生科技近5日 {hstech_5d:.1f}% ，外部科技环境偏弱。")
        risk_count += 1
    else:
        positives.append(f"恒生科技近5日 {hstech_5d:.1f}% ，外部科技环境提供支持。")
    if dgs10_5d_bp > 5:
        negatives.append(f"美国10年期收益率近5日上行 {dgs10_5d_bp:.0f}bp，成长估值压力增加。")
        risk_count += 1
    elif dgs10_5d_bp < -5:
        positives.append(f"美国10年期收益率近5日下行 {abs(dgs10_5d_bp):.0f}bp，成长估值压力缓和。")
    if dxy_5d > 0.5:
        negatives.append(f"美元指数近5日上涨 {dxy_5d:.1f}% ，港股风险偏好承压。")
        risk_count += 1
    elif dxy_5d < -0.5:
        positives.append(f"美元指数近5日下跌 {abs(dxy_5d):.1f}% ，外部流动性压力缓和。")

    if risk_count >= 4:
        level, title = "橙色预警", "多项领先变量转坏，先控制风险"
        action = "停止加仓；已有仓位以60日线和外部环境是否继续恶化为重点。"
    elif risk_count >= 2:
        level, title = "黄色预警", "上涨条件开始松动，先保护判断空间"
        action = "不追跌、不加仓；观察是否重新站回20日线，以及恒生科技和利率压力是否改善。"
    else:
        level, title = "环境正常", "当前外部环境未出现集中恶化"
        action = "不代表可以买入；仍需结合位置、回踩和仓位管理判断。"

    return {
        "code": "159822",
        "as_of": f"数据更新：ETF {etf_dates[-1]} · 宏观数据截至最近可得交易日",
        "price": fmt(price),
        "ma20": fmt(ma20),
        "ma60": fmt(ma60),
        "relative_strength": f"恒科5日 {hstech_5d:+.1f}%",
        "alert_level": level,
        "action_title": title,
        "action": action,
        "logic_chain": ["美债/美元变化", "成长股估值压力", "恒生科技强弱", "ETF趋势", "新经济ETF环境"],
        "negative_signals": negatives or ["暂未发现本规则定义的集中转弱信号。"],
        "positive_signals": positives or ["暂未发现本规则定义的明显支持信号。"]
    }


def write_unavailable(reason: str) -> None:
    old = json.loads(STATUS_FILE.read_text(encoding="utf-8"))[0]
    old.update({
        "as_of": "数据更新失败：已暂停判断",
        "alert_level": "数据不完整",
        "action_title": "不输出交易判断",
        "action": "关键数据未能完整验证，因此系统不生成预警。原因：" + reason,
        "negative_signals": ["数据质量保护已触发：" + reason],
        "positive_signals": ["上一次有效数值不会被坏数据覆盖。"]
    })
    STATUS_FILE.write_text(json.dumps([old], ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    try:
        status = build_status()
        STATUS_FILE.write_text(json.dumps([status], ensure_ascii=False, indent=2), encoding="utf-8")
        print("Market data updated successfully.")
    except Exception as error:
        write_unavailable(str(error))
        print(f"Update paused: {error}")


if __name__ == "__main__":
    main()
