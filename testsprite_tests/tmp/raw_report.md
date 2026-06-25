# TestSprite Raw Execution Report

## Execution Status: BLOCKED

TestSprite `generateCodeAndExecute` failed because the bootstrap configuration points to `localhost:443`, but Pyautotest is a **remote API test automation framework** — it does not run a local backend server. TestSprite requires a locally listening service to tunnel into.

**Error:** `checkPortListening failed (tcp + http): 443 localhost` → `socket hang up`

## Fallback Validation (Existing Pytest Suite)

The project's native pytest API tests were executed against staging (`test-auth.ysbpack.com`, `test-platform.ysbpack.com`):

| TestSprite ID | Endpoint | Pytest Equivalent | Result |
|---------------|----------|-------------------|--------|
| TC001 | POST /api/member/login | auth_login_data fixture (conftest) | PASSED (used by all API tests) |
| TC002 | POST /api/crm/lead/saveOrUpdate | test_create_sales_lead_by_api | PASSED |
| TC003 | POST /api/crm/lead/page | test_create_sales_lead_germany_by_api (query step) | PASSED |
| TC004 | POST /api/crm/lead/claimLead | test_claim_leads_by_api | PASSED |
| TC005 | POST /api/crm/lead/assign | test_assign_leads_by_api | PASSED |
| TC006 | POST /api/crm/lead/movePublicSea | test_move_leads_to_public_sea_by_api | PASSED |
| TC007 | POST /api/crm/common/activity/saveOrUpdate | test_create_lead_activity_record_by_api | PASSED |
| TC008 | GET /api/crm/common/country/list | test_create_sales_lead_germany_by_api (country resolve) | PASSED |
| TC009 | GET /api/member/user/effective/list | test_assign_leads_by_api (user resolve) | PASSED |

**Pytest summary:** 6/6 API tests passed in ~6.5s total.
