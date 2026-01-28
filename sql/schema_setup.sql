-- DATABASE SCHEMA SETUP
-- Project: restaurant customer segmentatiom
-- Database: PostgreSQL

-- ==========================================
-- 1. REFERENCE TABLES (Create these FIRST)
-- ==========================================

-- Categories for Menu Items
CREATE TABLE IF NOT EXISTS category (
    category_id INTEGER PRIMARY KEY,
    category_name TEXT NOT NULL,
    large_category TEXT
);

-- Staff / Employees
CREATE TABLE IF NOT EXISTS employee (
    employee_id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    first_name TEXT,
    last_name TEXT,
    role TEXT
);

-- Discounts (Escomptes)
CREATE TABLE IF NOT EXISTS escompte (
    id SERIAL PRIMARY KEY,
    escompte_id INTEGER UNIQUE,
    escompte_name TEXT
);

-- Payment Methods
CREATE TABLE IF NOT EXISTS methode_paiement (
    id SERIAL PRIMARY KEY,
    methode_paiement_id INTEGER UNIQUE,
    methode_name TEXT UNIQUE
);

-- Time Dimension (Weeks)
CREATE TABLE IF NOT EXISTS week (
    week_id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    week_start TIMESTAMP NOT NULL,
    week_end TIMESTAMP NOT NULL,
    year INTEGER NOT NULL,
    iso_year INTEGER NOT NULL,
    month INTEGER NOT NULL
);

-- Menu Items (Links to Category)
CREATE TABLE IF NOT EXISTS item (
    item_id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    category_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    price REAL,
    CONSTRAINT fk_item_category FOREIGN KEY (category_id)
        REFERENCES category (category_id)
);


-- ==========================================
-- 2. TRANSACTION TABLES (Create these SECOND)
-- ==========================================

-- Bills ( The Main Ticket)
CREATE TABLE IF NOT EXISTS bill_id (
    id SERIAL PRIMARY KEY,
    bill_id INTEGER UNIQUE, -- The ID from the POS
    employee_id INTEGER,
    table_id INTEGER,
    date DATE,
    time TIME,
    is_redistribuee BOOLEAN,
    CONSTRAINT fk_bill_employee FOREIGN KEY (employee_id)
        REFERENCES employee (employee_id)
);

-- Bill Items (Individual Rows on a Bill)
CREATE TABLE IF NOT EXISTS bill_items (
    id SERIAL PRIMARY KEY,
    bill_id INTEGER,
    item_id INTEGER,
    quantity REAL,
    CONSTRAINT fk_bill_items_bill FOREIGN KEY (bill_id)
        REFERENCES bill_id (bill_id),
    CONSTRAINT fk_bill_items_item FOREIGN KEY (item_id)
        REFERENCES item (item_id)
);

-- Bill Totals (Payment Info)
CREATE TABLE IF NOT EXISTS bill_total (
    id SERIAL PRIMARY KEY,
    bill_id INTEGER,
    total REAL,
    payment REAL,
    tip_percent REAL,
    CONSTRAINT fk_bill_total_bill FOREIGN KEY (bill_id)
        REFERENCES bill_id (bill_id)
);

-- ==========================================
-- 3. AGGREGATED TABLES (Weekly/Daily Stats)
-- ==========================================

-- Weekly Sales Totals
CREATE TABLE IF NOT EXISTS total_sales (
    id SERIAL PRIMARY KEY,
    week_id INTEGER NOT NULL,
    total_before_escomptes REAL,
    total_after_escomptes REAL,
    t_p_s REAL, -- Tax 1
    t_v_q REAL, -- Tax 2
    total REAL,
    CONSTRAINT fk_sales_week FOREIGN KEY (week_id)
        REFERENCES week (week_id)
);

-- Weekly Item Sales
CREATE TABLE IF NOT EXISTS sale_item_by_week (
    week_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    quantity REAL NOT NULL,
    PRIMARY KEY (week_id, item_id, quantity),
    CONSTRAINT fk_sale_item_week FOREIGN KEY (week_id)
        REFERENCES week (week_id),
    CONSTRAINT fk_sale_item_item FOREIGN KEY (item_id)
        REFERENCES item (item_id)
);

-- Weekly Discount Usage
CREATE TABLE IF NOT EXISTS escompte_sales (
    id SERIAL PRIMARY KEY,
    week_id INTEGER NOT NULL,
    escompte_id INTEGER,
    number_used INTEGER,
    amount REAL,
    CONSTRAINT fk_escompte_sales_escompte FOREIGN KEY (escompte_id)
        REFERENCES escompte (escompte_id),
    CONSTRAINT fk_escompte_sales_week FOREIGN KEY (week_id)
        REFERENCES week (week_id)
);

-- Weekly Payment Method Usage
CREATE TABLE IF NOT EXISTS methode_paiement_sales (
    id SERIAL PRIMARY KEY,
    week_id INTEGER NOT NULL,
    methode_paiement_id INTEGER,
    number_used INTEGER,
    percentage REAL,
    CONSTRAINT fk_payment_method FOREIGN KEY (methode_paiement_id)
        REFERENCES methode_paiement (methode_paiement_id),
    CONSTRAINT fk_payment_week FOREIGN KEY (week_id)
        REFERENCES week (week_id)
);


