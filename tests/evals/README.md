# Ask Me Evaluations

DeepEval-based evaluation suite for JeromeLu's Ask Me chat feature.

## Setup

```bash
pip install deepeval pyyaml
```

Requires environment variables:
- `OPENAI_API_KEY` — used by DeepEval's evaluation LLM
- `DATABASE_URL` — PostgreSQL connection for knowledge base queries

## Running

```bash
# Run all eval tests
deepeval test run tests/evals/test_ask_me.py

# Run with verbose output
deepeval test run tests/evals/test_ask_me.py -v

# Run a specific test
deepeval test run tests/evals/test_ask_me.py -k "trade Cleary"
```

## Golden Examples

Golden examples live in `golden/ask_me_golden.yaml`. Each example has:

| Field | Description |
|-------|-------------|
| `question` | The user question to test |
| `temperature` | Tone mode (straight/sharp/roast) |
| `expected_topics` | Topics the answer should reference |
| `must_not_contain` | Forbidden terms (hallucination guard) |
| `context_type` | Optional KB type filter |
| `notes` | Why this example exists |

## Adding Examples

After real user interactions, save interesting Q&A pairs:

```yaml
- question: "Is Ponga worth the price tag?"
  temperature: "sharp"
  expected_topics: ["Kalyn Ponga", "price"]
  must_not_contain: []
  context_type: null
  notes: "Premium player value question"
```

## Metrics

| Metric | What it catches | Threshold |
|--------|----------------|-----------|
| Faithfulness | Answer grounded in KB context? | 0.7 |
| Hallucination | Invents stats or players? | 0.7 |
| Answer Relevancy | Actually answers the question? | 0.7 |
| NRL Voice (GEval) | In-character, opinionated, uses jargon? | 0.6 |
| No Fabrication (GEval) | Makes up specific numbers? | 0.8 |
