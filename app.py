import os, sqlite3, io, base64
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-secret-key-before-deploying')
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024
DB_PATH = os.path.join(BASE_DIR, 'shop.db')
ALLOWED = {'png', 'jpg', 'jpeg', 'webp', 'gif'}


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    with db() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT NOT NULL, price REAL NOT NULL, stock INTEGER NOT NULL DEFAULT 0, image TEXT, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL, email TEXT NOT NULL, phone TEXT NOT NULL, address TEXT NOT NULL, total REAL NOT NULL, created_at TEXT NOT NULL, payment_status TEXT NOT NULL DEFAULT 'PENDING');
        CREATE TABLE IF NOT EXISTS order_items (id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE, product_id INTEGER, product_name TEXT NOT NULL, quantity INTEGER NOT NULL, unit_price REAL NOT NULL, subtotal REAL NOT NULL);
        ''')
        if not con.execute('SELECT id FROM admins LIMIT 1').fetchone():
            con.execute('INSERT INTO admins(username,password_hash) VALUES (?,?)', ('admin', generate_password_hash('admin123')))
        if not con.execute('SELECT id FROM products LIMIT 1').fetchone():
            samples = [
                ('Wireless Headphones', 'Comfortable wireless headphones with clear sound and long battery life.', 29.90, 18, 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=800&q=80', 1),
                ('Everyday Backpack', 'A lightweight everyday backpack with a roomy main compartment.', 24.50, 12, 'https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=800&q=80', 1),
                ('Smart Watch', 'A modern smartwatch for notifications, activity tracking and daily use.', 45.00, 9, 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=800&q=80', 1),
                ('Ceramic Coffee Mug', 'Minimal ceramic mug for your coffee and tea moments.', 8.75, 30, 'https://images.unsplash.com/photo-1514228742587-6b1558f1123d?auto=format&fit=crop&w=800&q=80', 1),
            ]
            # Replace the first sample image with a valid remote image URL.
            samples[0] = ('Wireless Headphones', samples[0][1], 29.90, 18, 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=800&q=80', 1)
            con.executemany('INSERT INTO products(name,description,price,stock,image,active) VALUES (?,?,?,?,?,?)', samples)


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('admin_id'):
            return redirect(url_for('admin_login'))
        return fn(*args, **kwargs)
    return wrapper


def cart_data():
    cart = session.get('cart', {})
    if not cart: return [], 0
    ids = [int(x) for x in cart.keys()]
    marks = ','.join('?' for _ in ids)
    with db() as con:
        products = con.execute(f'SELECT * FROM products WHERE id IN ({marks}) AND active=1', ids).fetchall()
    rows, total = [], 0
    for p in products:
        qty = max(1, int(cart.get(str(p['id']), 1)))
        subtotal = p['price'] * qty
        rows.append({'product': p, 'quantity': qty, 'subtotal': subtotal})
        total += subtotal
    return rows, total


@app.context_processor
def inject_cart_count():
    return {'cart_count': sum(int(v) for v in session.get('cart', {}).values())}


@app.route('/')
def home():
    with db() as con:
        products = con.execute('SELECT * FROM products WHERE active=1 ORDER BY id DESC').fetchall()
    return render_template('home.html', products=products)


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    with db() as con:
        product = con.execute('SELECT * FROM products WHERE id=? AND active=1', (product_id,)).fetchone()
    if not product: abort(404)
    return render_template('detail.html', product=product)


@app.post('/cart/add/<int:product_id>')
def add_to_cart(product_id):
    with db() as con:
        p = con.execute('SELECT * FROM products WHERE id=? AND active=1', (product_id,)).fetchone()
    if not p: abort(404)
    qty = max(1, int(request.form.get('quantity', 1)))
    if p['stock'] < 1:
        flash('This product is out of stock.', 'error')
    else:
        cart = session.get('cart', {})
        cart[str(product_id)] = min(p['stock'], int(cart.get(str(product_id), 0)) + qty)
        session['cart'] = cart
        flash('Product added to your cart.', 'success')
    return redirect(request.referrer or url_for('home'))


@app.route('/cart')
def cart():
    items, total = cart_data()
    return render_template('cart.html', items=items, total=total)


@app.post('/cart/update')
def update_cart():
    cart = session.get('cart', {})
    with db() as con:
        for key, value in request.form.items():
            if key.startswith('qty_'):
                pid = key[4:]
                p = con.execute('SELECT stock FROM products WHERE id=?', (pid,)).fetchone()
                qty = int(value or 1)
                if not p or qty <= 0: cart.pop(pid, None)
                else: cart[pid] = min(qty, p['stock'])
    session['cart'] = cart
    return redirect(url_for('cart'))


@app.post('/cart/remove/<int:product_id>')
def remove_cart_item(product_id):
    cart = session.get('cart', {})
    cart.pop(str(product_id), None)
    session['cart'] = cart
    return redirect(url_for('cart'))


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    items, total = cart_data()
    if not items:
        flash('Your cart is empty.', 'error')
        return redirect(url_for('home'))
    if request.method == 'POST':
        data = [request.form.get(k, '').strip() for k in ('full_name', 'email', 'phone', 'address')]
        if not all(data):
            flash('Please complete all customer information fields.', 'error')
            return render_template('checkout.html', items=items, total=total)
        with db() as con:
            # Re-check stock and create the order atomically.
            for item in items:
                current = con.execute('SELECT stock FROM products WHERE id=?', (item['product']['id'],)).fetchone()
                if not current or current['stock'] < item['quantity']:
                    flash(f"Not enough stock for {item['product']['name']}. Please update your cart.", 'error')
                    return redirect(url_for('cart'))
            cur = con.execute('INSERT INTO orders(full_name,email,phone,address,total,created_at,payment_status) VALUES (?,?,?,?,?,?,?)',
                              (*data, total, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'PENDING'))
            order_id = cur.lastrowid
            for item in items:
                p = item['product']
                con.execute('INSERT INTO order_items(order_id,product_id,product_name,quantity,unit_price,subtotal) VALUES (?,?,?,?,?,?)',
                            (order_id, p['id'], p['name'], item['quantity'], p['price'], item['subtotal']))
                con.execute('UPDATE products SET stock=stock-? WHERE id=?', (item['quantity'], p['id']))
        session['cart'] = {}
        return redirect(url_for('confirmation', order_id=order_id))
    return render_template('checkout.html', items=items, total=total)


@app.route('/order/<int:order_id>/confirmation')
def confirmation(order_id):
    with db() as con:
        order = con.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
        lines = con.execute('SELECT * FROM order_items WHERE order_id=?', (order_id,)).fetchall()
    if not order: abort(404)
    # Demo QR only: this is NOT a real Bakong/KHQR payment request.
    try:
        import qrcode
        payload = f'DEMO-KHQR|ORDER:{order_id}|AMOUNT:{order["total"]:.2f}|CURRENCY:USD|STATUS:NOT-A-REAL-PAYMENT'
        qr = qrcode.make(payload)
        buff = io.BytesIO(); qr.save(buff, format='PNG')
        qr_image = base64.b64encode(buff.getvalue()).decode('ascii')
    except Exception:
        qr_image = None
    return render_template('confirmation.html', order=order, lines=lines, qr_image=qr_image)


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username, password = request.form.get('username',''), request.form.get('password','')
        with db() as con:
            admin = con.execute('SELECT * FROM admins WHERE username=?', (username,)).fetchone()
        if admin and check_password_hash(admin['password_hash'], password):
            session['admin_id'] = admin['id']; session['admin_username'] = admin['username']
            return redirect(url_for('admin_dashboard'))
        flash('Incorrect username or password.', 'error')
    return render_template('admin/login.html')


@app.get('/admin/logout')
def admin_logout():
    session.pop('admin_id', None); session.pop('admin_username', None)
    return redirect(url_for('admin_login'))


@app.route('/admin')
@admin_required
def admin_dashboard():
    with db() as con:
        products = con.execute('SELECT * FROM products ORDER BY id DESC').fetchall()
        orders = con.execute('SELECT * FROM orders ORDER BY id DESC LIMIT 8').fetchall()
        stats = {'products': con.execute('SELECT COUNT(*) FROM products').fetchone()[0],
                 'orders': con.execute('SELECT COUNT(*) FROM orders').fetchone()[0],
                 'revenue': con.execute('SELECT COALESCE(SUM(total),0) FROM orders').fetchone()[0]}
    return render_template('admin/dashboard.html', products=products, orders=orders, stats=stats)


def save_product_image(file):
    if not file or not file.filename: return None
    filename = secure_filename(file.filename)
    if '.' not in filename or filename.rsplit('.', 1)[1].lower() not in ALLOWED: return None
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    safe_name = f'{datetime.now().strftime("%Y%m%d%H%M%S%f")}_{filename}'
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], safe_name))
    return 'uploads/' + safe_name


@app.route('/admin/products/new', methods=['GET', 'POST'])
@app.route('/admin/products/<int:product_id>/edit', methods=['GET', 'POST'])
@admin_required
def product_form(product_id=None):
    with db() as con:
        product = con.execute('SELECT * FROM products WHERE id=?', (product_id,)).fetchone() if product_id else None
        if product_id and not product: abort(404)
        if request.method == 'POST':
            name = request.form.get('name','').strip(); description = request.form.get('description','').strip()
            try: price = float(request.form.get('price','0')); stock = int(request.form.get('stock','0'))
            except ValueError: flash('Price and stock must be valid numbers.', 'error'); return render_template('admin/product_form.html', product=product)
            if not name or not description or price < 0 or stock < 0:
                flash('Please enter valid product details.', 'error'); return render_template('admin/product_form.html', product=product)
            image = save_product_image(request.files.get('image')) or (product['image'] if product else '')
            active = 1 if request.form.get('active') == 'on' else 0
            if product:
                con.execute('UPDATE products SET name=?,description=?,price=?,stock=?,image=?,active=? WHERE id=?', (name,description,price,stock,image,active,product_id))
            else:
                con.execute('INSERT INTO products(name,description,price,stock,image,active) VALUES (?,?,?,?,?,?)', (name,description,price,stock,image,active))
            return redirect(url_for('admin_dashboard'))
    return render_template('admin/product_form.html', product=product)


@app.post('/admin/products/<int:product_id>/delete')
@admin_required
def delete_product(product_id):
    with db() as con: con.execute('DELETE FROM products WHERE id=?', (product_id,))
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/orders')
@admin_required
def admin_orders():
    with db() as con: orders = con.execute('SELECT * FROM orders ORDER BY id DESC').fetchall()
    return render_template('admin/orders.html', orders=orders)


@app.route('/admin/orders/<int:order_id>')
@admin_required
def admin_order_detail(order_id):
    with db() as con:
        order = con.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
        lines = con.execute('SELECT * FROM order_items WHERE order_id=?', (order_id,)).fetchall()
    if not order: abort(404)
    return render_template('admin/order_detail.html', order=order, lines=lines)


@app.errorhandler(404)
def not_found(_): return render_template('404.html'), 404


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
