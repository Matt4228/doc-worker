import os
from dataclasses import dataclass
from typing import Literal
import anthropic
from models import ChatMessage
from services.retrieval import Retrieved
from dotenv import load_dotenv

load_dotenv()

default_client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# Haiku by default: the live demo runs on a capped budget, and document Q&A
# doesn't need a bigger model. Set ANTHROPIC_MODEL to switch without a deploy.
DEFAULT_MODEL = "claude-haiku-5-5"

# Current models think before answering, and thinking tokens count toward
# max_tokens. A tight cap like 1024 can be used up by thinking alone, leaving
# no room for the answer.
MAX_TOKENS = 16000

NO_ANSWER = "I couldn't produce an answer to that. Try rephrasing the question."

WHOLE_PROMPT = """You are Doc Worker, an AI assistant that answers questions about documents.
You will be given the full text of a document and a user question.
Answer clearly and concisely. If the document's pages are marked like [Page 12], cite the page right after the statement it supports, like [Page 12], and cite only pages you actually used.
If the answer cannot be found in the document, say so honestly."""

RETRIEVAL_PROMPT = """You are Doc Worker, an AI assistant that answers questions about documents.
The document is long, so you will be given numbered excerpts from it, the ones most relevant to the question, labelled like [3] (page 212).
Answer clearly and concisely using only those excerpts. Cite the excerpts you use right after the statement they support, like [3] or [1, 4].
If the excerpts don't contain the answer, say the document doesn't appear to cover it rather than guessing."""

@dataclass
class AnswerResult:
    text: str
    input_tokens: int
    output_tokens: int

def whole_context(pages: list[str] | None, content: str) -> str:
    """The whole document, with [Page N] markers when the pages are known
    so the model can cite them."""
    if pages is None:
        return content
    return "\n\n".join(f"[Page {n}]\n{text}" for n, text in enumerate(pages, start=1))

def retrieval_context(chunks: list[Retrieved]) -> str:
    """Retrieved chunks numbered from 1, each with its page when known."""
    parts = []
    for n, chunk in enumerate(chunks, start=1):
        label = f"[{n}] (page {chunk.page})" if chunk.page is not None else f"[{n}]"
        parts.append(f"{label}\n{chunk.content}")
    return "\n\n".join(parts)

async def ask_question(
    context: str,
    message: str,
    history: list[ChatMessage],
    mode: Literal["whole", "retrieval"],
    model: str | None = None,
    client: anthropic.AsyncAnthropic | None = None,
) -> AnswerResult:
    """client and model let the eval use its own key and model."""
    history_messages = [{"role": msg.role, "content": msg.content} for msg in history]

    if mode == "whole":
        # The document opens the conversation, the same for every question.
        messages = [
            {"role": "user", "content": f"Here is the document you will answer questions about:\n\n{context}"},
            {"role": "assistant", "content": "Understood. I have read the document and am ready to answer your questions."},
            *history_messages,
            {"role": "user", "content": message},
        ]
    else:
        # Excerpts are chosen for this question, so they travel with it.
        messages = [
            *history_messages,
            {"role": "user", "content": f"Excerpts from the document:\n\n{context}\n\nQuestion: {message}"},
        ]

    response = await (client or default_client).messages.create(
        model=model or os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL),
        max_tokens=MAX_TOKENS,
        system=WHOLE_PROMPT if mode == "whole" else RETRIEVAL_PROMPT,
        messages=messages,
    )

    # The response is a list of blocks, and with thinking on the first one is
    # a thinking block with no .text. Only the text blocks are the answer.
    answer = "".join(block.text for block in response.content if block.type == "text")

    # A safety refusal (stop_reason "refusal") can come back with no text.
    if response.stop_reason == "refusal" or not answer.strip():
        answer = NO_ANSWER
    return AnswerResult(
        text=answer,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
