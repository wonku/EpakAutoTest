"""CRM 造数回滚：按公司名清理客户及相关会员数据。

测试库为 PostgreSQL（Navicat/psycopg2）。默认 SQL 来自业务方模板，`{name}` 自动替换。
需配置 CRM_DB_* 且 CRM_CUSTOMER_ROLLBACK_ENABLED=true 才会真正执行。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable

from config.settings import (
    CRM_CUSTOMER_ROLLBACK_ENABLED,
    CRM_CUSTOMER_ROLLBACK_SQL,
    CRM_DB_DATABASE,
    CRM_DB_HOST,
    CRM_DB_PASSWORD,
    CRM_DB_PORT,
    CRM_DB_USER,
)

logger = logging.getLogger(__name__)

# 业务方提供的默认回滚语句（{name} / %(company_name)s 均可）
# 注意：先删机会子表 → 机会/成交 → 联系人 → 客户 → 会员
_DEFAULT_ROLLBACK_SQL = """
-- 销售机会子表 / 成交
DELETE FROM crm_sale_opportunity_product WHERE sale_opportunity_id IN (
  SELECT id FROM crm_sale_opportunity WHERE customer_id IN (SELECT id FROM crm_customer WHERE company_name = '{name}')
);
DELETE FROM crm_sale_opportunity_team_member WHERE sale_opportunity_id IN (
  SELECT id FROM crm_sale_opportunity WHERE customer_id IN (SELECT id FROM crm_customer WHERE company_name = '{name}')
);
DELETE FROM crm_deal_record WHERE customer_id IN (SELECT id FROM crm_customer WHERE company_name = '{name}');
DELETE FROM crm_deal_record WHERE sale_opportunity_id IN (
  SELECT id FROM crm_sale_opportunity WHERE customer_id IN (SELECT id FROM crm_customer WHERE company_name = '{name}')
);
DELETE FROM crm_sale_opportunity WHERE customer_id IN (SELECT id FROM crm_customer WHERE company_name = '{name}');
DELETE FROM crm_sale_opportunity WHERE contact_person_id IN (
  SELECT id FROM crm_contact_person WHERE customer_id IN (SELECT id FROM crm_customer WHERE company_name = '{name}')
);

-- 联系人团队 / 联系人 / 客户团队 / 客户
DELETE FROM crm_contact_person_team_member WHERE contact_id IN (
  SELECT id FROM crm_contact_person WHERE customer_id IN (SELECT id FROM crm_customer WHERE company_name = '{name}')
);
DELETE FROM crm_contact_person WHERE customer_id IN (SELECT id FROM crm_customer WHERE company_name = '{name}');
DELETE FROM crm_customer_team_member WHERE customer_id IN (SELECT id FROM crm_customer WHERE company_name = '{name}');
DELETE FROM crm_customer WHERE company_name = '{name}';

-- 活动记录
DELETE FROM crm_lead_activity WHERE relation_name = '{name}';

-- 会员押金明细 / 关系 / 角色 / 用户 / 会员
DELETE FROM ms_mc_member_deposit_detail WHERE relation_id IN (
  SELECT id FROM ms_mc_member_relation WHERE sub_member_id IN (
    SELECT id FROM ms_mc_member WHERE name = '{name}'
  )
);
DELETE FROM ms_mc_member_relation WHERE sub_member_id IN (SELECT id FROM ms_mc_member WHERE name = '{name}');
DELETE FROM ms_mc_member_user_member_role_relation WHERE member_role_id IN (
  SELECT id FROM ms_mc_member_role WHERE member_id IN (
    SELECT id FROM ms_mc_member WHERE name = '{name}'
  )
);
DELETE FROM ms_mc_member_user WHERE member_id IN (SELECT id FROM ms_mc_member WHERE name = '{name}');
DELETE FROM ms_mc_member_role WHERE member_id IN (SELECT id FROM ms_mc_member WHERE name = '{name}');
DELETE FROM ms_mc_member WHERE name = '{name}';
"""


@dataclass
class CreatedCustomerRef:
    """用例创建的客户引用，供 teardown 回滚。"""

    company_name: str
    customer_id: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _sql_literal(value: str) -> str:
    """PostgreSQL 单引号字面量转义。"""
    return (value or "").replace("'", "''")


def render_rollback_sql(company_name: str, *, sql_template: str | None = None) -> list[str]:
    """渲染回滚 SQL 列表（已按 ; 拆分）。"""
    name = (company_name or "").strip()
    if not name:
        return []
    raw = (sql_template if sql_template is not None else CRM_CUSTOMER_ROLLBACK_SQL) or ""
    raw = raw.strip() or _DEFAULT_ROLLBACK_SQL
    lit = _sql_literal(name)
    # 同时支持 {name} / %(company_name)s / {company_name}
    rendered = (
        raw.replace("{name}", lit)
        .replace("{company_name}", lit)
        .replace("%(company_name)s", lit)
        .replace("%(name)s", lit)
    )
    stmts: list[str] = []
    for part in rendered.split(";"):
        lines = []
        for line in part.splitlines():
            stripped = line.strip()
            if stripped.startswith("--"):
                continue
            lines.append(line)
        stmt = "\n".join(lines).strip()
        if stmt:
            stmts.append(stmt)
    return stmts


def db_config_ready() -> bool:
    return bool(CRM_DB_HOST and CRM_DB_USER and CRM_DB_DATABASE)


def open_crm_db_conn() -> Any | None:
    """打开 CRM PostgreSQL 测试库；缺依赖/缺配置时返回 None。"""
    if not db_config_ready():
        logger.warning(
            "CRM DB 未配置：请设置 CRM_DB_HOST / CRM_DB_USER / CRM_DB_PASSWORD / "
            "CRM_DB_DATABASE（见 .env.example）"
        )
        return None
    try:
        import psycopg2  # type: ignore
    except ImportError:
        logger.warning(
            "未安装 psycopg2，无法执行客户回滚 SQL。请 pip install psycopg2-binary"
        )
        return None
    return psycopg2.connect(
        host=CRM_DB_HOST,
        port=int(CRM_DB_PORT or 5432),
        user=CRM_DB_USER,
        password=CRM_DB_PASSWORD or "",
        dbname=CRM_DB_DATABASE,
        connect_timeout=15,
    )


def execute_rollback_sql(
    statements: Iterable[str],
    *,
    db_conn: Any = None,
    close_conn: bool = False,
) -> int:
    """执行多条 DELETE；返回成功执行条数。"""
    own = False
    conn = db_conn
    if conn is None:
        conn = open_crm_db_conn()
        own = True
        close_conn = True
    if conn is None:
        return 0
    done = 0
    try:
        cursor = conn.cursor()
        for stmt in statements:
            cursor.execute(stmt)
            done += 1
            logger.info("rollback sql ok rows=%s: %s", cursor.rowcount, stmt[:120])
        conn.commit()
        return done
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        if close_conn and own and conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def rollback_customer_by_company_name(
    company_name: str,
    *,
    db_conn: Any = None,
    sql_template: str | None = None,
    force: bool = False,
) -> bool:
    """按公司名执行默认/覆盖回滚 SQL。

    force=True 时忽略 CRM_CUSTOMER_ROLLBACK_ENABLED（用于用例前清重）。
    """
    name = (company_name or "").strip()
    if not name:
        logger.warning("customer rollback skipped: empty company_name")
        return False
    if not force and not CRM_CUSTOMER_ROLLBACK_ENABLED:
        logger.info(
            "customer rollback no-op (CRM_CUSTOMER_ROLLBACK_ENABLED=false): company=%s",
            name,
        )
        return False
    stmts = render_rollback_sql(name, sql_template=sql_template)
    if not stmts:
        return False
    try:
        n = execute_rollback_sql(stmts, db_conn=db_conn)
        logger.info("customer rollback by name done: company=%s stmts=%s", name, n)
        return n > 0
    except Exception:
        logger.exception("customer rollback by name failed: company=%s", name)
        raise


def rollback_created_customer(
    ref: CreatedCustomerRef,
    *,
    db_conn: Any = None,
) -> bool:
    """按 customer_id / 公司名回滚新建客户。"""
    if not ref.customer_id and not ref.company_name:
        logger.warning("customer rollback skipped: empty ref")
        return False

    if not CRM_CUSTOMER_ROLLBACK_ENABLED:
        logger.info(
            "customer rollback no-op (CRM_CUSTOMER_ROLLBACK_ENABLED=false): "
            "id=%s company=%s",
            ref.customer_id,
            ref.company_name,
        )
        return False

    if ref.company_name:
        return rollback_customer_by_company_name(
            ref.company_name, db_conn=db_conn, force=True
        )

    logger.warning(
        "customer rollback skipped: 仅有 customer_id=%s 无公司名，默认 SQL 按 name 删除",
        ref.customer_id,
    )
    return False


def rollback_created_customers(
    refs: list[CreatedCustomerRef],
    *,
    db_conn: Any = None,
) -> None:
    """批量回滚；单项失败不阻断后续（记录日志）。"""
    for ref in reversed(refs):
        try:
            rollback_created_customer(ref, db_conn=db_conn)
        except Exception:
            logger.exception("batch rollback item failed: %s", ref)


class CrmDataRollback:
    """用例侧登记器：创建后 register，teardown 调 rollback_all。"""

    def __init__(self, *, db_conn: Any = None) -> None:
        self._refs: list[CreatedCustomerRef] = []
        self._db_conn = db_conn

    def register_customer(
        self,
        *,
        customer_id: int | str | None = None,
        company_name: str = "",
        **extra: Any,
    ) -> CreatedCustomerRef:
        cid: int | None
        try:
            cid = int(customer_id) if customer_id is not None else None
        except (TypeError, ValueError):
            cid = None
        ref = CreatedCustomerRef(
            company_name=(company_name or "").strip(),
            customer_id=cid,
            extra=dict(extra) if extra else {},
        )
        self._refs.append(ref)
        logger.info(
            "登记客户回滚: id=%s company=%s",
            ref.customer_id,
            ref.company_name,
        )
        return ref

    @property
    def customers(self) -> list[CreatedCustomerRef]:
        return list(self._refs)

    def rollback_all(self) -> None:
        rollback_created_customers(self._refs, db_conn=self._db_conn)
        self._refs.clear()
