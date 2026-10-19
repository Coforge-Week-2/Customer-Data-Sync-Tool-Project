# Customer Data Sync Tool (Team 2)

> Context file for AI agents and contributors. Read this before making changes. Items marked **LOCKED** must not change without team agreement.

## 1. Project Summary

A customer keeps contact records in an external system and needs them copied into a local database every day. The data arrives messy and the connection sometimes fails, so manual re-runs are not reliable.

**Deliverable:** a command-line tool that:

1. Pulls customer records from the Random User API.
2. Cleans and validates the data.
3. Stores records in a local SQLite database.
4. Prints a sync summary: records **added**, **updated**, **unchanged**, **rejected**.

The tool also supports `--from-file <path>` to read a saved API response (for demos and testing, no network needed).

## 2. Data Source

- API: `https://randomuser.me/api/` (no API key required)
- Use the `seed`, `results`, and `page` query parameters to get stable, reproducible data.

Example: `https://randomuser.me/api/?seed=team2&results=50&page=1`

## 3. Agreed Decisions (LOCKED)

These are confirmed on Monday, before coding begins, and recorded in the README. Do not change without team agreement.

| Decision | Value |
|---|---|
| Clean customer record shape (fields and types) | **TBD: fill in once agreed, mirror in README** |
| Unique identifier | **TBD: `login.uuid` or `email`** (pick one) |

> Agents: if these are still TBD, do not invent them. Ask the team or check the README for the agreed values.

## 4. Architecture

Pipeline, one module per stage:

```
API Client  ->  Cleaning/Validation  ->  SQLite Storage  ->  CLI summary
(fetch,         (Customer class,         (upsert, counts)     (--from-file,
 retries)        reject bad records)                           integration)
```

`--from-file` replaces the API Client stage with a saved response file.

## 5. Components and Ownership

### 5.1 API Client: Vedant Misra

**Builds**
- Client class that fetches paged results from the API using a seed.
- Retries on failure; raises a clear error when retries are exhausted.
- pytest tests using saved responses (no internet needed).

**Presentation:** live API call demo and failure handling; discussion of retry limits and potential issues.

**Q&A to be ready for**
- What happens if the API is down during the nightly job?
- How to add a second data source without a rewrite?

### 5.2 Data Cleaning & Validation: Julian Marchington

**Builds**
- Transforms raw API records into the agreed clean format.
- Flags or rejects bad records: missing fields, wrong types, duplicates.
- A `Customer` class for downstream use.
- pytest tests covering both accepted and rejected records.

**Presentation:** before-and-after view of sample data; list of rejected records with reasons.

**Q&A to be ready for**
- Should bad records be fixed or rejected? Who decides?
- What if the API changes a field name overnight?

### 5.3 SQLite Storage: Nikita Ravi

**Builds**
- Creates the SQLite database and table for clean records.
- Inserts new records and updates existing ones (no duplicates on re-run).
- Reports counts: added, updated, unchanged.
- pytest tests using a temporary database.

**Presentation:** database state before and after sync (including the edited demo record); how new, changed, and unchanged records are detected.

**Q&A to be ready for**
- What if the sync stops halfway?
- How to migrate from SQLite to a larger database later?

### 5.4 CLI, CI, README & Integration Test: Ansh Harjai

**Builds**
- Command-line entry point with `--from-file` option and summary output.
- One integration test: full sync from a saved response to a temp database.
- CI workflow that runs tests on every pull request.
- README with usage instructions and the customer record schema.
- Keeps the team task board up to date.

**Presentation:** live demo of a full sync and an update scenario; integration test purpose and pull request walkthrough.

**Q&A to be ready for**
- How to test code that depends on an external service?
- How to schedule this tool for nightly runs?

## 6. Requirements Checklist for Agents

When implementing or modifying code, ensure:

- [ ] Re-running a sync never creates duplicate records (idempotent on the unique identifier).
- [ ] Summary reports all four counts: added, updated, unchanged, rejected.
- [ ] Every rejected record has a recorded reason.
- [ ] API failures are retried, then surface a clear error.
- [ ] All tests run offline using saved responses and temporary databases.
- [ ] `--from-file` works end to end without network access.
- [ ] Each component has its own pytest tests.
- [ ] Schema and unique identifier match the README.

## 7. Testing Conventions

- Framework: `pytest`.
- No test may require internet; use saved API responses as fixtures.
- Storage tests use a temporary database (e.g. `tmp_path`).
- One integration test covers: saved response -> clean -> temp SQLite -> summary.
- CI runs the full suite on every pull request.

## 8. Team Rules

- Use feature branches; merge via pull requests, with your name on commits.
- Each member writes tests for their own piece and presents their own work.
- Track tasks in Linear; link PRs to tasks.
- Do not change locked decisions (section 3) without team agreement.

## 9. Team

| Member | Area |
|---|---|
| Vedant Misra | API Client |
| Julian Marchington | Data Cleaning & Validation |
| Nikita Ravi | SQLite Storage |
| Ansh Harjai | CLI, CI, README & Integration Test |