import os
import json

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


client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


SYSTEM_PROMPT = """
You are an external AI shopping buyer.

You are purchasing on behalf of a customer
from a merchant's AI-readable commerce API.

Rules:

1. Never invent products, prices, or stock.
2. When the customer asks to buy a product,
   search the merchant catalog first.
3. Use the merchant tools to resolve product details
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
                        "type": ["number","null"]
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
                "properties": {},
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
                "properties": {},
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

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
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