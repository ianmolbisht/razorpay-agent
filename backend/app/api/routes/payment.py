from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.order import Order
from app.models.payment import Payment


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


@router.post("/{order_id}")
def create_payment(
    order_id: int,
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id).first()

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