"""ETF Radar 数据更新入口。

第一版故意不自动抓取：先确定数据源与字段，再启用更新。
任何关键数据缺失时，不覆盖 data/etf_status.json，避免坏数据产生假预警。
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
STATUS_FILE = ROOT / "data" / "etf_status.json"


def main() -> None:
    status = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    print("ETF Radar updater is in safe mode.")
    print("No market data source has been configured; status file was not changed.")
    print(f"Loaded {len(status)} ETF status record(s).")


if __name__ == "__main__":
    main()
