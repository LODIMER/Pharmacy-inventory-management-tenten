from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

STAFF_ROLES = (
    "admin",
    "chief_pharmacist",
    "dispensing_staff",
    "inventory_controller",
)
CUSTOMER_ROLES = ("patient", "department")
ALL_ROLES = STAFF_ROLES + CUSTOMER_ROLES

ROLE_LABELS = {
    "admin": "Admin",
    "chief_pharmacist": "Chief Pharmacist",
    "dispensing_staff": "Dispensing Staff",
    "inventory_controller": "Inventory Controller",
    "patient": "Patient",
    "department": "Department Requisitioner",
}

DOSAGE_FORMS = ("Tablet", "Syrup", "Injection", "Ointment", "Capsule", "Drops", "Inhaler")
CATEGORIES = (
    "Antibiotic",
    "Analgesic",
    "Controlled Substance",
    "OTC",
    "Cardiovascular",
    "Antidiabetic",
    "Respiratory",
    "Gastrointestinal",
)
STORAGE_CONDITIONS = (
    "Room Temp",
    "Cold Chain 2°C–8°C",
    "Frozen",
    "Controlled Vault",
)
UOMS = ("Box", "Strip", "Bottle", "Ampoule", "Vial", "Tube", "Pack")
LOCATIONS = ("Shelf", "Bin", "Fridge", "Controlled Vault")
BATCH_STATUSES = ("available", "damaged", "quarantine", "returned")
PO_STATUSES = ("draft", "submitted", "partially_received", "completed", "cancelled")
REQ_STATUSES = (
    "pending_review",
    "processing",
    "ready_for_pickup",
    "completed",
    "cancelled",
    "rejected",
)
SALE_DISCOUNTS = ("None", "Senior Citizen", "PWD")


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(40))
    role = db.Column(db.String(40), nullable=False, default="patient")
    department_name = db.Column(db.String(80))
    is_active = db.Column(db.Boolean, default=True)
    prescription_notes = db.Column(db.Text)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_staff(self):
        return self.role in STAFF_ROLES

    def is_admin_like(self):
        return self.role in ("admin", "chief_pharmacist")

    def can_manage_users(self):
        return self.role == "admin"

    def can_inventory(self):
        return self.role in ("admin", "chief_pharmacist", "inventory_controller")

    def can_dispense(self):
        return self.role in ("admin", "chief_pharmacist", "dispensing_staff")

    def can_approve(self):
        return self.role in ("admin", "chief_pharmacist")

    def can_purchase(self):
        return self.role in ("admin", "chief_pharmacist", "inventory_controller")

    def can_reports(self):
        return self.is_staff()

    def role_label(self):
        return ROLE_LABELS.get(self.role, self.role)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ndc = db.Column(db.String(40), unique=True)
    upc = db.Column(db.String(40))
    barcode = db.Column(db.String(60), unique=True)
    brand_name = db.Column(db.String(120), nullable=False)
    generic_name = db.Column(db.String(120), nullable=False)
    dosage_form = db.Column(db.String(40))
    strength = db.Column(db.String(40))
    category = db.Column(db.String(60))
    therapeutic_class = db.Column(db.String(80))
    storage_condition = db.Column(db.String(80))
    uom = db.Column(db.String(30))
    unit_cost = db.Column(db.Float, default=0)
    retail_price = db.Column(db.Float, default=0)
    markup_percent = db.Column(db.Float, default=0)
    reorder_point = db.Column(db.Integer, default=10)
    max_level = db.Column(db.Integer, default=100)
    lasa_flag = db.Column(db.Boolean, default=False)
    safety_alerts = db.Column(db.Text)
    interaction_warnings = db.Column(db.Text)
    is_controlled = db.Column(db.Boolean, default=False)
    schedule = db.Column(db.String(10))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    batches = db.relationship("Batch", backref="product", lazy=True)

    def available_qty(self):
        return sum(b.quantity for b in self.batches if b.status == "available")

    def stock_status(self):
        qty = self.available_qty()
        if qty <= 0:
            return "out"
        if qty <= self.reorder_point:
            return "low"
        if qty > self.max_level:
            return "overstock"
        return "ok"

    def availability_label(self):
        status = self.stock_status()
        return {
            "out": "Out of stock",
            "low": "Limited availability",
            "overstock": "In stock",
            "ok": "In stock",
        }[status]


class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    contact_name = db.Column(db.String(80))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(40))
    address = db.Column(db.String(200))
    lead_time_days = db.Column(db.Integer, default=7)
    payment_terms = db.Column(db.String(80))
    is_active = db.Column(db.Boolean, default=True)


class PurchaseOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    po_number = db.Column(db.String(40), unique=True, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"), nullable=False)
    status = db.Column(db.String(30), default="draft")
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime)

    supplier = db.relationship("Supplier")
    created_by = db.relationship("User")
    lines = db.relationship("POLine", backref="purchase_order", cascade="all, delete-orphan")


class POLine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    po_id = db.Column(db.Integer, db.ForeignKey("purchase_order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    qty_ordered = db.Column(db.Integer, default=0)
    qty_received = db.Column(db.Integer, default=0)
    unit_cost = db.Column(db.Float, default=0)

    product = db.relationship("Product")


class Batch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    lot_number = db.Column(db.String(60), nullable=False)
    mfg_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date, nullable=False)
    location = db.Column(db.String(40), default="Shelf")
    quantity = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="available")
    po_id = db.Column(db.Integer, db.ForeignKey("purchase_order.id"))
    invoice_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    po = db.relationship("PurchaseOrder")

    def days_to_expiry(self):
        return (self.expiry_date - date.today()).days


class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    receipt_no = db.Column(db.String(40), unique=True, nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    prescription_id = db.Column(db.String(60))
    dispenser_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    verifier_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    doctor_license = db.Column(db.String(60))
    discount_type = db.Column(db.String(40), default="None")
    discount_amount = db.Column(db.Float, default=0)
    tax_amount = db.Column(db.Float, default=0)
    subtotal = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    patient = db.relationship("User", foreign_keys=[patient_id])
    dispenser = db.relationship("User", foreign_keys=[dispenser_id])
    verifier = db.relationship("User", foreign_keys=[verifier_id])
    lines = db.relationship("SaleLine", backref="sale", cascade="all, delete-orphan")


class SaleLine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sale.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey("batch.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, default=0)
    line_total = db.Column(db.Float, default=0)

    product = db.relationship("Product")
    batch = db.relationship("Batch")


class Requisition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    req_number = db.Column(db.String(40), unique=True, nullable=False)
    requester_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    req_type = db.Column(db.String(30), default="refill")  # refill | transfer
    status = db.Column(db.String(30), default="pending_review")
    fulfillment = db.Column(db.String(20), default="pickup")  # pickup | delivery
    pickup_time = db.Column(db.String(80))
    notes = db.Column(db.Text)
    prescription_file = db.Column(db.String(200))
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    review_note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    requester = db.relationship("User", foreign_keys=[requester_id])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])
    lines = db.relationship("RequisitionLine", backref="requisition", cascade="all, delete-orphan")


class RequisitionLine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    requisition_id = db.Column(db.Integer, db.ForeignKey("requisition.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    product = db.relationship("Product")


class StockAdjustment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("batch.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reason = db.Column(db.String(80))  # damaged, sample, quarantine, rts, write_off
    qty_before = db.Column(db.Integer)
    qty_after = db.Column(db.Integer)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    batch = db.relationship("Batch")
    user = db.relationship("User")


class SupplierReturn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    return_number = db.Column(db.String(40), unique=True, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey("batch.id"), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    reason = db.Column(db.String(80))  # expired, recalled
    credit_note = db.Column(db.String(60))
    credit_amount = db.Column(db.Float, default=0)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    supplier = db.relationship("Supplier")
    batch = db.relationship("Batch")
    created_by = db.relationship("User")


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    ip_address = db.Column(db.String(60))
    workstation = db.Column(db.String(80))
    action = db.Column(db.String(80), nullable=False)
    entity = db.Column(db.String(80))
    entity_id = db.Column(db.String(40))
    details = db.Column(db.Text)
    before_value = db.Column(db.Text)
    after_value = db.Column(db.Text)
    immutable = db.Column(db.Boolean, default=True)

    user = db.relationship("User")


class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(300), nullable=False)
    kind = db.Column(db.String(40), default="info")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    user = db.relationship("User")


class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    alert_type = db.Column(db.String(20), nullable=False)  # low | out
    message = db.Column(db.String(300), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    product = db.relationship("Product")
