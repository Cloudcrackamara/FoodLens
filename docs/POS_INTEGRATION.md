# FoodLens POS integration

This guide is for developers connecting a shop till (point of sale) to FoodLens. A till uses the API to:

- look up a pack before selling it;
- record a sale **after payment is confirmed**;
- record refunds and voids.

FoodLens is a demonstration prototype. All companies, partners and codes in examples are fictional.

> **Payment data stays in your till.** FoodLens stores no amounts, card details, customer details or checkout data. Requests carry only an opaque `payment_reference` (at most 100 characters) and your transaction ID. Bodies with any other field are refused.

Decisions behind this API: D121–D123 and D151 in `docs/DECISIONS.md`.

---

## 1. Credentials

A FoodLens admin sets up your partner account and gives you:

| Item | Format | Notes |
|---|---|---|
| API key | `flk_…` | Shown once. FoodLens stores only its SHA-256 hash. An admin can issue more keys and revoke any key. |
| Signing secret | `fls_…` | Shown once. FoodLens stores it encrypted. Keep it on your server, never in a browser or app bundle. |
| Retailer ID | UUID | One per shop company linked to your account. |
| Till ID | text, at most 64 characters | Your own till reference, registered by the admin against one of the shop's reviewed locations. That location gives each event its area. |

A request is accepted only when all of these hold:

- the retailer is approved on FoodLens, is a retailer, and is linked to your account;
- the till is registered for that retailer on a reviewed location.

---

## 2. Signing a request

Every request is a `POST` with a JSON body and three headers:

| Header | Value |
|---|---|
| `X-FoodLens-Key` | Your API key. |
| `X-FoodLens-Timestamp` | The current Unix time in seconds. |
| `X-FoodLens-Signature` | Lower-case hex `HMAC-SHA256(signing_secret, "{timestamp}.{raw_body}")`. |

Rules:

- Sign the **exact bytes** you send. Serialise the body once, sign those bytes, and send the same bytes. Don't let your HTTP library re-serialise the JSON.
- The timestamp must be within **300 seconds** of FoodLens's clock, either way (`POS_MAX_SKEW_SECONDS`). Keep till clocks synced with NTP.
- The timestamp is signed together with the body, so a captured request can't be resent under a fresh timestamp.

### Python

<!-- example: python-signing -->
```python
import hashlib
import hmac
import json
import time


def signed_request(api_key, signing_secret, body, timestamp=None):
    """Return (raw_body, headers) for a FoodLens POS call. Send raw_body exactly as returned."""
    raw_body = json.dumps(body, separators=(",", ":")).encode("utf-8")
    ts = str(int(time.time()) if timestamp is None else timestamp)
    message = ts.encode("ascii") + b"." + raw_body
    signature = hmac.new(signing_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-FoodLens-Key": api_key,
        "X-FoodLens-Timestamp": ts,
        "X-FoodLens-Signature": signature,
    }
    return raw_body, headers
```

Sending it, for example with `httpx`:

```python
import httpx

raw_body, headers = signed_request(API_KEY, SIGNING_SECRET, sale)
response = httpx.post(f"{BASE_URL}/api/pos/v1/sales", content=raw_body, headers=headers)
```

### JavaScript (Node.js 18 or later)

<!-- example: js-signing -->
```js
import { createHmac } from "node:crypto";

export function signedRequest(apiKey, signingSecret, body, timestamp) {
  const rawBody = JSON.stringify(body);
  const ts = String(timestamp ?? Math.floor(Date.now() / 1000));
  const signature = createHmac("sha256", signingSecret)
    .update(`${ts}.${rawBody}`, "utf8")
    .digest("hex");
  return {
    rawBody,
    headers: {
      "Content-Type": "application/json",
      "X-FoodLens-Key": apiKey,
      "X-FoodLens-Timestamp": ts,
      "X-FoodLens-Signature": signature,
    },
  };
}
```

Sending it:

```js
const { rawBody, headers } = signedRequest(API_KEY, SIGNING_SECRET, sale);
const response = await fetch(`${BASE_URL}/api/pos/v1/sales`, {
  method: "POST",
  headers,
  body: rawBody,
});
```

`backend/tests/test_pos_docs.py` runs both examples against the test API, so they stay correct.

---

## 3. Endpoints

Base path: `{PUBLIC_BASE_URL}/api/pos/v1`. Every body includes `retailer_id` and `till_id`.

Pack codes are the 26-character code printed under the QR, or the code read from the QR (the last part of `/p/{code}`). Spaces and hyphens are ignored, `O` is read as `0`, and `I` and `L` as `1`. Responses show only the last 4 characters.

### `POST /units/lookup`

This endpoint is read-only: it never changes anything. Call it when a pack is scanned, before payment.

```json
{
  "retailer_id": "5b1f0c7e-2a51-4c1e-9f0a-3d2c1b0a9e88",
  "till_id": "DEMO-TILL-1",
  "code": "7Q2M 8KD3 XH4N 9PRT 6WCV 5JBZ 3F"
}
```

Response `200`:

```json
{
  "subject": "UNIT",
  "code_last4": "BZ3F",
  "product_name": "Sample Palm Oil",
  "brand": "Demo Harvest Foods",
  "size": "1 L",
  "gtin": "96385074",
  "batch_number": "DEMO-LOT-101",
  "expiry_date": "2027-12-04",
  "status": "IN_STOCK",
  "warning": null
}
```

`status` is one of `ISSUED`, `RELEASED`, `IN_TRANSIT`, `IN_STOCK`, `SOLD`, `RECALLED` and `VOIDED`.

`warning` is `null`, or one of the following. Show it to the cashier.

| `warning.code` | `warning.message` |
|---|---|
| `ALREADY_SOLD` | Already recorded as sold on {date}. Don't sell this pack until it's checked. |
| `RECALLED` | Covered by a recall from the manufacturer. Don't sell. |
| `UNRELEASED` | Not yet released for sale by the manufacturer. Don't sell. |
| `VOIDED` | This code was voided by the manufacturer. Don't sell. |
| `CARTON_CODE` | This is a carton code. Scan the individual pack. |

An unknown code returns `404 UNKNOWN_CODE`.

### `POST /sales`

Call this **only after the till has confirmed payment**.

```json
{
  "retailer_id": "5b1f0c7e-2a51-4c1e-9f0a-3d2c1b0a9e88",
  "till_id": "DEMO-TILL-1",
  "transaction_id": "DEMO-TXN-000123",
  "payment_reference": "DEMO-PAY-88412",
  "occurred_at": "2026-10-30T14:05:00+01:00",
  "units": ["7Q2M8KD3XH4N9PRT6WCV5JBZ3F", "2K9D4M7Q1XRT8WCV6PZB3HN5JA"]
}
```

| Field | Rule |
|---|---|
| `transaction_id` | Your transaction ID, 1–100 characters. Part of the idempotency key. |
| `payment_reference` | An opaque reference, 1–100 characters. Don't put amounts or card data in it. |
| `occurred_at` | When payment was confirmed. ISO 8601 **with a time zone**. It may be up to `POS_MAX_EVENT_AGE_DAYS` (default 7) days old, and at most 5 minutes in the future. |
| `units` | 1–100 pack codes (`POS_MAX_UNITS_PER_REQUEST`). |

Response `200`. Each pack has its own result, and a refused pack does not stop the others:

```json
{
  "transaction_id": "DEMO-TXN-000123",
  "event_type": "SOLD",
  "recorded": 1,
  "errors": 1,
  "units": [
    { "index": 0, "code_last4": "BZ3F", "result": "RECORDED", "error": null },
    {
      "index": 1,
      "code_last4": "N5JA",
      "result": "ERROR",
      "error": {
        "code": "ALREADY_SOLD",
        "message": "This pack is already recorded as sold. Don't complete the sale; set the pack aside and check it."
      }
    }
  ]
}
```

After a sale, a buyer who checks the pack at `/check` sees "Just sold by {retailer}" for `JUST_SOLD_WINDOW_HOURS` (default 6).

### `POST /refunds`

Records `RETURNED` for packs whose standing sale belongs to this retailer, however the sale was recorded (this API or the FoodLens merchant page).

- The pack goes back `IN_STOCK` at the retailer.
- The sold state is cleared, so the next consumer check shows "In circulation, not yet sold".
- The `SOLD` event always stays in the history, and the return points to it.

```json
{
  "retailer_id": "5b1f0c7e-2a51-4c1e-9f0a-3d2c1b0a9e88",
  "till_id": "DEMO-TILL-1",
  "transaction_id": "DEMO-RFD-000045",
  "occurred_at": "2026-10-30T16:20:00+01:00",
  "units": ["7Q2M8KD3XH4N9PRT6WCV5JBZ3F"]
}
```

`transaction_id` is the refund's own transaction ID. `occurred_at` must not be earlier than the sale's.

### `POST /voids`

Records `SALE_CORRECTED`, for a sale rung up by mistake. The body is the same as for a refund, plus `reason` (required, at most 500 characters). The pack goes back `IN_STOCK`, and the earlier sale stays in the history.

```json
{
  "retailer_id": "5b1f0c7e-2a51-4c1e-9f0a-3d2c1b0a9e88",
  "till_id": "DEMO-TILL-1",
  "transaction_id": "DEMO-VOID-000007",
  "occurred_at": "2026-10-30T14:07:00+01:00",
  "units": ["7Q2M8KD3XH4N9PRT6WCV5JBZ3F"],
  "reason": "Scanned twice"
}
```

Refunds and voids return the same response shape as sales.

---

## 4. Idempotency and retries

Each pack event is unique on **(partner, `transaction_id`, pack, event type)**.

- Resending a request with the same `transaction_id` returns the same per-pack results and writes nothing new. This holds whether you resend the identical signed request or re-sign it with a new timestamp.
- So when a request times out or the connection drops, retry it with the **same** `transaction_id`. Never generate a new one for a retry.
- The same pack in a **new** `transaction_id` is a new sale, and gets `ALREADY_SOLD` while the first sale stands.
- A refund may reuse the sale's transaction ID, because the event type differs.

## 5. Offline queueing

When the till is offline:

1. Complete the sale in the till as usual, and store the FoodLens request body with the real `occurred_at` (the time payment was confirmed).
2. When the connection returns, send the queued requests **in the order they happened**, oldest first. Sign each one at send time with the current timestamp.
3. Retry failures with the same body and `transaction_id` (see section 4).

FoodLens accepts events up to `POS_MAX_EVENT_AGE_DAYS` (default 7) days old, and rebuilds each pack's status from its events in `occurred_at` order, so a late sale takes its place in the history. Older events get `EVENT_TOO_OLD`; record those on the merchant page instead.

A late event is checked against the pack's **current** status. If newer events already exist for the pack, the pack ends in the state of the newest event, and both events stay in the history (D151).

## 6. Errors

Request-level errors have this shape, with no per-pack list:

```json
{ "error": { "code": "STALE_TIMESTAMP", "message": "Request timestamp is too far from the server time. Check the till clock." } }
```

| HTTP | `code` | Message | What to do |
|---|---|---|---|
| 401 | `MISSING_SIGNATURE` | Missing X-FoodLens-Key, X-FoodLens-Timestamp or X-FoodLens-Signature header. | Send all three headers. |
| 401 | `INVALID_KEY` | API key not recognised. | The key is wrong or revoked, or the account is suspended. Ask the FoodLens admin. |
| 401 | `STALE_TIMESTAMP` | Request timestamp is too far from the server time. Check the till clock. | Sync the clock, re-sign and resend. |
| 401 | `INVALID_SIGNATURE` | Signature does not match the request. | Sign the exact bytes you send, with the right secret. |
| 403 | `RETAILER_NOT_LINKED` | This retailer is not linked to your POS account, or is not approved on FoodLens. | Check `retailer_id`; ask the admin. |
| 404 | `UNKNOWN_CODE` | No FoodLens code found. Check the code and try again. | Lookup only. |
| 422 | `UNKNOWN_TILL` | This till is not registered for the retailer. | Check `till_id`; ask the admin. |
| 422 | `INVALID_BODY` | Request body is not valid. Check the fields against the POS integration guide. | Missing or extra field, a bad type, or `occurred_at` without a time zone. |
| 422 | `EVENT_TOO_OLD` | This event is older than {N} days and can't be recorded. | Record it on the merchant page. |
| 422 | `EVENT_IN_FUTURE` | This event's time is in the future. Check the till clock. | Fix the clock. |
| 422 | `TOO_MANY_UNITS` | A request can carry at most {N} packs. | Split the request. |
| 422 | `NEED_REASON` | Give a reason for the void. | Voids only. |
| 429 | `RATE_LIMITED` | Too many requests. Try again in {s} seconds. | Wait for `Retry-After` seconds. |
| 503 | `POS_NOT_CONFIGURED` | POS integration is not set up on this server. | Server configuration; contact FoodLens. |

Per-pack errors (in `units[].error`, with HTTP 200):

| `code` | Message |
|---|---|
| `ALREADY_SOLD` | This pack is already recorded as sold. Don't complete the sale; set the pack aside and check it. |
| `RECALLED` | This pack is covered by a recall, so it can't be recorded. |
| `UNRELEASED` | The manufacturer has not released this code for sale yet, so it can't be recorded. |
| `VOIDED` | This code was voided by the manufacturer, so it can't be recorded. |
| `CARTON_CODE` | This is a carton code. Scan the individual pack. |
| `UNKNOWN_CODE` | No FoodLens code found. Check the code and try again. |
| `DUPLICATE_IN_REQUEST` | This pack appears more than once in the sale. |
| `NOT_SOLD` | This pack is not recorded as sold. (Refunds and voids.) |
| `NOT_SELLER` | Only the company that recorded the sale can do this. (Refunds and voids.) |
| `BEFORE_SALE` | The refund time is earlier than the sale. (Refunds and voids.) |

## 7. Rate limits

Each partner has its own token bucket: a burst of `RATE_LIMIT_POS_BURST` requests (default 60), refilled at `RATE_LIMIT_POS_REFILL_PER_SECOND` (default 5 per second). One partner's traffic never uses up another's. Over the limit, you get `429` with a `Retry-After` header.

## 8. What FoodLens does with your data

- **Each event stores:** the pack, the event type, the retailer, your partner account, the till ID, the area of the till's location, `occurred_at`, the time FoodLens recorded it, `transaction_id` and `payment_reference`.
- **FoodLens never stores:** amounts, card data, customer details, or the cashier's identity.
- **Lookups** store nothing.
- **Recorded events feed** the consumer check result and the manufacturer's dashboard.

## 9. Simulated till

`/demo/pos` is a demonstration till. It is available only when the server runs with `DEMO_POS_ENABLED=true` (off by default), and only to signed-in members of a retailer linked to the demo partner.

- The browser sends only the till and the code.
- The FoodLens server builds the same JSON body described above and signs it with the demo partner's secret, which never reaches the browser.
- It then runs the same checks and the same recording code as the real API. The only step it skips is the API key lookup, because the demo key is never stored (D151).
