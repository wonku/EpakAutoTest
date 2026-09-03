"""按 EPAK_ENV / --env 加载中英文商城环境配置（test | uat | prod）。

加载顺序（后者覆盖同名键）:
  1. 根目录 .env          —— 共享基础项
  2. .env.en.{env}        —— 英文商城（EPAK_* / CRM_INQUIRY_EN_*）
  3. .env.cn.{env}        —— 中文商城（PLATFORM_* / CRM_INQUIRY_BUYER_* 等）

中英文主数据必须分文件维护，互不覆盖对方专用键。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_EN_ENVS = ("test", "uat", "prod")


def resolve_epak_env(cli_env: str | None = None) -> str:
    raw = (cli_env or os.getenv("EPAK_ENV") or "test").strip().lower()
    aliases = {
        "test": "test",
        "testing": "test",
        "sit": "test",
        "dev": "test",
        "uat": "uat",
        "pre": "uat",
        "staging": "uat",
        "prod": "prod",
        "production": "prod",
        "prd": "prod",
        "live": "prod",
    }
    env = aliases.get(raw, raw)
    if env not in SUPPORTED_EN_ENVS:
        raise ValueError(
            f"不支持的环境 EPAK_ENV={raw!r}，可选: {', '.join(SUPPORTED_EN_ENVS)}"
        )
    return env


def peek_cli_env(argv: list[str] | None = None) -> str | None:
    args = argv if argv is not None else sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--env" and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith("--env="):
            return arg.split("=", 1)[1]
    return None


def _profile_path(mall: str, env: str) -> Path:
    return PROJECT_ROOT / f".env.{mall}.{env}"


def bootstrap_env(cli_env: str | None = None) -> str:
    """先加载根 .env，再按环境覆盖 .env.en.* 与 .env.cn.*。

    必须在 import config.settings 之前调用（或由 settings 首行调用）。
    """
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    env = resolve_epak_env(cli_env or peek_cli_env())
    os.environ["EPAK_ENV"] = env
    # 英文站：EPAK_* / CRM_INQUIRY_EN_* / 供应商线上报价
    en_profile = _profile_path("en", env)
    if en_profile.is_file():
        load_dotenv(en_profile, override=True)
    # 中文站：PLATFORM_* / LOGIN_* / CRM_INQUIRY_BUYER_*（不含 EN_ 前缀）
    cn_profile = _profile_path("cn", env)
    if cn_profile.is_file():
        load_dotenv(cn_profile, override=True)
    return env


def describe_env_files(env: str | None = None) -> dict[str, str | bool]:
    name = resolve_epak_env(env)
    en_profile = _profile_path("en", name)
    cn_profile = _profile_path("cn", name)
    return {
        "epak_env": name,
        "base_env": str(PROJECT_ROOT / ".env"),
        "en_profile": str(en_profile),
        "en_profile_exists": en_profile.is_file(),
        "cn_profile": str(cn_profile),
        "cn_profile_exists": cn_profile.is_file(),
        # 兼容旧字段：profile 指向英文配置
        "profile": str(en_profile),
        "profile_exists": en_profile.is_file(),
        "is_prod": name == "prod",
    }


def is_prod_env(env: str | None = None) -> bool:
    return resolve_epak_env(env) == "prod"
