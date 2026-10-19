from pathlib import Path

import pytest
import sync_workspace as sw


def make_service(root: Path, name: str, compose_env: str | None = None) -> None:
    (root / "services" / name / "service").mkdir(parents=True)
    (root / "services" / name / "contracts").mkdir(parents=True)
    (root / "services" / name / "service" / "pyproject.toml").write_text("")
    (root / "services" / name / "contracts" / "pyproject.toml").write_text("")
    if compose_env is not None:
        (root / "services" / name / "service" / "compose.env").write_text(compose_env)


def test_compose_env_is_read_per_service_and_ignores_comments(tmp_path: Path) -> None:
    make_service(
        tmp_path,
        "mail",
        "# comment\n\nMAIL_HOST=mailpit\nMAIL_PORT=1025\nMAIL_URL=smtp://${HOST:-x}:1\n",
    )
    assert sw.read_compose_env(tmp_path, "mail") == [
        ("MAIL_HOST", "mailpit"),
        ("MAIL_PORT", "1025"),
        ("MAIL_URL", "smtp://${HOST:-x}:1"),
    ]
    assert sw.read_compose_env(tmp_path, "absent") == []


def test_compose_env_flows_into_the_generated_app_env_block(tmp_path: Path) -> None:
    make_service(tmp_path, "mail", 'MAIL_NAME=say "hi"\n')
    blocks = sw.compose_blocks(["mail"], tmp_path)
    assert blocks["app-env"][0].startswith("MAIL_DATABASE_URL: ")
    assert blocks["app-env"][1] == 'MAIL_NAME: "say \\"hi\\""'  # valid YAML double-quoted scalar


def test_malformed_compose_env_fails_loudly(tmp_path: Path) -> None:
    make_service(tmp_path, "mail", "not a pair\n")
    with pytest.raises(SystemExit):
        sw.read_compose_env(tmp_path, "mail")


def test_provision_sql_is_idempotent_and_per_service() -> None:
    sql = sw.render_provision_sql(["auth", "users"])
    assert sql.count("CREATE SCHEMA IF NOT EXISTS") == 2
    assert "CREATE ROLE auth LOGIN" in sql and "CREATE ROLE users LOGIN" in sql
