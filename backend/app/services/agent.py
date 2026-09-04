import json

from app.services.gemini import client, MODEL_NAME

from app.models.product import Product
from app.models.order import Order
from app.models.cart import Cart

from app.services.agent_tools import (
    search_product_catalog,
    get_product,
    get_cart,
    add_to_cart,
)

from app.services.ai_buyer import (
    request_checkout,
    create_order_from_cart,
    approve_order,
)

from app.services.audit import log_action

from app.db.database import SessionLocal

#pormpts to agent

SYSTEM_PROMPT = """
You are an AI Merchant Sales & Checkout Agent.

You help customers discover products, manage their shopping cart,
prepare checkout, and explicitly approve pending orders.

IMPORTANT RULES:

1. NEVER invent products, prices, stock, product IDs, or product details.

2. When the customer asks to FIND, SEARCH, RECOMMEND, or COMPARE
   products, use search_product_catalog.

3. When the customer asks what products are available or asks to
   browse the store, use list_products.

4. When the customer explicitly asks to ADD a product to their cart,
   use add_to_cart.

5. If the customer refers to a product by name and you do not know
   its product ID, first use search_product_catalog.

6. If a product ID is already available from a previous tool result,
   use that product ID directly with add_to_cart.

7. NEVER claim that an item was added unless add_to_cart actually
   returned success=true.

8. The backend automatically determines the customer's active cart.
   NEVER ask the customer for a cart ID.

9. Respect backend constraints such as stock, product availability,
   cart status, and quantity limits.

10. If a tool returns an error, explain that error to the customer.
    Do not pretend the operation succeeded.

11. Payment ALWAYS requires explicit customer approval.

12. NEVER initiate or claim that payment happened unless the customer
    explicitly approved the payment.

13. When the customer says things such as:
    "yes", "confirm", "confirmed", "yes go ahead", "proceed",
    "approve", or "I approve"
    immediately after being asked to approve a pending checkout,
    treat that as explicit payment approval.

14. When explicit approval is received for a pending checkout,
    use approve_order.

15. approve_order automatically finds the customer's most recent
    pending order. NEVER ask the customer for an order ID.

16. After approve_order succeeds, DO NOT call get_cart or
    request_checkout again. The frontend will use the returned
    order_id to start Razorpay Checkout.

17. After approve_order succeeds, respond briefly that the payment
    approval was recorded and that checkout/payment can now proceed.

18. Do not claim that the Razorpay payment itself succeeded.
    approve_order only records customer approval.

19. Be concise and helpful.

20. When a tool result contains real product information, use that
    information instead of inventing details.

21. NEVER use Markdown tables.

22. Do not repeat complete product catalog data in your final response.
    The frontend separately displays product cards.

23. Do not output product IDs unless the customer specifically asks
    for them.

24. Never claim an order was placed merely because approve_order
    succeeded. It only means customer approval was recorded.
"""


# =============================================================
# GROQ TOOL DEFINITIONS
# =============================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_product_catalog",
            "description": (
                "Search the merchant's real product catalog using "
                "semantic search. Use this whenever the customer asks "
                "to find, recommend, or compare products."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What the customer is looking for",
                    },
                    "max_price": {
                        "type": ["number", "null"],
                        "description": "Maximum price in INR. Omit or use null when no maximum price is specified.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of products to return",
                    },
                },
                "required": ["query"],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "list_products",
            "description": (
                "List all active products currently available "
                "in the merchant catalog. Use this when the customer "
                "asks what products are available, what they can buy, "
                "wants to browse the store, or asks to see all products."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "get_product",
            "description": (
                "Get exact details of a product from the merchant catalog."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "The product ID",
                    },
                },
                "required": ["product_id"],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "get_cart",
            "description": (
                "Get the customer's current active shopping cart. "
                "The backend automatically determines the active cart. "
                "Never ask the customer for a cart ID."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "add_to_cart",
            "description": (
                "Add a product to the customer's active shopping cart. "
                "Use this ONLY when the customer explicitly asks to "
                "add a product."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "The product ID",
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Quantity to add",
                    },
                },
                "required": ["product_id"],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "request_checkout",
            "description": (
                "Prepare checkout for the customer's current cart. "
                "This does NOT make a payment. "
                "Use this when the customer asks to proceed with checkout."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "approve_order",
            "description": (
                "Approve the customer's most recent pending order after "
                "the customer explicitly confirms payment. "
                "The backend automatically finds the pending order. "
                "Do not provide an order ID."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


def get_active_cart_id(customer_id: int = 1):
    db = SessionLocal()

    try:
        cart = (
            db.query(Cart)
            .filter(
                Cart.customer_id == customer_id,
                Cart.status == "active",
            )
            .first()
        )

        if cart:
            return cart.id

        cart = Cart(
            customer_id=customer_id,
            status="active",
        )

        db.add(cart)
        db.commit()
        db.refresh(cart)

        return cart.id

    finally:
        db.close()



def execute_tool(tool_name: str, args: dict):
   
    if tool_name == "approve_order":

        db = SessionLocal()

        try:
            order = (
                db.query(Order)
                .filter(
                    Order.customer_id == 1,
                    Order.status == "pending",
                )
                .order_by(Order.id.desc())
                .first()
            )

            if not order:
                return {
                    "success": False,
                    "error": "No pending order found.",
                }

            result = approve_order(order.id)

            return {
                **result,
                "order_id": order.id,
            }

        finally:
            db.close()

    if tool_name == "request_checkout":
        checkout = request_checkout()
        order = create_order_from_cart(checkout["cart_id"])

        return {
            **checkout,
            "order_id": order["id"],
        }

    if tool_name in ["get_cart", "add_to_cart"]:

        cart_id = get_active_cart_id(customer_id=1)

        if cart_id is None:
            return {
                "success": False,
                "error": "No active cart exists for this customer.",
            }

        args["cart_id"] = cart_id


    if tool_name == "search_product_catalog":

        return search_product_catalog(
            query=args["query"],
            max_price=args.get("max_price"),
            limit=args.get("limit", 5),
        )


    if tool_name == "list_products":

        db = SessionLocal()

        try:
            products = (
                db.query(Product)
                .filter(Product.is_active == True)
                .all()
            )

            return [
                {
                    "id": product.id,
                    "name": product.name,
                    "description": product.description,
                    "price": float(product.price),
                    "stock": product.stock,
                }
                for product in products
            ]

        finally:
            db.close()


    if tool_name == "get_product":

        return get_product(
            args["product_id"]
        )

    if tool_name == "get_cart":

        return get_cart(
            args["cart_id"]
        )

    if tool_name == "add_to_cart":

        return add_to_cart(
            cart_id=args["cart_id"],
            product_id=args["product_id"],
            quantity=args.get("quantity", 1),
        )

    return {
        "success": False,
        "error": f"Unknown tool: {tool_name}",
    }

def run_agent(
    message: str,
    history: list[dict] | None = None,
):
    if message.lower().strip() in [
        "what all can i buy",
        "what can i buy",
        "what products are available",
        "show all products",
        "show me all products",
        "find all products",
        "list all products",
        "list me all items",
        "show me all items",
    ]:

        result = execute_tool(
            "list_products",
            {},
        )

        return {
            "type": "message",
            "response": json.dumps(
                result,
                default=str,
            ),
            "tool": "list_products",
            "tool_result": result,
        }

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    if history:

        for item in history:

            if item.get("role") in ["user", "assistant"]:

                content = item.get("content", "")

                if content:
                    messages.append(
                        {
                            "role": item["role"],
                            "content": content,
                        }
                    )

    messages.append(
        {
            "role": "user",
            "content": message,
        }
    )

    MAX_ITERATIONS = 5

    last_tool_name = None
    last_tool_result = None

    for _ in range(MAX_ITERATIONS):

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        assistant_message = response.choices[0].message

        if not assistant_message.tool_calls:

            return {
                "type": "message",
                "response": assistant_message.content or "",
                "tool": last_tool_name,
                "tool_result": last_tool_result,
            }

        messages.append(assistant_message)

       
        for tool_call in assistant_message.tool_calls:

            tool_name = tool_call.function.name

            last_tool_name = tool_name


            try:

                args = json.loads(
                    tool_call.function.arguments or "{}"
                )

            except json.JSONDecodeError:

                result = {
                    "success": False,
                    "error": (
                        "The AI generated invalid tool arguments."
                    ),
                }

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": json.dumps(result),
                    }
                )

                last_tool_result = result

                continue


            if tool_name in [
                "get_cart",
                "add_to_cart",
            ]:

                cart_id = get_active_cart_id(
                    customer_id=1
                )

                if cart_id is None:

                    result = {
                        "success": False,
                        "error": (
                            "No active cart exists "
                            "for this customer."
                        ),
                    }

                    log_action(
                        session_id="customer_1",
                        action="TOOL_RESULT",
                        tool_name=tool_name,
                        arguments=args,
                        result=result,
                    )

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_name,
                            "content": json.dumps(result),
                        }
                    )

                    last_tool_result = result

                    continue

                args["cart_id"] = cart_id

            log_action(
                session_id="customer_1",
                action="TOOL_CALL",
                tool_name=tool_name,
                arguments=args,
            )
            try:

                result = execute_tool(
                    tool_name,
                    args,
                )

            except Exception as exc:

                print(
                    f"Tool '{tool_name}' failed: {exc}"
                )

                result = {
                    "success": False,
                    "error": (
                        f"Tool '{tool_name}' failed."
                    ),
                }

            log_action(
                session_id="customer_1",
                action="TOOL_RESULT",
                tool_name=tool_name,
                arguments=args,
                result=result,
            )

            last_tool_result = result

            if (
                tool_name == "approve_order"
                and isinstance(result, dict)
                and result.get("success") is True
                and result.get("approved") is True
                and result.get("order_id") is not None
            ):

                return {
                    "type": "message",
                    "response": (
                        "Your payment approval has been recorded. "
                        "Opening Razorpay Checkout now."
                    ),
                    "tool": "approve_order",
                    "tool_result": result,
                    "order_id": result["order_id"],
                    "payment_approved": True,
                }

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": json.dumps(
                        result,
                        default=str,
                    ),
                }
            )

    return {
        "type": "message",
        "response": (
            "I couldn't complete that request safely. "
            "Please try again."
        ),
        "tool": last_tool_name,
        "tool_result": last_tool_result,
    }
