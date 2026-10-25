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
    usage = SimpleNamespace(input_tokens=10, output_tokens=5)
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason, usage=usage)


def thinking():
    return SimpleNamespace(type="thinking", thinking="")


def text(value):
    return SimpleNamespace(type="text", text=value)


@pytest.fixture
def fake(monkeypatch):
    def install(resp):
        messages = FakeMessages(resp)
        monkeypatch.setattr(service, "default_client", SimpleNamespace(messages=messages))
        return messages

    return install


def ask(mode="whole", **kwargs):
    result = asyncio.run(service.ask_question(context="doc", message="question", history=[], mode=mode, **kwargs))
    return result.text


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


def test_ask_question_returns_token_usage(fake):
    fake(response(text("ok")))
    result = asyncio.run(service.ask_question(context="doc", message="q", history=[], mode="whole"))
    assert (result.input_tokens, result.output_tokens) == (10, 5)


def test_model_argument_overrides_env(fake, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
    messages = fake(response(text("ok")))
    ask(model="claude-opus-5-5")
    assert messages.request["model"] == "claude-opus-5-5"


def test_mode_selects_the_system_prompt(fake):
    messages = fake(response(text("ok")))
    ask(mode="whole")
    assert messages.request["system"] == service.WHOLE_PROMPT
    ask(mode="retrieval")
    assert messages.request["system"] == service.RETRIEVAL_PROMPT


def test_whole_mode_sends_the_document_before_the_history(fake):
    messages = fake(response(text("ok")))
    ask(mode="whole")
    sent = messages.request["messages"]
    assert "doc" in sent[0]["content"]
    assert sent[-1] == {"role": "user", "content": "question"}


def test_retrieval_mode_puts_the_excerpts_with_the_question(fake):
    # Excerpts are chosen for this question, so they travel with it rather
    # than sitting at the top of the conversation.
    messages = fake(response(text("ok")))
    ask(mode="retrieval")
    last = messages.request["messages"][-1]
    assert last["role"] == "user"
    assert "doc" in last["content"] and "question" in last["content"]


def test_whole_context_marks_pages():
    assert service.whole_context(["alpha", "beta"], "alpha\n\nbeta") == "[Page 1]\nalpha\n\n[Page 2]\nbeta"


def test_whole_context_without_pages_is_the_plain_content():
    assert service.whole_context(None, "plain text") == "plain text"


def test_retrieval_context_numbers_chunks_with_pages():
    from services.retrieval import Retrieved

    chunks = [Retrieved(id=1, page=212, content="undo it"), Retrieved(id=2, page=None, content="notes")]
    assert service.retrieval_context(chunks) == "[1] (page 212)\nundo it\n\n[2]\nnotes"


def test_a_given_client_is_used_instead_of_the_module_client(fake):
    # The eval passes its own client so it never spends the demo's key.
    fake(response(text("module")))
    own = FakeMessages(response(text("own")))
    result = asyncio.run(service.ask_question(
        context="doc", message="q", history=[], mode="whole", client=SimpleNamespace(messages=own),
    ))
    assert result.text == "own"
    assert own.request is not None
