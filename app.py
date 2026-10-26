"""Cartboard backend. Run:  pip install -r requirements.txt && python app.py  ->  http://localhost:5000"""
import sqlite3, os
from datetime import datetime
from flask import Flask, g, jsonify, request, send_from_directory

DB = os.path.join(os.path.dirname(__file__), "cartboard.db")
app = Flask(__name__, static_folder="static", static_url_path="")
if not os.path.exists(DB):
    import seed; seed.build(DB)

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB); g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

@app.teardown_appcontext
def close(_):
    d = g.pop("db", None)
    if d: d.close()

rows = lambda sql, a=(): [dict(r) for r in db().execute(sql, a).fetchall()]
now = lambda: datetime.now().strftime("%Y-%m-%d %H:%M")

BASE = """SELECT c.id, c.status, c.created_at, c.updated_at, c.coupon, u.customer_id, u.name, u.city, u.state,
  SUM(i.qty) AS items, ROUND(SUM(i.qty*i.unit_price),2) AS total
  FROM carts c JOIN customers u USING(customer_id) JOIN cart_items i ON i.cart_id=c.id"""

def attach_previews(carts):
    for c in carts:
        c["preview"] = rows("""SELECT p.emoji, p.category, p.name FROM cart_items i JOIN products p ON p.id=i.product_id
                               WHERE i.cart_id=? ORDER BY i.qty*i.unit_price DESC""", (c["id"],))
    return carts

@app.get("/")
def index(): return send_from_directory("static", "index.html")

@app.get("/api/meta")
def meta():
    return jsonify(states=[r["state"] for r in rows("SELECT DISTINCT state FROM customers ORDER BY 1")],
                   categories=[r["category"] for r in rows("SELECT DISTINCT category FROM products ORDER BY 1")],
                   products=rows("SELECT * FROM products ORDER BY category, name"))

@app.get("/api/stats")
def stats():
    s = rows("""SELECT COUNT(*) carts, COALESCE(SUM(status='purchased'),0) purchased, COALESCE(SUM(status='abandoned'),0) abandoned,
                COALESCE(SUM(status='active'),0) active FROM carts""")[0]
    s["revenue"] = db().execute("""SELECT COALESCE(ROUND(SUM(qty*unit_price)),0) FROM cart_items JOIN carts ON id=cart_id
                                   WHERE status='purchased'""").fetchone()[0]
    s["customers"] = db().execute("SELECT COUNT(DISTINCT customer_id) FROM carts").fetchone()[0]
    return jsonify(s)

@app.get("/api/carts")
def list_carts():
    a, w = request.args, []; p = []
    if a.get("status"): w.append("c.status=?"); p.append(a["status"])
    if a.get("state"): w.append("u.state=?"); p.append(a["state"])
    if a.get("customer_id"): w.append("c.customer_id=?"); p.append(a["customer_id"])
    if a.get("category"):
        w.append("c.id IN (SELECT cart_id FROM cart_items JOIN products ON id=product_id WHERE category=?)"); p.append(a["category"])
    if a.get("q"):
        w.append("(u.name LIKE ? OR u.city LIKE ? OR CAST(u.customer_id AS TEXT)=? OR CAST(c.id AS TEXT)=?)")
        p += [f"%{a['q']}%", f"%{a['q']}%", a["q"], a["q"]]
    order = {"new": "c.created_at DESC", "old": "c.created_at ASC", "high": "total DESC", "low": "total ASC"}.get(a.get("sort"), "c.created_at DESC")
    limit, offset = min(int(a.get("limit", 24)), 60), int(a.get("offset", 0))
    sql = BASE + (" WHERE " + " AND ".join(w) if w else "") + f" GROUP BY c.id ORDER BY {order} LIMIT ? OFFSET ?"
    carts = attach_previews(rows(sql, p + [limit + 1, offset]))
    return jsonify(carts=carts[:limit], more=len(carts) > limit)

@app.get("/api/carts/<int:cid>")
def get_cart(cid):
    c = rows(BASE + " WHERE c.id=? GROUP BY c.id", (cid,))
    if not c: return jsonify(error="Cart not found"), 404
    c = c[0]
    c["customer"] = rows("SELECT * FROM customers WHERE customer_id=?", (c["customer_id"],))[0]
    c["lines"] = rows("""SELECT p.id product_id, p.name, p.emoji, p.category, i.qty, i.unit_price FROM cart_items i
                         JOIN products p ON p.id=i.product_id WHERE i.cart_id=?""", (cid,))
    c["events"] = rows("SELECT event, at FROM cart_events WHERE cart_id=? ORDER BY at, id", (cid,))
    return jsonify(c)

@app.post("/api/carts")
def create_cart():
    d = request.get_json(force=True)
    items = [i for i in d.get("items", []) if int(i.get("qty", 0)) > 0]
    if not items: return jsonify(error="Add at least one product to the cart"), 400
    if not rows("SELECT 1 FROM customers WHERE customer_id=?", (d.get("customer_id"),)):
        return jsonify(error="Choose a customer for this cart"), 400
    cur = db().execute("INSERT INTO carts(customer_id,status,created_at,updated_at,coupon) VALUES(?,?,?,?,?)",
                       (d["customer_id"], "active", now(), now(), d.get("coupon") or None))
    cid = cur.lastrowid
    for i in items:
        db().execute("INSERT OR REPLACE INTO cart_items SELECT ?,id,?,price FROM products WHERE id=?", (cid, int(i["qty"]), i["product_id"]))
    db().executemany("INSERT INTO cart_events(cart_id,event,at) VALUES(?,?,?)", [(cid, "Cart created", now()), (cid, "Item added", now())])
    db().commit()
    return get_cart(cid), 201

@app.patch("/api/carts/<int:cid>")
def set_status(cid):
    st = (request.get_json(force=True) or {}).get("status")
    if st not in ("active", "purchased", "abandoned"): return jsonify(error="Status must be active, purchased or abandoned"), 400
    if not db().execute("UPDATE carts SET status=?, updated_at=? WHERE id=?", (st, now(), cid)).rowcount:
        return jsonify(error="Cart not found"), 404
    db().execute("INSERT INTO cart_events(cart_id,event,at) VALUES(?,?,?)",
                 (cid, {"active": "Reopened", "purchased": "Purchased", "abandoned": "Abandoned"}[st], now()))
    db().commit(); return get_cart(cid)

@app.delete("/api/carts/<int:cid>")
def delete_cart(cid):
    db().execute("DELETE FROM carts WHERE id=?", (cid,)); db().commit(); return "", 204

@app.get("/api/customers")
def customers():
    q = request.args.get("q", "").strip()
    return jsonify(rows("""SELECT customer_id, name, city, state FROM customers
                           WHERE name LIKE ? OR CAST(customer_id AS TEXT)=? ORDER BY name LIMIT 8""", (f"%{q}%", q)))

@app.get("/api/customers/<int:uid>")
def customer(uid):
    u = rows("SELECT * FROM customers WHERE customer_id=?", (uid,))
    if not u: return jsonify(error="Customer not found"), 404
    u = u[0]
    u.update(rows("""SELECT COUNT(DISTINCT c.id) carts, COALESCE(ROUND(SUM(CASE WHEN c.status='purchased' THEN i.qty*i.unit_price END),2),0) spent
                     FROM carts c JOIN cart_items i ON i.cart_id=c.id WHERE c.customer_id=?""", (uid,))[0])
    return jsonify(u)

if __name__ == "__main__":
    app.run(debug=True)
