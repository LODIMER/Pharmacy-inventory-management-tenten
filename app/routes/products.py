from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app import db
from app.models import (
    Product,
    DOSAGE_FORMS,
    CATEGORIES,
    STORAGE_CONDITIONS,
    UOMS,
)
from app.decorators import staff_required
from app.utils import log_audit, add_activity, refresh_stock_alerts

products_bp = Blueprint("products", __name__, url_prefix="/products")


def _fill(product, form):
    product.ndc = form.get("ndc")
    product.upc = form.get("upc")
    product.barcode = form.get("barcode")
    product.brand_name = form.get("brand_name") or product.brand_name
    product.generic_name = form.get("generic_name") or product.generic_name
    product.dosage_form = form.get("dosage_form")
    product.strength = form.get("strength")
    product.category = form.get("category")
    product.therapeutic_class = form.get("therapeutic_class")
    product.storage_condition = form.get("storage_condition")
    product.uom = form.get("uom")
    product.unit_cost = float(form.get("unit_cost") or 0)
    product.retail_price = float(form.get("retail_price") or 0)
    cost = product.unit_cost or 0
    product.markup_percent = ((product.retail_price - cost) / cost * 100) if cost else 0
    product.reorder_point = int(form.get("reorder_point") or 0)
    product.max_level = int(form.get("max_level") or 0)
    product.lasa_flag = bool(form.get("lasa_flag"))
    product.safety_alerts = form.get("safety_alerts")
    product.interaction_warnings = form.get("interaction_warnings")
    product.is_controlled = bool(form.get("is_controlled"))
    product.schedule = form.get("schedule")
    product.is_active = bool(form.get("is_active"))


@products_bp.route("/")
@staff_required
def index():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    query = Product.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Product.brand_name.ilike(like),
                Product.generic_name.ilike(like),
                Product.ndc.ilike(like),
                Product.barcode.ilike(like),
            )
        )
    if category:
        query = query.filter_by(category=category)
    products = query.order_by(Product.brand_name).all()
    return render_template(
        "products/index.html",
        products=products,
        q=q,
        category=category,
        categories=CATEGORIES,
    )


@products_bp.route("/catalog")
@login_required
def catalog():
    q = request.args.get("q", "").strip()
    query = Product.query.filter_by(is_active=True)
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(Product.brand_name.ilike(like), Product.generic_name.ilike(like))
        )
    products = query.order_by(Product.brand_name).all()
    return render_template("products/catalog.html", products=products, q=q)


@products_bp.route("/new", methods=["GET", "POST"])
@staff_required
def create():
    if not current_user.can_inventory():
        abort(403)
    if request.method == "POST":
        product = Product(brand_name="New", generic_name="New")
        _fill(product, request.form)
        db.session.add(product)
        db.session.flush()
        log_audit("Stock Created", "Product", product.id, details=product.brand_name)
        add_activity(f"Added drug master record: {product.brand_name} ({product.generic_name}).", "product")
        refresh_stock_alerts()
        db.session.commit()
        flash("Product added to master directory.", "success")
        return redirect(url_for("products.index"))
    return render_template(
        "products/form.html",
        product=None,
        dosage_forms=DOSAGE_FORMS,
        categories=CATEGORIES,
        storage_conditions=STORAGE_CONDITIONS,
        uoms=UOMS,
    )


@products_bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
@staff_required
def edit(product_id):
    if not current_user.can_inventory():
        abort(403)
    product = db.session.get(Product, product_id) or abort(404)
    if request.method == "POST":
        before_price = product.retail_price
        before_cost = product.unit_cost
        _fill(product, request.form)
        if before_price != product.retail_price or before_cost != product.unit_cost:
            log_audit(
                "Price Changed",
                "Product",
                product.id,
                before=f"cost={before_cost} price={before_price}",
                after=f"cost={product.unit_cost} price={product.retail_price}",
            )
        else:
            log_audit("Product Updated", "Product", product.id, details=product.brand_name)
        refresh_stock_alerts()
        db.session.commit()
        flash("Product updated.", "success")
        return redirect(url_for("products.index"))
    return render_template(
        "products/form.html",
        product=product,
        dosage_forms=DOSAGE_FORMS,
        categories=CATEGORIES,
        storage_conditions=STORAGE_CONDITIONS,
        uoms=UOMS,
    )


@products_bp.route("/<int:product_id>/archive", methods=["POST"])
@staff_required
def archive(product_id):
    if not current_user.can_inventory():
        abort(403)
    product = db.session.get(Product, product_id) or abort(404)
    product.is_active = False
    log_audit("Product Archived", "Product", product.id, details=product.brand_name)
    db.session.commit()
    flash("Product archived.", "success")
    return redirect(url_for("products.index"))
