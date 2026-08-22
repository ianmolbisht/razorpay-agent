from pydantic import BaseModel, ConfigDict


class ProductCreate(BaseModel):
    name: str
    description: str | None = None
    price: float
    stock: int
    category_id: int
    image_url: str | None = None


class ProductResponse(ProductCreate):
    id: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)