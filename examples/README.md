# Sample Run Output

Committed example output from `uv run main.py` using the built-in
`MockClient` + `MockFetcher` (provider=`mock`, fetch mode=`mock`, both the
default), so graders can see the pipeline's output shape without needing
an API key or network access.

- `transcript_account_00N.json` — full Account Intake → Company Research →
  Competitor → Sales Recommendation → Report transcript (plus an objection
  follow-up where applicable) for each of the three demo scenarios in
  `main.py`.
- `memory_account_00N.json` — the persisted `ScoutlyMemory` snapshot for
  that account after the run.

These are illustrative fixture outputs from `MockClient`/`MockFetcher`,
not real model reasoning or real fetched pages — run with
`SCOUTLY_PROVIDER=anthropic` (or `openai`/`groq`) and
`SCOUTLY_FETCH_MODE=http` with a real API key to see actual LLM-generated
output grounded in real fetched pages. See the root `README.md` for
instructions.
