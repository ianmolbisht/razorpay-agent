from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.customer import Customer


router = APIRouter(
    prefix="/customers",
    tags=["Customers"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/")
def create_customer(
    name: str,
    email: str,
    db: Session = Depends(get_db)
):
    customer = Customer(
        name=name,
        email=email
    )

    db.add(customer)
    db.commit()
    db.refresh(customer)

    return customer