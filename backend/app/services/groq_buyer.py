import os
import json
import requests

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

from app.services.ai_buyer import (
    search_products,
    get_product,
    check_availability,
    add_to_cart,
    get_cart,
    request_checkout,
)

BASE_URL = "http://127.0.0.1:8000/api/commerce"

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


def discover_merchant():
    """
    Discover the merchant's machine-readable
    commerce contract before interacting with it.
    """

    response = requests.get(
        f"{BASE_URL}/manifest"
    )

    response.raise_for_status()

    return response.json()


def validate_merchant_manifest(manifest):
    """
    Validate the merchant contract before allowing
    the external AI buyer to interact with it.
    """

    required_fields = [
        "manifest_version",
        "merchant",
        "buyer_interface",
        "capabilities",
        "payment_policy",
        "commerce_constraints",
        "security_boundary",
        "transaction_flow",
    ]

    for field in required_fields:
        if field not in manifest:
            raise RuntimeError(
                f"Invalid merchant manifest: missing {field}"
            )

    payment_policy = manifest["payment_policy"]

    if payment_policy.get(
        "automatic_payment"
    ) is not False:
        raise RuntimeError(
            "Unsafe merchant: automatic payment is enabled."
        )

    if payment_policy.get(
        "explicit_customer_approval_required"
    ) is not True:
        raise RuntimeError(
            "Unsafe merchant: customer approval is not required."
        )

    if payment_policy.get(
        "signature_verification_required"
    ) is not True:
        raise RuntimeError(
            "Unsafe merchant: payment signature verification is not required."
        )

    security_boundary = manifest[
        "security_boundary"
    ]

    forbidden_actions = {
        "automatically_charge_customer",
        "bypass_customer_approval",
        "mark_payment_as_successful",
        "bypass_payment_signature_verification",
    }

    declared_forbidden = set(
        security_boundary.get(
            "ai_cannot",
            []
        )
    )

    missing_protections = (
        forbidden_actions - declared_forbidden
    )

    if missing_protections:
        raise RuntimeError(
            "Unsafe merchant manifest. "
            f"Missing protections: {sorted(missing_protections)}"
        )

    return True




def is_tool_allowed(manifest, tool_name):
    """
    Check whether the merchant explicitly exposes
    the corresponding operation to external AI buyers.
    """

    tool_to_capability = {
        "search_products": "catalog_search",
        "get_product": "product_details",
        "check_availability": "availability_check",
        "get_cart": "get_cart",
        "add_to_cart": "add_to_cart",
        "request_checkout": "request_checkout",
    }

    capability_name = tool_to_capability.get(
        tool_name
    )

    if capability_name is None:
        return False

    capabilities = manifest.get(
        "capabilities",
        []
    )

    for capability in capabilities:
        if capability.get("name") == capability_name:
            return capability.get(
                "safe_for_ai",
                False
            ) is True

    return False





SYSTEM_PROMPT = """
You are an external AI shopping buyer.

You are purchasing on behalf of a customer
from a merchant's AI-readable commerce API.

The merchant provides a machine-readable manifest.
Use that manifest to understand the merchant's
capabilities, payment policy, and safety boundaries.

Rules:

1. Never invent products, prices, or stock.

2. When the customer asks to buy a product,
   search the merchant catalog first.

3. Use merchant tools to resolve product details
   instead of asking unnecessary clarification questions.

4. Check availability before adding a product.

5. If the requested quantity exceeds available stock,
   DO NOT add the product to the cart.

6. Clearly explain the stock limitation to the customer.

7. You may add products to the cart when stock is sufficient.

8. You may request checkout.

9. You MUST NOT claim payment happened.

10. Payment requires explicit customer approval.

11. Never bypass the merchant's approval requirement.

12. Never invent alternative products unless the customer
    asks for alternatives.

13. Treat the merchant manifest as the source of truth
    for its commerce capabilities and safety constraints.
"""


tools = [

    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search the merchant catalog.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string"
                    },
                    "max_price": {
                        "type": ["number", "null"]
                    }
                },
                "required": ["query"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "get_product",
            "description": "Get exact product details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer"
                    }
                },
                "required": ["product_id"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check live product stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer"
                    }
                },
                "required": ["product_id"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "add_to_cart",
            "description": "Add a product to the customer's cart.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer"
                    },
                    "quantity": {
                        "type": "integer"
                    }
                },
                "required": ["product_id"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "get_cart",
            "description": "View the customer's active cart.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "request_checkout",
            "description": (
                "Prepare checkout. "
                "This does NOT make a payment."
            ),
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]


def execute_tool(name, arguments):

    if name == "search_products":
        return search_products(
            query=arguments["query"],
            max_price=arguments.get("max_price")
        )

    if name == "get_product":
        return get_product(
            arguments["product_id"]
        )

    if name == "check_availability":
        return check_availability(
            arguments["product_id"]
        )

    if name == "add_to_cart":
        return add_to_cart(
            product_id=arguments["product_id"],
            quantity=arguments.get("quantity", 1)
        )

    if name == "get_cart":
        return get_cart()

    if name == "request_checkout":
        return request_checkout()

    return {
        "error": "Unknown tool"
    }


def run_buyer(message: str):

    # -----------------------------------------------------
    # Discover merchant before interacting
    # -----------------------------------------------------

    merchant_manifest = discover_merchant()

    validate_merchant_manifest(
        merchant_manifest
    )

    print("\n==============================")
    print("MERCHANT MANIFEST DISCOVERED")
    print("==============================")
    print(json.dumps(
        merchant_manifest,
        indent=2
    ))

    messages = [

        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },

        {
            "role": "system",
            "content": (
                "MERCHANT MANIFEST:\n"
                + json.dumps(
                    merchant_manifest,
                    indent=2
                )
            )
        },

        {
            "role": "user",
            "content": message
        }
    ]

    while True:

        response = client.chat.completions.create(

            model="openai/gpt-oss-120b",

            messages=messages,

            tools=tools,

            tool_choice="auto",

            temperature=0
        )

        assistant_message = response.choices[0].message

        # -------------------------------------------------
        # No more tool calls
        # -------------------------------------------------

        if not assistant_message.tool_calls:

            return assistant_message.content

        # -------------------------------------------------
        # Add assistant tool-call message
        # -------------------------------------------------

        messages.append(
            assistant_message
        )

        # -------------------------------------------------
        # Execute every requested tool
        # -------------------------------------------------

        for tool_call in assistant_message.tool_calls:

            function_name = (
                tool_call.function.name
            )

            arguments = json.loads(
                tool_call.function.arguments
            )

            print(
                f"\n[AI BUYER TOOL] "
                f"{function_name}"
            )

            print(
                f"[ARGUMENTS] "
                f"{arguments}"
            )

            if not is_tool_allowed(
                merchant_manifest,
                function_name
            ):
                result = {
                    "success": False,
                    "error": (
                        f"Merchant does not allow "
                        f"AI action: {function_name}"
                    )
                }

                print(
                    f"[AI BUYER BLOCKED] "
                    f"{function_name}"
                )

            else:
                result = execute_tool(
                    function_name,
                    arguments
                )

            print(
                f"[RESULT] "
                f"{result}"
            )

            messages.append(
                {
                    "role": "tool",

                    "tool_call_id":
                        tool_call.id,

                    "content":
                        json.dumps(
                            result,
                            default=str
                        )
                }
            )