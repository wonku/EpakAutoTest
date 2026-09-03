# -*- coding: utf-8 -*-
"""Fetch Feishu electronic spreadsheet values for form-fields-2.2."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)

APP_ID = os.getenv("FEISHU_APP_ID", "").strip()
APP_SECRET = os.getenv("FEISHU_APP_SECRET", "").strip()
SPREADSHEET = os.getenv("FEISHU_SHEET_SPREADSHEET", "W469sXDObhCosWtUGx0ctb8VnXd")
SHEET_ID = os.getenv("FEISHU_SHEET_ID", "zQuRgR")
OUT = ROOT / "testcases" / "_form_fields_2_2.json"


def _require_feishu_credentials() -> None:
    missing = [
        name
        for name, value in (
            ("FEISHU_APP_ID", APP_ID),
            ("FEISHU_APP_SECRET", APP_SECRET),
        )
        if not value
    ]
    if missing:
        print(
            "Missing Feishu credentials in .env: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        raise SystemExit(1)


def api(url: str, token: str, data: dict | None = None) -> dict:
    body = None if data is None else json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="GET" if data is None else "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print("http_error", exc.code, detail)
        raise


def main() -> None:
    _require_feishu_credentials()
    tok = api(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        token="",
        data={"app_id": APP_ID, "app_secret": APP_SECRET},
    )
    # auth endpoint ignores Authorization; re-call without bearer
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        tok = json.loads(resp.read().decode("utf-8"))
    print("token_code", tok.get("code"), tok.get("msg"))
    token = tok["tenant_access_token"]

    meta = api(
        f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{SPREADSHEET}/metainfo",
        token,
    )
    print("meta_code", meta.get("code"), meta.get("msg"))
    sheets = ((meta.get("data") or {}).get("sheets")) or []
    print("sheets", [(s.get("sheetId"), s.get("title")) for s in sheets])

    ranges = urllib.parse.quote(f"{SHEET_ID}!A1:AZ300")
    vals = api(
        "https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/"
        f"{SPREADSHEET}/values_batch_get?ranges={ranges}&valueRenderOption=ToString",
        token,
    )
    print("vals_code", vals.get("code"), vals.get("msg"))
    ranges_data = ((vals.get("data") or {}).get("valueRanges")) or []
    if ranges_data:
        values = ranges_data[0].get("values") or []
        print("rows", len(values))
        for i, row in enumerate(values[:50]):
            print(i, row)
    OUT.write_text(json.dumps(vals, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", OUT)


if __name__ == "__main__":
    main()
