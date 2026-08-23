from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

from app.core.config import (
    APP_NAME,
    APP_VERSION
)

from app.api.routes.products import (
    router as products_router
)

from app.api.routes.audit import router as audit_router

from app.api.routes.cart import (
    router as cart_router
)

from app.api.routes.customer import (
    router as customer_router
)

from app.api.routes.order import (
    router as order_router
)

from app.api.routes.payment import (
    router as payment_router
)

from app.api.routes.agent import (
    router as agent_router
)

from app.api.routes.commerce import (
    router as commerce_router
)


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION
)


app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://localhost:3000"
    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)


# =========================================================
# API ROUTES
# =========================================================
app.include_router(
    audit_router,
    prefix="/api"
)

app.include_router(
    products_router,
    prefix="/api"
)

app.include_router(
    cart_router,
    prefix="/api"
)

app.include_router(
    order_router,
    prefix="/api"
)

app.include_router(
    customer_router,
    prefix="/api"
)

app.include_router(
    payment_router,
    prefix="/api"
)

app.include_router(
    agent_router,
    prefix="/api"
)

# AI-readable merchant commerce API
app.include_router(
    commerce_router,
    prefix="/api"
)


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():
    return {
        "message":
            "Razorpay AI Merchant Agent API is running"
    }


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }