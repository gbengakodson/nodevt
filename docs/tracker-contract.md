# NODE Tracker Contract — Specification

## Purpose
Formalize the tracker as a perpetual investment contract with a 5-year minimum commitment,
enforced by a declining early-exit penalty. Aligns with the Nigerian prudential savings
model (e.g. Zenith PrudentialLife) and protects the platform's long-term economics.

## Contract Terms

### Duration
- Perpetual. No maximum term.
- Minimum commitment: 5 years from activation.
- After year 5, user may close freely with 0% penalty.

### Exit Penalty Schedule
Applied to the user's **capital only** at time of close. Accrued NVT bonus is never subject to penalty.

| Tenure at close | Penalty % | User receives |
|---|---|---|
| < 1 year | 40% | 60% |
| 1–2 years | 30% | 70% |
| 2–3 years | 20% | 80% |
| 3–4 years | 10% | 90% |
| 4–5 years | 5% | 95% |
| 5+ years | 0% | 100% |

### User Disclosures
1. Activation form: mandatory checkbox with the 5-year term + penalty schedule.
2. Close attempt: modal showing exact years held, capital, penalty amount, net payout, and the year-5 relief.
3. Statement that accrued NVT bonus is not affected by the exit penalty.

### Backend
- New endpoint: `GET /api/trading/tracker_exit_penalty/?bot_id=<uuid>` → penalty info for a bot
- Modified endpoint: `POST /api/trading/close_grid/` → applies penalty before crediting net to user wallet
- New transaction type: `PENALTY` → recorded for audit trail
- **No admin waiver.** The penalty is applied programmatically with no override.

### Frontend
- Checkbox in the activation form (trading page) — required to activate
- Warning modal before close (dashboard) — shows exact numbers, no bypass
- Tracker card display: shows "Year X of 5" and current exit penalty percentage

### Edge Cases
- If capital is 0, penalty is 0 and net payout is 0.
- If user is within 30 days of the next penalty tier boundary, show "wait N days to save X%" hint.
- Penalty revenue is platform revenue, recorded separately from fees.

### Regulatory Notes
- Penalty schedule disclosed before activation. E-signature (checkbox + timestamp) is the record.
- Same legal basis as Nigerian prudential savings products.
- NVT bonus is separate from the contract and not penalized.

## Implementation Order
1. Backend penalty endpoint + logic in `close_grid`
2. Migration: add `PENALTY` to `Transaction.transaction_type` choices
3. Frontend: checkbox + close modal
4. Frontend: tracker card shows "Year X of 5" + current penalty
5. Test: activate → close at year 0.5 → verify 40% penalty
6. Test: activate → wait → close at year 5.5 → verify 0% penalty
7. Deploy