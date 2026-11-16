# DemoShop — Python Mini E-Commerce Project

A Flask + SQLite student project implementing a customer storefront, cart, guest checkout, demo KHQR QR display, admin product management, and order history.

## 1. Run locally

Requirements: Python 3.10 or newer.

```bash
# Windows PowerShell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000**.

The database and sample products are initialized automatically on the first run.

## 2. Demo admin login

- Admin URL: `http://127.0.0.1:5000/admin/login`
- Username: `admin`
- Password: `admin123`

Change the default password before deploying publicly. The demo app uses a development secret key; set a strong `SECRET_KEY` environment variable for deployment.

## 3. Demo walkthrough

1. Open the home page and browse the sample products.
2. Open a product, choose a quantity, and add it to the cart.
3. Open the cart, change a quantity or remove an item, then update the cart.
4. Proceed to checkout and enter name, email, phone, and shipping address.
5. Place the order. The app saves the order and its line items in SQLite, reduces stock, and displays the confirmation page with a demonstration QR.
6. Open `/admin/login` and sign in.
7. Add a product, edit a product, or delete a product from the dashboard.
8. Open Orders and inspect the order details and shipping address.

## 4. KHQR / Bakong integration note

The QR on the confirmation page is intentionally marked **DEMO ONLY**. It encodes a demo text payload; it is not a valid KHQR payment request, does not transfer funds, and does not verify payment. For a real payment flow, register for the Bakong developer service, obtain the appropriate credentials, generate a compliant KHQR payload using the official SDK/API, and verify the transaction status server-side before marking an order as paid. Never trust a browser redirect or QR scan as proof of payment.

## 5. Project structure

```text
demoshop/
├── app.py
├── requirements.txt
├── README.md
├── shop.db                 # generated on first run
├── static/
│   ├── css/style.css
│   └── uploads/            # admin product image uploads
└── templates/
    ├── base.html
    ├── home.html
    ├── detail.html
    ├── cart.html
    ├── checkout.html
    ├── confirmation.html
    ├── 404.html
    └── admin/
```

## 6. Before public deployment

- Change `SECRET_KEY` and the default admin password.
- Use HTTPS and a production WSGI server (for example, Gunicorn on Linux).
- Add CSRF protection, login rate limiting, secure cookie settings, and input validation.
- Use persistent storage/backups for SQLite or migrate to PostgreSQL.
- Implement official Bakong KHQR generation and server-side payment verification.
- Configure image upload limits and storage appropriate for the hosting provider.

## 7. Suggested short video demo script (2–3 minutes)

- 0:00–0:20 — Introduce DemoShop and show the product home page.
- 0:20–0:50 — Open product details, share buttons, and add to cart.
- 0:50–1:15 — Update cart quantity and show the total.
- 1:15–1:45 — Enter guest checkout details and place a demo order.
- 1:45–2:10 — Show order confirmation and the clearly labeled demo QR.
- 2:10–2:45 — Log in as admin, manage a product, and open the order history/detail page.
