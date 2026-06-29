"""CRM 线索看板「人员处理与工作量」专项造数脚本。

覆盖责任周期 + 6 种结束类型：
  1) 当前持有
  2) 分配（转出给其他员工）
  3) 主动移入公海
  4) 系统回收
  5) 转客户
  6) 作废

注意：
  - 创建线索 + 活动记录可走自动化接口；
  - 转分配 / 移入公海 / 系统回收 / 转客户 / 作废 部分接口可能为定向接口，未配置时会
    输出待手工触发清单（manifest），由 QA 在 CRM 后台按清单触发，再做指标对账。

用法：
  python scripts/create_lead_dashboard_emp_dataset.py [--config scenarios.json] [--dry-run]

环境变量（在 .env 或环境中覆写）：
  EMP_DATASET_OUTPUT_DIR  默认 testcases/_emp_dataset
  EMP_DATASET_TAG         默认带时间戳

输出：
  testcases/_emp_dataset/<tag>/lead_ids.json          # 全部新建线索的 ID 与归属
  testcases/_emp_dataset/<tag>/manifest.md            # 人工触发清单（按场景顺序）
  testcases/_emp_dataset/<tag>/run.log                # 执行日志

可选脚本配置（--config）:
  {
    "members": [
      {"name": "甲", "phone": "...", "password_encrypted": "..."},
      ...
    ],
    "scenarios": [
      {"id": "CUR-HOLD-001", "owner": "甲", "activities": 1, "end_type": "当前持有"},
      ...
    ]
  }
未提供 config 时，使用默认演练矩阵（与 EMP 用例 EMP-051~062 一致）。
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.auth_context import AuthContext
from api.client import ApiClient
from api.services.auth_service import AuthService
from api.services.crm_lead_service import CrmLeadService
from config.settings import (
    ACTIVITY_RECORD_TYPE_CODE,
    ACTIVITY_TYPE_CODE,
    API_TIMEOUT_SECONDS,
    CRM_DEFAULT_FOLLOW_USER_ID,
    CRM_DEFAULT_FOLLOW_USER_NAME,
    LOGIN_PASSWORD_ENCRYPTED,
    LOGIN_PHONE,
)

END_TYPES = ("当前持有", "分配", "主动移入公海", "系统回收", "转客户", "作废")

DEFAULT_MATRIX: list[dict[str, Any]] = [
    # 责任周期开始 + 6 种结束类型 + 跨筛选时段的边界
    {"id": "CUR-001", "owner": "甲", "activities": 1, "end_type": "当前持有", "note": "EMP-056 / 当前仍由该员工负责=是"},
    {"id": "CUR-002", "owner": "甲", "activities": 0, "end_type": "当前持有", "note": "EMP-013 仍持有未首跟"},
    {"id": "ASN-001", "owner": "甲", "activities": 1, "end_type": "分配", "transfer_to": "乙", "note": "EMP-057 转出给乙"},
    {"id": "ASN-002", "owner": "甲", "activities": 0, "end_type": "分配", "transfer_to": "乙", "note": "EMP-014 已结束未首跟"},
    {"id": "MAN-POOL-001", "owner": "甲", "activities": 1, "end_type": "主动移入公海", "note": "EMP-058 操作人=甲"},
    {"id": "AUTO-POOL-001", "owner": "甲", "activities": 0, "end_type": "系统回收", "note": "EMP-059 等待超期后系统回收触发"},
    {"id": "WIN-CUST-001", "owner": "甲", "activities": 2, "end_type": "转客户", "note": "EMP-060 在甲名下转客户"},
    {"id": "VOID-001", "owner": "甲", "activities": 1, "end_type": "作废", "note": "EMP-061 在甲名下作废"},
    # 多周期与多员工
    {"id": "MULTI-CYCLE-001", "owner": "丙", "activities": 1, "end_type": "分配", "transfer_to": "甲", "note": "EMP-054 同一线索多周期 - 第一段：丙→甲"},
    {"id": "MULTI-CYCLE-002", "owner": "甲", "activities": 1, "end_type": "分配", "transfer_to": "丙", "reuse_lead_of": "MULTI-CYCLE-001", "note": "EMP-054 第二段：甲→丙"},
    {"id": "MULTI-USER-001", "owner": "甲", "activities": 1, "end_type": "分配", "transfer_to": "乙", "note": "EMP-055 不同员工承接同一线索 - 第一段"},
    {"id": "MULTI-USER-002", "owner": "乙", "activities": 1, "end_type": "分配", "transfer_to": "丙", "reuse_lead_of": "MULTI-USER-001", "note": "EMP-055 第二段"},
    {"id": "MULTI-USER-003", "owner": "丙", "activities": 0, "end_type": "当前持有", "reuse_lead_of": "MULTI-USER-001", "note": "EMP-055 第三段（当前持有）"},
    # 与筛选时间段交集边界
    {"id": "SPAN-001", "owner": "甲", "activities": 1, "end_type": "当前持有", "back_days_for_assign": 365, "note": "EMP-052 责任周期跨筛选时段"},
    {"id": "OUT-001", "owner": "甲", "activities": 0, "end_type": "作废", "back_days_for_assign": 400, "void_after_days": 380, "note": "EMP-053 完全在筛选时段之前"},
]


@dataclass
class MemberAuth:
    name: str
    phone: str
    password_encrypted: str
    member_id: int = 0
    user_id: int = 0
    token: str = ""

    def authed(self) -> bool:
        return bool(self.token and self.member_id and self.user_id)


@dataclass
class ScenarioRecord:
    scenario_id: str
    owner: str
    end_type: str
    lead_id: Optional[int] = None
    lead_name: Optional[str] = None
    lead_phone: Optional[str] = None
    activities_created: int = 0
    activity_ids: list[int] = field(default_factory=list)
    transfer_to: Optional[str] = None
    manual_steps: list[str] = field(default_factory=list)
    auto_steps: list[str] = field(default_factory=list)
    error: Optional[str] = None
    note: str = ""


def _tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _load_config(path: Optional[str]) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"配置文件不存在: {path}")
    return json.loads(p.read_text(encoding="utf-8"))


def _login_member(auth: AuthService, m: MemberAuth) -> MemberAuth:
    data = auth.login_with_encrypted_password(m.phone, m.password_encrypted)
    m.member_id = int(data["memberId"])
    m.user_id = int(data["userId"])
    m.token = data["token"]
    return m


def _ensure_members(members_cfg: list[dict[str, Any]]) -> list[MemberAuth]:
    if not members_cfg:
        # 默认仅登录主账号；其他角色不登录，仅做为「待手工触发」标记
        members_cfg = [{"name": "甲", "phone": LOGIN_PHONE, "password_encrypted": LOGIN_PASSWORD_ENCRYPTED}]
    members = [MemberAuth(**m) for m in members_cfg]
    auth = AuthService(ApiClient(timeout=API_TIMEOUT_SECONDS))
    for m in members:
        try:
            _login_member(auth, m)
        except Exception as exc:
            print(f"[WARN] 登录失败 ({m.name}/{m.phone}): {exc}")
    return members


def _get_owner(members: list[MemberAuth], name: str) -> Optional[MemberAuth]:
    for m in members:
        if m.name == name and m.authed():
            return m
    return None


def _create_lead_for(svc: CrmLeadService, owner: MemberAuth) -> tuple[dict, int]:
    ctx = AuthContext(
        member_id=owner.member_id,
        user_id=owner.user_id,
        token=owner.token,
    )
    payload = svc.build_random_lead_payload(
        ctx,
        follow_user_id=CRM_DEFAULT_FOLLOW_USER_ID,
        follow_user_name=CRM_DEFAULT_FOLLOW_USER_NAME,
    )
    resp = svc.create_lead(ctx, payload)
    relation_id = svc.resolve_relation_id_from_created_lead(
        ctx,
        create_response=resp,
        create_payload=payload,
    )
    return payload, int(relation_id)


def _create_activity(svc: CrmLeadService, owner: MemberAuth, relation_id: int) -> int:
    ctx = AuthContext(
        member_id=owner.member_id,
        user_id=owner.user_id,
        token=owner.token,
    )
    payload = svc.build_activity_payload(
        relation_id=relation_id,
        activity_type_code=ACTIVITY_TYPE_CODE,
        activity_record_type_code=ACTIVITY_RECORD_TYPE_CODE,
    )
    resp = svc.create_activity_record(ctx, payload)
    data = resp.get("data")
    if isinstance(data, dict):
        return int(data.get("id") or data.get("activityId") or 0)
    if isinstance(data, int):
        return data
    return 0


def _build_manual_steps(scenario: dict[str, Any], lead_name: str) -> list[str]:
    end_type = scenario["end_type"]
    transfer_to = scenario.get("transfer_to") or ""
    steps: list[str] = []
    if end_type == "当前持有":
        steps.append("无需手工触发：保持当前归属即可")
    elif end_type == "分配":
        steps.append(f"CRM 后台找到线索「{lead_name}」 → 操作「转分配」 → 目标员工：{transfer_to}")
    elif end_type == "主动移入公海":
        steps.append(f"CRM 后台找到线索「{lead_name}」 → 操作「移入公海」（由当前归属人执行）")
    elif end_type == "系统回收":
        steps.append(f"等待该线索超期未跟进，由定时任务自动回收 → 或临时调整该规则后触发；线索：{lead_name}")
    elif end_type == "转客户":
        steps.append(f"CRM 后台找到线索「{lead_name}」 → 操作「转客户」")
    elif end_type == "作废":
        steps.append(f"CRM 后台找到线索「{lead_name}」 → 操作「作废」")
    if scenario.get("back_days_for_assign"):
        steps.append(
            "（造数说明）该场景需要责任周期开始时间早于筛选窗口 "
            f"{scenario['back_days_for_assign']} 天，请通过 DB 回写或测试库辅助接口设置 dispatch_time"
        )
    if scenario.get("void_after_days"):
        steps.append(
            "（造数说明）作废时间需早于筛选窗口 "
            f"{scenario['void_after_days']} 天，请通过 DB 回写或测试库辅助接口设置 void_time"
        )
    return steps


def _execute_one(
    svc: CrmLeadService,
    members: list[MemberAuth],
    scenario: dict[str, Any],
    reuse_map: dict[str, ScenarioRecord],
    log_lines: list[str],
) -> ScenarioRecord:
    record = ScenarioRecord(
        scenario_id=scenario["id"],
        owner=scenario["owner"],
        end_type=scenario["end_type"],
        transfer_to=scenario.get("transfer_to"),
        note=scenario.get("note", ""),
    )
    reuse_of = scenario.get("reuse_lead_of")
    owner = _get_owner(members, scenario["owner"])
    try:
        if reuse_of:
            base = reuse_map.get(reuse_of)
            if not base or not base.lead_id:
                raise RuntimeError(f"复用线索失败：未找到基础场景 {reuse_of}")
            record.lead_id = base.lead_id
            record.lead_name = base.lead_name
            record.lead_phone = base.lead_phone
            record.auto_steps.append(f"复用线索 {reuse_of} -> lead_id={base.lead_id}")
        else:
            if not owner:
                raise RuntimeError(f"未登录归属员工: {scenario['owner']}（仅做手工触发清单）")
            payload, relation_id = _create_lead_for(svc, owner)
            record.lead_id = relation_id
            record.lead_name = payload["name"]
            record.lead_phone = payload["phone"]
            record.auto_steps.append(f"创建线索 -> lead_id={relation_id}, name={payload['name']}")

        if owner and scenario.get("activities", 0) > 0:
            for _ in range(int(scenario["activities"])):
                aid = _create_activity(svc, owner, record.lead_id)
                if aid:
                    record.activity_ids.append(aid)
                record.activities_created += 1
                record.auto_steps.append(f"创建活动记录 -> id={aid}")
                time.sleep(0.2)

        record.manual_steps = _build_manual_steps(scenario, record.lead_name or "(未知)")
        log_lines.append(f"[OK] {scenario['id']} lead_id={record.lead_id} 活动 x{record.activities_created}")
    except Exception as exc:
        record.error = f"{type(exc).__name__}: {exc}"
        record.manual_steps = _build_manual_steps(scenario, record.lead_name or "(未创建)")
        log_lines.append(f"[ERR] {scenario['id']} -> {record.error}")
    return record


def _write_outputs(out_dir: Path, records: list[ScenarioRecord], log_lines: list[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "lead_ids.json").write_text(
        json.dumps([asdict(r) for r in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# 线索看板·人员模块 责任周期造数 Manifest",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| 场景ID | 归属员工 | 结束类型 | 转出至 | lead_id | 线索名称 | 已建活动 | 备注 |",
        "|--------|----------|----------|--------|---------|----------|----------|------|",
    ]
    for r in records:
        lines.append(
            f"| {r.scenario_id} | {r.owner} | {r.end_type} | {r.transfer_to or '-'} | "
            f"{r.lead_id or '-'} | {r.lead_name or '-'} | {r.activities_created} | {r.note or '-'} |"
        )
    lines.extend(["", "## 待手工触发步骤", ""])
    for r in records:
        if not r.manual_steps:
            continue
        lines.append(f"### {r.scenario_id} ({r.end_type})")
        for s in r.manual_steps:
            lines.append(f"- {s}")
        if r.error:
            lines.append(f"- [自动步骤错误] {r.error}")
        lines.append("")

    (out_dir / "manifest.md").write_text("\n".join(lines), encoding="utf-8")
    (out_dir / "run.log").write_text("\n".join(log_lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="人员模块责任周期造数脚本")
    parser.add_argument("--config", help="JSON 配置文件路径")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只输出计划，不发起接口请求",
    )
    parser.add_argument("--tag", default=os.getenv("EMP_DATASET_TAG", _tag()))
    args = parser.parse_args()

    cfg = _load_config(args.config)
    members_cfg: list[dict[str, Any]] = cfg.get("members") or []
    scenarios: list[dict[str, Any]] = cfg.get("scenarios") or DEFAULT_MATRIX

    out_root = Path(os.getenv("EMP_DATASET_OUTPUT_DIR", _ROOT / "testcases" / "_emp_dataset"))
    out_dir = out_root / args.tag

    if args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "plan.json").write_text(
            json.dumps({"members": members_cfg, "scenarios": scenarios}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[DRY-RUN] 计划已写入 {out_dir / 'plan.json'}")
        return 0

    members = _ensure_members(members_cfg)
    svc = CrmLeadService(ApiClient(timeout=API_TIMEOUT_SECONDS))

    log_lines: list[str] = [
        f"==== {datetime.now().isoformat()} 开始造数 ====",
        f"已登录员工: {[m.name for m in members if m.authed()]}",
    ]
    records: list[ScenarioRecord] = []
    reuse_map: dict[str, ScenarioRecord] = {}
    for sc in scenarios:
        rec = _execute_one(svc, members, sc, reuse_map, log_lines)
        records.append(rec)
        reuse_map[sc["id"]] = rec
        time.sleep(random.uniform(0.2, 0.6))

    _write_outputs(out_dir, records, log_lines)
    print(f"[DONE] 共 {len(records)} 个场景；产物目录: {out_dir}")
    return 0 if all(not r.error for r in records) else 2


if __name__ == "__main__":
    raise SystemExit(main())
