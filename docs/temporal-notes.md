---
tags: [area/architecture]
---

# Temporal

**Created:** 2026-03-09
**Last reviewed:** 2026-03-09
**Status:** New

## Overview

Temporal is a durable execution platform — it lets you write code that survives crashes, restarts, and infrastructure failures without you manually handling retries, state persistence, or recovery logic. You write workflows as normal functions; Temporal guarantees they run to completion, even if the process dies mid-execution.

In Jaromelu, Temporal is the backbone: it orchestrates the entire pipeline from content ingestion through extraction, decisioning, and publishing. It replaces what would otherwise be a fragile chain of queues, cron jobs, and retry logic.

## Key Concepts

- **Workflow** — A durable function that defines the *sequence* of work. Survives crashes. Deterministic: same inputs always produce the same execution path. In Jaromelu, the orchestrator service owns all workflow definitions.
- **Activity** — A regular function that does the actual *work* (API calls, DB writes, ML inference). Non-deterministic, can fail. Temporal retries them according to your policy. In Jaromelu, each worker service (ingestion, extraction, decision, publishing) registers its own activities.
- **Worker** — A process that polls a Task Queue and executes workflows or activities. You run as many as you need for throughput.
- **Task Queue** — A named queue that routes work to the right workers. Jaromelu uses separate queues: `orchestrator`, `ingestion`, `extraction`, `decision`, `publishing`.
- **Workflow ID** — A unique, deterministic identifier for a workflow execution. Prevents duplicate runs (idempotency). Jaromelu plans readable IDs like `ingest-<source>-<date>`.
- **Temporal Client** — How your application code (e.g., the API service) starts workflows and queries their state.
- **Namespace** — Logical isolation boundary. Jaromelu uses the `jeromelu` namespace.
- **Schedule** — Temporal's built-in cron replacement. Triggers workflows on a recurring basis without external schedulers.
- **Signal** — A way to send data to a running workflow from the outside (e.g., "new content arrived, process it now").
- **Query** — Read the current state of a running workflow without affecting it.
- **Child Workflow** — A workflow started by another workflow. Useful for fan-out patterns (e.g., process 50 articles in parallel).

## How It Works

### The Core Mental Model

Think of Temporal as a **replay engine**. Your workflow function runs, and every time it calls an activity or sleeps, Temporal records that event in a persistent history. If the worker crashes mid-workflow:

1. A new worker picks up the workflow
2. Temporal replays the history — fast-forwarding through already-completed steps
3. Execution resumes from exactly where it left off

This is why workflows must be **deterministic** — the replay has to produce the same sequence of events. No random numbers, no reading the clock, no direct I/O inside workflows. All side effects go in activities.

### Jaromelu Architecture (Dedicated Orchestrator Pattern)

```
API Service
    │
    ▼ (starts workflow via Temporal Client)
Orchestrator Worker  ──────  "orchestrator" task queue
    │
    ├──▶ Ingestion Worker  ──  "ingestion" task queue
    │       (scrape, transcribe, fetch)
    │
    ├──▶ Extraction Worker  ──  "extraction" task queue
    │       (entity extraction, quote extraction)
    │
    ├──▶ Decision Worker  ──  "decision" task queue
    │       (scoring, ranking, strategy)
    │
    └──▶ Publishing Worker  ──  "publishing" task queue
            (feed events, voice rendering)
```

The orchestrator workflow calls activities on remote task queues. Each worker only registers its own activities — it doesn't know about the overall pipeline. This separation means you can scale, deploy, and version each worker independently.

### Activity Retry Policies

Temporal retries failed activities automatically. You configure:
- **Initial interval** — wait before first retry (e.g., 1s)
- **Backoff coefficient** — multiplier per retry (e.g., 2.0 = exponential backoff)
- **Maximum attempts** — give up after N tries
- **Maximum interval** — cap on backoff duration
- **Non-retryable errors** — errors that should fail immediately (e.g., validation errors)

### Python SDK Patterns

```python
# Defining a workflow
@workflow.defn
class ProcessContentWorkflow:
    @workflow.run
    async def run(self, content_id: str) -> ProcessResult:
        # Execute activity on the ingestion worker's task queue
        raw = await workflow.execute_activity(
            ingest_content,
            content_id,
            task_queue="ingestion",
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        # Next step on a different task queue
        extracted = await workflow.execute_activity(
            extract_entities,
            raw,
            task_queue="extraction",
            start_to_close_timeout=timedelta(minutes=10),
        )
        return extracted

# Defining an activity
@activity.defn
async def ingest_content(content_id: str) -> RawContent:
    # This is where real I/O happens — API calls, DB reads, etc.
    ...

# Running a worker
async def main():
    client = await Client.connect("localhost:7233", namespace="jeromelu")
    worker = Worker(
        client,
        task_queue="ingestion",
        activities=[ingest_content],
    )
    await worker.run()
```

## Common Pitfalls / Misconceptions

- **"Workflows are like background jobs"** — No. Workflows are long-lived, stateful orchestrations. A single workflow can run for days or months. Don't think of them as fire-and-forget tasks.
- **Non-determinism in workflows** — Using `datetime.now()`, `random()`, or `uuid4()` inside a workflow breaks replay. Use `workflow.now()`, `workflow.random()`, and pass IDs in as parameters.
- **Giant workflows** — Temporal has a history size limit (~50K events). If your workflow runs thousands of activities, use Continue-As-New to reset the history while preserving logical continuity.
- **Confusing task queues** — If you register a workflow on queue A but try to start it targeting queue B, nothing will pick it up. Make sure your client targets the correct queue.
- **Over-retrying** — Default retry is infinite. Always set `maximum_attempts` or `schedule_to_close_timeout` to avoid zombies.
- **Treating activities like workflows** — Activities don't have durable state. If an activity crashes halfway, it restarts from the beginning, not from where it left off. Keep activities short and focused.

## Practice Questions

1. Why must workflow code be deterministic? What happens during replay if it isn't?
2. Your ingestion activity is calling an external API that's rate-limited. How would you configure the retry policy to handle 429 responses gracefully?
3. In Jaromelu's architecture, why use a dedicated orchestrator worker instead of having each worker register both workflows and activities?
4. A workflow processes 10,000 articles by calling an activity for each one. After a few weeks, it starts failing. What's likely wrong, and how do you fix it?
5. How would you use Temporal Schedules to replace a cron job that triggers content ingestion every 6 hours?

## Resources

- Temporal documentation: docs.temporal.io
- Temporal Python SDK: github.com/temporalio/sdk-python
- "What is Temporal?" core concepts page: docs.temporal.io/temporal
- Temporal 101 course (free): learn.temporal.io/courses/temporal_101
- Temporal Python SDK samples: github.com/temporalio/samples-python
