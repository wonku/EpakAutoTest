"""英文商城 Linkseeks_AUTH_EN cookie：与前台 setAuth 编码一致。"""
from __future__ import annotations

import base64
import json
from urllib.parse import quote, urlparse

def _linkseeks_auth_payload(login_data: dict) -> dict:
    service_type_code = login_data.get("serviceTypeCode")
    member_id = login_data.get("memberId")
    upstream = "1" if service_type_code == 2 or (service_type_code == 3 and member_id == 6) else "0"
    return {
        "userId": login_data.get("userId"),
        "memberId": member_id,
        "token": login_data.get("token"),
        "name": login_data.get("name"),
        "logo": login_data.get("logo"),
        "level": login_data.get("level"),
        "phone": login_data.get("phone") or login_data.get("account"),
        "levelTag": login_data.get("levelTag"),
        "score": login_data.get("score") or 0,
        "creditPoint": login_data.get("creditPoint") or 0,
        "memberRoleType": login_data.get("memberRoleType"),
        "memberRoleId": login_data.get("memberRoleId"),
        "memberType": login_data.get("memberType"),
        "locales": login_data.get("locales"),
        "roles": login_data.get("roles") or [],
        "validateStatus": login_data.get("validateStatus"),
        "validateStatusDesc": login_data.get("validateStatusDesc"),
        "companyList": login_data.get("multiMemberBOS"),
        "supplierId": login_data.get("supplierId"),
        "company": login_data.get("company"),
        "serviceTypeCode": service_type_code,
        "buyerRegisterStatus": login_data.get("buyerRegisterStatus"),
        "dealerRegisterStatus": login_data.get("dealerRegisterStatus"),
        "temporarilyType": login_data.get("temporarilyType"),
        "upstream": upstream,
    }


def cookie_domain_from_url(url: str) -> str:
    host = (urlparse(url).hostname or "").strip().lower()
    parts = [p for p in host.split(".") if p]
    if len(parts) >= 2:
        return "." + ".".join(parts[-2:])
    return host or ".epakgroup.com"


def cookie_hosts_from_url(url: str) -> list[str]:
    host = (urlparse(url).hostname or "").strip().lower()
    wildcard = cookie_domain_from_url(url)
    hosts = [wildcard]
    if host and host not in hosts:
        hosts.append(host)
    return hosts


def build_auth_en_cookie(login_data: dict) -> str:
    """encodeURIComponent(Base64(encodeURIComponent(JSON)))."""
    payload = _linkseeks_auth_payload(login_data)
    json_str = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    encoded = base64.b64encode(quote(json_str, safe="").encode("utf-8")).decode("ascii")
    return quote(encoded, safe="")


def inject_mall_ui_auth(
    context,
    login_data: dict,
    *,
    cookie_domain: str,
    locale: str = "en-US",
    lang_cookie: str | None = None,
    cookie_names: tuple[str, ...] = ("Linkseeks_AUTH_EN", "Linkseeks_AUTH"),
    extra_hosts: list[str] | None = None,
) -> str:
    token = login_data["token"]
    auth_cookie = build_auth_en_cookie(login_data)
    lang = lang_cookie or ("ZW4tVVM=" if locale.lower().startswith("en") else "emgtQ04=")
    domains = [cookie_domain]
    for host in extra_hosts or []:
        host = (host or "").strip().lower()
        if host and host not in domains:
            domains.append(host)
    cookies = []
    for domain in domains:
        for name, value in [(n, auth_cookie) for n in cookie_names] + [("LX_LANG", lang), ("token", token)]:
            cookies.append(
                {
                    "name": name,
                    "value": value,
                    "domain": domain,
                    "path": "/",
                    "sameSite": "Lax",
                    "secure": True,
                }
            )
    context.add_cookies(cookies)
    context.set_extra_http_headers(
        {"Accept-Language": locale, "token": token, "Authorization": token}
    )
    context.add_init_script(
        f"""
        () => {{
          try {{
            const token = {json.dumps(token)};
            const auth = {json.dumps(auth_cookie)};
            const loginData = {json.dumps(login_data, ensure_ascii=False, default=str)};
            const keys = ["token", "access_token", "accessToken", "Authorization", "member_token"];
            keys.forEach((k) => window.localStorage.setItem(k, token));
            window.localStorage.setItem("isLogin", "true");
            window.localStorage.setItem("loginStatus", "1");
            window.localStorage.setItem("userInfo", JSON.stringify(loginData));
            window.localStorage.setItem("memberInfo", JSON.stringify(loginData));
            window.localStorage.setItem("loginUser", JSON.stringify(loginData));
            window.localStorage.setItem("Linkseeks_AUTH", auth);
            window.localStorage.setItem("Linkseeks_AUTH_EN", auth);
          }} catch (e) {{}}
        }}
        """
    )
    return token


def inject_epak_ui_auth(context, login_data: dict, *, cookie_domain: str, page_url: str = "") -> str:
    extra = []
    host = (urlparse(page_url).hostname or "").strip() if page_url else ""
    if host:
        extra.append(host)
    return inject_mall_ui_auth(
        context,
        login_data,
        cookie_domain=cookie_domain,
        locale="en-US",
        lang_cookie="ZW4tVVM=",
        cookie_names=("Linkseeks_AUTH_EN", "Linkseeks_AUTH"),
        extra_hosts=extra,
    )


def inject_esbao_ui_auth(context, login_data: dict, *, cookie_domain: str, page_url: str = "") -> str:
    extra = []
    host = (urlparse(page_url).hostname or "").strip() if page_url else ""
    if host:
        extra.append(host)
    return inject_mall_ui_auth(
        context,
        login_data,
        cookie_domain=cookie_domain,
        locale="zh-CN",
        lang_cookie="emgtQ04=",
        cookie_names=("Linkseeks_AUTH", "Linkseeks_AUTH_EN"),
        extra_hosts=extra,
    )
