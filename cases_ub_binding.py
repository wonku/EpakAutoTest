# -*- coding: utf-8 -*-
"""1-用户企微绑定管理 详细用例（单数据源）。"""
from generate_ub_binding_test_artifacts import CASES as _SRC

CASES_UB = [
    (
        "1-用户企微绑定",
        row[1],
        f"[{row[0]}] {row[2]}",
        *row[3:],
    )
    for row in _SRC
]
