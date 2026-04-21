-- Seed MySQL schema + sample data for the CDC pipeline.
-- Auto-loaded by the mysql container on first boot via /docker-entrypoint-initdb.d.

USE sales;

-- Debezium needs binlog + REPLICATION SLAVE privileges
GRANT RELOAD, FLUSH_TABLES, REPLICATION CLIENT, REPLICATION SLAVE ON *.* TO 'debezium'@'%';
GRANT ALL PRIVILEGES ON sales.* TO 'debezium'@'%';
FLUSH PRIVILEGES;

-- ----------------------------------------------------------------------------
-- customers
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
    customer_id     INT          NOT NULL AUTO_INCREMENT,
    email           VARCHAR(255) NOT NULL,
    first_name      VARCHAR(100),
    last_name       VARCHAR(100),
    country         CHAR(2),
    tier            ENUM('bronze', 'silver', 'gold', 'platinum') DEFAULT 'bronze',
    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (customer_id),
    UNIQUE KEY ux_customers_email (email),
    INDEX ix_customers_country (country)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- products
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    product_id      INT          NOT NULL AUTO_INCREMENT,
    sku             VARCHAR(50)  NOT NULL,
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    category        VARCHAR(50),
    price           DECIMAL(10, 2) NOT NULL,
    is_active       BOOLEAN      DEFAULT TRUE,
    updated_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (product_id),
    UNIQUE KEY ux_products_sku (sku),
    INDEX ix_products_category (category)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- orders
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    order_id        BIGINT       NOT NULL AUTO_INCREMENT,
    customer_id     INT          NOT NULL,
    order_status    ENUM('placed', 'paid', 'shipped', 'delivered', 'cancelled') DEFAULT 'placed',
    total_amount    DECIMAL(12, 2) NOT NULL,
    currency        CHAR(3)      DEFAULT 'USD',
    placed_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (order_id),
    INDEX ix_orders_customer (customer_id),
    INDEX ix_orders_status (order_status),
    FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- order_items
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_items (
    order_id        BIGINT       NOT NULL,
    line_item_id    INT          NOT NULL,
    product_id      INT          NOT NULL,
    quantity        INT          NOT NULL,
    unit_price      DECIMAL(10, 2) NOT NULL,
    discount        DECIMAL(4, 2) DEFAULT 0.00,
    PRIMARY KEY (order_id, line_item_id),
    INDEX ix_order_items_product (product_id),
    FOREIGN KEY (order_id) REFERENCES orders (order_id),
    FOREIGN KEY (product_id) REFERENCES products (product_id)
) ENGINE=InnoDB;

-- Seed data — small, enough for local testing
INSERT INTO customers (email, first_name, last_name, country, tier) VALUES
    ('alice@example.com', 'Alice', 'Anderson', 'US', 'gold'),
    ('bob@example.com',   'Bob',   'Brown',    'GB', 'silver'),
    ('carol@example.com', 'Carol', 'Chen',     'IN', 'platinum');

INSERT INTO products (sku, name, category, price) VALUES
    ('SKU-00000001', 'Wireless Headphones', 'electronics', 89.99),
    ('SKU-00000002', 'Running Shoes',       'sports',      120.00),
    ('SKU-00000003', 'Cotton T-Shirt',      'apparel',     19.50);

INSERT INTO orders (customer_id, order_status, total_amount, currency) VALUES
    (1, 'delivered', 229.99, 'USD'),
    (2, 'shipped',   139.50, 'GBP'),
    (3, 'placed',    89.99,  'INR');

INSERT INTO order_items (order_id, line_item_id, product_id, quantity, unit_price, discount) VALUES
    (1, 1, 1, 1, 89.99, 0.00),
    (1, 2, 3, 2, 19.50, 0.05),
    (2, 1, 2, 1, 120.00, 0.15),
    (3, 1, 1, 1, 89.99, 0.00);
