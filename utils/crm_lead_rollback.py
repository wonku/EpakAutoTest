"""CRM 线索造数回滚（接口删除，我的线索 / 公海均可）。

权威实现在 `CrmLeadService.rollback_created_lead` / `delete_lead`。
用例侧：创建后 `register`，teardown 调 `rollback_all`。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from api.auth_context import AuthContext
from api.services.crm_lead_service import CrmLeadService

logger = logging.getLogger(__name__)


@dataclass
class CreatedLeadRef:
    """用例创建的线索引用，供 teardown 回滚。"""

    lead_id: int | None = None
    name: str = ""
    phone: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


class LeadRollbackRegistry:
    """登记本用例造数线索，结束时按接口删除。"""

    def __init__(self, service: CrmLeadService, ctx: AuthContext):
        self.service = service
        self.ctx = ctx
        self._refs: list[CreatedLeadRef] = []

    def register(
        self,
        *,
        lead_id: int | None = None,
        name: str = "",
        phone: str = "",
        **extra: Any,
    ) -> CreatedLeadRef:
        ref = CreatedLeadRef(
            lead_id=int(lead_id) if lead_id else None,
            name=(name or "").strip(),
            phone=str(phone or ""),
            extra=extra,
        )
        self._refs.append(ref)
        logger.info(
            "登记线索回滚: id=%s name=%s", ref.lead_id, ref.name
        )
        return ref

    def rollback_all(self) -> list[int]:
        deleted: list[int] = []
        for ref in list(self._refs):
            try:
                deleted.extend(
                    self.service.rollback_created_lead(
                        self.ctx, lead_id=ref.lead_id, name=ref.name
                    )
                )
            except Exception:
                logger.exception("线索回滚失败: %s", ref)
        self._refs.clear()
        return deleted
