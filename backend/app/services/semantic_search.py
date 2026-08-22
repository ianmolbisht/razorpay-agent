from sqlalchemy import text

from app.db.database import SessionLocal
from app.services.embedding import generate_embedding


def search_products(query: str,limit: int = 5,min_similarity: float = 0.45):
    db = SessionLocal()

    try:
        embedding = generate_embedding(query)

        sql = text("""
            SELECT
                id,
                name,
                description,
                price,
                stock,
                1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM products
            WHERE is_active = true
            AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
        """)

        result = db.execute(
            sql,
            {
                "embedding": str(embedding),
                "limit": limit
            }
        )

        results = []

        for row in result:
            product = dict(row._mapping)
            product["price"] = float(product["price"])
            product["similarity"] = float(product["similarity"])
            results.append(product)
        return [
            product
            for product in results
            if product["similarity"] >= min_similarity
        ]

    finally:
        db.close()


if __name__ == "__main__":
    results = search_products("comfortable shoes for running")

    for product in results:
        print(product)