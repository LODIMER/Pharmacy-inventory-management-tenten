from datetime import datetime, date, timedelta
from app import db
from app.models import (
    User,
    Product,
    Supplier,
    PurchaseOrder,
    POLine,
    Batch,
    Sale,
    SaleLine,
    Requisition,
    RequisitionLine,
    AuditLog,
    Activity,
    Alert,
    StockAdjustment,
    SupplierReturn,
)
from app.utils import refresh_stock_alerts


def seed_if_empty():
    if User.query.first():
        return

    users = {}
    specs = [
        ("admin", "admin123", "Elena Navarro", "admin", None, "admin@medvault.ph"),
        ("pharmacist", "pharma123", "Dr. Marco Reyes", "chief_pharmacist", None, "chief@medvault.ph"),
        ("dispenser", "dispense123", "Aira Santos", "dispensing_staff", None, "dispense@medvault.ph"),
        ("inventory", "inventory123", "Luis Tan", "inventory_controller", None, "stock@medvault.ph"),
        ("patient", "patient123", "Maria Cruz", "patient", None, "maria.cruz@email.com"),
        ("department", "dept123", "ER Charge Nurse", "department", "Emergency", "er@hospital.ph"),
        ("ward", "ward123", "Ward 3 Clerk", "department", "Ward 3", "ward3@hospital.ph"),
        ("patient2", "patient123", "Jose Dela Cruz", "patient", None, "jose.dc@email.com"),
    ]
    for username, pw, name, role, dept, email in specs:
        u = User(
            username=username,
            full_name=name,
            role=role,
            department_name=dept,
            email=email,
            phone="09" + str(abs(hash(username)) % 10**9).zfill(9),
            prescription_notes="NKDA. Prefers generic substitution." if role == "patient" else None,
        )
        u.set_password(pw)
        db.session.add(u)
        users[username] = u
    db.session.flush()

    suppliers = [
        Supplier(
            name="Zuellig Pharma",
            contact_name="Rhea Lim",
            email="orders@zuellig.ph",
            phone="02-8888-1000",
            address="Makati City",
            lead_time_days=3,
            payment_terms="Net 30",
        ),
        Supplier(
            name="Metro Drug Inc.",
            contact_name="Paolo Cruz",
            email="sales@metrodrug.ph",
            phone="02-8777-2200",
            address="Quezon City",
            lead_time_days=5,
            payment_terms="Net 15",
        ),
        Supplier(
            name="PharmaCare Wholesale",
            contact_name="Nina Go",
            email="credit@pharmacare.ph",
            phone="02-8555-3300",
            address="Pasig City",
            lead_time_days=7,
            payment_terms="COD",
        ),
    ]
    db.session.add_all(suppliers)
    db.session.flush()

    catalog = [
        dict(
            ndc="45802-046-70",
            upc="480001100001",
            barcode="890123000001",
            brand_name="Amoxil",
            generic_name="Amoxicillin",
            dosage_form="Capsule",
            strength="500mg",
            category="Antibiotic",
            therapeutic_class="Penicillin",
            storage_condition="Room Temp",
            uom="Box",
            unit_cost=18.5,
            retail_price=28.0,
            markup_percent=51.4,
            reorder_point=40,
            max_level=200,
            lasa_flag=True,
            safety_alerts="Check penicillin allergy.",
            interaction_warnings="May reduce oral contraceptive efficacy.",
        ),
        dict(
            ndc="50580-506-02",
            upc="480001100002",
            barcode="890123000002",
            brand_name="Biogesic",
            generic_name="Paracetamol",
            dosage_form="Tablet",
            strength="500mg",
            category="Analgesic",
            therapeutic_class="Analgesic/Antipyretic",
            storage_condition="Room Temp",
            uom="Strip",
            unit_cost=2.1,
            retail_price=4.5,
            markup_percent=114.3,
            reorder_point=80,
            max_level=500,
        ),
        dict(
            ndc="00406-0513-01",
            upc="480001100003",
            barcode="890123000003",
            brand_name="OxyContin",
            generic_name="Oxycodone",
            dosage_form="Tablet",
            strength="10mg",
            category="Controlled Substance",
            therapeutic_class="Opioid analgesic",
            storage_condition="Controlled Vault",
            uom="Bottle",
            unit_cost=45.0,
            retail_price=72.0,
            markup_percent=60.0,
            reorder_point=8,
            max_level=40,
            is_controlled=True,
            schedule="II",
            safety_alerts="Schedule II. Dual verification required.",
            interaction_warnings="Do not combine with benzodiazepines.",
        ),
        dict(
            ndc="0002-8215-01",
            upc="480001100004",
            barcode="890123000004",
            brand_name="Humalog",
            generic_name="Insulin lispro",
            dosage_form="Injection",
            strength="100 IU/mL",
            category="Antidiabetic",
            therapeutic_class="Rapid-acting insulin",
            storage_condition="Cold Chain 2°C–8°C",
            uom="Vial",
            unit_cost=320.0,
            retail_price=480.0,
            markup_percent=50.0,
            reorder_point=6,
            max_level=30,
            safety_alerts="Keep refrigerated. Do not freeze.",
        ),
        dict(
            ndc="0093-0058-01",
            upc="480001100005",
            barcode="890123000005",
            brand_name="Lipitor",
            generic_name="Atorvastatin",
            dosage_form="Tablet",
            strength="20mg",
            category="Cardiovascular",
            therapeutic_class="Statin",
            storage_condition="Room Temp",
            uom="Box",
            unit_cost=12.0,
            retail_price=22.0,
            markup_percent=83.3,
            reorder_point=25,
            max_level=150,
        ),
        dict(
            ndc="0071-0156-23",
            upc="480001100006",
            barcode="890123000006",
            brand_name="Ventolin",
            generic_name="Salbutamol",
            dosage_form="Inhaler",
            strength="100mcg",
            category="Respiratory",
            therapeutic_class="SABA",
            storage_condition="Room Temp",
            uom="Pack",
            unit_cost=95.0,
            retail_price=145.0,
            markup_percent=52.6,
            reorder_point=12,
            max_level=60,
            lasa_flag=True,
        ),
        dict(
            ndc="0074-3346-13",
            upc="480001100007",
            barcode="890123000007",
            brand_name="Nexium",
            generic_name="Esomeprazole",
            dosage_form="Capsule",
            strength="40mg",
            category="Gastrointestinal",
            therapeutic_class="PPI",
            storage_condition="Room Temp",
            uom="Box",
            unit_cost=16.0,
            retail_price=30.0,
            markup_percent=87.5,
            reorder_point=20,
            max_level=120,
        ),
        dict(
            ndc="0049-1770-66",
            upc="480001100008",
            barcode="890123000008",
            brand_name="Betadine",
            generic_name="Povidone-iodine",
            dosage_form="Ointment",
            strength="10%",
            category="OTC",
            therapeutic_class="Antiseptic",
            storage_condition="Room Temp",
            uom="Tube",
            unit_cost=35.0,
            retail_price=58.0,
            markup_percent=65.7,
            reorder_point=15,
            max_level=80,
        ),
        dict(
            ndc="0006-0277-31",
            upc="480001100009",
            barcode="890123000009",
            brand_name="Cozaar",
            generic_name="Losartan",
            dosage_form="Tablet",
            strength="50mg",
            category="Cardiovascular",
            therapeutic_class="ARB",
            storage_condition="Room Temp",
            uom="Box",
            unit_cost=8.5,
            retail_price=15.0,
            markup_percent=76.5,
            reorder_point=30,
            max_level=180,
        ),
        dict(
            ndc="0002-1433-80",
            upc="480001100010",
            barcode="890123000010",
            brand_name="Ceftriaxone-IV",
            generic_name="Ceftriaxone",
            dosage_form="Injection",
            strength="1g",
            category="Antibiotic",
            therapeutic_class="Cephalosporin",
            storage_condition="Fridge",
            uom="Vial",
            unit_cost=55.0,
            retail_price=88.0,
            markup_percent=60.0,
            reorder_point=10,
            max_level=50,
            safety_alerts="Reconstitute immediately before use.",
        ),
        dict(
            ndc="0071-4117-68",
            upc="480001100011",
            barcode="890123000011",
            brand_name="Metformin XR",
            generic_name="Metformin",
            dosage_form="Tablet",
            strength="500mg",
            category="Antidiabetic",
            therapeutic_class="Biguanide",
            storage_condition="Room Temp",
            uom="Box",
            unit_cost=4.2,
            retail_price=8.0,
            markup_percent=90.5,
            reorder_point=50,
            max_level=300,
        ),
        dict(
            ndc="0054-0244-25",
            upc="480001100012",
            barcode="890123000012",
            brand_name="Morphine Sulfate",
            generic_name="Morphine",
            dosage_form="Injection",
            strength="10mg/mL",
            category="Controlled Substance",
            therapeutic_class="Opioid analgesic",
            storage_condition="Controlled Vault",
            uom="Ampoule",
            unit_cost=28.0,
            retail_price=42.0,
            markup_percent=50.0,
            reorder_point=5,
            max_level=25,
            is_controlled=True,
            schedule="II",
            safety_alerts="Schedule II. Dual verification and doctor license required.",
        ),
    ]
    products = []
    for row in catalog:
        p = Product(**row)
        db.session.add(p)
        products.append(p)
    db.session.flush()
    by_name = {p.brand_name: p for p in products}

    po1 = PurchaseOrder(
        po_number="PO-00001",
        supplier_id=suppliers[0].id,
        status="completed",
        created_by_id=users["inventory"].id,
        submitted_at=datetime.utcnow() - timedelta(days=12),
    )
    po2 = PurchaseOrder(
        po_number="PO-00002",
        supplier_id=suppliers[1].id,
        status="partially_received",
        created_by_id=users["pharmacist"].id,
        submitted_at=datetime.utcnow() - timedelta(days=2),
    )
    po3 = PurchaseOrder(
        po_number="PO-00003",
        supplier_id=suppliers[0].id,
        status="submitted",
        created_by_id=users["inventory"].id,
        submitted_at=datetime.utcnow() - timedelta(hours=6),
    )
    db.session.add_all([po1, po2, po3])
    db.session.flush()

    def line(po, name, ordered, received, cost):
        return POLine(
            po_id=po.id,
            product_id=by_name[name].id,
            qty_ordered=ordered,
            qty_received=received,
            unit_cost=cost,
        )

    db.session.add_all(
        [
            line(po1, "Amoxil", 120, 120, 18.5),
            line(po1, "Biogesic", 400, 400, 2.1),
            line(po1, "Lipitor", 80, 80, 12.0),
            line(po1, "Humalog", 20, 20, 320.0),
            line(po2, "Ventolin", 30, 10, 95.0),
            line(po2, "Nexium", 60, 0, 16.0),
            line(po3, "Cozaar", 90, 0, 8.5),
            line(po3, "Metformin XR", 150, 0, 4.2),
        ]
    )

    today = date.today()
    batches = [
        Batch(
            product_id=by_name["Amoxil"].id,
            lot_number="AMX-2401",
            mfg_date=today - timedelta(days=200),
            expiry_date=today + timedelta(days=18),
            location="Shelf",
            quantity=25,
            po_id=po1.id,
            invoice_date=today - timedelta(days=12),
        ),
        Batch(
            product_id=by_name["Amoxil"].id,
            lot_number="AMX-2408",
            mfg_date=today - timedelta(days=40),
            expiry_date=today + timedelta(days=400),
            location="Shelf",
            quantity=90,
            po_id=po1.id,
            invoice_date=today - timedelta(days=12),
        ),
        Batch(
            product_id=by_name["Biogesic"].id,
            lot_number="BIO-331",
            mfg_date=today - timedelta(days=90),
            expiry_date=today + timedelta(days=55),
            location="Bin",
            quantity=60,
            po_id=po1.id,
            invoice_date=today - timedelta(days=12),
        ),
        Batch(
            product_id=by_name["Biogesic"].id,
            lot_number="BIO-402",
            mfg_date=today - timedelta(days=20),
            expiry_date=today + timedelta(days=500),
            location="Bin",
            quantity=20,
            po_id=po1.id,
            invoice_date=today - timedelta(days=12),
        ),
        Batch(
            product_id=by_name["OxyContin"].id,
            lot_number="OXY-091",
            mfg_date=today - timedelta(days=60),
            expiry_date=today + timedelta(days=300),
            location="Controlled Vault",
            quantity=12,
        ),
        Batch(
            product_id=by_name["Humalog"].id,
            lot_number="HUM-118",
            mfg_date=today - timedelta(days=30),
            expiry_date=today + timedelta(days=22),
            location="Fridge",
            quantity=8,
            po_id=po1.id,
            invoice_date=today - timedelta(days=12),
        ),
        Batch(
            product_id=by_name["Lipitor"].id,
            lot_number="LIP-77",
            mfg_date=today - timedelta(days=150),
            expiry_date=today + timedelta(days=80),
            location="Shelf",
            quantity=70,
            po_id=po1.id,
        ),
        Batch(
            product_id=by_name["Ventolin"].id,
            lot_number="VEN-55",
            mfg_date=today - timedelta(days=70),
            expiry_date=today + timedelta(days=200),
            location="Shelf",
            quantity=10,
            po_id=po2.id,
        ),
        Batch(
            product_id=by_name["Nexium"].id,
            lot_number="NEX-12",
            mfg_date=today - timedelta(days=400),
            expiry_date=today - timedelta(days=5),
            location="Shelf",
            quantity=6,
            status="quarantine",
        ),
        Batch(
            product_id=by_name["Betadine"].id,
            lot_number="BET-9",
            mfg_date=today - timedelta(days=100),
            expiry_date=today + timedelta(days=250),
            location="Bin",
            quantity=40,
        ),
        Batch(
            product_id=by_name["Cozaar"].id,
            lot_number="COZ-3",
            mfg_date=today - timedelta(days=80),
            expiry_date=today + timedelta(days=310),
            location="Shelf",
            quantity=4,
        ),
        Batch(
            product_id=by_name["Ceftriaxone-IV"].id,
            lot_number="CEF-44",
            mfg_date=today - timedelta(days=15),
            expiry_date=today + timedelta(days=120),
            location="Fridge",
            quantity=0,
        ),
        Batch(
            product_id=by_name["Metformin XR"].id,
            lot_number="MET-21",
            mfg_date=today - timedelta(days=50),
            expiry_date=today + timedelta(days=420),
            location="Shelf",
            quantity=140,
        ),
        Batch(
            product_id=by_name["Morphine Sulfate"].id,
            lot_number="MOR-02",
            mfg_date=today - timedelta(days=25),
            expiry_date=today + timedelta(days=180),
            location="Controlled Vault",
            quantity=9,
        ),
    ]
    db.session.add_all(batches)
    db.session.flush()
    batch_map = {b.lot_number: b for b in batches}

    sale = Sale(
        receipt_no="RCP-00001",
        patient_id=users["patient"].id,
        prescription_id="RX-77821",
        dispenser_id=users["dispenser"].id,
        discount_type="Senior Citizen",
        discount_amount=5.04,
        tax_amount=0,
        subtotal=28.0 + 9.0,
        total=31.96,
        created_at=datetime.utcnow() - timedelta(hours=3),
    )
    db.session.add(sale)
    db.session.flush()
    db.session.add_all(
        [
            SaleLine(
                sale_id=sale.id,
                product_id=by_name["Amoxil"].id,
                batch_id=batch_map["AMX-2401"].id,
                quantity=1,
                unit_price=28.0,
                line_total=28.0,
            ),
            SaleLine(
                sale_id=sale.id,
                product_id=by_name["Biogesic"].id,
                batch_id=batch_map["BIO-331"].id,
                quantity=2,
                unit_price=4.5,
                line_total=9.0,
            ),
        ]
    )

    ctrl_sale = Sale(
        receipt_no="RCP-00002",
        patient_id=users["patient2"].id,
        prescription_id="RX-88011",
        dispenser_id=users["dispenser"].id,
        verifier_id=users["pharmacist"].id,
        doctor_license="PRC-1234567",
        discount_type="None",
        tax_amount=8.64,
        subtotal=72.0,
        total=80.64,
        created_at=datetime.utcnow() - timedelta(hours=1),
    )
    db.session.add(ctrl_sale)
    db.session.flush()
    db.session.add(
        SaleLine(
            sale_id=ctrl_sale.id,
            product_id=by_name["OxyContin"].id,
            batch_id=batch_map["OXY-091"].id,
            quantity=1,
            unit_price=72.0,
            line_total=72.0,
        )
    )

    r1 = Requisition(
        req_number="REQ-00001",
        requester_id=users["patient"].id,
        req_type="refill",
        status="ready_for_pickup",
        fulfillment="pickup",
        pickup_time="Today 4:00 PM",
        notes="Amoxicillin refill",
        reviewed_by_id=users["pharmacist"].id,
    )
    r2 = Requisition(
        req_number="REQ-00002",
        requester_id=users["department"].id,
        req_type="transfer",
        status="pending_review",
        fulfillment="pickup",
        notes="ER ward restock",
    )
    r3 = Requisition(
        req_number="REQ-00003",
        requester_id=users["patient"].id,
        req_type="refill",
        status="processing",
        fulfillment="delivery",
        notes="Metformin monthly refill",
        reviewed_by_id=users["pharmacist"].id,
    )
    db.session.add_all([r1, r2, r3])
    db.session.flush()
    db.session.add_all(
        [
            RequisitionLine(requisition_id=r1.id, product_id=by_name["Amoxil"].id, quantity=2),
            RequisitionLine(requisition_id=r2.id, product_id=by_name["Ceftriaxone-IV"].id, quantity=10),
            RequisitionLine(requisition_id=r2.id, product_id=by_name["Morphine Sulfate"].id, quantity=4),
            RequisitionLine(requisition_id=r3.id, product_id=by_name["Metformin XR"].id, quantity=3),
        ]
    )

    db.session.add(
        StockAdjustment(
            batch_id=batch_map["NEX-12"].id,
            user_id=users["inventory"].id,
            reason="quarantine",
            qty_before=6,
            qty_after=6,
            notes="Expired lot moved to quarantine pending reverse distribution.",
        )
    )
    db.session.add(
        SupplierReturn(
            return_number="RTN-00001",
            supplier_id=suppliers[0].id,
            batch_id=batch_map["NEX-12"].id,
            quantity=6,
            reason="expired",
            credit_note="CN-4419",
            credit_amount=96.0,
            created_by_id=users["inventory"].id,
        )
    )

    db.session.add_all(
        [
            Activity(message="Received PO-00001 from Zuellig Pharma (4 SKUs).", kind="receive", user_id=users["inventory"].id),
            Activity(message="Dispensed RCP-00001 to Maria Cruz (Senior Citizen discount).", kind="sale", user_id=users["dispenser"].id),
            Activity(message="Schedule II sale RCP-00002 dual-verified by Dr. Marco Reyes.", kind="sale", user_id=users["pharmacist"].id),
            Activity(message="ER requisition REQ-00002 awaiting chief pharmacist approval.", kind="order", user_id=users["department"].id),
            Activity(message="Expired Nexium lot NEX-12 quarantined.", kind="adjust", user_id=users["inventory"].id),
        ]
    )
    db.session.add_all(
        [
            AuditLog(
                user_id=users["admin"].id,
                ip_address="127.0.0.1",
                workstation="SEED",
                action="System Seeded",
                entity="Database",
                details="Initial catalog, users, and stock loaded.",
            )
        ]
    )

    refresh_stock_alerts()
    db.session.commit()
