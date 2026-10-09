-- PT-013: Add 'refunded' to payment_status enum for cancellation refunds.
-- Safe to run more than once.
ALTER TYPE payment_status ADD VALUE IF NOT EXISTS 'refunded';
