from google.genai import types

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

IMPORTANT:

- Never invent products, prices, stock, or product details.

- When the customer asks to FIND, SEARCH, RECOMMEND, or COMPARE
  products, use search_product_catalog.

- When the customer explicitly asks to ADD a product to their cart,
  use add_to_cart.

- If the customer refers to a product by name, first use
  search_product_catalog if you do not already know its product ID.

- If the product is already known and its product ID is available,
  use that product ID directly with add_to_cart.

- Never claim an item was added unless add_to_cart actually succeeds.

- The backend automatically determines the customer's active cart.
  Never ask the customer for a cart ID.

- Payment always requires explicit user approval.

- Never initiate or claim that a payment happened without explicit
  user approval.
"""


commerce_tools = types.Tool(
    function_declarations=[

        # ---------------------------------------------------------
        # SEARCH PRODUCTS
        # ---------------------------------------------------------

        types.FunctionDeclaration(
            name="search_product_catalog",
            description=(
                "Search the merchant's real product catalog using "
                "semantic search. Use this whenever the customer asks "
                "to find, recommend, or compare products."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "query": types.Schema(
                        type="STRING",
                        description="What the customer is looking for"
                    ),
                    "max_price": types.Schema(
                        type="NUMBER",
                        description="Maximum price in INR"
                    ),
                    "limit": types.Schema(
                        type="INTEGER",
                        description="Maximum number of products"
                    ),
                },
                required=["query"],
            ),
        ),

        # ---------------------------------------------------------
        # GET PRODUCT
        # ---------------------------------------------------------

        types.FunctionDeclaration(
            name="get_product",
            description=(
                "Get exact details of a product from the merchant catalog."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "product_id": types.Schema(
                        type="INTEGER",
                        description="The product ID"
                    ),
                },
                required=["product_id"],
            ),
        ),

        # ---------------------------------------------------------
        # GET CART
        # ---------------------------------------------------------

        types.FunctionDeclaration(
            name="get_cart",
            description=(
                "Get the customer's current active shopping cart. "
                "The backend automatically determines the active cart. "
                "Never ask the customer for a cart ID."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={},
            ),
        ),

        # ---------------------------------------------------------
        # ADD TO CART
        # ---------------------------------------------------------

        types.FunctionDeclaration(
            name="add_to_cart",
            description=(
                "Add a product to the customer's active shopping cart. "
                "Use this only when the customer explicitly asks to "
                "add a product. The backend automatically determines "
                "the active cart. Never ask the customer for a cart ID."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "product_id": types.Schema(
                        type="INTEGER",
                        description="The product ID"
                    ),
                    "quantity": types.Schema(
                        type="INTEGER",
                        description="Quantity to add"
                    ),
                },
                required=["product_id"],
            ),
        ),
    ]
)


# =============================================================
# ACTIVE CART
# =============================================================

def get_active_cart_id(customer_id: int = 1):
    db = SessionLocal()

    try:
        cart = db.query(Cart).filter(
            Cart.customer_id == customer_id,
            Cart.status == "active"
        ).first()

        if not cart:
            return None

        return cart.id

    finally:
        db.close()


# =============================================================
# AGENT
# =============================================================

def run_agent(message: str):

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part(text=message)
            ]
        )
    ]

    # =========================================================
    # FIRST GEMINI CALL
    # =========================================================

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[commerce_tools],
        ),
    )

    # Gemini answered directly
    if not response.function_calls:
        return response.text

    function_call = response.function_calls[0]

    args = dict(function_call.args)

    # =========================================================
    # AUTOMATIC ACTIVE CART RESOLUTION
    # =========================================================

    if function_call.name in ["get_cart", "add_to_cart"]:

        cart_id = get_active_cart_id(customer_id=1)

        if cart_id is None:
            return {
                "type": "message",
                "response": "You don't have an active cart right now.",
                "tool": function_call.name,
                "tool_result": None,
            }

        # Gemini does NOT need to know the cart ID.
        # Backend adds it here.
        args["cart_id"] = cart_id

    # =========================================================
    # AUDIT TOOL CALL
    # =========================================================

    log_action(
        session_id="customer_1",
        action="TOOL_CALL",
        tool_name=function_call.name,
        arguments=args,
    )

    # =========================================================
    # EXECUTE FIRST TOOL
    # =========================================================

    if function_call.name == "search_product_catalog":

        result = search_product_catalog(
            query=args["query"],
            max_price=args.get("max_price"),
            limit=args.get("limit", 5),
        )

    elif function_call.name == "get_product":

        result = get_product(
            args["product_id"]
        )

    elif function_call.name == "get_cart":

        result = get_cart(
            args["cart_id"]
        )

    elif function_call.name == "add_to_cart":

        result = add_to_cart(
            cart_id=args["cart_id"],
            product_id=args["product_id"],
            quantity=args.get("quantity", 1),
        )

    else:

        return {
            "type": "message",
            "response": "I couldn't perform that action.",
        }

    # =========================================================
    # AUDIT FIRST TOOL RESULT
    # =========================================================

    log_action(
        session_id="customer_1",
        action="TOOL_RESULT",
        tool_name=function_call.name,
        arguments=args,
        result=result,
    )

    # =========================================================
    # SEND FIRST TOOL RESULT BACK TO GEMINI
    # =========================================================

    contents.append(
        response.candidates[0].content
    )

    contents.append(
        types.Content(
            role="tool",
            parts=[
                types.Part.from_function_response(
                    name=function_call.name,
                    response={
                        "result": result
                    }
                )
            ]
        )
    )

    # =========================================================
    # SECOND GEMINI CALL
    # =========================================================

    final_response = client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[commerce_tools],
        ),
    )

    # =========================================================
    # HANDLE SECOND TOOL CALL
    # =========================================================

    if final_response.function_calls:

        second_call = final_response.function_calls[0]

        second_args = dict(second_call.args)

        # -----------------------------------------------------
        # Automatically resolve active cart again
        # -----------------------------------------------------

        if second_call.name in ["get_cart", "add_to_cart"]:

            cart_id = get_active_cart_id(customer_id=1)

            if cart_id is None:
                return {
                    "type": "message",
                    "response": (
                        "You don't have an active cart right now."
                    ),
                    "tool": second_call.name,
                    "tool_result": None,
                }

            second_args["cart_id"] = cart_id

        # -----------------------------------------------------
        # Audit second tool call
        # -----------------------------------------------------

        log_action(
            session_id="customer_1",
            action="TOOL_CALL",
            tool_name=second_call.name,
            arguments=second_args,
        )

        # -----------------------------------------------------
        # Execute second tool
        # -----------------------------------------------------

        if second_call.name == "search_product_catalog":

            second_result = search_product_catalog(
                query=second_args["query"],
                max_price=second_args.get("max_price"),
                limit=second_args.get("limit", 5),
            )

        elif second_call.name == "get_product":

            second_result = get_product(
                second_args["product_id"]
            )

        elif second_call.name == "get_cart":

            second_result = get_cart(
                second_args["cart_id"]
            )

        elif second_call.name == "add_to_cart":

            second_result = add_to_cart(
                cart_id=second_args["cart_id"],
                product_id=second_args["product_id"],
                quantity=second_args.get("quantity", 1),
            )

        else:

            return {
                "type": "message",
                "response": "I couldn't perform that action.",
            }

        # -----------------------------------------------------
        # Audit second tool result
        # -----------------------------------------------------

        log_action(
            session_id="customer_1",
            action="TOOL_RESULT",
            tool_name=second_call.name,
            arguments=second_args,
            result=second_result,
        )

        # -----------------------------------------------------
        # Return result
        # -----------------------------------------------------

        if second_call.name == "add_to_cart":

            if (
                isinstance(second_result, dict)
                and second_result.get("success")
            ):
                response_text = (
                    "✅ Added the product to your cart."
                )
            else:
                response_text = (
                    "I couldn't add the product to your cart."
                )

        else:

            response_text = final_response.text

        return {
            "type": "message",
            "response": response_text,
            "tool": second_call.name,
            "tool_result": second_result,
        }

    # =========================================================
    # NORMAL FINAL RESPONSE
    # =========================================================

    return {
        "type": "message",
        "response": final_response.text,
        "tool": function_call.name,
        "tool_result": result,
    }