---
tags: [area/architecture]
---

# C4 System Blueprint

> **Status (2026-05-23): cut back — the prior C4 model described a system that doesn't exist.** The earlier ~600-line blueprint laid out a microservice topology (separate ingestion / extraction / decision / publishing services + a message broker) that was never built and contradicts the real deployment. Production is a single Lightsail VM running `api` / `web` / `postgres` / `caddy`. It was also framed around SuperCoach rather than the V1 NRL-commentary product.

Rather than maintain a formal C4 of an aspirational system, the real architecture is documented where it's actually true:

- **Containers / deployment / topology** → [09-aws-architecture](09-aws-architecture.md)
- **Runtime layers + which crew member owns each** → [02-runtime-architecture](02-runtime-architecture.md)
- **Technology choices + service split** → [08-technology-stack](08-technology-stack.md)
- **Data model / lineage** → [data-lineage](data-lineage.md) + the `operations/` catalogue

A fresh C4 of the *actual* system can be written here if and when the topology grows complex enough to warrant a formal diagram. The previous content is recoverable from git history (pre-2026-05-23).
