-- ====================================================================== --
-- add_email_verification.sql                                              --
-- Additive migration for the two-phase email verification feature.        --
-- Safe to run multiple times (CREATE TABLE IF NOT EXISTS).                 --
-- Does NOT modify the existing clients / sales / payment_items tables.     --
-- ====================================================================== --

-- Table: unconfirmed_clients
-- Mirrors the clients table exactly, plus verification columns.
-- registered_by FK is critical for vendor fraud detection.
-- Do NOT modify the clients table in any way.

CREATE TABLE IF NOT EXISTS unconfirmed_clients (
    pending_client_id     SERIAL PRIMARY KEY,
    nombre_completo       VARCHAR                 NOT NULL,
    curp                  VARCHAR                 NOT NULL,
    clave_de_elector      VARCHAR                 NOT NULL,
    fecha_nacimiento      VARCHAR                 NOT NULL,
    domicilio             VARCHAR                 NOT NULL,
    email                 VARCHAR                 NOT NULL,
    phone                 VARCHAR,
    front_submission_id   INTEGER REFERENCES submissions(submission_id),
    back_submission_id    INTEGER REFERENCES submissions(submission_id),
    event_id              INTEGER REFERENCES events(event_id),
    registered_by         INTEGER NOT NULL REFERENCES users(user_id),
    registered_at         TIMESTAMP WITH TIME ZONE NOT NULL,
    confirmation_token    VARCHAR UNIQUE          NOT NULL,
    token_expires_at      TIMESTAMP WITH TIME ZONE NOT NULL,
    status                VARCHAR NOT NULL DEFAULT 'pending'
);

-- Table: payment_confirmation_tokens
-- One row per PaymentEvent (payment_event_id is UNIQUE).
-- verification_source column is intentionally present for future
-- bank statement reconciliation (phase 2). In phase 1 it is
-- always 'email'. Do not remove this column.

CREATE TABLE IF NOT EXISTS payment_confirmation_tokens (
    token_id             SERIAL PRIMARY KEY,
    payment_event_id     INTEGER NOT NULL UNIQUE
                             REFERENCES payment_events(payment_event_id),
    token                VARCHAR UNIQUE NOT NULL,
    expires_at           TIMESTAMP WITH TIME ZONE NOT NULL,
    status               VARCHAR NOT NULL DEFAULT 'pending',
    confirmed_at         TIMESTAMP WITH TIME ZONE,
    verification_source  VARCHAR NOT NULL DEFAULT 'email',
    created_at           TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
