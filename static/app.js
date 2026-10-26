const $ = s => document.querySelector(s), api = (u, o) => fetch(u, o && { headers: { "Content-Type": "application/json" }, ...o }).then(async r => { const j = r.status === 204 ? null : await r.json(); if (!r.ok) throw new Error(j.error); return j; });
const money = n => "A$" + Number(n).toLocaleString("en-AU", { minimumFractionDigits: n % 1 ? 2 : 0, maximumFractionDigits: 2 });
const when = s => new Date(s.replace(" ", "T")).toLocaleString("en-AU", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
const col = c => `style="--c:var(--${c})"`, esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const S = { status: "", offset: 0, customer: null, meta: null }; let timer;

function toast(t) { const d = document.createElement("div"); d.className = "toast"; d.textContent = t; document.body.append(d); setTimeout(() => d.remove(), 2200); }

async function init() {
  S.meta = await api("/api/meta");
  S.meta.states.forEach(s => $("#state").add(new Option(s, s)));
  S.meta.categories.forEach(c => $("#category").add(new Option(c, c)));
  $("#statusChips").innerHTML = [["", "All"], ["active", "Active"], ["purchased", "Purchased"], ["abandoned", "Abandoned"]]
    .map(([v, l]) => `<button class="chip" data-s="${v}" aria-pressed="${v === S.status}">${l}</button>`).join(" ");
  $("#statusChips").onclick = e => { const b = e.target.closest("[data-s]"); if (!b) return; S.status = b.dataset.s; [...$("#statusChips").children].forEach(x => x.setAttribute("aria-pressed", x === b)); load(true); };
  ["state", "category", "sort"].forEach(id => $("#" + id).onchange = () => load(true));
  $("#q").oninput = () => { clearTimeout(timer); timer = setTimeout(() => load(true), 250); };
  $("#moreBtn").onclick = () => load(false);
  $("#newBtn").onclick = openCreate;
  stats(); load(true);
}

async function stats() {
  const s = await api("/api/stats");
  $("#stats").innerHTML = [["#ffd6ec", -1.5, s.carts.toLocaleString(), "carts tracked"], ["#d9ccff", 1, money(s.revenue), "from purchases"], ["#c9f3e3", -1, s.active, "still active"],
    ["#ffe0cc", 1.5, Math.round(s.abandoned / s.carts * 100) + "%", "abandoned"], ["#cfe3ff", -.5, s.customers, "shoppers"]]
    .map(([c, r, b, t]) => `<div class="sticker" style="--c:${c};--r:${r}deg"><b>${b}</b>${t}</div>`).join("");
}

async function load(reset) {
  if (reset) { S.offset = 0; $("#board").innerHTML = ""; }
  const p = new URLSearchParams({ status: S.status, state: $("#state").value, category: $("#category").value, sort: $("#sort").value, q: $("#q").value.trim(), offset: S.offset, limit: 24 });
  if (S.customer) p.set("customer_id", S.customer);
  const r = await api("/api/carts?" + p);
  $("#board").insertAdjacentHTML("beforeend", r.carts.map(pin).join(""));
  S.offset += r.carts.length; $("#moreBtn").hidden = !r.more; $("#empty").hidden = S.offset > 0;
}

function collage(items, cls = "") {
  const t = items.slice(0, 4); return `<div class="collage n${t.length} ${cls}">${t.map(i => `<div class="tile" ${col(i.category)} title="${esc(i.name)}">${i.emoji}</div>`).join("")}</div>`;
}
const pin = c => `<button class="pin" onclick="openCart(${c.id})">${collage(c.preview)}
  <div class="meta"><div class="row"><h3>${esc(c.name)}</h3><span class="st ${c.status}">${c.status}</span></div>
  <p>${esc(c.city)}, ${esc(c.state)} · ${c.items} item${c.items > 1 ? "s" : ""} · ${new Date(c.created_at.replace(" ", "T")).toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric" })}</p>
  <div class="row"><span class="price">${money(c.total)}</span>${c.coupon ? `<small>🏷️ ${c.coupon}</small>` : ""}</div></div></button>`;

async function openCart(id) {
  const c = await api("/api/carts/" + id), u = c.customer, d = $("#detail");
  d.innerHTML = `<div class="sheet"><div class="band">${c.lines.slice(0, 6).map(l => `<div ${col(l.category)}>${l.emoji}</div>`).join("")}</div>
  <div class="row"><h2>Cart #${c.id}</h2><span class="st ${c.status}">${c.status}</span></div>
  <p style="color:var(--mute);margin:2px 0 8px"><a href="#" id="seeCust" style="color:var(--grape);font-weight:700">${esc(u.name)}</a> · ${esc(u.address)}, ${esc(u.city)} ${String(u.zip).padStart(4, "0")}, ${esc(u.state)}${c.coupon ? ` · coupon ${c.coupon}` : ""}</p>
  ${c.lines.map(l => `<div class="line"><div class="e" ${col(l.category)}>${l.emoji}</div><div class="g"><b>${esc(l.name)}</b><br><small>${l.category} · ${l.qty} × ${money(l.unit_price)}</small></div><b>${money(l.qty * l.unit_price)}</b></div>`).join("")}
  <div class="row" style="margin-top:12px"><span>Cart total</span><span class="price">${money(c.total)}</span></div>
  <h3 style="margin-top:18px">History</h3><ul class="tl">${c.events.map(e => `<li>${e.event}<br><small>${when(e.at)}</small></li>`).join("")}</ul>
  <div class="actions">${["active", "purchased", "abandoned"].filter(s => s !== c.status).map(s => `<button class="btn ghost" data-st="${s}">Mark ${s}</button>`).join("")}
  <button class="btn danger" id="del">Delete cart</button><button class="btn" onclick="this.closest('dialog').close()">Close</button></div></div>`;
  d.querySelectorAll("[data-st]").forEach(b => b.onclick = async () => { await api("/api/carts/" + id, { method: "PATCH", body: JSON.stringify({ status: b.dataset.st }) }); toast("Cart marked " + b.dataset.st); d.close(); refresh(); });
  $("#del").onclick = async () => { if (!confirm(`Delete cart #${id}? This removes its history too.`)) return; await api("/api/carts/" + id, { method: "DELETE" }); toast("Cart deleted"); d.close(); refresh(); };
  $("#seeCust").onclick = e => { e.preventDefault(); d.close(); showCustomer(u.customer_id); };
  d.showModal();
}

async function showCustomer(id) {
  const u = await api("/api/customers/" + id); S.customer = id;
  $("#who").innerHTML = `<div class="who"><div class="av">${esc(u.name[0])}</div><div style="flex:1"><h2>${esc(u.name)}</h2>
    <small style="color:var(--mute)">Customer #${u.customer_id} · ${u.gender}, ${u.age} · ${esc(u.city)}, ${esc(u.state)} · ${u.carts} carts · ${money(u.spent)} spent</small></div>
    <button class="btn ghost" id="clr">Show all carts</button></div>`;
  $("#clr").onclick = () => { S.customer = null; $("#who").innerHTML = ""; load(true); };
  load(true); scrollTo({ top: 0, behavior: "smooth" });
}
const refresh = () => { stats(); load(true); if (S.customer) showCustomer(S.customer); };

function openCreate() {
  const d = $("#create"), sel = {}; let cust = null;
  d.innerHTML = `<div class="sheet"><h2>New cart</h2><input class="field" id="cq" placeholder="Find customer by name or ID" autocomplete="off"><div class="hits" id="hits"></div>
  <p id="picked" style="color:var(--mute);margin:6px 0">No customer chosen yet</p>
  <b>Pick products</b> <small style="color:var(--mute)">tap to add, tap again for more</small>
  <div class="picker">${S.meta.products.map(p => `<button class="prod" data-id="${p.id}" ${col(p.category)}><span class="em">${p.emoji}</span>${esc(p.name)}<br><b>${money(p.price)}</b></button>`).join("")}</div>
  <input class="field" id="coupon" placeholder="Coupon code (optional)">
  <div class="actions"><button class="btn pink" id="save">Create cart</button><button class="btn ghost" onclick="this.closest('dialog').close()">Cancel</button></div></div>`;
  d.querySelector(".picker").onclick = e => { const b = e.target.closest(".prod"); if (!b) return; const id = b.dataset.id; sel[id] = ((sel[id] || 0) + 1) % 5;
    b.classList.toggle("on", !!sel[id]); b.querySelector("i")?.remove(); if (sel[id]) b.insertAdjacentHTML("beforeend", `<i>${sel[id]}</i>`); };
  let t; $("#cq").oninput = e => { clearTimeout(t); t = setTimeout(async () => { const r = await api("/api/customers?q=" + encodeURIComponent(e.target.value));
    $("#hits").innerHTML = r.map(c => `<button class="chip" data-id="${c.customer_id}" data-n="${esc(c.name)}">${esc(c.name)} · #${c.customer_id}</button>`).join(""); }, 200); };
  $("#hits").onclick = e => { const b = e.target.closest(".chip"); if (!b) return; cust = +b.dataset.id; $("#picked").textContent = "Cart for " + b.dataset.n; $("#hits").innerHTML = ""; };
  $("#save").onclick = async () => { try {
    const items = Object.entries(sel).filter(([, q]) => q).map(([product_id, qty]) => ({ product_id: +product_id, qty }));
    const c = await api("/api/carts", { method: "POST", body: JSON.stringify({ customer_id: cust, items, coupon: $("#coupon").value.trim() }) });
    d.close(); toast("Cart created"); refresh(); openCart(c.id); } catch (e) { toast(e.message); } };
  d.showModal();
}
init();
