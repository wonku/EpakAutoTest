"""按 EPAK_ENV / --env 加载英文商城环境配置（test | uat | prod）。"""
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


def bootstrap_env(cli_env: str | None = None) -> str:
    """先加载根 .env，再按环境覆盖 .env.en.{test|uat|prod}。

    必须在 import config.settings 之前调用（或由 settings 首行调用）。
    """
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    env = resolve_epak_env(cli_env or peek_cli_env())
    os.environ["EPAK_ENV"] = env
    profile = PROJECT_ROOT / f".env.en.{env}"
    if profile.is_file():
        load_dotenv(profile, override=True)
    return env


def describe_env_files(env: str | None = None) -> dict[str, str | bool]:
    name = resolve_epak_env(env)
    profile = PROJECT_ROOT / f".env.en.{name}"
    return {
        "epak_env": name,
        "base_env": str(PROJECT_ROOT / ".env"),
        "profile": str(profile),
        "profile_exists": profile.is_file(),
        "is_prod": name == "prod",
    }


def is_prod_env(env: str | None = None) -> bool:
    return resolve_epak_env(env) == "prod"
