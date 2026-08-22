from app.services.semantic_search import search_products

from app.db.database import SessionLocal
from app.models.product import Product
from app.models.cart import Cart
from app.models.cart_item import CartItem

def search_product_catalog(
    query: str,
    max_price: float | None = None,
    limit: int = 5
):
    results = search_products(query, limit)

    if max_price is not None:
        results = [
            product
            for product in results
            if float(product["price"]) <= max_price
        ]

    return results


SEARCH_PRODUCTS_TOOL = {
    "name": "search_product_catalog",
    "description": (
        "Search the merchant's real product catalog using semantic search. "
        "Use this whenever the customer asks to find, recommend, or compare products."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What the customer is looking for"
            },
            "max_price": {
                "type": "number",
                "description": "Maximum price in INR"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of products to return"
            }
        },
        "required": ["query"]
    }
}


def get_product(product_id: int):
    db = SessionLocal()

    try:
        product = (
            db.query(Product)
            .filter(
                Product.id == product_id,
                Product.is_active == True
            )
            .first()
        )

        if not product:
            return None

        return {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "price": float(product.price),
            "stock": product.stock,
            "category_id": product.category_id,
        }

    finally:
        db.close()

GET_PRODUCT_TOOL = {
    "name": "get_product",
    "description": "Get exact details of a product from the merchant catalog.",
    "parameters": {
        "type": "object",
        "properties": {
            "product_id": {
                "type": "integer",
                "description": "The product ID"
            }
        },
        "required": ["product_id"]
    }
}
def get_cart(cart_id: int):
    db = SessionLocal()

    try:
        cart = db.query(Cart).filter(Cart.id == cart_id).first()

        if not cart:
            return None

        items = (
            db.query(CartItem)
            .filter(CartItem.cart_id == cart_id)
            .all()
        )

        return {
            "id": cart.id,
            "customer_id": cart.customer_id,
            "status": cart.status,
            "items": [
                {
                    "id": item.id,
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                }
                for item in items
            ],
        }

    finally:
        db.close()


def add_to_cart(cart_id: int, product_id: int, quantity: int = 1):
    db = SessionLocal()

    try:
        cart = db.query(Cart).filter(Cart.id == cart_id).first()

        if not cart:
            return {"error": "Cart not found"}
        if cart.status != "active":
            return {"error": "Cart is not active"}
        product = (
            db.query(Product)
            .filter(
                Product.id == product_id,
                Product.is_active == True
            )
            .first()
        )

        if not product:
            return {"error": "Product not found"}

        if quantity <= 0:
            return {"error": "Quantity must be positive"}

        if quantity > product.stock:
            return {"error": "Not enough stock"}

        item = (
            db.query(CartItem)
            .filter(
                CartItem.cart_id == cart_id,
                CartItem.product_id == product_id
            )
            .first()
        )

        if item:
            if item.quantity + quantity > product.stock:
                return {"error": "Not enough stock"}

            item.quantity += quantity
        else:
            item = CartItem(
                cart_id=cart_id,
                product_id=product_id,
                quantity=quantity
            )
            db.add(item)

        db.commit()
        db.refresh(item)

        return {
            "success": True,
            "cart_item_id": item.id,
            "cart_id": cart_id,
            "product_id": product_id,
            "quantity": item.quantity,
        }

    finally:
        db.close()

GET_CART_TOOL = {
    "name": "get_cart",
    "description": "Get the customer's current cart and its items.",
    "parameters": {
        "type": "object",
        "properties": {
            "cart_id": {
                "type": "integer",
                "description": "The cart ID"
            }
        },
        "required": ["cart_id"]
    }
}


ADD_TO_CART_TOOL = {
    "name": "add_to_cart",
    "description": "Add a product to the customer's cart.",
    "parameters": {
        "type": "object",
        "properties": {
            "cart_id": {
                "type": "integer",
                "description": "The cart ID"
            },
            "product_id": {
                "type": "integer",
                "description": "The product ID"
            },
            "quantity": {
                "type": "integer",
                "description": "Quantity to add"
            }
        },
        "required": ["cart_id", "product_id"]
    }
}