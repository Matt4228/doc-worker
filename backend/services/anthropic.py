import os
import anthropic
from models import ChatMessage
from dotenv import load_dotenv

load_dotenv()

client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

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
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    return response.content[0].text