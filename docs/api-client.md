# API client

Owner: Vedant Misra. Code: `src/customer_sync/api_client.py`. Tests: `tests/test_api_client.py`.

## What it does

`RandomUserClient` is the first stage of the pipeline. It asks the Random User API for
customer records and hands them on, untouched, to the cleaning stage. It does no cleaning
itself: it returns the raw `results` list, exactly as the API sent it.

```
RandomUserClient  ->  cleaning  ->  SQLite storage  ->  summary
```

Each request is a `GET` to `https://randomuser.me/api/1.4/` with three query parameters:

| Param | Default | Why |
|---|---|---|
| `seed` | `team2` | A fixed seed makes the API return the same people every time, so runs are repeatable. |
| `results` | `50` | Records per page. |
| `page` | `1`, then `2`, ... | Which page of that seeded list. `pages` (default 1) sets how many pages `fetch_records()` walks. |

The URL is pinned to `/api/1.4/`. The API version is part of the path, so a field renamed in a
later version cannot change our data overnight.

Two methods:

- `fetch_page(page)` returns one page of raw records.
- `fetch_records()` returns every configured page joined into one list. This is the method the
  rest of the pipeline calls. `FileSource` (used by `--from-file`) has the same method, so the
  pipeline cannot tell the two apart.

If anything cannot be recovered, the client raises `ApiError`. It never returns partial or
guessed data.

## Retry policy

The client makes up to **3 attempts** per page (`max_retries=3`, the total number of attempts,
not extra ones). It waits between attempts with exponential backoff, `backoff * 2**(attempt-1)`:

| Attempt | Outcome | Wait before next |
|---|---|---|
| 1 | fails | 0.5 s |
| 2 | fails | 1.0 s |
| 3 | fails | none: raise `ApiError` |

Each attempt has a 10 s timeout, so the worst case for one page is about 31.5 s (3 timeouts plus
1.5 s of waiting).

**Retried** (these are usually temporary):

- connection errors and timeouts
- server errors (HTTP 5xx)
- rate limiting (HTTP 429)
- an HTTP 200 whose body is `{"error": "..."}`. Random User sometimes does this when it is
  overloaded.

**Not retried** (trying again will not help, so we fail at once):

- other 4xx responses such as 404: our request is wrong
- a body that is not valid JSON
- a JSON body with no `results` list

**Why 3 attempts?** Most outages that fix themselves clear within a couple of seconds, and the
backoff covers that. More attempts would only keep the nightly job hanging on an API that is
really down, and would hit a free public service harder. A job that fails clearly after about
2 s is better than one that fails vaguely after minutes. The next scheduled run is the longer
retry. All three numbers (`max_retries`, `backoff`, `timeout`) are constructor arguments, so
they can be changed without touching the code.

**Why back off at all?** Immediate retries tend to hit the same overloaded server in the same
bad moment. Doubling the wait gives it room to recover.

The error message names the page, the URL, the number of attempts and the last cause, for
example:

```
page 1 from http://127.0.0.1:9 failed after 3 attempt(s): HTTPConnectionPool(host='127.0.0.1', port=9): Max retries exceeded ... Connection refused
```

For tests, `session` and `sleep` are injectable, so the suite uses saved responses and never
touches the network or really sleeps.

## Live demo script

Run from the repository root with the virtual environment active
(`source .venv/bin/activate`, then `pip install -e ".[dev]"` once). Total time: about 3 minutes.

### 1. Live call

```bash
python -c "
from customer_sync.api_client import RandomUserClient
records = RandomUserClient().fetch_records()
print(len(records), 'records')
print(records[0]['login']['uuid'], records[0]['name']['first'], records[0]['email'])
"
```

Expected: `50 records`, then the uuid, first name and email of the first record. Point out that
`seed=team2` means anyone running this sees the same 50 people.

Optional, to show the exact URL we send:

```bash
python -c "
import requests
print(requests.Request('GET', 'https://randomuser.me/api/1.4/', params={'seed': 'team2', 'results': 50, 'page': 1}).prepare().url)
"
```

### 2. Forced failure

Port 9 on localhost has nothing listening, so every connection is refused immediately. That
is a safe, offline way to make the API "go down".

```bash
time python -c "
import sys
from customer_sync.api_client import RandomUserClient
from customer_sync.contracts import ApiError
try:
    RandomUserClient(base_url='http://127.0.0.1:9').fetch_records()
except ApiError as exc:
    print('error:', exc, file=sys.stderr)
    sys.exit(1)
"
echo "exit code: $?"
```

What to say while it runs:

1. Nothing prints for about 1.5 s. That is the client retrying: attempt 1 fails, waits 0.5 s,
   attempt 2 fails, waits 1.0 s, attempt 3 fails.
2. Then one clear error appears: which page, which URL, how many attempts, and the cause
   (`Connection refused`).
3. `exit code: 1` (the `time` line shows about 1.7 s in total). A scheduler sees the non-zero
   exit and can alert.

Optional, to show the waiting without delay: pass `sleep=print`. Each backoff then prints
(`0.5`, then `1.0`) instead of pausing. The error itself goes to stderr, which this hides.

```bash
python -c "
from customer_sync.api_client import RandomUserClient
RandomUserClient(base_url='http://127.0.0.1:9', sleep=print).fetch_records()
" 2>/dev/null
```

### 3. Same failure through the CLI (once the CLI is merged)

The CLI has no base-URL flag, so the forced failure above stays a Python snippet. A normal run
uses the same client and turns `ApiError` into exit code 1:

```bash
customer-sync --db demo.db
echo "exit code: $?"
```

### 4. Tests

```bash
pytest tests/test_api_client.py -q
```

All of these run offline against the saved responses in `tests/fixtures/api/`.

## Q&A

### What happens if the API is down during the nightly job?

The client retries with backoff (3 attempts, 0.5 s then 1.0 s apart). If it is still failing,
it raises `ApiError` with a message that names the page, URL, attempt count and cause. The CLI
turns that into exit code 1 and an error message.

The database is not touched. The pipeline fetches first, then cleans, then stores, and the
fetch fails before anything is written. Because a sync is an upsert on `login.uuid`, the next
successful run simply catches up, and re-running never creates duplicates.

The scheduler is what notices: cron or CI should alert on a non-zero exit code. If the API is
down for hours, the next night's run is the real retry.

### How do we add a second data source without a rewrite?

The pipeline only needs one thing from a source: `fetch_records()` returning a list of raw
records. That is the `RecordSource` protocol in `contracts.py`, and `RandomUserClient` and
`FileSource` already both satisfy it.

1. Write a new class with `fetch_records()` (for example `CsvSource` or `CrmClient`). It raises
   `SyncError` subclasses on failure, like the others.
2. Choose it with a CLI flag (for example `--source crm`). `run_sync` already accepts any
   `RecordSource`, so it does not change.
3. Add a per-source mapper in cleaning that turns that source's field names into the same raw
   shape (or straight into the agreed `Customer`). Validation, storage and the summary stay
   as they are.

### Bonus: what if the API renames a field overnight?

The URL pins `/api/1.4/`, so the version we coded against keeps its field names. If a field
ever did go missing, cleaning rejects the record with `missing_field` instead of inventing a
value.
