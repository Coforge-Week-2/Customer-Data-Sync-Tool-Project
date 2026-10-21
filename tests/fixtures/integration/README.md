# Integration fixtures

Saved API responses for the end-to-end sync test. Shape: `{"results": [...], "info": {...}}`, same as the Random User API. `FileSource` reads `results` only.

Indexes are positions in `results` (0-based). Records 0-9 are copied from `tests/fixtures/raw/seed_team2_r10_p1.json`. That file is frozen and is not edited here. It has 10 unique `login.uuid` values and 10 unique emails, so the counts below hold.

Reject rules come from PLAN.md §2.1. A missing required field is `missing_field`. A repeated `uuid` in the same batch is `duplicate` (first occurrence kept).

## day1.json

12 records. Sync into an empty database.

| Index | Case | Expected result |
|---|---|---|
| 0-9 | The 10 raw records, unchanged | accepted |
| 10 | Copy of record 1 with a new uuid (`10000000-0000-4000-8000-000000000010`) and the `email` key removed | rejected: `missing_field` (email) |
| 11 | Copy of record 0 with the same uuid (`18d3d4f8-1b6c-480d-be6f-51de14bc1017`) and a different email (`duplicate.uuid@example.com`) | rejected: `duplicate` (uuid first seen at #0) |

Counts on an empty database: **added 10, updated 0, unchanged 0, rejected 2**.

## day2_edited.json

13 records. Sync into the database that day1 already filled.

| Index | Case | Expected result |
|---|---|---|
| 0 | Same as day1 record 0, except `phone` changed from `(026) 7000444` to `(026) 7000999` (Beaudine Ottevanger) | accepted, **updated** |
| 1-9 | Same as day1 records 1-9, no field changes | accepted, **unchanged** |
| 10 | Brand-new valid record: Nova Fixture, uuid `10000000-0000-4000-8000-000000000012`, email `nova.fixture@example.com` | accepted, **added** |
| 11 | Same missing-email record as day1 index 10 | rejected: `missing_field` (email) |
| 12 | Same duplicate-uuid record as day1 index 11 | rejected: `duplicate` (uuid first seen at #0) |

Counts after day1: **added 1, updated 1, unchanged 9, rejected 2**.

## day1 a second time

Run `day1.json` again on a database that already has that same day1 sync. Nothing in the 10 accepted records changed, so the second run is **added 0, updated 0, unchanged 10, rejected 2**.

## Notes

- The two invalid records are identical in both files. They are never stored.
- Record 10 in day1 has its own uuid, so it is rejected only because `email` is missing.
- Record 11 keeps record 0's uuid and uses a new email, so it is rejected only because the uuid is already in the batch.
- The new day2 record is a copy of record 0 with a new name, uuid, email, and phone, so it does not collide with the original 10.
