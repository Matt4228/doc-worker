import os
import anthropic
from models import ChatMessage
from dotenv import load_dotenv

load_dotenv()

client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# Haiku by default: the live demo runs on a capped budget, and document Q&A
# doesn't need a bigger model. Set ANTHROPIC_MODEL to switch without a deploy.
DEFAULT_MODEL = "claude-haiku-5-5"

# Current models think before answering, and thinking tokens count toward
# max_tokens. A tight cap like 1024 can be used up by thinking alone, leaving
# no room for the answer.
MAX_TOKENS = 16000

NO_ANSWER = "I couldn't produce an answer to that. Try rephrasing the question."

SYSTEM_PROMPT = """You are Doc Worker, an AI assitant that answers questions about documents.
You will be given the full text of a document and a user question.
Answer clearly and concisely, citing specific parts of the coument where relevant.
If the answer cannot be found in the document, say so honestly."""

async def ask_question(
    document_content: str,
    message: str,
    history: list[ChatMessage],
) -> str:
    messages = []

    messages.append({
        "role": "user",
        "content": f"Here is the document you will answer questions about:\n\n{document_content}",
    })
    messages.append({
        "role": "assistant",
        "content": "Understood. I have read the doument and am ready to answer your questions.",
    })

    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": message})

    response = await client.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL),
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    # The response is a list of blocks, and with thinking on the first one is
    # a thinking block with no .text. Only the text blocks are the answer.
    answer = "".join(block.text for block in response.content if block.type == "text")

    # A safety refusal (stop_reason "refusal") can come back with no text.
    if response.stop_reason == "refusal" or not answer.strip():
        return NO_ANSWER
    return answer