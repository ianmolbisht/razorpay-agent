# Razorpay AI Merchant Agent

> An AI-native commerce system where external AI buyers can discover,
> understand, and transact with a merchant through an AI-readable commerce API.

## 🚀 Overview

Razorpay AI Merchant Agent enables an external AI shopping agent to interact
with a merchant programmatically.

Instead of an AI being tightly coupled to a specific store implementation,
the merchant exposes a machine-readable commerce manifest describing:

- Available commerce capabilities
- Product and inventory access
- Cart operations
- Checkout behavior
- Payment policies
- AI safety constraints

The external AI buyer discovers this contract first and then interacts with
the merchant through the exposed commerce APIs.

The customer remains in control of payment.

---

## 💡 Key Innovation

### AI-readable merchant + external AI buyer

Traditional AI commerce:

```text
Customer
   ↓
AI Assistant
   ↓
Hardcoded Store Integration
   ↓
Merchant

Our architecture:

Customer
   ↓
External AI Buyer
   ↓
Discover Merchant Manifest
   ↓
Validate Capabilities & Safety Policies
   ↓
Merchant Commerce API
   ↓
Human Approval
   ↓
Razorpay Payment

The buyer does not blindly assume what the merchant supports.

It first discovers the merchant's capabilities and transaction boundaries.

🧠 How It Works
1. Merchant Discovery

The merchant exposes:

GET /api/commerce/manifest

Example information exposed:

{
  "merchant": {
    "name": "Razorpay AI Merchant Agent",
    "currency": "INR"
  },
  "capabilities": [...],
  "payment_policy": {...},
  "security_boundary": {...}
}

This allows an external AI buyer to understand the merchant before
performing commerce actions.

2. Merchant Contract Validation

The AI buyer validates the merchant manifest before transacting.

It verifies that:

Automatic payment is disabled
Customer approval is required
Payment signature verification is required
Required safety protections are present

If the merchant exposes an unsafe contract, the AI buyer refuses to proceed.

3. Capability Enforcement

Every commerce action is checked against the merchant manifest.

For example:

search_products
      ↓
catalog_search
      ↓
safe_for_ai = true
      ↓
ALLOW

If the merchant disables an operation:

add_to_cart
      ↓
safe_for_ai = false
      ↓
BLOCK

This creates an explicit AI-to-merchant permission boundary.

🛒 Commerce Capabilities

The merchant currently exposes:

Capability	Purpose
catalog_search	Search merchant products
product_details	Retrieve product information
availability_check	Check live inventory
get_cart	Retrieve active cart
add_to_cart	Add available products
request_checkout	Prepare checkout
🔐 Payment Safety

The AI buyer cannot automatically charge the customer.

The transaction flow is:

AI discovers product
        ↓
AI checks availability
        ↓
AI manages cart
        ↓
AI requests checkout
        ↓
Customer explicitly approves
        ↓
Razorpay payment
        ↓
Backend verifies Razorpay signature
        ↓
Order marked as PAID

Payment is only considered successful after backend verification.

📦 Inventory Safety

The AI buyer checks live stock before purchasing.

Example:

Customer requests: 100 Running Shoes

Available stock: 20

AI:
❌ Does not add 100 items
❌ Does not claim the purchase succeeded
✅ Explains the stock limitation

The merchant API also enforces stock constraints independently.

This provides defense in depth.

🧾 Audit Trail

Commerce actions are audit logged.

Examples:

AI_CHECKOUT_REQUESTED
PAYMENT_APPROVED
PAYMENT_INITIATED
PAYMENT_VERIFIED
PAYMENT_REJECTED
PAYMENT_VERIFICATION_FAILED

The audit trail records important transaction context such as:

Session/customer
Action
Tool
Arguments
Result
Approval state
Timestamp

This provides visibility into AI-driven commerce actions.

🏗️ Architecture
                         ┌─────────────────────┐
                         │      CUSTOMER       │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │    Next.js UI       │
                         │  Chat + Cart        │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   External AI Buyer │
                         │    Groq / GPT-OSS   │
                         └──────────┬──────────┘
                                    │
                           Discover Manifest
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │     Commerce Manifest        │
                    │                              │
                    │ Capabilities                 │
                    │ Payment Policy               │
                    │ Safety Constraints           │
                    └──────────────┬───────────────┘
                                   │
                         Validate + Authorize
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │     FastAPI Commerce API     │
                    │                              │
                    │ Catalog │ Stock │ Cart      │
                    │ Checkout │ Orders │ Payments │
                    └──────────────┬───────────────┘
                                   │
                         Customer Approval
                                   │
                                   ▼
                         ┌─────────────────┐
                         │    Razorpay     │
                         │   Test Mode     │
                         └────────┬────────┘
                                  │
                         Signature Verify
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
             PostgreSQL                    Audit Trail
             Orders/Payments              Every Action
🧰 Tech Stack
Frontend
Next.js
React
TypeScript
Tailwind CSS
Backend
FastAPI
Python
SQLAlchemy
PostgreSQL
AI
Groq API
GPT-OSS 120B
Tool/function calling
Payments
Razorpay Test Mode
Razorpay signature verification
Infrastructure
REST APIs
PostgreSQL
Git/GitHub
🔌 Important API Endpoints
Merchant Discovery
GET /api/commerce/manifest
Catalog
GET /api/commerce/catalog/search
GET /api/commerce/products/{product_id}
GET /api/commerce/products/{product_id}/availability
Cart
GET /api/commerce/cart/{customer_id}
POST /api/commerce/cart/{customer_id}/items
Checkout
POST /api/commerce/checkout/{customer_id}
Payments
POST /api/orders/{order_id}/razorpay
POST /api/payments/{order_id}/verify
Audit
GET /api/audit
🧪 Tested Scenarios
Normal purchase
Discover merchant
      ↓
Search product
      ↓
Check availability
      ↓
Add to cart
      ↓
Prepare checkout
      ↓
Customer approval
      ↓
Razorpay
      ↓
Payment verified
Insufficient stock
Requested: 100
Available: 20

→ AI refuses to exceed inventory
Merchant capability disabled
add_to_cart
safe_for_ai = false

→ AI buyer blocks the operation
Successful payment

Verified end-to-end:

Frontend payment success
        ↓
Razorpay signature verification
        ↓
Order status = paid
        ↓
Payment status = paid
        ↓
Cart status = checked_out
        ↓
Audit trail updated
▶️ Local Setup
Backend
cd backend

python -m venv venv

# Windows
venv\Scripts\activate

pip install -r requirements.txt

Create:

backend/.env

with your local credentials:

DATABASE_URL=...
RAZORPAY_KEY_ID=...
RAZORPAY_KEY_SECRET=...
GROQ_API_KEY=...

Run:

uvicorn app.main:app --reload

Backend:

http://localhost:8000
Frontend
cd frontend

npm install

npm run dev

Frontend:

http://localhost:3000
🔑 Environment Variables

Never commit secrets.

Required variables include:

DATABASE_URL
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
GROQ_API_KEY

.env and virtual environments should remain excluded from Git.

🎬 Demo Flow

A recommended demonstration:

1. Ask the AI
Find me 2 running shoes and prepare checkout.
2. AI discovers the merchant
GET /api/commerce/manifest
3. AI searches the catalog
search_products
4. AI checks inventory
check_availability
5. AI prepares checkout
request_checkout
6. Human approval

The UI explicitly displays:

🔐 Customer approval required
💳 No automatic payment
7. Payment

Customer clicks:

Approve & Pay
8. Verification

Backend verifies the Razorpay payment signature.

9. Audit

The transaction appears in the Agent Audit Trail.

🛡️ Safety Principles

The system follows four important principles:

Explicit authorization

AI cannot automatically charge the customer.

Capability boundaries

AI can only execute capabilities exposed and permitted by the merchant.

Defense in depth

Both the AI buyer and merchant backend enforce commerce constraints.

Verifiable transactions

Payment success is determined by backend signature verification,
not by an AI response or frontend state alone.

🚀 Future Scope

Potential extensions include:

Multi-merchant AI shopping
Merchant discovery across multiple stores
Standardized AI-commerce manifests
Dynamic capability negotiation
Personalized recommendations
Multi-agent purchasing
Order tracking agents
Refund/return agents
Merchant-side AI analytics
Production payment integration