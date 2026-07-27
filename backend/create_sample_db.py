"""
Creates backend/data/company.db — a small sample SQLite database for the
data/SQL agent (F5) to query.
"""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "company.db")


def main():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            plan TEXT NOT NULL,
            signup_quarter TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE churn_events (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            quarter TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """)

    customers = [
        (1, "Acme Retail", "Starter", "Q1"),
        (2, "Blue Harbor", "Starter", "Q1"),
        (3, "Cedar Works", "Pro", "Q1"),
        (4, "Delta Foods", "Enterprise", "Q2"),
        (5, "Echo Studio", "Starter", "Q2"),
        (6, "Falcon Labs", "Pro", "Q2"),
        (7, "Granite Co", "Enterprise", "Q3"),
        (8, "Harbor Tools", "Enterprise", "Q3"),
        (9, "Ivory Health", "Enterprise", "Q3"),
        (10, "Juno Media", "Pro", "Q3"),
    ]
    cur.executemany("INSERT INTO customers VALUES (?, ?, ?, ?)", customers)

    churn_events = [
        (1, 1, "Q1"), (2, 2, "Q1"),
        (3, 5, "Q2"),
        (4, 7, "Q3"), (5, 8, "Q3"), (6, 9, "Q3"),
    ]
    cur.executemany("INSERT INTO churn_events VALUES (?, ?, ?)", churn_events)

    conn.commit()
    conn.close()
    print(f"Created {DB_PATH} with {len(customers)} customers and "
          f"{len(churn_events)} churn events.")


if __name__ == "__main__":
    main()