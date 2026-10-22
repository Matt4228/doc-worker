import asyncio
from types import SimpleNamespace

import pytest

from services import anthropic as service


class FakeMessages:
    """Stands in for client.messages: records the request and returns a
    canned response, so no test calls the real API."""

    def __init__(self, response):
        self.response = response
        self.request = None

    async def create(self, **kwargs):
        self.request = kwargs
        return self.response


def response(*blocks, stop_reason="end_turn"):
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason)


def thinking():
    return SimpleNamespace(type="thinking", thinking="")


def text(value):
    return SimpleNamespace(type="text", text=value)


@pytest.fixture
def fake(monkeypatch):
    def install(resp):
        messages = FakeMessages(resp)
        monkeypatch.setattr(service, "client", SimpleNamespace(messages=messages))
        return messages

    return install


def ask():
    return asyncio.run(service.ask_question(document_content="doc", message="question", history=[]))


def test_answer_skips_a_leading_thinking_block(fake):
    # The old code returned content[0].text, which crashes here: with
    # thinking on, content[0] is a thinking block and has no .text.
    fake(response(thinking(), text("The answer.")))
    assert ask() == "The answer."


def test_multiple_text_blocks_are_joined(fake):
    fake(response(text("Part one. "), text("Part two.")))
    assert ask() == "Part one. Part two."


def test_refusal_returns_a_readable_message(fake):
    fake(response(stop_reason="refusal"))
    assert ask() == service.NO_ANSWER


def test_empty_answer_returns_a_readable_message(fake):
    fake(response(thinking()))
    assert ask() == service.NO_ANSWER


def test_model_defaults_to_haiku(fake, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    messages = fake(response(text("ok")))
    ask()
    assert messages.request["model"] == "claude-haiku-5-5"


def test_model_can_be_overridden_by_env(fake, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
    messages = fake(response(text("ok")))
    ask()
    assert messages.request["model"] == "claude-sonnet-5-5"


def test_max_tokens_leaves_room_for_thinking(fake):
    messages = fake(response(text("ok")))
    ask()
    assert messages.request["max_tokens"] >= 16000
