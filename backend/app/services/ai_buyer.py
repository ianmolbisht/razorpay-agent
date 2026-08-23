import requests


BASE_URL = "http://127.0.0.1:8000/api/commerce"

CUSTOMER_ID = 1


def search_products(query, max_price=None):
    params = {
        "query": query
    }

    if max_price is not None:
        params["max_price"] = max_price

    response = requests.get(
        f"{BASE_URL}/catalog/search",
        params=params
    )

    response.raise_for_status()

    return response.json()


def get_product(product_id):
    response = requests.get(
        f"{BASE_URL}/products/{product_id}"
    )

    response.raise_for_status()

    return response.json()


def check_availability(product_id):
    response = requests.get(
        f"{BASE_URL}/products/{product_id}/availability"
    )

    response.raise_for_status()

    return response.json()


def add_to_cart(product_id, quantity=1):
    response = requests.post(
        f"{BASE_URL}/cart/{CUSTOMER_ID}/items",
        json={
            "product_id": product_id,
            "quantity": quantity
        }
    )

    response.raise_for_status()

    return response.json()


def get_cart():
    response = requests.get(
        f"{BASE_URL}/cart/{CUSTOMER_ID}"
    )

    response.raise_for_status()

    return response.json()


def request_checkout():
    response = requests.post(
        f"{BASE_URL}/checkout/{CUSTOMER_ID}"
    )

    response.raise_for_status()

    return response.json()