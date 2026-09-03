from config.env_loader import is_prod_env, resolve_epak_env


def test_resolve_epak_env_aliases():
    assert resolve_epak_env("test") == "test"
    assert resolve_epak_env("uat") == "uat"
    assert resolve_epak_env("prod") == "prod"
    assert resolve_epak_env("production") == "prod"
    assert resolve_epak_env("prd") == "prod"
    assert is_prod_env("prod")
    assert not is_prod_env("uat")
