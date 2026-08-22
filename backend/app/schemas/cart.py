from pydantic import BaseModel


class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = 1


class CartItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int

    model_config = {"from_attributes": True}


class CartResponse(BaseModel):
    id: int
    customer_id: int
    status: str
    items: list[CartItemResponse] = []

    model_config = {"from_attributes": True}

    