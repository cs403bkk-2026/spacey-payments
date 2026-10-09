-- Only the payment-related columns of the old bookings table.
-- No foreign keys: spaces and users live in other services.
CREATE TABLE IF NOT EXISTS bookings (
    id SERIAL PRIMARY KEY,
    member TEXT NOT NULL,
    paid BOOLEAN NOT NULL,
    amount_cents INTEGER,
    card_last4 TEXT
);
