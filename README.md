# MedVault Pharmacy Inventory

A Python web app for pharmacy inventory, dispensing, purchasing, and patient/department requests. It uses **Flask** (the website), **SQLite** (a small database file on your computer), and role-based login so staff and patients see different screens.

---

## Admin login

Open the app, then sign in with:

| Field | Value |
|---|---|
| **Username** | `admin` |
| **Password** | `admin123` |

The admin account can manage users, reset passwords, view all inventory, suppliers, sales, reports, and the audit log.

Other demo accounts (optional):

| Role | Username | Password |
|---|---|---|
| Chief Pharmacist | `pharmacist` | `pharma123` |
| Dispensing Staff | `dispenser` | `dispense123` |
| Inventory Controller | `inventory` | `inventory123` |
| Patient | `patient` | `patient123` |
| Department Requisitioner | `department` | `dept123` |

These users are created automatically the first time you run the app (see `app/seed.py`).

---

## What you need first

1. **Python 3.10 or newer**  
   Check in a terminal:

   ```bash
   python --version
   ```

   On some Windows setups the command is `py --version`.

2. This project folder on your computer.

---

## Install the requirements

`requirements.txt` is a shopping list of Python libraries the app needs (Flask, the database helper, Excel/PDF export, and so on).

Open a terminal in this project folder (`Pharmacy-inventory-management-tenten`).

### 1. Create a virtual environment (recommended)

A virtual environment is a private Python folder so these libraries do not mix with other projects.

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If activation is blocked, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

When it is on, your prompt usually starts with `(.venv)`.

### 2. Download and install the packages

```bash
python -m pip install -r requirements.txt
```

That command reads `requirements.txt` and downloads every listed package.

To install without a virtual environment (not recommended, but works):

```bash
python -m pip install -r requirements.txt
```

---

## How to run the app

Still in the project folder, with the virtual environment activated:

```bash
python run.py
```

You should see something like:

```text
Running on http://127.0.0.1:5000
```

1. Open a browser.
2. Go to [http://127.0.0.1:5000](http://127.0.0.1:5000).
3. Log in with **admin / admin123**.

Stop the server with `Ctrl + C` in the terminal.

The first run creates a database file under `instance/pharmacy.db` and fills it with sample drugs, stock lots, and users.

---

## How the code works (beginner walkthrough)

Think of the app as three layers:

1. **Pages you see** — HTML files in `app/templates/`
2. **Python that handles clicks** — route files in `app/routes/`
3. **Data that is saved** — tables defined in `app/models.py`, stored in SQLite

### Starting the website: `run.py`

This file is the on-switch. It builds the Flask app and starts a local server on port `5000`.

### Building the app: `app/__init__.py`

`create_app()` is a factory: it creates the Flask app, points it at the SQLite database, turns on login, and **registers blueprints**.

A **blueprint** is a group of related pages (products, sales, reports). Registering them is like plugging those pages into the website.

On first start it also calls `seed_if_empty()` so you have demo data to click through.

### The database: `app/models.py`

Each **class** here is a table. Examples:

- `User` — usernames, hashed passwords, roles
- `Product` — drug master data (NDC, brand, generic, prices)
- `Batch` — a physical lot with expiry date and quantity
- `Sale` / `SaleLine` — a receipt and the items on it
- `Requisition` — a patient refill or ward stock request
- `AuditLog` — who did what, and before/after values

Passwords are **hashed** (turned into a one-way code). The database never stores `admin123` as plain text.

### Login: `app/auth.py`

The `/login` page checks the username and password. If they match, Flask-Login remembers you in a cookie (session). `/logout` signs you out and writes an audit row.

### “Who is allowed?”: `app/decorators.py`

Decorators wrap a page function:

- `@staff_required` — only pharmacy staff
- `@customer_required` — only patients / departments
- `@roles_required("admin")` — only that role

If you are the wrong role, you get a 403 “Access denied” page. That is why a patient cannot see supplier prices or exact stock counts.

### Helper functions: `app/utils.py`

Small tools used in many places:

- write an audit log line
- pick the **FEFO** batch (First-Expired, First-Out — the lot that expires soonest)
- create or clear **low stock / out of stock alerts**

### Sample data: `app/seed.py`

If the database has no users yet, this file creates the admin account, other demo users, products, lots, a couple of sales, and alerts. Running the app again does **not** wipe data; it only seeds when empty.

### Pages (routes)

| File | What it does |
|---|---|
| `app/routes/dashboard.py` | Home screen: staff metrics vs patient portal |
| `app/routes/users.py` | Admin creates accounts, assigns roles, resets passwords |
| `app/routes/products.py` | Drug master for staff; public catalog for patients |
| `app/routes/inventory.py` | Receive stock, lots, locations, adjustments |
| `app/routes/dispensing.py` | POS / dispensing, FEFO scan, receipts, return-to-stock |
| `app/routes/requisitions.py` | Refill and ward requests, approve/reject, status tracking |
| `app/routes/suppliers.py` | Suppliers, purchase orders, returns for credit |
| `app/routes/reports.py` | Valuation, ABC, sales, controlled-drug register, PDF/CSV/Excel |
| `app/routes/audit.py` | Security log (staff) or personal login history (patient) |

A **route** is a URL. Example: visiting `/products` runs a Python function that loads products from the database and renders an HTML template.

### What you see: `app/templates/`

These are HTML files with **Jinja** tags like `{{ current_user.full_name }}`. Flask fills those in before sending the page to the browser.

- `base.html` — sidebar and layout shared by logged-in pages
- `login.html` — sign-in form
- Folders like `products/` and `dispensing/` — screens for each feature

Styles live in `app/static/css/app.css`.

### A typical click, step by step

1. You open `/dispense` and add a drug.
2. Python looks up the product and chooses the earliest-expiring lot (`fefo_batch`).
3. You complete the sale. Quantities on that lot go down.
4. An `AuditLog` row is saved, and if stock is low an `Alert` is created.
5. The dashboard shows the new totals and the alert.

You do not need to write SQL by hand. **SQLAlchemy** turns Python classes into database rows.

---

## Project map

```text
Pharmacy-inventory-management-tenten/
  run.py                 # start the server
  requirements.txt       # libraries to install
  app/
    __init__.py          # create the Flask app
    models.py            # database tables
    auth.py              # login / logout
    decorators.py        # permission checks
    utils.py             # alerts, FEFO, audit helpers
    seed.py              # demo users and sample stock
    routes/              # one file per feature
    templates/           # HTML pages
    static/css/          # styling
  instance/              # created at runtime (database file)
```

---

## Common problems

**`python` is not recognized**  
Try `py -3 run.py` on Windows, or install Python from [python.org](https://www.python.org/downloads/) and tick “Add Python to PATH”.

**Port 5000 is already in use**  
Another program is using that port. Close it, or change `port=5000` in `run.py`.

**Want a fresh demo database?**  
Stop the server, delete `instance/pharmacy.db`, then run `python run.py` again. Seed data (including admin) will be recreated.

---

## Note about this demo

The app is meant for local learning. The Flask secret key and demo passwords are not for a real pharmacy on the public internet.
