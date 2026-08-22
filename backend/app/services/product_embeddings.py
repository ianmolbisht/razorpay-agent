from app.db.database import SessionLocal
from app.models.product import Product
from app.services.embedding import generate_embedding


def generate_product_embeddings():
    db = SessionLocal()

    try:
        products = db.query(Product).all()

        for product in products:
            text = f"{product.name}. {product.description or ''}"
            product.embedding = generate_embedding(text)

        db.commit()

        print(f"Generated embeddings for {len(products)} products")

    finally:
        db.close()


if __name__ == "__main__":
    generate_product_embeddings()