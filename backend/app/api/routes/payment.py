import os

import razorpay

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.order import Order
from app.models.payment import Payment
from app.models.cart import Cart
from app.services.audit import log_action


router = APIRouter(
    prefix="/payments",
    tags=["Payments"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


razorpay_client = razorpay.Client(
    auth=(
        os.getenv("RAZORPAY_KEY_ID"),
        os.getenv("RAZORPAY_KEY_SECRET")
    )
)


class PaymentVerification(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post("/{order_id}/verify")
def verify_payment(
    order_id: int,
    payment_data: PaymentVerification,
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

    if order.razorpay_order_id != payment_data.razorpay_order_id:
        raise HTTPException(
            status_code=400,
            detail="Invalid Razorpay order"
        )

    if order.status == "paid":
        raise HTTPException(
            status_code=400,
            detail="Order already paid"
        )

    # Verify Razorpay signature
    try:
        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": payment_data.razorpay_order_id,
            "razorpay_payment_id": payment_data.razorpay_payment_id,
            "razorpay_signature": payment_data.razorpay_signature
        })
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Payment verification failed"
        )

    # Find existing payment record
    payment = db.query(Payment).filter(
        Payment.order_id == order.id
    ).first()

    if not payment:
        payment = Payment(
            order_id=order.id,
            amount=order.total_amount,
            status="paid",
            razorpay_payment_id=payment_data.razorpay_payment_id
        )
        db.add(payment)
    else:
        payment.razorpay_payment_id = (
            payment_data.razorpay_payment_id
        )
        payment.status = "paid"

    # Mark order as paid
    order.status = "paid"

    # Only after successful verification
    # mark the cart as checked out
    cart = db.query(Cart).filter(
        Cart.customer_id == order.customer_id,
        Cart.status == "active"
    ).first()

    if cart:
        cart.status = "checked_out"

    db.commit()

    # Audit: payment verified
    log_action(
        session_id=f"customer_{order.customer_id}",
        action="PAYMENT_VERIFIED",
        tool_name="razorpay",
        result={
            "order_id": order.id,
            "payment_id": payment_data.razorpay_payment_id,
            "status": "paid"
        }
    )

    return {
        "success": True,
        "order_id": order.id,
        "payment_id": payment_data.razorpay_payment_id,
        "status": "paid"
    }


@router.post("/{order_id}")
def create_payment(
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

    payment = Payment(
        order_id=order.id,
        amount=order.total_amount,
        status="pending"
    )

    db.add(payment)
    db.commit()
    db.refresh(payment)

    return payment