"""Managed-Postgres URL handling (Render/Neon). No database connection needed."""

import pytest

from backend.db.session import _normalise_url


def test_heroku_style_scheme_is_rewritten_to_psycopg2():
    url = _normalise_url("postgres://user:pw@db.example.com:5432/app")
    assert url.startswith("postgresql+psycopg2://")


def test_plain_postgresql_scheme_gets_an_explicit_driver():
    url = _normalise_url("postgresql://user:pw@db.example.com:5432/app")
    assert url == "postgresql+psycopg2://user:pw@db.example.com:5432/app?sslmode=require"


def test_remote_hosts_require_tls():
    url = _normalise_url("postgresql://u:p@ep-cool-123.eu-central-1.aws.neon.tech/neondb")
    assert url.endswith("?sslmode=require")


def test_local_hosts_do_not_force_tls():
    for host in ("localhost", "127.0.0.1", "db"):
        url = _normalise_url(f"postgresql://u:p@{host}:5432/app")
        assert "sslmode" not in url, host


def test_existing_sslmode_is_preserved():
    url = _normalise_url("postgresql://u:p@remote.example.com/app?sslmode=verify-full")
    assert url.count("sslmode=") == 1
    assert "sslmode=verify-full" in url


def test_existing_query_string_is_extended_not_replaced():
    url = _normalise_url("postgresql://u:p@remote.example.com/app?application_name=signal")
    assert "application_name=signal" in url
    assert "&sslmode=require" in url


@pytest.mark.parametrize("scheme", ["postgres://", "postgresql://"])
def test_idempotent_scheme_detection(scheme):
    url = _normalise_url(f"{scheme}u:p@localhost:5432/app")
    assert url.startswith("postgresql+psycopg2://")
