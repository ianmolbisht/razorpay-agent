from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductResponse
from app.services.semantic_search import search_products as semantic_search

router = APIRouter(
    prefix="/products",
    tags=["Products"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/")
def get_products(db: Session = Depends(get_db)):
    return db.query(Product).all()



@router.post("/", response_model=ProductResponse)
def create_product(
    product_data: ProductCreate,
    db: Session = Depends(get_db)
):
    product = Product(**product_data.model_dump())

    db.add(product)
    db.commit()
    db.refresh(product)

    return product



@router.get("/search")
def search_products(
    query: str,
    max_price: float | None = None,
    category_id: int | None = None,
    db: Session = Depends(get_db)
):
    products_query = (
        db.query(Product)
        .filter(
            Product.name.ilike(f"%{query}%"),
            Product.is_active == True
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

    return products_query.all()

@router.get("/semantic-search")
def semantic_product_search(
    query: str,
    limit: int = 5
):
    return semantic_search(query, limit)