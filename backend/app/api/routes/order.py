import os

import razorpay

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.services.audit import log_action


razorpay_client = razorpay.Client(
    auth=(
        os.getenv("RAZORPAY_KEY_ID"),
        os.getenv("RAZORPAY_KEY_SECRET")
    )
)


router = APIRouter(
    prefix="/orders",
    tags=["Orders"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/from-cart/{cart_id}")
def create_order_from_cart(
    cart_id: int,
    db: Session = Depends(get_db)
):
    cart = db.query(Cart).filter(
        Cart.id == cart_id
    ).first()

    if not cart:
        raise HTTPException(
            status_code=404,
            detail="Cart not found"
        )

    if cart.status != "active":
        raise HTTPException(
            status_code=400,
            detail="Cart is not active"
        )

    items = db.query(CartItem).filter(
        CartItem.cart_id == cart_id
    ).all()

    if not items:
        raise HTTPException(
            status_code=400,
            detail="Cart is empty"
        )

    total_amount = 0
    order_items = []

    for item in items:
        product = db.query(Product).filter(
            Product.id == item.product_id
        ).first()

        if not product:
            raise HTTPException(
                status_code=404,
                detail=f"Product {item.product_id} not found"
            )

        if item.quantity > product.stock:
            raise HTTPException(
                status_code=400,
                detail=f"Not enough stock for {product.name}"
            )

        total_amount += float(product.price) * item.quantity

        order_items.append(
            OrderItem(
                product_id=product.id,
                quantity=item.quantity,
                price=product.price
            )
        )

    order = Order(
        customer_id=cart.customer_id,
        total_amount=total_amount,
        status="pending"
    )

    db.add(order)
    db.flush()

    for order_item in order_items:
        order_item.order_id = order.id
        db.add(order_item)

    db.commit()
    db.refresh(order)

    # Audit: order created
    log_action(
        session_id=f"customer_{order.customer_id}",
        action="ORDER_CREATED",
        result={
            "order_id": order.id,
            "amount": float(order.total_amount),
            "status": order.status
        }
    )

    return order


@router.post("/{order_id}/razorpay")
def create_razorpay_order(
    order_id: int,
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(
        Order.id == order_id
    ).first()

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    if order.status != "pending":
        raise HTTPException(
            status_code=400,
            detail="Order is not pending"
        )

    razorpay_order = razorpay_client.order.create(
        data={
            "amount": int(float(order.total_amount) * 100),
            "currency": "INR",
            "receipt": f"order_{order.id}"
        }
    )

    order.razorpay_order_id = razorpay_order["id"]

    db.commit()
    db.refresh(order)

    # Audit: Razorpay payment initiated
    log_action(
        session_id=f"customer_{order.customer_id}",
        action="PAYMENT_INITIATED",
        tool_name="razorpay",
        result={
            "order_id": order.id,
            "razorpay_order_id": razorpay_order["id"],
            "amount": razorpay_order["amount"],
            "currency": razorpay_order["currency"]
        }
    )

    return {
        "order_id": order.id,
        "razorpay_order_id": razorpay_order["id"],
        "amount": razorpay_order["amount"],
        "currency": razorpay_order["currency"],
        "key_id": os.getenv("RAZORPAY_KEY_ID")
    }