"""更新 159822 的第一批市场信号。

仅使用两个稳定来源：
- 东方财富：159822 与 3033.HK（恒生科技ETF代理）日线
- FRED：美国10年期收益率 DGS10、广义美元指数 DTWEXBGS

原则：关键数据任一缺失，就暂停判断，不生成交易预警。
"""
from __future__ import annotations

import csv
import io
import json
import statistics
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
STATUS_FILE = ROOT / "data" / "etf_status.json"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def get_json(url: str) -> dict:
    request = Request(url, headers=HEADERS)
    with urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def get_text(url: str) -> str:
    request = Request(url, headers=HEADERS)
    with urlopen(request, timeout=25) as response:
        return response.read().decode("utf-8")


def eastmoney_closes(secid: str, label: str) -> list[tuple[str, float]]:
    url = (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get?"
        f"secid={secid}&klt=101&fqt=1&lmt=140&"
        "fields1=f1,f2,f3,f4,f5,f6&"
        "fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
    )
    payload = get_json(url)
    rows = (payload.get("data") or {}).get("klines") or []
    values = [(r.split(",")[0], float(r.split(",")[2])) for r in rows if r.split(",")[2] != "-"]
    if len(values) < 25:
        raise ValueError(f"东方财富未返回足够的{label}日线")
    return values


def fred_series(series: str, label: str) -> list[tuple[str, float]]:
    text = get_text(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}")
    rows = csv.DictReader(io.StringIO(text))
    values = []
    for row in rows:
        value = row.get(series, "")
        if value and value != ".":
            values.append((row["DATE"], float(value)))
    if len(values) < 25:
        raise ValueError(f"FRED未返回足够的{label}数据")
    return values[-140:]


def pct_change(values: list[float], periods: int = 5) -> float:
    return (values[-1] / values[-1 - periods] - 1) * 100


def fmt(value: float) -> str:
    return f"{value:.3f}"


def build_status() -> dict:
    etf = eastmoney_closes("0.159822", "159822")
    # 港交所：3033.HK，东方财富港股代码格式为 116.03033
    hstech_proxy = eastmoney_closes("116.03033", "恒生科技ETF代理")
    dgs10 = fred_series("DGS10", "美国10年期收益率")
    dollar = fred_series("DTWEXBGS", "广义美元指数")

    etf_dates, etf_values = zip(*etf)
    hstech_values = [v for _, v in hstech_proxy]
    dgs_values = [v for _, v in dgs10]
    dollar_values = [v for _, v in dollar]
    price = etf_values[-1]
    ma20 = statistics.mean(etf_values[-20:])
    ma60 = statistics.mean(etf_values[-60:])
    hstech_5d = pct_change(hstech_values)
    dollar_5d = pct_change(dollar_values)
    dgs10_5d_bp = (dgs_values[-1] - dgs_values[-6]) * 100

    negatives, positives, risk_count = [], [], 0
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
        negatives.append(f"恒生科技ETF代理近5日 {hstech_5d:.1f}% ，外部科技环境偏弱。")
        risk_count += 1
    else:
        positives.append(f"恒生科技ETF代理近5日 {hstech_5d:.1f}% ，外部科技环境提供支持。")
    if dgs10_5d_bp > 5:
        negatives.append(f"美国10年期收益率近5日上行 {dgs10_5d_bp:.0f}bp，成长估值压力增加。")
        risk_count += 1
    elif dgs10_5d_bp < -5:
        positives.append(f"美国10年期收益率近5日下行 {abs(dgs10_5d_bp):.0f}bp，成长估值压力缓和。")
    if dollar_5d > 0.3:
        negatives.append(f"广义美元指数近5日上涨 {dollar_5d:.1f}% ，外部流动性压力增加。")
        risk_count += 1
    elif dollar_5d < -0.3:
        positives.append(f"广义美元指数近5日下跌 {abs(dollar_5d):.1f}% ，外部流动性压力缓和。")

    if risk_count >= 4:
        level, title = "橙色预警", "多项领先变量转坏，先控制风险"
        action = "停止加仓；已有仓位重点看60日线与外部环境是否继续恶化。"
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
        "relative_strength": f"恒科代理5日 {hstech_5d:+.1f}%",
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


if __name__ == "__main__":
    try:
        STATUS_FILE.write_text(json.dumps([build_status()], ensure_ascii=False, indent=2), encoding="utf-8")
        print("Market data updated successfully.")
    except Exception as error:
        write_unavailable(str(error))
        print(f"Update paused: {error}")
