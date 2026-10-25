import json
import re
from models import Source

# Per million tokens, from Anthropic's pricing on 2026-10-06. Check the
# pricing page before quoting results that depend on these.
# Haiku 5.5 charges more for prompts over 100K tokens.
PRICES = {
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "long_input": 0.50, "long_output": 2.50, "long_above": 100_000},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00},
}

def cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Dollar cost of one request."""
    price = PRICES[model]
    long = input_tokens > price.get("long_above", float("inf"))
    per_input = price["long_input"] if long else price["input"]
    per_output = price["long_output"] if long else price["output"]
    return (input_tokens * per_input + output_tokens * per_output) / 1_000_000

def hit(retrieved_pages: list[int | None], expected: list[int]) -> bool | None:
    """Whether retrieval found at least one page the answer is on. None
    for questions the document can't answer, where there's nothing to find."""
    if not expected:
        return None
    return any(page in expected for page in retrieved_pages)

def cited_pages(answer: str, sources: list[Source]) -> list[int]:
    """The page of every [[n]] marker in a checked answer, in order."""
    pages = []
    for n in re.findall(r"\[\[(\d+)\]\]", answer):
        page = sources[int(n) - 1].page
        if page is not None:
            pages.append(page)
    return pages

def citation_accuracy(cited: list[int], expected: list[int]) -> float | None:
    """The share of citations that point at an expected page. None when
    nothing was cited or the question has no right page."""
    if not cited or not expected:
        return None
    return sum(page in expected for page in cited) / len(cited)

def parse_verdict(reply: str) -> tuple[bool | None, str]:
    """Read the grader's {"correct": ..., "reason": ...} from its reply."""
    match = re.search(r"\{.*\}", reply, re.DOTALL)
    try:
        verdict = json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        verdict = None
    if not isinstance(verdict, dict) or not isinstance(verdict.get("correct"), bool):
        return None, f"Grader reply had no verdict: {reply.strip()[:200]}"
    return verdict["correct"], str(verdict.get("reason", ""))
