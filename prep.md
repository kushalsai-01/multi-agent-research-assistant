# Technical Interview Preparation

## One-minute project explanation

This is a production-oriented research assistant built with React, FastAPI, LangGraph, Groq, Qdrant Cloud, and Supabase. A user submits a question and can attach private PDFs. The backend plans the work, researches current web sources, retrieves grounded PDF evidence, analyzes the evidence, streams a report, and sends the report through an independent quality gate. The UI receives every state change through Server-Sent Events, so the user sees progress and report generation in real time.

## Architecture

```text
Vercel React client
  | HTTPS + SSE
  v
Render FastAPI service
  |-- Researcher: Tavily, DuckDuckGo fallback, and RAG evidence
  |-- RAG retriever: Qdrant Cloud, session-filtered evidence
  |-- Analyst: structured findings, gaps, confidence
  |-- Writer: streamed Markdown report
  |-- Reviewer: independent QA and bounded revision loop
  |
  |-- Groq primary model -> Groq fallback model
  |-- Qdrant Cloud: vector payloads and document metadata
  |-- Supabase Postgres: scoped report history and session memory
  `-- LangSmith: traces, latency, prompts, failures
```

## Agent flow

```text
request
  -> researcher
  -> analyst
  -> low-confidence re-research, at most once
  -> writer
  -> reviewer
  -> revision, at most twice
  -> persisted final report
```

The researcher, analyst, writer, and reviewer are the four specialist agents. Document retrieval and citation formatting are internal capabilities of the research stage, not additional agents. The analyst can request targeted re-research when confidence is below the policy threshold. The reviewer is intentionally separate from the writer; it checks evidence, citations, completeness, and style before deciding whether a revision is needed.

## RAG decisions

| Concern | Decision | Why it matters |
|---|---|---|
| Chunking | Heading-aware, page-aware token chunks of 320 tokens with 64-token overlap | Keeps a claim and its nearby context together without wasting the LLM context window. |
| Context recovery | A 1,100-token parent window is stored with each child embedding | Retrieval is precise, but the generator sees enough surrounding context to avoid clipped claims. |
| Embeddings | `BAAI/bge-small-en-v1.5`, normalized cosine vectors | A fast, high-quality retrieval model that is practical on Render. The model can be swapped through configuration. |
| Retrieval | Dense top-30 candidate recall plus lexical reranking | Semantic retrieval finds paraphrases; lexical relevance protects exact names, dates, and terms. |
| Diversity | Maximum two chunks from a page and duplicate-content removal | Prevents one highly similar page from crowding out the rest of the evidence. |
| Provenance | Filename, page, section, content hash, chunk ID, and score travel with every result | Supports visible source evidence and grounded citations such as `[report.pdf p.4]`. |
| Isolation | `owner_id` filter on every upload, list, retrieval, and delete | Anonymous browser sessions cannot access each other's document corpus through the API. |
| Deployment | PDFs are read in memory; Qdrant Cloud is the durable store | Render local disk is ephemeral, so no source-of-truth document data is kept on the instance. |

The next upgrade for a larger corpus is a cross-encoder reranker, evaluated against a labeled retrieval set before enabling it. It is not included by default because it adds cold-start latency and memory pressure on a free Render instance.

## Reliability policy

- Groq calls use a primary model with a smaller fallback model.
- Transient model rate limits retry with exponential backoff up to three attempts.
- The analyst can trigger one targeted re-research pass rather than repeating the full workflow indefinitely.
- The reviewer can request at most two writer revisions.
- Optional integrations fail independently: a report can still complete when report caching, memory persistence, or document retrieval is unavailable.
- SSE communicates retries, agent failures, citations, and completion to the user instead of hiding execution state.
- LangSmith traces should be enabled in deployed environments to investigate prompt, model, and tool behavior.

## Security and data boundaries

The frontend keeps a randomly generated browser session ID in local storage. It is used as a data namespace for reports, memory, and uploaded documents. This is isolation for a portfolio app, not authentication. For a multi-user commercial release, replace it with Supabase Auth JWT verification, derive `owner_id` from the verified subject, enable Row Level Security, and use signed URLs for original document storage.

Never expose `GROQ_API_KEY`, `QDRANT_API_KEY`, Supabase service-role credentials, or LangSmith keys to Vercel. They belong only in Render environment variables.

## Deployment checklist

1. Run `docs/supabase_schema.sql` for a new Supabase project. For an existing project, run `docs/supabase_production_migration.sql` as well.
2. Create a Qdrant Cloud collection through the application or use the configured `research_documents` collection. Configure `QDRANT_URL` and `QDRANT_API_KEY` in Render.
3. In Render, configure `GROQ_API_KEY`, `GROQ_FALLBACK_MODEL`, `TAVILY_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, Qdrant variables, `LANGCHAIN_API_KEY`, and the exact `CORS_ORIGINS` Vercel origin.
4. Deploy the backend with `render.yaml` and verify `/health`.
5. In Vercel, select `frontend` as the root directory and set `VITE_API_URL` to the Render HTTPS URL.
6. Confirm the deployed browser can upload a PDF, retrieve its source pages, stream a report, load history, and delete the PDF.

## Answers to likely interview questions

**Why not put the entire PDF in the prompt?** It does not scale, increases cost, and makes it easier for the model to miss relevant evidence. Retrieval injects only the most relevant, page-attributed evidence.

**Why page-aware chunks?** A user needs to verify the answer. Page metadata turns an LLM response into an auditable response.

**Why both a reviewer and an analyst?** The analyst creates a structured evidence model before writing. The reviewer evaluates the finished artifact independently, catching unsupported claims, missing sections, and citation problems.

**How do you limit agent loops?** Low-confidence re-research is capped at one pass; writing revisions are capped at two. A bounded state machine makes cost and latency predictable.

**What would you monitor?** End-to-end latency, per-agent latency, tool and model error rates, fallback rate, retrieved-source count, reviewer pass rate, retrieval relevance from labeled queries, token cost, and abandoned SSE connections.

**What would you improve first for production scale?** Add authenticated users and RLS, async document-ingestion jobs, a persistent LangGraph checkpoint store, a cross-encoder reranker after offline evaluation, distributed rate limiting, and CI with contract, retrieval, and end-to-end tests.
