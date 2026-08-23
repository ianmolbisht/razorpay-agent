from app.services.ai_buyer import (
    search_products,
    get_product,
    check_availability,
    add_to_cart,
    get_cart,
    request_checkout,
)


print("\n=== AI BUYER ===")

# 1. Search
print("\n1. Searching for running shoes under ₹5000...")

search_result = search_products(
    "running shoes",
    max_price=5000
)

print(search_result)


# 2. Select first product
products = search_result.get("products", [])

if not products:
    print("No products found.")
    exit()

product = products[0]

product_id = product["id"]

print(
    f"\n2. AI selected: "
    f"{product['name']} "
    f"(₹{product['price']})"
)


# 3. Check availability
print("\n3. Checking availability...")

availability = check_availability(
    product_id
)

print(availability)


if not availability["availability"]["in_stock"]:
    print("Product is out of stock.")
    exit()


# 4. Add to cart
print("\n4. Adding product to cart...")

cart_result = add_to_cart(
    product_id,
    quantity=1
)

print(cart_result)


# 5. Read cart
print("\n5. Reading cart...")

cart = get_cart()

print(cart)


# 6. Request checkout
print("\n6. Requesting checkout...")

checkout = request_checkout()

print(checkout)


print("\n=== AI BUYER FINISHED ===")