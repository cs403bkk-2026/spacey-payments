-- PT-016: payments live in their own table. No foreign key to bookings on
-- purpose - Payment never touches Bookings. Safe to run more than once.
DO $$ BEGIN
  CREATE TYPE payment_status AS ENUM ('success', 'failed', 'unknown');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
  CREATE TYPE payment_currency AS ENUM ('USD');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS payments (
  id              SERIAL PRIMARY KEY,
  booking_id      INTEGER NOT NULL,
  amount_cents    INTEGER NOT NULL CHECK (amount_cents > 0),
  currency        payment_currency NOT NULL DEFAULT 'USD',
  status          payment_status   NOT NULL,
  reason          TEXT,
  card_last4      TEXT,
  idempotency_key TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
