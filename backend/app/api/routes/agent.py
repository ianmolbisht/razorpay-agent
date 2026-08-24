from fastapi import APIRouter
from pydantic import BaseModel

from app.services.agent import run_agent
from fastapi import APIRouter
from pydantic import BaseModel
from app.services.agent import run_agent

router = APIRouter(
    prefix="/agent",
    tags=["Agent"]
)

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


@router.post("/chat")
def chat(request: ChatRequest):

    result = run_agent(
        request.message,
        request.history
    )

    if isinstance(result, str):
        return {
            "type": "message",
            "response": result,
            "products": [],
        }

    products = []

    if result.get("tool") in [
        "search_product_catalog",
        "list_products",
    ]:
        products = result.get("tool_result", [])

    return {
        "type": result.get("type", "message"),
        "response": result.get("response", ""),
        "products": products,
        "tool": result.get("tool"),
        "tool_result": result.get("tool_result"),
    }