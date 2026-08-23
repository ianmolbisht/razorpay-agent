import json

from app.services.gemini import client, MODEL_NAME

from app.services.agent_tools import (
    search_product_catalog,
    get_product,
    get_cart,
    add_to_cart,
)

from app.services.audit import log_action

from app.db.database import SessionLocal
from app.models.cart import Cart


SYSTEM_PROMPT = """
You are an AI Merchant Sales & Checkout Agent.

You help customers discover products and manage their shopping cart.

IMPORTANT RULES:

1. NEVER invent products, prices, stock, product IDs, or product details.

2. When the customer asks to FIND, SEARCH, RECOMMEND, or COMPARE
   products, use search_product_catalog.

3. When the customer explicitly asks to ADD a product to their cart,
   use add_to_cart.

4. If the customer refers to a product by name and you do not know
   its product ID, first use search_product_catalog.

5. If a product ID is already available from a previous tool result,
   use that product ID directly with add_to_cart.

6. NEVER claim that an item was added unless add_to_cart actually
   returned success=true.

7. The backend automatically determines the customer's active cart.
   NEVER ask the customer for a cart ID.

8. If there is no active cart, clearly tell the customer that there
   is no active cart.

9. Respect backend constraints such as stock, product availability,
   cart status, and quantity limits.

10. If a tool returns an error, explain that error to the customer.
    Do not pretend the operation succeeded.

11. Payment ALWAYS requires explicit user approval.

12. NEVER initiate, claim, or imply that a payment happened unless
    the customer explicitly approved the payment.

13. Be concise and helpful.

14. When a tool result contains real product information, use that
    information in your response instead of inventing additional
    details.

15. NEVER use Markdown tables when presenting products.

16. Do not repeat complete product catalog data in your final response.
    The frontend separately displays product cards.

17. When products are returned by search_product_catalog, give a
    concise natural-language summary of the relevant products.

18. Do not output product IDs unless the customer specifically asks
    for them.

19. Never use Markdown tables for product listings.
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
                        "description": (
                            "What the customer is looking for"
                        ),
                    },
                    "max_price": {
                        "type": "number",
                        "description": (
                            "Maximum price in INR"
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": (
                            "Maximum number of products to return"
                        ),
                    },
                },
                "required": ["query"],
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
                "add a product. The backend automatically determines "
                "the active cart."
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
]


# =============================================================
# ACTIVE CART
# =============================================================

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

        if not cart:
            return None

        return cart.id

    finally:
        db.close()


# =============================================================
# TOOL EXECUTION
# =============================================================

def execute_tool(tool_name: str, args: dict):
    """
    Execute one commerce tool and return its result.
    """

    # ---------------------------------------------------------
    # Automatically resolve active cart
    # ---------------------------------------------------------

    if tool_name in ["get_cart", "add_to_cart"]:

        cart_id = get_active_cart_id(customer_id=1)

        if cart_id is None:
            return {
                "success": False,
                "error": "No active cart exists for this customer.",
            }

        args["cart_id"] = cart_id

    # ---------------------------------------------------------
    # Search products
    # ---------------------------------------------------------

    if tool_name == "search_product_catalog":

        return search_product_catalog(
            query=args["query"],
            max_price=args.get("max_price"),
            limit=args.get("limit", 5),
        )

    # ---------------------------------------------------------
    # Get product
    # ---------------------------------------------------------

    if tool_name == "get_product":

        return get_product(
            args["product_id"]
        )

    # ---------------------------------------------------------
    # Get cart
    # ---------------------------------------------------------

    if tool_name == "get_cart":

        return get_cart(
            args["cart_id"]
        )

    # ---------------------------------------------------------
    # Add to cart
    # ---------------------------------------------------------

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


# =============================================================
# AGENT
# =============================================================

def run_agent(message: str):

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": message,
        },
    ]

    # Maximum number of tool iterations.
    # This prevents an infinite agent loop.
    MAX_ITERATIONS = 5

    for _ in range(MAX_ITERATIONS):

        # -----------------------------------------------------
        # Ask Groq
        # -----------------------------------------------------

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        assistant_message = response.choices[0].message

        # -----------------------------------------------------
        # No more tools → final answer
        # -----------------------------------------------------

        if not assistant_message.tool_calls:

            return {
                "type": "message",
                "response": assistant_message.content or "",
                "tool": None,
                "tool_result": None,
            }

        # -----------------------------------------------------
        # Add assistant's tool-call message to conversation
        # -----------------------------------------------------

        messages.append(assistant_message)

        last_tool_name = None
        last_tool_result = None

        # -----------------------------------------------------
        # Execute every tool requested by Groq
        # -----------------------------------------------------

        for tool_call in assistant_message.tool_calls:

            tool_name = tool_call.function.name
            last_tool_name = tool_name

            # Parse JSON arguments safely
            try:
                args = json.loads(
                    tool_call.function.arguments or "{}"
                )
            except json.JSONDecodeError:

                result = {
                    "success": False,
                    "error": "The AI generated invalid tool arguments.",
                }

                log_action(
                    session_id="customer_1",
                    action="TOOL_RESULT",
                    tool_name=tool_name,
                    arguments={},
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

            # -------------------------------------------------
            # Resolve cart internally
            # -------------------------------------------------

            if tool_name in ["get_cart", "add_to_cart"]:

                cart_id = get_active_cart_id(
                    customer_id=1
                )

                if cart_id is None:

                    result = {
                        "success": False,
                        "error": (
                            "No active cart exists for this customer."
                        ),
                    }

                    log_action(
                        session_id="customer_1",
                        action="TOOL_CALL",
                        tool_name=tool_name,
                        arguments=args,
                    )

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

            # -------------------------------------------------
            # Audit tool call
            # -------------------------------------------------

            log_action(
                session_id="customer_1",
                action="TOOL_CALL",
                tool_name=tool_name,
                arguments=args,
            )

            # -------------------------------------------------
            # Execute tool
            # -------------------------------------------------

            try:

                result = execute_tool(
                    tool_name,
                    args,
                )

            except Exception as exc:

                result = {
                    "success": False,
                    "error": (
                        "Tool execution failed."
                    ),
                }

            # -------------------------------------------------
            # Audit tool result
            # -------------------------------------------------

            log_action(
                session_id="customer_1",
                action="TOOL_RESULT",
                tool_name=tool_name,
                arguments=args,
                result=result,
            )

            last_tool_result = result

            # -------------------------------------------------
            # Send tool result back to Groq
            # -------------------------------------------------

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

        # -----------------------------------------------------
        # Loop continues:
        #
        # Groq receives the tool result and can:
        #
        # 1. Give a final response
        # 2. Call another tool
        #
        # This is what allows:
        #
        # search → get_product → add_to_cart → final response
        # -----------------------------------------------------

    # =========================================================
    # SAFETY FALLBACK
    # =========================================================

    return {
        "type": "message",
        "response": (
            "I couldn't complete that request safely. "
            "Please try again."
        ),
        "tool": last_tool_name,
        "tool_result": last_tool_result,
    }