from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.product import Product
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.services.audit import log_action


router = APIRouter(
    prefix="/commerce",
    tags=["AI Commerce"]
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()



class AddToCartRequest(BaseModel):
    product_id: int
    quantity: int = 1



@router.get("/catalog/search")
def search_catalog(
    query: str,
    max_price: float | None = None,
    category_id: int | None = None,
    limit: int = 10,
    db: Session = Depends(get_db)
):

    if limit < 1:
        limit = 1

    if limit > 50:
        limit = 50

    products_query = (
        db.query(Product)
        .filter(
            Product.is_active == True,
            Product.name.ilike(f"%{query}%")
        )
    )

    if max_price is not None:
        products_query = products_query.filter(
            Product.price <= max_price
        )

    if category_id is not None:
        products_query = products_query.filter(
            Product.category_id == category_id
        )

    products = (
        products_query
        .limit(limit)
        .all()
    )

    return {
        "merchant": "Razorpay AI Merchant Agent",
        "currency": "INR",
        "query": query,
        "filters": {
            "max_price": max_price,
            "category_id": category_id
        },
        "products": [
            {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "price": float(product.price),
                "currency": "INR",
                "availability": {
                    "in_stock": product.stock > 0,
                    "quantity": product.stock
                }
            }
            for product in products
        ],
        "count": len(products)
    }


@router.get("/products/{product_id}")
def get_commerce_product(
    product_id: int,
    db: Session = Depends(get_db)
):

    product = (
        db.query(Product)
        .filter(
            Product.id == product_id,
            Product.is_active == True
        )
        .first()
    )

    if not product:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    return {
        "merchant": "Razorpay AI Merchant Agent",
        "product": {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "price": float(product.price),
            "currency": "INR",
            "availability": {
                "in_stock": product.stock > 0,
                "quantity": product.stock
            }
        }
    }


@router.get("/products/{product_id}/availability")
def get_product_availability(
    product_id: int,
    db: Session = Depends(get_db)
):

    product = (
        db.query(Product)
        .filter(
            Product.id == product_id,
            Product.is_active == True
        )
        .first()
    )

    if not product:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    return {
        "product_id": product.id,
        "name": product.name,
        "currency": "INR",
        "price": float(product.price),
        "availability": {
            "in_stock": product.stock > 0,
            "quantity": product.stock
        }
    }



@router.get("/cart/{customer_id}")
def get_commerce_cart(
    customer_id: int,
    db: Session = Depends(get_db)
):
   

    cart = (
        db.query(Cart)
        .filter(
            Cart.customer_id == customer_id,
            Cart.status == "active"
        )
        .first()
    )

    if not cart:
        return {
            "customer_id": customer_id,
            "cart_id": None,
            "status": "no_active_cart",
            "items": [],
            "total": 0,
            "currency": "INR"
        }

    items = (
        db.query(CartItem, Product)
        .join(
            Product,
            CartItem.product_id == Product.id
        )
        .filter(
            CartItem.cart_id == cart.id
        )
        .all()
    )

    formatted_items = []

    total = 0

    for item, product in items:
        subtotal = (
            float(product.price) *
            item.quantity
        )

        total += subtotal

        formatted_items.append({
            "cart_item_id": item.id,
            "product_id": product.id,
            "name": product.name,
            "price": float(product.price),
            "quantity": item.quantity,
            "subtotal": subtotal,
            "currency": "INR",
            "available": (
                product.stock >= item.quantity
            )
        })

    return {
        "customer_id": customer_id,
        "cart_id": cart.id,
        "status": cart.status,
        "currency": "INR",
        "items": formatted_items,
        "total": total
    }


@router.post("/cart/{customer_id}/items")
def commerce_add_to_cart(
    customer_id: int,
    request: AddToCartRequest,
    db: Session = Depends(get_db)
):

    if request.quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be greater than zero"
        )

    cart = (
        db.query(Cart)
        .filter(
            Cart.customer_id == customer_id,
            Cart.status == "active"
        )
        .first()
    )

    if not cart:
        raise HTTPException(
            status_code=404,
            detail="Active cart not found"
        )

    product = (
        db.query(Product)
        .filter(
            Product.id == request.product_id,
            Product.is_active == True
        )
        .first()
    )

    if not product:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    if request.quantity > product.stock:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Not enough stock for "
                f"{product.name}. "
                f"Only {product.stock} available."
            )
        )

    
    cart_item = (
        db.query(CartItem)
        .filter(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product.id
        )
        .first()
    )

    if cart_item:

        new_quantity = (
            cart_item.quantity +
            request.quantity
        )

        if new_quantity > product.stock:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Not enough stock for "
                    f"{product.name}. "
                    f"Only {product.stock} available."
                )
            )

        cart_item.quantity = new_quantity

    else:

        cart_item = CartItem(
            cart_id=cart.id,
            product_id=product.id,
            quantity=request.quantity
        )

        db.add(cart_item)

    db.commit()
    db.refresh(cart_item)

    log_action(
        session_id=f"customer_{customer_id}",
        action="AI_BUYER_ADD_TO_CART",
        tool_name="commerce_api",
        arguments={
            "customer_id": customer_id,
            "cart_id": cart.id,
            "product_id": product.id,
            "quantity": request.quantity
        },
        result={
            "success": True,
            "product": product.name,
            "quantity_added": request.quantity,
            "cart_item_quantity":
                cart_item.quantity
        }
    )

    return {
        "success": True,
        "merchant": "Razorpay AI Merchant Agent",
        "customer_id": customer_id,
        "cart_id": cart.id,
        "product": {
            "id": product.id,
            "name": product.name,
            "price": float(product.price),
            "currency": "INR"
        },
        "quantity": cart_item.quantity,
        "message": (
            f"{request.quantity} x "
            f"{product.name} added to cart."
        ),
        "payment_initiated": False,
        "approval_required_for_payment": True
    }

@router.post("/checkout/{customer_id}")
def request_checkout(
    customer_id: int,
    db: Session = Depends(get_db)
):
   

    cart = (
        db.query(Cart)
        .filter(
            Cart.customer_id == customer_id,
            Cart.status == "active"
        )
        .first()
    )

    if not cart:
        raise HTTPException(
            status_code=404,
            detail="Active cart not found"
        )

    items = (
        db.query(CartItem, Product)
        .join(
            Product,
            CartItem.product_id == Product.id
        )
        .filter(
            CartItem.cart_id == cart.id
        )
        .all()
    )

    if not items:
        raise HTTPException(
            status_code=400,
            detail="Cart is empty"
        )

    total = 0

    checkout_items = []


    for item, product in items:

        if item.quantity > product.stock:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Not enough stock for "
                    f"{product.name}. "
                    f"Only {product.stock} available."
                )
            )

        subtotal = (
            float(product.price) *
            item.quantity
        )

        total += subtotal

        checkout_items.append({
            "product_id": product.id,
            "name": product.name,
            "quantity": item.quantity,
            "unit_price": float(product.price),
            "subtotal": subtotal,
            "currency": "INR"
        })

    # -----------------------------------------------------
    # Audit checkout request
    # -----------------------------------------------------

    log_action(
        session_id=f"customer_{customer_id}",
        action="AI_CHECKOUT_REQUESTED",
        tool_name="commerce_api",
        arguments={
            "customer_id": customer_id,
            "cart_id": cart.id
        },
        result={
            "total": total,
            "currency": "INR",
            "approval_required": True,
            "payment_initiated": False
        },
        approval_required=True,
        approved=False
    )

    return {
        "success": True,
        "checkout_status": "awaiting_customer_approval",

        "merchant":
            "Razorpay AI Merchant Agent",

        "customer_id": customer_id,

        "cart_id": cart.id,

        "currency": "INR",

        "items": checkout_items,

        "total": total,

        "payment": {
            "initiated": False,
            "approval_required": True,
            "approved": False
        },

        "next_action": (
            "Obtain explicit customer approval "
            "before initiating payment."
        )
    }


@router.get("/manifest")
def get_commerce_manifest():
  

    return {
        "manifest_version": "1.0",

        "merchant": {
            "name": "Razorpay AI Merchant Agent",
            "type": "ai_transactable_merchant",
            "currency": "INR"
        },

        "buyer_interface": {
            "type": "http_api",
            "base_path": "/api/commerce"
        },

        "capabilities": [
            {
                "name": "catalog_search",
                "method": "GET",
                "endpoint": "/api/commerce/catalog/search",
                "description": "Search active merchant products.",
                "safe_for_ai": True
            },
            {
                "name": "product_details",
                "method": "GET",
                "endpoint": "/api/commerce/products/{product_id}",
                "description": "Retrieve exact product information.",
                "safe_for_ai": True
            },
            {
                "name": "availability_check",
                "method": "GET",
                "endpoint": "/api/commerce/products/{product_id}/availability",
                "description": "Check live product stock before purchase.",
                "safe_for_ai": True
            },
            {
                "name": "get_cart",
                "method": "GET",
                "endpoint": "/api/commerce/cart/{customer_id}",
                "description": "View the customer's active cart.",
                "safe_for_ai": True
            },
            {
                "name": "add_to_cart",
                "method": "POST",
                "endpoint": "/api/commerce/cart/{customer_id}/items",
                "description": "Add an available product to the customer's cart.",
                "safe_for_ai": True,
                "payment_required": False
            },
            {
                "name": "request_checkout",
                "method": "POST",
                "endpoint": "/api/commerce/checkout/{customer_id}",
                "description": (
                    "Prepare checkout and request explicit customer approval. "
                    "Does not initiate payment."
                ),
                "safe_for_ai": True,
                "payment_required": False,
                "approval_required": True
            }
        ],

        "payment_policy": {
            "automatic_payment": False,
            "payment_initiated_by_ai": False,
            "explicit_customer_approval_required": True,
            "signature_verification_required": True
        },

        "commerce_constraints": {
            "stock_checked_before_cart_action": True,
            "stock_checked_before_checkout": True,
            "cannot_exceed_available_stock": True,
            "audit_logging_enabled": True
        },

        "security_boundary": {
            "ai_can": [
                "discover_products",
                "check_availability",
                "manage_cart",
                "request_checkout"
            ],
            "ai_cannot": [
                "automatically_charge_customer",
                "bypass_customer_approval",
                "mark_payment_as_successful",
                "bypass_payment_signature_verification"
            ]
        },

        "transaction_flow": [
            "discover",
            "check_availability",
            "add_to_cart",
            "request_checkout",
            "customer_approval",
            "razorpay_payment",
            "signature_verification"
        ]
    }


@router.get("/capabilities")
def get_commerce_capabilities():
   

    return {
        "merchant":
            "Razorpay AI Merchant Agent",

        "version": "1.0",

        "currency": "INR",

        "capabilities": [

            {
                "name": "catalog_search",
                "method": "GET",
                "endpoint":
                    "/api/commerce/catalog/search",
                "description":
                    "Search merchant products."
            },

            {
                "name": "product_details",
                "method": "GET",
                "endpoint":
                    "/api/commerce/products/{product_id}",
                "description":
                    "Retrieve exact product details."
            },

            {
                "name": "availability_check",
                "method": "GET",
                "endpoint":
                    "/api/commerce/products/"
                    "{product_id}/availability",
                "description":
                    "Check current product stock."
            },

            {
                "name": "get_cart",
                "method": "GET",
                "endpoint":
                    "/api/commerce/cart/{customer_id}",
                "description":
                    "View the customer's active cart."
            },

            {
                "name": "add_to_cart",
                "method": "POST",
                "endpoint":
                    "/api/commerce/cart/"
                    "{customer_id}/items",
                "description":
                    "Add an available product to cart."
            },

            {
                "name": "request_checkout",
                "method": "POST",
                "endpoint":
                    "/api/commerce/checkout/"
                    "{customer_id}",
                "description":
                    (
                        "Prepare checkout and request "
                        "customer approval. "
                        "Does not initiate payment."
                    )
            }
        ],

        "payment_policy": {

            "requires_explicit_customer_approval":
                True,

            "automatic_payment":
                False,

            "payment_initiated_by_ai":
                False,

            "signature_verification_required":
                True
        },

        "safety_constraints": [

            "AI cannot automatically charge the customer.",

            "Product availability is checked against live stock.",

            "Checkout requires explicit customer approval.",

            "Payment is only considered successful "
            "after Razorpay signature verification.",

            "Commerce actions are audit logged."
        ]
    }