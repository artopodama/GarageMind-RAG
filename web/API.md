# GarageMind API

The frontend (`web/`) is served by the same FastAPI app that exposes the RAG
endpoints, so it calls these same-origin. Base URL in dev: `http://127.0.0.1:8000`.

## `GET /health`
```json
{ "status": "ok" }
```

## `POST /ask`
Ask a maintenance question, optionally scoped to a vehicle.

**Request**
```json
{
  "question": "What is the recommended tyre pressure?",
  "make": "Honda",      // optional; enables vehicle scoping
  "model": "Civic",     // optional
  "year": 2019,         // optional
  "reasoning": false    // optional; true routes to the reasoning model
}
```

**Response**
```json
{
  "text": "The recommended tyre pressure is ... [Honda Civic - Tyres].",
  "refused": false,
  "safety_critical": true,
  "scoped": true,
  "manual_id": "honda/civic/4-door-2017-2023",
  "top_score": 0.83,
  "citations": ["honda/civic/.../tyres.md::a1b2c3d4", "..."],
  "sources": [
    {
      "label": "Honda Civic 4-door-2017-2023 - Tyres",
      "make": "Honda", "model": "civic", "variant": "4-door-2017-2023",
      "section": "tyres",
      "source_url": "https://www.mycarusermanual.com/honda/civic/4-door/2017-2023/tyres"
    }
  ],
  "top_passage": "Recommended tyre inflation pressure (cold): ..."
}
```

Field notes for the UI:
- `refused: true` → render the amber "not covered" card; `text` is the refusal
  message, `sources`/`citations` are empty.
- `safety_critical: true` → show the shield/trust indicator on the answer card.
- `scoped: false` → the question was answered without a resolved vehicle manual
  (either no vehicle selected, or that make/model/year has no matching manual);
  `manual_id` is `null`.
- `sources` is de-duplicated by (manual_id, section) — use it for the citation
  chip(s); `top_passage` is the highest-ranked manual excerpt for the expandable
  "source excerpt" view.
- `top_score` is the cross-encoder reranker score of the best passage; answers
  below the server's `REFUSAL_SCORE` threshold are refused before generation.

## Notes
- Generation runs locally via **Ollama** (`qwen2.5:7b-instruct`) behind the
  OpenAI-compatible endpoint; no external API key required.
- Only vehicles whose manuals have been indexed return grounded answers. Others
  fall back to unscoped retrieval or a refusal.
