-- DDL owner (AD-10). Each story adds the tables it needs.
-- US-101: products, orders, order_lines, audit_events.

CREATE TABLE products (
    sku              TEXT    PRIMARY KEY,
    name             TEXT    NOT NULL,
    returnable       INTEGER NOT NULL CHECK (returnable IN (0, 1)),
    quantity_on_hand INTEGER NOT NULL CHECK (quantity_on_hand >= 0)
);

CREATE TABLE orders (
    order_id       TEXT PRIMARY KEY,
    customer_email TEXT NOT NULL CHECK (customer_email <> '' AND customer_email = lower(trim(customer_email))),
    status         TEXT NOT NULL CHECK (status IN ('placed', 'shipped', 'delivered', 'cancelled')),
    order_date     TEXT NOT NULL,
    delivery_date  TEXT NULL,
    CHECK ((status = 'delivered') = (delivery_date IS NOT NULL))
);

CREATE TABLE order_lines (
    order_id         TEXT    NOT NULL REFERENCES orders (order_id),
    sku              TEXT    NOT NULL REFERENCES products (sku),
    quantity         INTEGER NOT NULL CHECK (quantity >= 1),
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0),
    PRIMARY KEY (order_id, sku)
);

-- No FKs: not_found events reference IDs that do not exist.
CREATE TABLE audit_events (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id     TEXT    NOT NULL UNIQUE,
    occurred_at  TEXT    NOT NULL,
    action       TEXT    NOT NULL,
    outcome      TEXT    NOT NULL,
    order_id     TEXT    NULL,
    return_id    TEXT    NULL,
    details_json TEXT    NOT NULL
);

CREATE INDEX ix_audit_events_order_id ON audit_events (order_id);
