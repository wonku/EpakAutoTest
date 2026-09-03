@echo off
setlocal
cd /d "%~dp0.."

if not exist reports\junit mkdir reports\junit

if /I "%INCLUDE_NEGATIVE%"=="false" (
    set "MARKER_EXPR=api and not api_negative"
) else (
    set "MARKER_EXPR=api"
)

echo ============================================================
echo CRM API Jenkins regression
echo marker: %MARKER_EXPR%
echo scope : lead + customer + opportunity + contact + optional negative + other @api
echo lead       : tests/test_api_create_lead*.py + claim/assign/public_sea + test_api_lead_flow.py
echo customer   : tests/test_api_customer_flow.py
echo opportunity: tests/test_api_opportunity_flow.py
echo contact    : tests/test_api_contact_flow.py
echo ============================================================

set "EMAIL_ARG="
if /I "%SEND_EMAIL_REPORT%"=="true" set "EMAIL_ARG=--email-report"

python -m pytest -m "%MARKER_EXPR%" -v --junitxml=reports/junit/crm-api.xml %EMAIL_ARG%
exit /b %ERRORLEVEL%
