# Customer Data Sync Tool: Setup & Task Plan

> Team 2 · Starts Monday 19 Oct 2026 · Demo assumed Friday 23 Oct 2026
> Source of truth for scope: `AGENTS.md`. This file covers *how* we build it without stepping on each other.

**Ground rules in one line each**
- One file, one owner. You never edit a file you don't own.
- Contracts (`contracts.py`) are written in Phase 0 and then frozen.
- Every test runs offline against saved fixtures and temp databases.
- `main` is protected: PR + 1 review + green CI, no direct pushes.

---

## 1. Repository skeleton (Phase 0)

### 1.1 Tree (created by Ansh on one branch, merged before anyone else branches)

```
.
├── .github/
│   ├── workflows/ci.yml              # lint + types + tests on every PR
│   ├── pull_request_template.md
│   └── CODEOWNERS
├── src/customer_sync/
│   ├── __init__.py                   # __version__ only
│   ├── contracts.py                  # shared types + protocols (FROZEN after Phase 0)
│   ├── api_client.py                 # stub → Vedant
│   ├── cleaning.py                   # stub → Julian
│   ├── storage.py                    # stub → Nikita
│   └── cli.py                        # stub → Ansh
├── tests/
│   ├── conftest.py                   # only: fixtures_dir + raw_records loader
│   ├── test_smoke.py                 # placeholder: package imports, contracts exist
│   ├── test_api_client.py            # empty module docstring → Vedant
│   ├── test_cleaning.py              # empty → Julian
│   ├── test_storage.py               # empty → Nikita
│   ├── test_cli.py                   # empty → Ansh
│   ├── test_integration.py           # empty → Ansh
│   └── fixtures/
│       ├── raw/seed_team2_r10_p1.json  # real API capture, FROZEN, read-only for all
│       ├── api/                      # .gitkeep → Vedant
│       ├── cleaning/                 # .gitkeep → Julian
│       ├── storage/                  # .gitkeep → Nikita (likely unused)
│       └── integration/              # .gitkeep → Ansh
├── docs/
│   ├── api-client.md                 # presentation notes + Q&A → Vedant
│   ├── cleaning.md                   # → Julian
│   ├── storage.md                    # → Nikita
│   └── cli.md                        # → Ansh
├── scripts/
│   ├── check.sh                      # local pre-push gate (ruff, mypy, pytest)
│   └── capture_fixture.py            # stub → Vedant
├── pyproject.toml
├── README.md
├── AGENTS.md                         # §3 filled in with locked decisions
├── PLAN.md
└── .gitignore                        # + *.db, .coverage, .ruff_cache/, .mypy_cache/
```

The raw fixture is captured once in Phase 0 with:
`curl -s "https://randomuser.me/api/1.4/?seed=team2&results=10&page=1" > tests/fixtures/raw/seed_team2_r10_p1.json`
It gives every person real API-shaped data on day one, with no dependency on Vedant's client.

### 1.2 `pyproject.toml` (single source for deps and tool config)

```toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "customer-sync"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["requests>=2.31"]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-cov>=5", "pytest-socket>=0.7", "ruff>=0.6", "mypy>=1.10", "types-requests"]

[project.scripts]
customer-sync = "customer_sync.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers --disable-socket"   # pytest-socket: any network call fails the test
markers = ["integration: full pipeline test (saved response -> temp SQLite -> summary)"]

[tool.ruff]
line-length = 100
target-version = "py311"
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[tool.mypy]
python_version = "3.11"
strict = true
files = ["src"]
```

`src/` layout + `pip install -e ".[dev]"` means `import customer_sync` works identically locally and in CI.

### 1.3 Stub rule

Each module stub contains the exact public signatures from §2 with typed parameters, a docstring stating the contract, and `raise NotImplementedError`. Stubs pass ruff and mypy, so CI is green on day one. Owners replace bodies; they do not change signatures (that is a contract change, §2.6).

### 1.4 CI on day one

`.github/workflows/ci.yml` as in §7, plus `tests/test_smoke.py`: imports every module, asserts `Customer`, `Rejection`, `CleanResult`, `UpsertCounts`, `SyncSummary` exist and that the raw fixture loads with 10 records. This is the "placeholder passing test" and stays forever as a cheap guard.

### 1.5 Who and in what order

**Ansh builds Phase 0; all four review.** One author on `main` means zero conflicts; Ansh already owns CI, README and wiring.

| # | PR | Author | Merge when |
|---|---|---|---|
| 1 | `docs: add AGENTS.md and PLAN.md` | Ansh | Mon, before the contracts meeting |
| 2 | `chore: project skeleton, contracts, CI` | Ansh | Mon EOD, after all 3 others approve contracts |
| — | Turn on branch protection (§6.4) | repo admin | Immediately after PR 2 merges |

Nobody branches for feature work until PR 2 is on `main`.

---

## 2. Interface contracts (agree Monday, then freeze)

All of this lives in `src/customer_sync/contracts.py`. Julian designs the `Customer` shape and validation rules (his presentation covers it); it sits in `contracts.py` so everyone can import it from hour one.

### 2.1 Clean customer record

| Field | Type | Nullable | Source (API) | Cleaning rule |
|---|---|---|---|---|
| `uuid` | `str` | no | `login.uuid` | strip, lowercase, must parse as UUID |
| `first_name` | `str` | no | `name.first` | strip, non-empty |
| `last_name` | `str` | no | `name.last` | strip, non-empty |
| `email` | `str` | no | `email` | strip, lowercase, `^[^@\s]+@[^@\s]+\.[^@\s]+$` |
| `phone` | `str \| None` | yes | `phone` | strip; int → str; empty → `None` |
| `city` | `str \| None` | yes | `location.city` | strip; empty → `None` |
| `country` | `str \| None` | yes | `location.country` | strip; empty → `None` |
| `registered_at` | `str` | no | `registered.date` | parse ISO 8601, emit UTC `YYYY-MM-DDTHH:MM:SSZ` |

Policy: **normalise safely, otherwise reject.** Never invent a missing value. A required field that is missing → `MISSING_FIELD`; wrong type that can't be safely coerced → `WRONG_TYPE`; bad format → `INVALID_VALUE`. Within one batch, a repeated `uuid` or a repeated `email` under a different uuid → `DUPLICATE` (first occurrence kept).

### 2.2 Unique identifier: `login.uuid` (locked)

| | `login.uuid` ✅ | `email` |
|---|---|---|
| Stability | System-generated, never changes | Changes when a customer updates contact info |
| Email change | Shows as `updated` (correct) | Shows as add + orphaned old row (wrong) |
| Normalisation | Lowercase only | Case, whitespace, aliases |
| Readability in demo | Opaque | Human-readable |
| Duplicate risk | API guarantees uniqueness | Real data shares emails |

Email is still validated and checked for in-batch duplicates. Known limitation: two different uuids with the same email across *separate* runs are both stored (documented in README).

### 2.3 `contracts.py` (frozen content)

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Protocol

RawRecord = dict[str, Any]            # one element of the API "results" array

@dataclass(frozen=True, slots=True)
class Customer:
    uuid: str
    first_name: str
    last_name: str
    email: str
    phone: str | None
    city: str | None
    country: str | None
    registered_at: str

class RejectCode(str, Enum):
    MISSING_FIELD = "missing_field"
    WRONG_TYPE = "wrong_type"
    INVALID_VALUE = "invalid_value"
    DUPLICATE = "duplicate"

@dataclass(frozen=True, slots=True)
class Rejection:
    index: int                        # position in the input list
    uuid: str | None                  # if it could be read
    code: RejectCode
    reason: str                       # e.g. "missing field: email"
    raw: RawRecord

@dataclass(frozen=True, slots=True)
class CleanResult:
    accepted: list[Customer]
    rejected: list[Rejection]

@dataclass(frozen=True, slots=True)
class UpsertCounts:
    added: int
    updated: int
    unchanged: int

@dataclass(frozen=True, slots=True)
class SyncSummary:
    added: int
    updated: int
    unchanged: int
    rejected: int
    rejections: list[Rejection] = field(default_factory=list)

class RecordSource(Protocol):         # API client and file source both implement this
    def fetch_records(self) -> list[RawRecord]: ...

class CustomerRepository(Protocol):   # SQLite store implements this; CLI tests use a fake
    def upsert_many(self, customers: Iterable[Customer]) -> UpsertCounts: ...

class SyncError(Exception): ...
class ApiError(SyncError): ...        # retries exhausted / unrecoverable API response
class SourceFileError(SyncError): ... # --from-file missing, unreadable, or wrong shape
class StorageError(SyncError): ...
```

### 2.4 Module signatures (stubs in Phase 0)

| Module | Public API | Input → Output |
|---|---|---|
| `api_client.py` (Vedant) | `RandomUserClient(base_url="https://randomuser.me/api/1.4/", seed="team2", results=50, pages=1, max_retries=3, backoff=0.5, timeout=10.0, session=None, sleep=time.sleep)`<br>`.fetch_page(page: int) -> list[RawRecord]`<br>`.fetch_records() -> list[RawRecord]` | API → raw records (all pages). Raises `ApiError`. `session`/`sleep` injectable for offline tests. |
| | `FileSource(path: str \| Path)`<br>`.fetch_records() -> list[RawRecord]` | Saved response JSON → `results` list. Raises `SourceFileError`. |
| `cleaning.py` (Julian) | `clean_record(raw: RawRecord) -> Customer` (raises `RecordRejected(code, reason)`)<br>`clean_records(raws: list[RawRecord]) -> CleanResult` | Raw → accepted + rejected-with-reason; batch handles duplicates. |
| `storage.py` (Nikita) | `CustomerStore(db_path: str \| Path)` (context manager)<br>`.upsert_many(customers) -> UpsertCounts`<br>`.get(uuid) -> Customer \| None` · `.all() -> list[Customer]` · `.count() -> int` · `.close()` | Customers → counts. One transaction per call (all or nothing). Input uuids are unique (guaranteed by cleaner). |
| `cli.py` (Ansh) | `run_sync(source: RecordSource, repo: CustomerRepository) -> SyncSummary`<br>`format_summary(s: SyncSummary, show_rejected: bool = True) -> str`<br>`main(argv: list[str] \| None = None) -> int` | Wires the pipeline; prints summary; exit 0 OK (even with rejections), 1 on `SyncError`, 2 bad usage. |

`RecordRejected` is an exception defined in `cleaning.py` (internal to Julian; not used by others).

### 2.5 CLI surface and summary format

```
customer-sync [--from-file PATH] [--db PATH=customers.db] [--seed team2] [--results 50] [--pages 1] [--quiet-rejections]
```

```
Sync complete (source: file tests/fixtures/integration/day1.json, db: customers.db)
  added:      10
  updated:     0
  unchanged:   0
  rejected:    2
Rejected records:
  #10  uuid=7a1c…  missing_field  missing field: email
  #11  uuid=3f9e…  duplicate      duplicate uuid (first seen at #4)
```

### 2.6 Changing a contract after freeze

1. Open an issue/board card "Contract change: …" describing the change and why.
2. Ansh opens a PR touching only `contracts.py` (+ stubs/smoke test if needed), label `contract-change`.
3. Merge requires approval from **all four**. Each owner then adapts their own module in their own PR.
4. Additive changes (new optional field with default) are preferred over renames/removals.

---

## 3. File ownership map

**Rule:** nobody edits a file they don't own. Need a change elsewhere? Ask the owner (board card or chat), or open a tiny PR that the owner must approve. CODEOWNERS enforces review.

| Path | Owner | Notes |
|---|---|---|
| `src/customer_sync/api_client.py` | Vedant | |
| `tests/test_api_client.py`, `tests/fixtures/api/**` | Vedant | |
| `scripts/capture_fixture.py`, `docs/api-client.md` | Vedant | |
| `src/customer_sync/cleaning.py` | Julian | |
| `tests/test_cleaning.py`, `tests/fixtures/cleaning/**`, `docs/cleaning.md` | Julian | |
| `src/customer_sync/storage.py` | Nikita | |
| `tests/test_storage.py`, `tests/fixtures/storage/**`, `docs/storage.md` | Nikita | |
| `src/customer_sync/cli.py`, `tests/test_cli.py`, `tests/test_integration.py` | Ansh | |
| `tests/fixtures/integration/**`, `docs/cli.md` | Ansh | |
| **Shared, single owner** | | |
| `src/customer_sync/contracts.py` | Ansh | Frozen; changes need all-4 approval (§2.6) |
| `src/customer_sync/__init__.py`, `tests/conftest.py`, `tests/test_smoke.py` | Ansh | Don't add shared fixtures; keep helpers in your own test file |
| `tests/fixtures/raw/**` | Ansh | Frozen after Phase 0; read-only for all |
| `pyproject.toml` | Ansh | New dependency? Ask Ansh in chat; he adds it in a 1-line PR same day |
| `README.md` | Ansh | Others send text for their section; Ansh pastes it |
| `.github/**`, `.gitignore`, `scripts/check.sh` | Ansh | |
| `AGENTS.md` | Ansh (maintainer) | Locked sections need all-4 approval |
| `PLAN.md` | Ansh | Plan changes via PR, any one approval |

Reading another owner's file (e.g. Ansh's integration test loading Julian's messy fixture) is fine. Editing it is not.

---

## 4. Per-person task breakdown

Branch per PR, named `<first-name>/<area>-<topic>`. PRs are small (§6.3) and listed in merge order.

### 4.1 Vedant Misra: API Client

**Owns:** `api_client.py`, `test_api_client.py`, `fixtures/api/**`, `scripts/capture_fixture.py`, `docs/api-client.md`
**Mocks while waiting:** nothing needed (first stage). Uses a `FakeSession` class in his test file that returns canned responses/raises errors.

| PR | Branch | Content | Tests |
|---|---|---|---|
| V1 | `vedant/api-fixtures` | `capture_fixture.py`; save `api/page1.json`, `api/page2.json` (seed team2, results 5), `api/error_body.json` (`{"error": "..."}`) | — |
| V2 | `vedant/api-fetch-page` | `fetch_page`, `fetch_records` over N pages; builds `seed/results/page` params; extracts `results` | params sent correctly; 2 pages concatenated; missing `results` → `ApiError` |
| V3 | `vedant/api-retries` | Retry on connection error, timeout, 5xx, 429, `{"error"}` body; no retry on other 4xx; exponential backoff via injected `sleep`; `ApiError` names URL, attempts, last cause | succeeds on attempt 3; exhausts after `max_retries`; 404 not retried; backoff delays asserted; no real sleeping |
| V4 | `vedant/api-file-source` | `FileSource` for `--from-file` | valid file; missing file; invalid JSON; no `results` key → `SourceFileError` |
| V5 | `vedant/api-docs` | `docs/api-client.md`: demo script (live call + forced failure via `base_url="http://127.0.0.1:9"`), retry-limit rationale, Q&A answers | — |

**Q&A prep (in V5):** API down during nightly job → retries with backoff, then `ApiError`, exit code 1, DB untouched so the next run catches up; scheduler alerts on non-zero exit. Second data source → implement `RecordSource.fetch_records()` in a new class; CLI picks it by flag; cleaning gets a per-source mapper. Pinning `/api/1.4/` protects against overnight field renames.

**Done when:** all four PRs merged, coverage of `api_client.py` ≥ 90%, no test touches network, docs written, demo rehearsed.

### 4.2 Julian Marchington: Data Cleaning & Validation

**Owns:** `cleaning.py`, `test_cleaning.py`, `fixtures/cleaning/**`, `docs/cleaning.md`
**Mocks while waiting:** input is plain `list[RawRecord]` loaded from `fixtures/raw/` and `fixtures/cleaning/`; no dependency on Vedant's code.

| PR | Branch | Content | Tests |
|---|---|---|---|
| J1 | `julian/cleaning-fixtures` | `cleaning/messy_response.json`: 10 raw records copied from the frozen fixture + injected cases: missing `email`; `email` as int; blank `first_name`; malformed email; missing `login.uuid`; bad `registered.date`; duplicate uuid; duplicate email/different uuid; `"  Foo@BAR.com "` (accept after normalise); missing phone (accept, `None`); int phone (accept, coerced) | — |
| J2 | `julian/cleaning-record` | `clean_record` + `RecordRejected`: mapping, normalisation, validation | one test per rule, accepted and rejected (parametrised) |
| J3 | `julian/cleaning-batch` | `clean_records`: indexes, duplicate detection, `CleanResult` | messy fixture → exact accepted count and exact (index, code) list of rejections; order preserved; every rejection has a non-empty reason |
| J4 | `julian/cleaning-docs` | `docs/cleaning.md`: before/after table from the messy fixture, rejection list with reasons, Q&A answers | — |

**Q&A prep:** Fix or reject? → we fix only lossless formatting; anything that needs guessing is rejected and reported; the business owner decides whether to correct at source. API renames a field overnight → mapping is in one place; missing required field → every record rejected as `missing_field: email`, which is loud and obvious; pinned API version reduces the risk.

**Done when:** every rule in §2.1 has accepted + rejected tests, coverage ≥ 90%, docs written.

### 4.3 Nikita Ravi: SQLite Storage

**Owns:** `storage.py`, `test_storage.py`, `fixtures/storage/**`, `docs/storage.md`
**Mocks while waiting:** builds `Customer(...)` objects directly in tests (type exists from Phase 0); uses `tmp_path / "test.db"`. No dependency on Julian.

| PR | Branch | Content | Tests |
|---|---|---|---|
| N1 | `nikita/storage-schema` | `CustomerStore` init creates table if absent; `get/all/count/close`; context manager | table created; reopening an existing DB keeps data |
| N2 | `nikita/storage-upsert` | `upsert_many`: insert new, update changed (any field differs), skip identical; `created_at`/`updated_at` set only on change; one transaction | new → added; same again → unchanged; edited phone → updated; mixed batch counts |
| N3 | `nikita/storage-robustness` | Rollback on failure; wrap `sqlite3.Error` in `StorageError` | idempotent re-run (0/0/N, row count stable); failure mid-batch leaves DB unchanged (monkeypatch to raise) |
| N4 | `nikita/storage-docs` | `docs/storage.md`: schema, change detection, before/after demo with `sqlite3` queries incl. edited record, Q&A answers | — |

Proposed table (Nikita owns final form):
```sql
CREATE TABLE IF NOT EXISTS customers (
  uuid TEXT PRIMARY KEY, first_name TEXT NOT NULL, last_name TEXT NOT NULL,
  email TEXT NOT NULL, phone TEXT, city TEXT, country TEXT,
  registered_at TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
```

**Q&A prep:** Sync stops halfway → single transaction, so it's all or nothing and a re-run is safe (idempotent). Migrate to a bigger DB → `CustomerRepository` protocol: write `PostgresStore` with the same `upsert_many`, swap in the CLI; the SQL is standard `INSERT … ON CONFLICT`.

**Done when:** idempotency + rollback tests pass, coverage ≥ 90%, docs written.

### 4.4 Ansh Harjai: CLI, CI, README & Integration Test

**Owns:** everything in §3 marked Ansh.
**Mocks while waiting:** `FakeSource` and `FakeRepo` classes in `test_cli.py` implementing the protocols; integration test marked `xfail` until real modules land.

| PR | Branch | Content | Tests |
|---|---|---|---|
| A0 | `ansh/skeleton` | Phase 0 (§1): tree, contracts, stubs, CI, CODEOWNERS, PR template, `check.sh`, raw fixture, AGENTS.md §3 + README decisions | smoke test |
| A1 | `ansh/cli-core` | `argparse`, `run_sync`, `format_summary`, exit codes | with fakes: 4 counts summed correctly; rejections printed; `SyncError` → exit 1; `--from-file` chooses `FileSource` |
| A2 | `ansh/integration-fixtures` | `integration/day1.json` (10 valid + 2 invalid) and `integration/day2_edited.json` (same 10 with one phone changed + 1 new + same 2 invalid); `test_integration.py` with `@pytest.mark.xfail(raises=NotImplementedError, strict=False)` | day1 → 10/0/0/2; day2 on same DB → 1/1/9/2; day1 twice → 0/0/10/2 |
| A3 | `ansh/readme` | README: install, usage, `--from-file`, schema table, identifier, summary example, nightly scheduling (cron / Task Scheduler), testing | — |
| A4 | `ansh/integration-enable` (Phase 2) | Remove `xfail`; run `main(["--from-file", …, "--db", tmp])` end to end | integration test passes for real |
| A5 | `ansh/cli-docs` | `docs/cli.md`: demo script (full sync + update scenario), PR walkthrough, Q&A | — |

Also: populate and maintain the task board; set up branch protection with the repo admin.

**Q&A prep:** Testing code that depends on an external service → protocols + injected session + saved responses + `pytest-socket` blocks the network. Nightly runs → cron `0 2 * * * customer-sync --db /data/customers.db >> sync.log 2>&1`; non-zero exit triggers an alert.

**Done when:** CI green on all PRs, integration test passing without `xfail`, README complete, demo rehearsed.

---

## 5. Parallel-work strategy

- **Code against contracts, not code.** Phase 0 makes every type and signature importable. Unit tests only import `contracts` and the owner's own module.
- **Fixtures, one owner per directory, frozen once merged.** Need a new scenario? Add a new file, never edit a merged one. This kills fixture divergence and conflicts.

| Fixture | Owner | Purpose |
|---|---|---|
| `raw/seed_team2_r10_p1.json` | Ansh (Phase 0) | Real API shape for everyone, day one |
| `api/page1.json`, `page2.json`, `error_body.json` | Vedant | Paging + error-body tests |
| `cleaning/messy_response.json` | Julian | Every reject/normalise case |
| `integration/day1.json`, `day2_edited.json` | Ansh | Full sync + "demo edited record" update scenario |

- **Integration test grows in three steps:** (1) A1: `run_sync` tested with fakes, proving the wiring logic. (2) A2: the real end-to-end test is written with exact expected counts and `xfail(raises=NotImplementedError)`, so it passes CI while stubs remain. (3) A4: once V4/J3/N2 are on `main`, remove `xfail`; it must pass for real. An `xfail` that starts passing early is a nice signal, not a failure (`strict=False`).
- **Live demo edited record:** run day1 sync, `UPDATE customers SET phone='000' WHERE uuid=…` in `sqlite3`, re-run → `updated: 1` (source of truth restored).

---

## 6. Git workflow and conflict avoidance

### 6.1 Branches and commits
- Branch: `<first-name>/<area>-<topic>` (e.g. `julian/cleaning-batch`), always cut from fresh `main`.
- Git identity: `git config user.name "Full Name"` and your email. Each commit is yours.
- Message: `type(area): imperative summary`. Types: `feat fix test docs chore ci`. Areas: `api clean store cli ci docs contracts`.
  Example: `feat(api): retry on 5xx with exponential backoff`
- Squash-merge title keeps the same format and appends `(#PR)`. Squash keeps the author's name.

### 6.2 Keeping fresh
- Daily, and before opening/updating a PR: `git fetch origin && git rebase origin/main`, then `git push --force-with-lease` (your own branch only, never `main`).
- Branches live ≤ 1 day; merge, then cut the next one.

### 6.3 PR rules
- One board task per PR, ≤ ~300 changed lines excluding fixture JSON.
- Must touch only files you own (reviewer checks; CODEOWNERS enforces review).
- Template filled in; board card linked.
- Merge order: PR 1 (docs) → A0 skeleton → Phase 1 PRs in any order (disjoint files) → A4 last.

### 6.4 Branch protection on `main`
- Require a pull request; 1 approving review; **require review from Code Owners**; dismiss stale approvals on new commits.
- Require status check `CI / test` to pass; require branch up to date before merging.
- Block force pushes and deletion; require linear history (squash merge only); apply to admins too.

### 6.5 `.github/CODEOWNERS` (replace handles with real GitHub usernames)
```
*                                   @ansh-gh
/src/customer_sync/api_client.py    @vedant-gh
/tests/test_api_client.py           @vedant-gh
/tests/fixtures/api/                @vedant-gh
/scripts/capture_fixture.py         @vedant-gh
/docs/api-client.md                 @vedant-gh
/src/customer_sync/cleaning.py      @julian-gh
/tests/test_cleaning.py             @julian-gh
/tests/fixtures/cleaning/           @julian-gh
/docs/cleaning.md                   @julian-gh
/src/customer_sync/storage.py       @nikita-gh
/tests/test_storage.py              @nikita-gh
/tests/fixtures/storage/            @nikita-gh
/docs/storage.md                    @nikita-gh
/src/customer_sync/contracts.py     @ansh-gh @vedant-gh @julian-gh @nikita-gh
/PLAN.md                            @ansh-gh
```
(GitHub needs only one code-owner approval; the all-four rule for `contracts.py` is a team rule checked by the `contract-change` label.)

### 6.6 `.github/pull_request_template.md`
```markdown
## What
<!-- one or two sentences -->

## Board task
<!-- link -->

## Checklist
- [ ] Only files I own are changed (or the owner has approved)
- [ ] `scripts/check.sh` passes locally
- [ ] New behaviour has tests; tests are offline and use tmp_path / saved fixtures
- [ ] No change to `contracts.py` (or label `contract-change` + all-4 approval)
- [ ] Rebased on latest `main`
```

### 6.7 If a conflict happens anyway
1. `git fetch && git rebase origin/main`; resolve only in files you own; re-run `check.sh`.
2. If the conflict is in a file you don't own, stop: ownership was broken. Abort the rebase, tell the owner, and let them make the change in their branch.
3. Never resolve by force-pushing `main` or deleting someone else's changes. If stuck > 30 min, pair with the file owner.

---

## 7. CI and quality gates

### 7.1 `.github/workflows/ci.yml`
```yaml
name: CI
on:
  pull_request:
  push:
    branches: [main]
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: pyproject.toml
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: ruff format --check .
      - run: mypy
      - run: pytest --cov=customer_sync --cov-report=term-missing
```
Python 3.12 in CI; any 3.11+ locally. Ruff and mypy block from day one (stubs are typed, so this is cheap). Coverage is reported, not enforced, until Phase 2.

### 7.2 Local pre-push checklist (`scripts/check.sh` runs 2–5)
- [ ] 1. `git fetch origin && git rebase origin/main`
- [ ] 2. `ruff check . && ruff format --check .` (fix with `ruff format .`)
- [ ] 3. `mypy`
- [ ] 4. `pytest` (network is blocked; a failure here means your test is reaching out)
- [ ] 5. `git diff --name-only origin/main`: only your files?

### 7.3 Keep-CI-green rules
- No network in tests (`--disable-socket` enforces it). Inject sessions; use saved JSON.
- Databases only under `tmp_path`; never a repo-level `.db` (`*.db` is gitignored).
- Deterministic: no `time.sleep` (inject `sleep`), no `datetime.now()` in assertions, fixtures frozen.
- No shared global state: no module-level connections or singletons; each test builds its own objects.
- Red `main` is everyone's top priority: the author of the breaking PR fixes or reverts within the hour.

---

## 8. Task board (Linear)

All tasks live in the Linear project **[Customer Data Sync Tool](https://linear.app/julianmarchingtoncoforge/project/customer-data-sync-tool-67dda302dbec)** (team JUL), grouped by the milestones *Phase 0: Skeleton*, *Phase 1: Parallel build*, *Phase 2: Integration* and *Phase 3: Demo*. Each ticket has plain-language steps, the files you may and may not touch, the tests to write, acceptance criteria and a ready-to-paste **prompt for your AI assistant**. Dependencies are set as Linear "blocked by" links. Ticket titles start with the board ID (e.g. `[V2]`) so both IDs work. A0 in §4.4 is the same task as P0-3.

| ID | Linear | Title | Owner | Depends on | Branch | Acceptance criteria |
|---|---|---|---|---|---|---|
| **Phase 0** | | | | | | |
| P0-1 | [JUL-5](https://linear.app/julianmarchingtoncoforge/issue/JUL-5) | Commit AGENTS.md + PLAN.md | Ansh | — | `ansh/plan` | Merged to main |
| P0-2 | [JUL-6](https://linear.app/julianmarchingtoncoforge/issue/JUL-6) | Contracts meeting: sign off §2 | Ansh (facilitates), all attend | P0-1 | — | Schema, uuid, signatures approved in chat |
| P0-3 | [JUL-7](https://linear.app/julianmarchingtoncoforge/issue/JUL-7) | Skeleton, contracts, stubs, CI, CODEOWNERS, raw fixture | Ansh | P0-2 | `ansh/skeleton` | CI green; 3 approvals; AGENTS §3 filled |
| P0-4 | [JUL-8](https://linear.app/julianmarchingtoncoforge/issue/JUL-8) | Enable branch protection | Ansh + admin | P0-3 | — | §6.4 settings active |
| **Vedant** | | | | | | |
| V1 | [JUL-9](https://linear.app/julianmarchingtoncoforge/issue/JUL-9) | API fixtures + capture script | Vedant | P0-3 | `vedant/api-fixtures` | 3 fixture files committed, script reproduces them |
| V2 | [JUL-10](https://linear.app/julianmarchingtoncoforge/issue/JUL-10) | fetch_page / fetch_records | Vedant | V1 | `vedant/api-fetch-page` | Paging + params tests pass offline |
| V3 | [JUL-11](https://linear.app/julianmarchingtoncoforge/issue/JUL-11) | Retries + ApiError | Vedant | V2 | `vedant/api-retries` | Retry/backoff/give-up tests pass, no real sleep |
| V4 | [JUL-12](https://linear.app/julianmarchingtoncoforge/issue/JUL-12) | FileSource (--from-file) | Vedant | P0-3 | `vedant/api-file-source` | Valid/missing/invalid file tests pass |
| V5 | [JUL-13](https://linear.app/julianmarchingtoncoforge/issue/JUL-13) | API docs, demo, Q&A | Vedant | V3 | `vedant/api-docs` | docs/api-client.md complete; demo rehearsed |
| **Julian** | | | | | | |
| J1 | [JUL-14](https://linear.app/julianmarchingtoncoforge/issue/JUL-14) | Messy fixture | Julian | P0-3 | `julian/cleaning-fixtures` | Covers every §2.1 reject/normalise case |
| J2 | [JUL-15](https://linear.app/julianmarchingtoncoforge/issue/JUL-15) | clean_record rules | Julian | J1 | `julian/cleaning-record` | Accepted + rejected test per rule |
| J3 | [JUL-16](https://linear.app/julianmarchingtoncoforge/issue/JUL-16) | clean_records batch + duplicates | Julian | J2 | `julian/cleaning-batch` | Exact rejection list asserted; every reject has reason |
| J4 | [JUL-17](https://linear.app/julianmarchingtoncoforge/issue/JUL-17) | Cleaning docs, demo, Q&A | Julian | J3 | `julian/cleaning-docs` | Before/after + rejection table in docs |
| **Nikita** | | | | | | |
| N1 | [JUL-18](https://linear.app/julianmarchingtoncoforge/issue/JUL-18) | Schema + store basics | Nikita | P0-3 | `nikita/storage-schema` | Table created; reopen keeps data |
| N2 | [JUL-19](https://linear.app/julianmarchingtoncoforge/issue/JUL-19) | upsert_many with counts | Nikita | N1 | `nikita/storage-upsert` | added/updated/unchanged tests pass |
| N3 | [JUL-20](https://linear.app/julianmarchingtoncoforge/issue/JUL-20) | Idempotency + rollback | Nikita | N2 | `nikita/storage-robustness` | Re-run stable; mid-batch failure leaves DB unchanged |
| N4 | [JUL-21](https://linear.app/julianmarchingtoncoforge/issue/JUL-21) | Storage docs, demo, Q&A | Nikita | N3 | `nikita/storage-docs` | Before/after DB queries in docs |
| **Ansh** | | | | | | |
| A1 | [JUL-22](https://linear.app/julianmarchingtoncoforge/issue/JUL-22) | CLI core with fakes | Ansh | P0-3 | `ansh/cli-core` | Summary/exit-code tests pass with fakes |
| A2 | [JUL-23](https://linear.app/julianmarchingtoncoforge/issue/JUL-23) | Integration fixtures + xfail test | Ansh | P0-3 | `ansh/integration-fixtures` | Test encodes 10/0/0/2 and 1/1/9/2; CI green |
| A3 | [JUL-24](https://linear.app/julianmarchingtoncoforge/issue/JUL-24) | README | Ansh | P0-3 | `ansh/readme` | Usage, schema, identifier, scheduling documented |
| A4 | [JUL-25](https://linear.app/julianmarchingtoncoforge/issue/JUL-25) | Enable integration test | Ansh | V4, J3, N3, A1, A2 | `ansh/integration-enable` | xfail removed; passes on main |
| A5 | [JUL-26](https://linear.app/julianmarchingtoncoforge/issue/JUL-26) | CLI docs, demo, Q&A | Ansh | A4 | `ansh/cli-docs` | Demo script + PR walkthrough ready |
| **Phase 3** | | | | | | |
| D1 | [JUL-27](https://linear.app/julianmarchingtoncoforge/issue/JUL-27) | Full dry run of demo | Ansh (organises), all present | A4, V5, J4, N4 | — | Each presenter ≤ time limit; fallback tested |

**Board hygiene:** move your ticket to *In Progress* when you branch, *In Review* when the PR is open, and *Done* when it merges. Put the Linear ID in the PR title (e.g. `feat(api): retry with backoff (JUL-11)`) so the PR links to the ticket.

---

## 9. Timeline and integration milestones

| When | Phase | What | Checkpoint (who verifies) |
|---|---|---|---|
| Mon AM | 0 | P0-1 merged; 60-min contracts meeting | Decisions posted in chat (Ansh) |
| Mon PM | 0 | A0 skeleton PR, 3 reviews, merge; branch protection | Everyone clones `main`, runs `pip install -e ".[dev]" && pytest` green (all) |
| Tue | 1 | V1–V2, J1–J2, N1–N2, A1–A2 | **CP1 Tue EOD:** each person has ≥ 1 PR merged; CI green (Ansh) |
| Wed | 1 | V3–V4, J3, N3, A3 | **CP2 Wed EOD:** all stubs replaced on `main`; `xfail` integration test already XPASSes (Ansh) |
| Thu AM | 2 | A4 integration-enable; owners fix bugs in their own files | **CP3 Thu noon:** team runs `customer-sync --from-file tests/fixtures/integration/day1.json` then `day2_edited.json` on `main` together; one live API run by Vedant (Ansh leads) |
| Thu PM | 3 | V5, J4, N4, A5 docs; demo scripts | Each presenter rehearses solo |
| Fri AM | 3 | D1 full dry run, then demo | Fallbacks ready (Ansh) |

Integrator: **Ansh**. Bugs found during integration go to the owning file's author.

---

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Interface drift | Frozen `contracts.py`; mypy strict in CI catches signature mismatches; changes only via §2.6 |
| Flaky CI | No network (`pytest-socket`), injected `sleep`, `tmp_path` DBs, frozen fixtures, `concurrency` cancels stale runs |
| One person blocked | Everyone works against contracts + fixtures; nobody's unit tests import another owner's module; blocker raised at daily standup, owner pairs within the day |
| API down during demo | Primary demo uses `--from-file`; live call is a bonus; a recorded terminal session of a live run as backup; showing the retry failure is itself a demo point |
| Fixture divergence | One owner per fixture directory; merged fixtures immutable; new scenario = new file |
| Merge conflicts | One owner per file + CODEOWNERS; branches ≤ 1 day; rebase daily |
| Someone off sick | Docs + tests per module let a teammate demo it; Ansh's integration test proves the whole flow |
| API field renamed | Pinned `/api/1.4/`; mapping in one function; renamed required field becomes loud `missing_field` rejections |

---

## 11. Open questions

Resolved with Vedant before writing this plan (confirm with the team Monday, then lock in AGENTS.md §3 + README):
- [x] Unique identifier → `login.uuid`
- [x] Record shape → core contact (§2.1)
- [x] Phase 0 → Ansh owns all four P0 tickets (JUL-5 to JUL-8); everyone reviews the skeleton PR
- [x] Bad records → safe normalisation, else reject with reason
- [x] Task board → Linear, team JUL (§8)

Still to confirm Monday:
- [ ] Demo date/time and length per presenter (plan assumes Friday)
- [ ] GitHub usernames for CODEOWNERS; who has admin rights to set branch protection
- [ ] Pin API version `/api/1.4/` (recommended) vs unversioned `/api/` as written in AGENTS.md
- [ ] Default `results`/`pages` for real runs (plan: 50 × 1)
- [ ] In-batch duplicate email under a different uuid: reject (plan) or accept?

---

## 12. Kickoff message (paste into team chat)

```
Hi team! Plan for the Customer Data Sync Tool is in PLAN.md (repo root), and every task is a ticket in Linear:
https://linear.app/julianmarchingtoncoforge/project/customer-data-sync-tool-67dda302dbec
Each ticket has step-by-step instructions, the files you may touch, tests, a "done when" checklist and a prompt you can paste into your AI assistant. Short version:

LOCKED (confirm at today's contracts meeting):
• Unique ID = login.uuid
• Record = uuid, first_name, last_name, email, phone?, city?, country?, registered_at
• Bad records: safe cleanup (trim, lowercase email), otherwise reject with a reason

TODAY (Mon)
1. Ansh merges AGENTS.md + PLAN.md (JUL-5)
2. All 4: 60-min contracts meeting (PLAN.md §2), sign off types + function signatures. Bring your GitHub username (JUL-6)
3. Ansh builds the skeleton (folders, contracts.py, stubs, CI, CODEOWNERS, raw fixture), everyone reviews, merge by EOD (JUL-7)
4. Branch protection on: PR + 1 review + green CI, no pushes to main (JUL-8)

FIRST TASKS (from Tue, all in parallel; don't branch until the skeleton is merged)
• Vedant: API fixtures (JUL-9) → fetch pages (JUL-10) → retries (JUL-11); --from-file loader (JUL-12) any time
• Julian: messy fixture (JUL-14) → clean_record rules (JUL-15) → batch + duplicates (JUL-16)
• Nikita: SQLite schema (JUL-18) → upsert with added/updated/unchanged counts (JUL-19) → rollback + idempotency (JUL-20)
• Ansh: CLI with fakes (JUL-22), integration test, xfail until modules land (JUL-23), README (JUL-24)

RULES
• Only edit files you own (PLAN.md §3). Need a change elsewhere? Ask the owner.
• Branch = yourname/area-topic, small PRs, rebase on main daily
• Run scripts/check.sh before pushing. No network in tests, tmp DBs only.
• Using AI? Paste the ticket's prompt. It tells the AI exactly which files it may change.
• Move your Linear ticket: In Progress → In Review → Done. Put the JUL-ID in your PR title.

CHECKPOINTS: Tue EOD 1 PR each merged · Wed EOD all modules real · Thu noon full integration run · Fri demo
```
