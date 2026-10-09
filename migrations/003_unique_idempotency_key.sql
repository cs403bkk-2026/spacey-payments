-- A refund retry must never create a second ledger entry.
CREATE UNIQUE INDEX IF NOT EXISTS payments_idempotency_key_unique
    ON payments (idempotency_key) WHERE idempotency_key IS NOT NULL;
