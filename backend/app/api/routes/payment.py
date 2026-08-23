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


class PaymentFailure(BaseModel):
    razorpay_order_id: str | None = None
    error_code: str | None = None
    error_description: str | None = None
    error_reason: str | None = None


# =========================================================
# VERIFY PAYMENT
# =========================================================

@router.post("/{order_id}/verify")
def verify_payment(
    order_id: int,
    payment_data: PaymentVerification,
    db: Session = Depends(get_db)
):
    order = (
        db.query(Order)
        .filter(
            Order.id == order_id
        )
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    if (
        order.razorpay_order_id
        != payment_data.razorpay_order_id
    ):
        log_action(
            session_id=f"customer_{order.customer_id}",
            action="PAYMENT_REJECTED",
            tool_name="razorpay",
            arguments={
                "order_id": order.id,
                "razorpay_order_id":
                    payment_data.razorpay_order_id
            },
            result={
                "reason":
                    "Invalid Razorpay order"
            },
            approval_required=True,
            approved=True
        )

        raise HTTPException(
            status_code=400,
            detail="Invalid Razorpay order"
        )

    if order.status == "paid":
        raise HTTPException(
            status_code=400,
            detail="Order already paid"
        )

    # -----------------------------------------------------
    # Verify Razorpay signature
    # -----------------------------------------------------

    try:
        razorpay_client.utility.verify_payment_signature(
            {
                "razorpay_order_id":
                    payment_data.razorpay_order_id,

                "razorpay_payment_id":
                    payment_data.razorpay_payment_id,

                "razorpay_signature":
                    payment_data.razorpay_signature
            }
        )

    except Exception:
        # -------------------------------------------------
        # Failed verification is also audited.
        # -------------------------------------------------

        log_action(
            session_id=f"customer_{order.customer_id}",
            action="PAYMENT_VERIFICATION_FAILED",
            tool_name="razorpay",
            arguments={
                "order_id": order.id,
                "razorpay_order_id":
                    payment_data.razorpay_order_id,
                "razorpay_payment_id":
                    payment_data.razorpay_payment_id
            },
            result={
                "status": "verification_failed",
                "order_status":
                    order.status
            },
            approval_required=True,
            approved=True
        )

        raise HTTPException(
            status_code=400,
            detail="Payment verification failed"
        )

    # -----------------------------------------------------
    # Find existing payment
    # -----------------------------------------------------

    payment = (
        db.query(Payment)
        .filter(
            Payment.order_id == order.id
        )
        .first()
    )

    if not payment:
        payment = Payment(
            order_id=order.id,
            amount=order.total_amount,
            status="paid",
            razorpay_payment_id=(
                payment_data.razorpay_payment_id
            )
        )

        db.add(payment)

    else:
        payment.razorpay_payment_id = (
            payment_data.razorpay_payment_id
        )

        payment.status = "paid"

    # -----------------------------------------------------
    # Mark order paid
    # -----------------------------------------------------

    order.status = "paid"

    # -----------------------------------------------------
    # Only after successful verification:
    # mark cart checked out
    # -----------------------------------------------------

    cart = (
        db.query(Cart)
        .filter(
            Cart.customer_id
            == order.customer_id,

            Cart.status == "active"
        )
        .first()
    )

    if cart:
        cart.status = "checked_out"

    db.commit()

    # -----------------------------------------------------
    # Audit: payment verified
    # -----------------------------------------------------

    log_action(
        session_id=f"customer_{order.customer_id}",
        action="PAYMENT_VERIFIED",
        tool_name="razorpay",
        arguments={
            "order_id": order.id,
            "razorpay_order_id":
                payment_data.razorpay_order_id,
            "razorpay_payment_id":
                payment_data.razorpay_payment_id
        },
        result={
            "order_id": order.id,
            "payment_id":
                payment_data.razorpay_payment_id,
            "status": "paid"
        },
        approval_required=True,
        approved=True
    )

    return {
        "success": True,
        "order_id": order.id,
        "payment_id":
            payment_data.razorpay_payment_id,
        "status": "paid"
    }


# =========================================================
# PAYMENT FAILED / CANCELLED
# =========================================================

@router.post("/{order_id}/failed")
def payment_failed(
    order_id: int,
    failure_data: PaymentFailure,
    db: Session = Depends(get_db)
):
    order = (
        db.query(Order)
        .filter(
            Order.id == order_id
        )
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    # -----------------------------------------------------
    # Never change a paid order back to failed.
    # -----------------------------------------------------

    if order.status == "paid":
        raise HTTPException(
            status_code=400,
            detail="Order is already paid"
        )

    # -----------------------------------------------------
    # Keep order pending.
    #
    # A failed/cancelled Razorpay attempt must NOT:
    # - mark the order paid
    # - check out the cart
    # - reduce stock
    # -----------------------------------------------------

    order.status = "pending"

    db.commit()

    # -----------------------------------------------------
    # Audit the failure
    # -----------------------------------------------------

    log_action(
        session_id=f"customer_{order.customer_id}",
        action="PAYMENT_FAILED",
        tool_name="razorpay",
        arguments={
            "order_id": order.id,
            "razorpay_order_id":
                failure_data.razorpay_order_id,
            "error_code":
                failure_data.error_code,
            "error_reason":
                failure_data.error_reason
        },
        result={
            "status": "payment_failed",
            "order_status": order.status,
            "error_description":
                failure_data.error_description
        },
        approval_required=True,
        approved=True
    )

    return {
        "success": True,
        "order_id": order.id,
        "status": "payment_failed",
        "order_status": order.status,
        "message": (
            "Payment failed. "
            "The order remains pending and "
            "the cart has not been checked out."
        )
    }


# =========================================================
# CREATE PAYMENT RECORD
# =========================================================

@router.post("/{order_id}")
def create_payment(
    order_id: int,
    db: Session = Depends(get_db)
):
    order = (
        db.query(Order)
        .filter(
            Order.id == order_id
        )
        .first()
    )

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

    log_action(
        session_id=f"customer_{order.customer_id}",
        action="PAYMENT_RECORD_CREATED",
        tool_name="payment",
        arguments={
            "order_id": order.id
        },
        result={
            "payment_id": payment.id,
            "amount": float(
                payment.amount
            ),
            "status": payment.status
        }
    )

    return payment