# Customer Data Sync Tool

Copies customer contact records from the Random User API into a local SQLite database. The pipeline fetches records, cleans and validates them, stores them, and prints how many were added, updated, unchanged, and rejected.

## Install

```bash
pip install -e ".[dev]"
```

## Locked decisions

Agreed by the team and frozen in `src/customer_sync/contracts.py`.

| Decision | Value |
|---|---|
| Unique identifier | `login.uuid` |
| Required fields | `uuid`, `first_name`, `last_name`, `email`, `registered_at` (`str`) |
| Optional fields | `phone`, `city`, `country` (`str` or `None`) |
| `registered_at` | UTC `YYYY-MM-DDTHH:MM:SSZ` |
| Bad records | Safe normalisation only (trim, lowercase email, numeric phone to text). Otherwise reject with a reason. Never invent a missing value. |
| Reject codes | `missing_field`, `wrong_type`, `invalid_value`, `duplicate` |
| In-batch duplicates | A repeated `uuid`, or a repeated email under a different uuid, is rejected. The first occurrence is kept. |
| API | `https://randomuser.me/api/1.4/` |
| Default fetch | `seed=team2`, `results=50`, `pages=1` |

```
customer-sync [--from-file PATH] [--db PATH=customers.db] [--seed team2] [--results 50] [--pages 1] [--quiet-rejections]
```
