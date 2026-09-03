# -*- coding: utf-8 -*-
"""Read Feishu sheet cell values with a provided user access token."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SPREADSHEET = "W469sXDObhCosWtUGx0ctb8VnXd"
SHEETS = {
    "zQuRgR": "供应商单（G）（英文）",
    "eyjJFp": "询价子单（S）（英文）",
}
OUT = Path(__file__).resolve().parents[1] / "testcases" / "_form_fields_2_2.json"


def api(url: str, token: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print("http_error", exc.code, detail[:1000])
        raise


def main() -> None:
    token = sys.argv[1]
    result = {"spreadsheet": SPREADSHEET, "sheets": {}}
    for sheet_id, title in SHEETS.items():
        ranges = urllib.parse.quote(f"{sheet_id}!A1:V220")
        url = (
            "https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/"
            f"{SPREADSHEET}/values_batch_get?ranges={ranges}&valueRenderOption=ToString"
        )
        vals = api(url, token)
        print("sheet", title, "code", vals.get("code"), vals.get("msg"))
        ranges_data = ((vals.get("data") or {}).get("valueRanges")) or []
        values = ranges_data[0].get("values") if ranges_data else []
        print("rows", len(values or []))
        for i, row in enumerate((values or [])[:8]):
            print(i, row)
        result["sheets"][sheet_id] = {"title": title, "raw": vals, "values": values}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", OUT)


if __name__ == "__main__":
    main()
