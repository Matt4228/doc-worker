# Retrieval eval

Measures how doc-worker should answer questions about a long document: send the whole thing, or retrieve the relevant passages (by keyword, by embedding, or both). The results are in [results.md](results.md).

## What it compares

Four methods, on two versions of the same book:

- **whole**: the entire document goes into the prompt, with `[Page N]` markers.
- **keyword**: Postgres full-text search picks the top chunks.
- **embedding**: Voyage embeddings and pgvector pick the chunks closest in meaning.
- **hybrid**: both searches, merged with reciprocal rank fusion.

The documents are the full Pro Git book (501 pages) and its first 100 pages. Haiku 5.5's 1M-token window fits the whole book, so whole-document prompting is a real option on both. On the full book the question is what it costs and how long it takes, not whether it fits.

## The dataset

[questions.json](questions.json) has 30 questions: 10 fact lookups, 9 "how do I", 4 whose answer spans pages, 3 follow-ups (asked after a previous question, to test that retrieval uses the conversation), and 4 the book doesn't answer, where the right answer is "the document doesn't cover this". Each has the physical PDF pages its answer is on (matching the viewer's page numbers, not the book's printed ones) and a short reference answer. The expected pages and references were checked against the PDF.

The excerpt only gets the questions whose answers fall in its first 100 pages, plus the unanswerable ones.

## Metrics

- **Correct**: a grader model (Sonnet 5.5) compares each answer with the reference answer.
- **Retrieval hit rate**: how often at least one expected page was among the retrieved chunks. This measures the search alone, before the model writes anything.
- **Citation accuracy**: the share of an answer's citations that point at an expected page.
- **Cost per question**: from the answer's token usage and the prices in [scoring.py](scoring.py).
- **Median seconds**: retrieval plus answering, per question. Answers run four at a time.

## Running it

From `backend/`, with `DATABASE_URL` pointing at a non-production database, plus `VOYAGE_API_KEY` and `ANTHROPIC_EVAL_API_KEY` in `.env`:

```
python -m eval.run --pdf eval/data/progit.pdf --estimate   # cost estimate, no model calls
python -m eval.run --pdf eval/data/progit.pdf              # the real run
```

The PDF isn't committed: download Pro Git from git-scm.com/book. The official build is over the 10 MB upload cap, so ours has its images downsampled; the text is identical on every page.

The script indexes both documents under fixed ids (they show up in the document list as `[eval] ...`) and only re-indexes when the chunk settings or embedding model change. It writes `results.json` (every answer, verdict and token count) and `results.md` (the summary tables).

## Why it isn't in CI

Every run calls real models and spends money, so it runs by hand with its own capped API key. The unit tests for the scoring functions ([tests/test_eval_scoring.py](../tests/test_eval_scoring.py)) do run in CI.
