---
name: countersign-api-match
description: Use whenever you add or change a backend HTTP endpoint or response shape in backend/app/api, or connect a frontend screen to the live backend. Keeps FastAPI responses identical to the shapes the finished frontend reads in frontend/src/api/types.ts.
---

# Keep the backend and the frontend in step

The frontend in `frontend/` is finished and runs on a mock API. Its contract with the backend is three files:

- `frontend/src/api/types.ts`: every response shape. **This is the source of truth.**
- `frontend/src/api/client.ts`: every endpoint path, method, header and form field.
- `frontend/src/api/mock.ts`: realistic example data and behaviour for each endpoint.

`docs/SPEC.md` §3.9 lists the same endpoints in prose.

## When you write an endpoint

1. Open `types.ts` and find the interface the endpoint returns (`Attempt`, `Stats`, `Registry`, `LedgerEvent`, `AppConfig`, `EvalResults`, `BatchSummary`, `DemoInvoice`, `LeaderboardEntry`).
2. Write a Pydantic response model with the same field names (snake_case) and the same optional/nullable fields. Amounts are decimal strings in human units, never floats.
3. Read the matching function in `mock.ts` for what realistic values look like, for example how `steps[]` progress and what `flags[]` contain.
4. Check it against the real server:
   ```bash
   curl -s localhost:8000/api/config | python3 -m json.tool
   curl -s localhost:8000/api/attempts/<id> -H "X-Device-Id: test-device" | python3 -m json.tool
   curl -s localhost:8000/api/team/attempts -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool | head -60
   ```
5. Run the frontend live (`cd frontend && npm run dev`, which proxies `/api` to :8000) and click through the screen that uses the endpoint. Run `npm run typecheck` if you touched any frontend file.

## Things that are easy to get wrong

- `GET /api/attempts/{id}` must answer a bounty phone **without** the admin token. Match the `X-Device-Id` header against the device that created the attempt; full detail for the owner device, outcome only for everyone else.
- `steps[]` always has the five names in order: `extract`, `hidden_text`, `match`, `guard`, `chain`. Skipped steps say `skipped`; a guard refusal is `status: done, detail: "refused"`.
- `hidden_text.spans[].bbox` is `[x0, y0, x1, y1]` in PDF points with a top-left origin (PyMuPDF's default), and `page_size` is `[width, height]` of that page.
- `tx.reason` is the contract's `Reason` name (`PayoutMismatch`), not its number.
- `pending_changes[].decoded` keys depend on the kind; SPEC §3.9 lists them. The Controls page reads them by name.
- Rate limits return **429** with `{message_en, message_zh}`. A rejected token returns 401 or 403. Anything 5xx makes every screen show "can't reach the server", so use 4xx for client mistakes.
- Return `[]` and `{}`, not `null`, for empty lists and empty eval results.

## When a shape really must change

Change `types.ts`, `client.ts` and `mock.ts` together in one commit, run `npm run typecheck` and `npm run build:mock`, and add a line to "Decisions made" in `docs/PROGRESS.md`.
