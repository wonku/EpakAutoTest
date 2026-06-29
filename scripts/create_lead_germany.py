"""一次性脚本：创建指定国家的销售线索。"""
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.auth_context import AuthContext
from api.client import ApiClient
from api.services.auth_service import AuthService
from api.services.crm_lead_service import CrmLeadService
from config.settings import API_TIMEOUT_SECONDS, LOGIN_PASSWORD_ENCRYPTED, LOGIN_PHONE


def main() -> int:
    country = sys.argv[1] if len(sys.argv) > 1 else "德国"
    auth = AuthService(ApiClient(timeout=API_TIMEOUT_SECONDS))
    login = auth.login_with_encrypted_password(LOGIN_PHONE, LOGIN_PASSWORD_ENCRYPTED)
    ctx = AuthContext.from_login_data(login)
    svc = CrmLeadService(ApiClient(timeout=API_TIMEOUT_SECONDS))
    payload = svc.build_random_lead_payload(ctx, country=country)
    resp = svc.create_lead(ctx, payload)
    relation_id = svc.resolve_relation_id_from_created_lead(
        ctx,
        create_response=resp,
        create_payload=payload,
    )
    result = {"lead": payload, "create_response": resp, "relation_id": relation_id}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if resp.get("code") == 1000 else 1


if __name__ == "__main__":
    raise SystemExit(main())
