# Cleaning fixtures

`messy_response.json` is the "before" data for the cleaner. Shape: `{"results": [...]}`, same as the API response. It holds 21 records: 13 should be accepted, 8 rejected.

Indexes 0-9 are the 10 clean records copied unchanged from `tests/fixtures/raw/seed_team2_r10_p1.json`. Indexes 10-20 are injected cases. Each injected case appears exactly once. Indexes are positions in `results` (0-based), which is the `index` the cleaner reports in a `Rejection`.

Rules and codes come from PLAN.md §2.1: a missing required field is `missing_field`, a wrong type that cannot be safely coerced is `wrong_type`, a bad format or blank value is `invalid_value`, and a repeated `uuid` or a repeated email under a different uuid is `duplicate` (first occurrence kept).

| Index | Case | Expected result |
|---|---|---|
| 0-9 | Clean records from the shared raw fixture | accepted, no changes needed beyond field mapping |
| 10 | `email` key missing | rejected: `missing_field` (email) |
| 11 | `email` is the number `12345` | rejected: `wrong_type` (email) |
| 12 | `name.first` is blank (`"   "`) | rejected: `invalid_value` (first_name empty after strip) |
| 13 | `email` is `"no-at-sign.com"` | rejected: `invalid_value` (email format) |
| 14 | `login.uuid` key missing | rejected: `missing_field` (uuid) |
| 15 | `registered.date` is `"yesterday"` | rejected: `invalid_value` (registered_at not ISO 8601) |
| 16 | Same `login.uuid` as record 0, different email | rejected: `duplicate` (uuid first seen at #0) |
| 17 | Same email as record 1, different uuid | rejected: `duplicate` (email first seen at #1) |
| 18 | `email` is `" Foo@BAR.com "` | accepted, email becomes `foo@bar.com` |
| 19 | `phone` key missing | accepted, `phone` is `None` |
| 20 | `phone` is the number `5551234567` | accepted, `phone` becomes `"5551234567"` |

## Totals for the batch test

- Accepted: 13 (indexes 0-9, 18, 19, 20).
- Rejected: 8, as `(index, code)` pairs: `(10, missing_field)`, `(11, wrong_type)`, `(12, invalid_value)`, `(13, invalid_value)`, `(14, missing_field)`, `(15, invalid_value)`, `(16, duplicate)`, `(17, duplicate)`.
- Order of accepted customers matches input order.

## Notes

- Injected records are copies of clean records with a new name and a new `login.uuid` (`10000000-0000-4000-8000-0000000000NN`, where NN is the index), so each one fails or passes for exactly one reason.
- Record 14 has no uuid, so its `Rejection.uuid` is `None`.
- Record 12 is whitespace-only on purpose: it shows that strip happens before the non-empty check.
- Do not edit `tests/fixtures/raw/`. If the shared raw fixture changes, regenerate indexes 0-9 and re-check this table.
