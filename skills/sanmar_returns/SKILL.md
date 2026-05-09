---
name: sanmar_returns
description: |
  Automate return-merchandise-authorisation (RMA) submissions on
  sanmar.com via a headless Chromium browser. Use this skill when the
  caller asks to start, fill, or submit a return for a SanMar sales
  order. The skill drives the live customer portal — it does not call
  the web-services SOAP API (which has no public returns endpoint).
---

# SanMar Returns Skill

Browser-automation skill that performs the end-to-end manual workflow
a SanMar customer would execute in their browser to file a return:

1. Log in at `https://www.sanmar.com/login`.
2. Navigate to `My SanMar → Order History`.
3. Find the right sales order (`SO-XXXXXXXXX`).
4. Click the return icon to open the initiation form
   (`/mysanmar/returns/initiate?salesOrderNumber=...`).
5. Tick line items, enter quantities, pick a reason, fill any
   reason-specific follow-up fields.
6. Submit and capture the RMA number.

It is built on Playwright (sync API) and reuses a single Chromium
context across tool calls in the same skill process. Cookies and local
storage are persisted to a `storage_state` JSON file so subsequent
invocations within the session-cookie's lifetime can skip the login
step.

## When to use this skill

Invoke a `sanmar_returns_*` tool when the caller's request involves any of:

- Initiating a return on an existing SanMar order.
- Marking specific SKUs / colors / sizes for return.
- Submitting an RMA request and capturing the resulting RMA number.

Do **not** use this skill for:

- Order placement, inventory, pricing, status, tracking, or PO PDF
  parsing — those live in the sibling `sanmar` skill (SOAP / FTP).
- Other vendors. The selectors are sanmar.com-specific.

## Architecture

Three layers, kept thin:

* **`pages/`** — Playwright page objects, one per page. Selectors live
  here and nowhere else.
  * `LoginPage`, `OrdersPage`, `ReturnFormPage`. (No `OrderDetailPage` —
    sanmar.com starts returns directly from the order-history row, so
    no detail page is involved.)
* **`tools/`** — agent-facing functions plus shared infrastructure.
  * `result.py` — `ToolResult` dataclass.
  * `session.py` — module-level `BrowserSession` singleton.
  * `retry.py` — `@with_retry` decorator (3 attempts, exponential
    backoff, screenshots failures).
  * `return_tools.py` — the seven exported tool functions.
* **`tests/test_selectors.py`** — live-site smoke tests gated by
  `SMOKE=1` so they never run in CI by accident.

## Credential flow

This skill follows the same class-2 contract the sibling `sanmar`
skill uses: **the calling agent collects credentials from the user and
passes them explicitly into `login()`**. Credentials are never read
from environment variables and are never logged. Once `login()`
succeeds the resulting session cookies are stored on disk so further
tool calls in the same container do not need them again until the
session expires.

```python
from skills.sanmar_returns import login, find_order, initiate_return, fill_return_form, submit_return

login(username=user_supplied_username, password=user_supplied_password)
find_order(order_number="SO-160940237")
initiate_return(order_number="SO-160940237")
fill_return_form(items=[
    {
        "style_number": "112PL",
        "color": "Black",
        "size": "OSFA",
        "quantity": 2,
        "reason": "DEFECTIVE_DAMAGED",
        "details": "Loose stitching on the brim of both hats.",
        "needs_replacement": True,
        # "image_path": "/tmp/defect.jpg",  # optional
    }
])
submit_return()
```

## Tool reference

All tools return a `ToolResult`:

```python
@dataclass
class ToolResult:
    success: bool
    observation: str          # human-readable summary
    data: dict | None         # tool-specific payload
    screenshot: str | None    # base64 PNG, set on failure
    metadata: dict
```

| Tool | Purpose | Risk |
| --- | --- | --- |
| `login(username, password, *, force=False)` | Authenticate and persist `storage_state`. | low — no submission |
| `find_order(order_number)` | Verify an SO is in order history; return PO/date/status. | read-only |
| `initiate_return(order_number)` | Deep-link to the return form. | read-only |
| `fill_return_form(items)` | Tick line items, set qty, choose reason, populate sub-row. | low — no submission |
| `submit_return()` | Click **Continue** to submit. Confirmation parsing is **not yet implemented**. | **high — external write** |
| `take_screenshot(*, full_page=True)` | Capture current page as base64 PNG. | read-only |
| `run_raw_playwright(code)` | Escape hatch; execs Python with `page` and `result` in scope. | high — arbitrary code |

### Workflow order

The tools are designed to compose linearly:

```
login → find_order → initiate_return → fill_return_form → submit_return
```

You do not have to call `find_order` before `initiate_return` — the
deep link in `initiate_return` works regardless — but `find_order` is
useful as a pre-flight to confirm the order exists, has shipped, and
matches what the user expects, *before* you touch the return form.

### Reasons and their required fields

The reason dropdown on the return form has five values. Three of them
require additional fields on the line item:

| `reason` | Extra fields required |
| --- | --- |
| `SAMPLES` | none |
| `UNWANTED` | none |
| `ORDER_INCORRECT` | `details` (str), `needs_replacement` (bool) |
| `DEFECTIVE_DAMAGED` | `details` (str), `needs_replacement` (bool); optional `image_path` |
| `INCORRECT_PRODUCT` | `details` (str), `needs_replacement` (bool) |

Pass the value (e.g. `"DEFECTIVE_DAMAGED"`), not the label. Validation
happens client-side in `fill_return_form` before any DOM interaction so
a missing required field surfaces as `success=False` immediately.

### Identifying a specific line item

`fill_return_form` matches each input dict against a row using
`style_number` plus optional `color` and `size`. If the order has
multiple colors or sizes of the same style, supply both disambiguators.
A match miss returns `success=False` with `observation` naming the
missing combination.

## Common failure modes

| Symptom | Likely cause | Recovery |
| --- | --- | --- |
| `login` succeeds but subsequent tools redirect to `/login` | Session cookie expired between calls. | Call `login(..., force=True)`. |
| `find_order` returns "Order not visible on the first 100 rows" | Order is older than what the order-history page renders by default. | The skill currently does not paginate. Confirm the SO with the user and call `initiate_return` directly — the deep link works for any SO on the account regardless of history-page filtering. |
| `fill_return_form` returns "No return-form row matched style=..." | Wrong style number, or missing color/size disambiguator. | Inspect the returned `screenshot` to read the visible style codes; retry with corrected fields. |
| `submit_return` reports `confirmation_pending=True` | Confirmation parsing is not yet configured (see TODO below). | Call `take_screenshot` and have the user verify the RMA visually. |
| Any tool fails with a Playwright `TimeoutError` after 3 retries | Site is slow, layout changed, or you hit an unexpected interstitial. | Inspect the attached `screenshot`. If the layout changed, update the relevant page object. |

## ⚠️ Known limitation — submission confirmation not yet captured

The submit-success page (post-`Continue`-click) has not yet been
inspected against a real successful submission. As a result:

- `ReturnFormPage.wait_for_confirmation()` raises `NotImplementedError`.
- `ReturnFormPage.extract_rma_number()` returns `None` and emits a
  warning log.
- `submit_return()` returns `success=True` after clicking Continue
  but with `data.rma_number = None` and
  `data.confirmation_pending = True`.

To finish the implementation, capture the post-submit URL, the success
banner element, and the RMA-number element from a real submission, then
update the two methods marked with `TODO(item-8b)` in
`pages/return_form_page.py`. Until that is done, the calling agent
should treat `submit_return` as "submission attempted, please verify"
and should screenshot the page so a human can confirm the RMA before
reporting success to the end user.

`grep -rn "TODO(item-8b)" skills/sanmar_returns` lists the spots that
need updating.

## Configuration

Operational env vars (none of these accept credentials):

| Variable | Default | Purpose |
| --- | --- | --- |
| `SANMAR_RETURNS_STORAGE_STATE` | `/tmp/sanmar-returns-storage.json` | Where to persist cookies / localStorage. |
| `SANMAR_RETURNS_HEADLESS` | `1` | Set to `0` to run with a visible browser when debugging locally. |
| `SANMAR_RETURNS_TIMEOUT_MS` | `15000` | Default per-action Playwright timeout. |

## Testing

Live-site smoke tests live in `tests/test_selectors.py`. They are
gated by `SMOKE=1`:

```bash
export SMOKE=1
export SANMAR_TEST_USERNAME=...
export SANMAR_TEST_PASSWORD=...
export SANMAR_TEST_ORDER=SO-160940237
export SANMAR_TEST_STYLE=112PL
SANMAR_RETURNS_HEADLESS=0 python -m pytest \
    skills/sanmar_returns/tests/test_selectors.py -s -v
```

Each test is independently runnable so you can verify one page object
at a time as you adjust selectors.
