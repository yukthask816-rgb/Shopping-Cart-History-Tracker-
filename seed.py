"""Builds cartboard.db: real customers from the TSV + generated products, carts, items and events."""
import sqlite3, random, os
from datetime import datetime, timedelta
import pandas as pd

random.seed(26)
NOW = datetime(2026, 10, 26, 12, 0)
P = [("Linen Wrap Dress","Fashion",89,"👗"),("Denim Jacket","Fashion",120,"🧥"),("Canvas Sneakers","Fashion",75,"👟"),("Straw Sun Hat","Fashion",35,"👒"),
("Gold Hoop Earrings","Fashion",48,"💍"),("Tote Bag","Fashion",42,"👜"),("Rose Face Serum","Beauty",54,"🌹"),("Matte Lipstick","Beauty",28,"💄"),
("Bamboo Brush Set","Beauty",32,"🪮"),("Lavender Candle","Home",26,"🕯️"),("Ceramic Vase","Home",64,"🏺"),("Monstera Plant","Home",38,"🪴"),
("Woven Throw Blanket","Home",79,"🧶"),("Pour-over Kettle","Home",85,"☕"),("Table Lamp","Home",96,"💡"),("Wireless Earbuds","Tech",149,"🎧"),
("Mechanical Keyboard","Tech",179,"⌨️"),("Smart Watch","Tech",299,"⌚"),("Phone Stand","Tech",24,"📱"),("Instant Camera","Tech",139,"📷"),
("Mini Projector","Tech",210,"📽️"),("Paperback Novel","Books",18,"📚"),("Watercolour Set","Books",45,"🎨"),("Bullet Journal","Books",22,"📓"),
("Cookbook","Books",39,"📖"),("Yoga Mat","Fitness",58,"🧘"),("Water Bottle","Fitness",30,"🍶"),("Running Belt","Fitness",27,"🏃"),
("Dumbbell Pair","Fitness",65,"🏋️"),("Manuka Honey","Food",34,"🍯"),("Single-origin Coffee","Food",24,"🫘"),("Matcha Tin","Food",31,"🍵"),
("Dark Chocolate Box","Food",19,"🍫"),("Gourmet Hot Sauce","Food",15,"🌶️"),("Plush Koala","Toys",29,"🐨"),("Wooden Puzzle","Toys",36,"🧩"),
("Kite","Toys",22,"🪁"),("Board Game","Toys",55,"🎲")]

def build(path="cartboard.db"):
    if os.path.exists(path): os.remove(path)
    db = sqlite3.connect(path)
    db.executescript("""
    CREATE TABLE customers(customer_id INTEGER PRIMARY KEY, name TEXT, gender TEXT, age INT, address TEXT, zip INT, city TEXT, state TEXT, country TEXT);
    CREATE TABLE products(id INTEGER PRIMARY KEY, name TEXT, category TEXT, price REAL, emoji TEXT);
    CREATE TABLE carts(id INTEGER PRIMARY KEY, customer_id INT REFERENCES customers, status TEXT CHECK(status IN('active','purchased','abandoned')), created_at TEXT, updated_at TEXT, coupon TEXT);
    CREATE TABLE cart_items(cart_id INT REFERENCES carts ON DELETE CASCADE, product_id INT REFERENCES products, qty INT, unit_price REAL, PRIMARY KEY(cart_id, product_id));
    CREATE TABLE cart_events(id INTEGER PRIMARY KEY, cart_id INT REFERENCES carts ON DELETE CASCADE, event TEXT, at TEXT);
    CREATE INDEX ix_carts_c ON carts(customer_id); CREATE INDEX ix_carts_s ON carts(status, created_at);""")
    df = pd.read_csv("data/clean_customer_data.tsv", sep="\t")
    db.executemany("INSERT INTO customers VALUES(?,?,?,?,?,?,?,?,?)", df.itertuples(index=False, name=None))
    db.executemany("INSERT INTO products(name,category,price,emoji) VALUES(?,?,?,?)", P)
    f = lambda d: d.strftime("%Y-%m-%d %H:%M")
    for cid in df["Customer ID"]:
        for _ in range(random.choices([0,1,2,3,4,5],[12,20,26,22,12,8])[0]):
            t = NOW - timedelta(days=random.random()*365)
            recent = (NOW - t).days < 3
            st = "active" if recent and random.random() < .5 else ("purchased" if random.random() < .64 else "abandoned")
            end = t + timedelta(hours=random.uniform(.2, 30))
            if st == "active": end = t
            cur = db.execute("INSERT INTO carts(customer_id,status,created_at,updated_at,coupon) VALUES(?,?,?,?,?)",
                (int(cid), st, f(t), f(end), random.choice([None]*4+["WELCOME10","SPRING15","FREESHIP"])))
            c = cur.lastrowid
            for pid in random.sample(range(1, len(P)+1), random.choices([1,2,3,4,5,6],[20,28,22,14,10,6])[0]):
                db.execute("INSERT INTO cart_items VALUES(?,?,?,?)", (c, pid, random.choices([1,2,3],[75,18,7])[0], P[pid-1][2]))
            ev = [("Cart created", t), ("Item added", t + timedelta(minutes=random.randint(1,25)))]
            if st == "purchased" or (st == "abandoned" and random.random() < .5): ev.append(("Checkout started", t + (end - t) * .8))
            if st != "active": ev.append(("Purchased" if st == "purchased" else "Abandoned", end))
            db.executemany("INSERT INTO cart_events(cart_id,event,at) VALUES(?,?,?)", [(c, e, f(a)) for e, a in ev])
    db.commit(); return db

if __name__ == "__main__":
    d = build()
    print(d.execute("SELECT (SELECT COUNT(*) FROM customers),(SELECT COUNT(*) FROM carts),(SELECT COUNT(*) FROM cart_items)").fetchone())
