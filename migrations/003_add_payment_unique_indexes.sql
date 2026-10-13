-- PT-019/PT-020: let the database settle concurrent retries. One row per
-- idempotency key (payments and refunds, 'refund:<payment_id>'), and at most one
-- 'success' payment per booking. Safe to run more than once.
CREATE UNIQUE INDEX IF NOT EXISTS payments_idempotency_key_unique
  ON payments (idempotency_key) WHERE idempotency_key IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS payments_one_success_per_booking
  ON payments (booking_id) WHERE status = 'success';
