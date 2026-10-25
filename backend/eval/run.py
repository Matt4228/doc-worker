"""Compare whole-document prompting with keyword, embedding and hybrid
retrieval on a long PDF. See eval/README.md.

Run from backend/:

    python -m eval.run --pdf eval/data/progit.pdf --estimate   # cost only, no model calls
    python -m eval.run --pdf eval/data/progit.pdf              # the real run
"""
import argparse
import asyncio
import json
import os
import statistics
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import anthropic
import asyncpg
from dotenv import load_dotenv

load_dotenv()

from db import SCHEMA_SQL  # noqa: E402
from eval.scoring import citation_accuracy, cited_pages, cost, hit, parse_verdict  # noqa: E402
from models import ChatMessage, Source  # noqa: E402
from routes.chat import retrieval_query  # noqa: E402
from services.anthropic import ask_question, retrieval_context, whole_context  # noqa: E402
from services.chunker import CHUNK_WORDS, OVERLAP_WORDS, chunk_pages  # noqa: E402
from services.citations import cite_retrieval, cite_whole, strip_citations  # noqa: E402
from services.embeddings import EMBED_MODEL  # noqa: E402
from services.indexing import embed_chunks, store_chunks  # noqa: E402
from services.parser import extract_pages  # noqa: E402
from services.retrieval import TOP_K, retrieve  # noqa: E402

HERE = Path(__file__).parent
METHODS = ["whole", "keyword", "embedding", "hybrid"]
ANSWER_MODEL = "claude-haiku-5-5"
GRADER_MODEL = "claude-sonnet-5-5"
CONCURRENCY = 4

GRADER_PROMPT = """You grade answers to questions about a book, comparing each answer with a reference answer.
An answer is correct if it gives the key facts of the reference without contradicting it. Extra correct detail is fine.
When the reference says the document doesn't cover the question, the answer is correct only if it says so instead of inventing an answer.
Reply with only a JSON object: {"correct": true or false, "reason": "one sentence"}."""

@dataclass
class Answer:
    text: str
    sources: list[Source]
    retrieved_pages: list[int | None] | None  # None in whole mode
    input_tokens: int
    output_tokens: int

def applies(question: dict, document: str, excerpt_pages: int) -> bool:
    """The excerpt only gets questions whose answers are inside it, plus
    the unanswerable ones."""
    return document == "full" or all(page <= excerpt_pages for page in question["expected_pages"])

async def ensure_indexed(pool, name: str, pages: list[str]) -> uuid.UUID:
    """Store an eval document under a fixed id, re-indexing only when the
    chunk settings or embedding model change (they're in the filename)."""
    document_id = uuid.uuid5(uuid.NAMESPACE_URL, f"doc-worker-eval-{name}")
    label = f"[eval] progit {name}, {len(pages)} pages, chunks {CHUNK_WORDS}/{OVERLAP_WORDS}, {EMBED_MODEL}"
    async with pool.acquire() as conn:
        current = await conn.fetchval(
            "SELECT filename FROM documents WHERE id = $1 AND EXISTS (SELECT 1 FROM chunks WHERE document_id = $1)",
            document_id,
        )
        if current == label:
            return document_id
        print(f"indexing {label}")
        chunks = chunk_pages(pages, paged=True)
        vectors = await embed_chunks(chunks)
        async with conn.transaction():
            await conn.execute("DELETE FROM documents WHERE id = $1", document_id)
            await conn.execute(
                "INSERT INTO documents (id, filename, content, content_type, pages) VALUES ($1, $2, $3, 'application/pdf', $4)",
                document_id, label, "\n\n".join(pages), pages,
            )
            await store_chunks(conn, document_id, chunks, vectors)
    return document_id

async def answer(client, pool, document_id, pages, question, history, method, k) -> Answer:
    """Answer one question the way the app would for the given method."""
    if method == "whole":
        result = await ask_question(
            whole_context(pages, "\n\n".join(pages)), question, history, "whole", model=ANSWER_MODEL, client=client,
        )
        text, sources = cite_whole(result.text, len(pages))
        retrieved = None
    else:
        async with pool.acquire() as conn:
            chunks = await retrieve(conn, document_id, retrieval_query(question, history), k=k, method=method)
        result = await ask_question(
            retrieval_context(chunks), question, history, "retrieval", model=ANSWER_MODEL, client=client,
        )
        text, sources = cite_retrieval(result.text, chunks)
        retrieved = [c.page for c in chunks]
    return Answer(text, sources, retrieved, result.input_tokens, result.output_tokens)

async def grade(client, question: dict, text: str) -> tuple[bool | None, str, int, int]:
    response = await client.messages.create(
        model=GRADER_MODEL,
        max_tokens=4000,
        output_config={"effort": "low"},
        system=GRADER_PROMPT,
        messages=[{"role": "user", "content": (
            f"Question: {question['question']}\n\nReference answer: {question['reference']}\n\n"
            f"Answer to grade: {strip_citations(text)}"
        )}],
    )
    reply = "".join(block.text for block in response.content if block.type == "text")
    correct, reason = parse_verdict(reply)
    return correct, reason, response.usage.input_tokens, response.usage.output_tokens

async def run_one(client, pool, document, document_id, pages, question, method, k) -> dict:
    row = {"document": document, "id": question["id"], "kind": question["kind"], "method": method}
    # A follow-up needs a real earlier turn: answer the previous question
    # first, the same way, and pass that exchange as history.
    history: list[ChatMessage] = []
    if question["previous"]:
        previous = await answer(client, pool, document_id, pages, question["previous"], [], method, k)
        history = [
            ChatMessage(role="user", content=question["previous"]),
            ChatMessage(role="assistant", content=strip_citations(previous.text)),
        ]
    started = time.perf_counter()
    result = await answer(client, pool, document_id, pages, question["question"], history, method, k)
    seconds = time.perf_counter() - started
    correct, reason, grader_in, grader_out = await grade(client, question, result.text)
    cited = cited_pages(result.text, result.sources)
    row.update(
        status="ok",
        correct=correct,
        reason=reason,
        hit=None if result.retrieved_pages is None else hit(result.retrieved_pages, question["expected_pages"]),
        retrieved_pages=result.retrieved_pages,
        cited_pages=cited,
        citation_accuracy=citation_accuracy(cited, question["expected_pages"]),
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost=cost(ANSWER_MODEL, result.input_tokens, result.output_tokens),
        grader_cost=cost(GRADER_MODEL, grader_in, grader_out),
        seconds=round(seconds, 2),
        answer=result.text,
    )
    return row

def estimate(plan, documents, methods, k) -> None:
    """Rough upper-end cost without calling any model. Input is chars / 4;
    output allows for thinking."""
    output_per_answer, grader_in, grader_out = 1500, 1000, 800
    chunk_tokens = CHUNK_WORDS * 1.4
    answers = grader = 0.0
    calls = 0
    for document, question in plan:
        whole_tokens = sum(len(p) for p in documents[document]) / 4
        for method in methods:
            input_tokens = whole_tokens if method == "whole" else k * chunk_tokens + 300
            # A follow-up answers its previous question first.
            times = 2 if question["previous"] else 1
            answers += times * cost(ANSWER_MODEL, int(input_tokens), output_per_answer)
            grader += cost(GRADER_MODEL, grader_in, grader_out)
            calls += times + 1
    print(f"{len(plan)} question/document pairs x {len(methods)} methods = {calls} model calls")
    print(f"estimated answers ${answers:.2f} + grading ${grader:.2f} = ${answers + grader:.2f}")
    print("Voyage: one-time indexing of both documents (free voyage-4 tokens), plus one query embedding per retrieval answer.")

def summarize(rows, meta) -> str:
    lines = [
        "# Retrieval eval results",
        "",
        f"Run {meta['date']}: answers by {ANSWER_MODEL}, graded by {GRADER_MODEL} (effort low).",
        f"Top {meta['k']} chunks of {CHUNK_WORDS} words ({OVERLAP_WORDS} overlap), embeddings from {EMBED_MODEL}.",
        f"Total spend: ${meta['spend']:.2f} (answers plus grading).",
        "",
    ]
    for document in ("full", "excerpt"):
        doc_rows = [r for r in rows if r["document"] == document]
        if not doc_rows:
            continue
        lines += [
            f"## {document} ({meta['pages'][document]} pages)",
            "",
            "| Method | Correct | Retrieval hit rate | Citation accuracy | Mean cost / question | Median seconds |",
            "|---|---|---|---|---|---|",
        ]
        for method in meta["methods"]:
            mrows = [r for r in doc_rows if r["method"] == method]
            if any(r["status"] == "does not fit" for r in mrows):
                lines.append(f"| {method} | does not fit | | | | |")
                continue
            ok = [r for r in mrows if r["status"] == "ok"]
            graded = [r for r in ok if r["correct"] is not None]
            hits = [r["hit"] for r in ok if r["hit"] is not None]
            accuracy = [r["citation_accuracy"] for r in ok if r["citation_accuracy"] is not None]

            def pct(values):
                return f"{100 * sum(values) / len(values):.0f}% ({len(values)})" if values else "n/a"

            lines.append(" | ".join([
                f"| {method}",
                pct([r["correct"] for r in graded]),
                pct(hits),
                f"{100 * statistics.mean(accuracy):.0f}%" if accuracy else "n/a",
                f"${statistics.mean(r['cost'] for r in ok):.4f}" if ok else "n/a",
                f"{statistics.median(r['seconds'] for r in ok):.1f}" if ok else "n/a",
            ]) + " |")
        errors = [r for r in doc_rows if r["status"] == "error"]
        if errors:
            lines.append(f"\n{len(errors)} answers failed with an API error; see results.json.")
        lines.append("")
    return "\n".join(lines)

async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--excerpt-pages", type=int, default=100)
    parser.add_argument("--methods", default=",".join(METHODS))
    parser.add_argument("--k", type=int, default=TOP_K)
    parser.add_argument("--estimate", action="store_true", help="print the estimated cost and exit")
    args = parser.parse_args()
    methods = args.methods.split(",")

    pages = extract_pages(Path(args.pdf).read_bytes(), "application/pdf")
    documents = {"full": pages, "excerpt": pages[:args.excerpt_pages]}
    questions = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))
    plan = [(d, q) for d in documents for q in questions if applies(q, d, args.excerpt_pages)]

    if args.estimate:
        estimate(plan, documents, methods, args.k)
        return 0

    key = os.environ.get("ANTHROPIC_EVAL_API_KEY")
    if not key:
        print("ANTHROPIC_EVAL_API_KEY is not set. The eval never uses the demo's key.", file=sys.stderr)
        return 1
    client = anthropic.AsyncAnthropic(api_key=key)
    pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], max_size=CONCURRENCY + 1)
    try:
        async with pool.acquire() as conn:
            await conn.execute(SCHEMA_SQL)
        ids = {name: await ensure_indexed(pool, name, doc_pages) for name, doc_pages in documents.items()}

        semaphore = asyncio.Semaphore(CONCURRENCY)
        too_long: set[str] = set()
        done = 0

        async def task(document, question, method):
            nonlocal done
            async with semaphore:
                if method == "whole" and document in too_long:
                    row = {"document": document, "id": question["id"], "kind": question["kind"], "method": method, "status": "does not fit"}
                else:
                    try:
                        row = await run_one(client, pool, document, ids[document], documents[document], question, method, args.k)
                    except anthropic.BadRequestError as e:
                        # The likeliest 400 here is a prompt over the context window.
                        if method == "whole":
                            too_long.add(document)
                        row = {"document": document, "id": question["id"], "kind": question["kind"], "method": method,
                               "status": "does not fit" if method == "whole" else "error", "error": str(e)}
                    except anthropic.APIError as e:
                        row = {"document": document, "id": question["id"], "kind": question["kind"], "method": method,
                               "status": "error", "error": str(e)}
                done += 1
                print(f"[{done}/{len(plan) * len(methods)}] {document} {question['id']} {method}: "
                      f"{row['status']} {'' if row.get('correct') is None else ('correct' if row['correct'] else 'wrong')}")
                return row

        rows = await asyncio.gather(*(task(d, q, m) for d, q in plan for m in methods))
    finally:
        await pool.close()

    meta = {
        "date": date.today().isoformat(),
        "k": args.k,
        "methods": methods,
        "pages": {name: len(p) for name, p in documents.items()},
        "spend": sum(r.get("cost", 0) + r.get("grader_cost", 0) for r in rows),
    }
    (HERE / "results.json").write_text(json.dumps({"meta": meta, "rows": rows}, indent=2), encoding="utf-8")
    (HERE / "results.md").write_text(summarize(rows, meta), encoding="utf-8")
    print(summarize(rows, meta))
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
