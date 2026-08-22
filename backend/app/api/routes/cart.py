from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.product import Product
from app.schemas.cart import CartItemCreate, CartResponse


router = APIRouter(
    prefix="/cart",
    tags=["Cart"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/{customer_id}", response_model=CartResponse)
def create_cart(
    customer_id: int,
    db: Session = Depends(get_db)
):
    cart = Cart(customer_id=customer_id)

    db.add(cart)
    db.commit()
    db.refresh(cart)

    return cart


@router.post("/{cart_id}/items")
def add_to_cart(
    cart_id: int,
    item: CartItemCreate,
    db: Session = Depends(get_db)
):
    cart = db.query(Cart).filter(Cart.id == cart_id).first()

    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    product = db.query(Product).filter(
        Product.id == item.product_id,
        Product.is_active == True
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if item.quantity > product.stock:
        raise HTTPException(status_code=400, detail="Not enough stock")

    cart_item = CartItem(
        cart_id=cart_id,
        product_id=item.product_id,
        quantity=item.quantity
    )

    db.add(cart_item)
    db.commit()
    db.refresh(cart_item)

    return cart_item


@router.get("/{cart_id}")
def get_cart(
    cart_id: int,
    db: Session = Depends(get_db)
):
    cart = db.query(Cart).filter(Cart.id == cart_id).first()

    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    items = db.query(CartItem).filter(
        CartItem.cart_id == cart_id
    ).all()

    return {
        "id": cart.id,
        "customer_id": cart.customer_id,
        "status": cart.status,
        "items": items
    }