"""Bedrock wiring: the env bearer token must reach the Bedrock client.

Regression context: botocore's default credential chain has no bearer-token
provider and langchain-aws does not auto-read AWS_BEARER_TOKEN_BEDROCK, so a
ChatBedrockConverse built without an explicit bedrock_api_key fails every
generation with NoCredentialsError — and the graph fail-closes every routine
question at Gate 2. This test pins the exact bug pattern: env var in,
client kwarg out.
"""

from __future__ import annotations

import importlib

import pytest

import src.ui.app as app


def test_build_llm_passes_bearer_token(monkeypatch):
    """build_llm must forward AWS_BEARER_TOKEN_BEDROCK as bedrock_api_key."""
    captured: dict = {}

    class FakeConverse:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("langchain_aws.ChatBedrockConverse", FakeConverse)
    # Reload AFTER patching (app's top-level load_dotenv() re-reads .env on
    # import, so set env after the reload, right before the call).
    importlib.reload(app)

    try:
        monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "test-token-123")
        app.build_llm()
    finally:
        importlib.reload(app)

    assert captured.get("bedrock_api_key") == "test-token-123"
    assert captured.get("temperature") == 0


def test_build_llm_works_without_token(monkeypatch):
    """No bearer token in env must not crash construction (fail-closed later)."""
    captured: dict = {}

    class FakeConverse:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("langchain_aws.ChatBedrockConverse", FakeConverse)
    importlib.reload(app)

    try:
        monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
        app.build_llm()
    finally:
        importlib.reload(app)

    assert captured.get("bedrock_api_key") is None
