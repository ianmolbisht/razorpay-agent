"use client";

import { useEffect, useState } from "react";

declare global {
  interface Window {
    Razorpay: any;
  }
}

type Product = {
  id: number;
  name: string;
  description: string;
  price: number;
  stock: number;
};

type CartItem = {
  id: number;
  product_id: number;
  name: string;
  price?: number;
  quantity: number;
  subtotal?: number;
};

type AICheckout = {
  checkout_status: string;
  cart_id: number;
  total: number;
  currency: string;
  items: Array<{
    product_id: number;
    name: string;
    quantity: number;
    unit_price: number;
    subtotal: number;
    currency: string;
  }>;
};

type Message = {
  role: "user" | "assistant";
  content: string;
  products?: Product[];
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Hey! 👋 I'm your AI shopping assistant. What are you looking for?",
    },
  ]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const [cartId, setCartId] = useState<number | null>(null);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [cartTotal, setCartTotal] = useState(0);

  const [aiCheckout, setAICheckout] =
    useState<AICheckout | null>(null);

  // =========================================================
  // SAFE NUMBER HELPER
  // =========================================================

  function safeNumber(
    value: any,
    fallback = 0
  ): number {
    const number = Number(value);

    return Number.isFinite(number)
      ? number
      : fallback;
  }

  // =========================================================
  // NORMALIZE CART ITEM
  // =========================================================

  function normalizeCartItem(
    item: any
  ): CartItem {
    const quantity = safeNumber(
      item?.quantity,
      1
    );

    const price = safeNumber(
      item?.price ??
        item?.unit_price ??
        item?.product_price ??
        item?.product?.price,
      0
    );

    const subtotal = safeNumber(
      item?.subtotal ??
        item?.total ??
        item?.item_total,
      price * quantity
    );

    return {
      id: safeNumber(item?.id),
      product_id: safeNumber(
        item?.product_id ??
          item?.product?.id
      ),
      name:
        item?.name ??
        item?.product_name ??
        item?.product?.name ??
        "Unknown Product",
      price,
      quantity,
      subtotal,
    };
  }

  // =========================================================
  // LOAD ACTIVE CART
  // =========================================================

  async function loadCart() {
    try {
      const response = await fetch(
        "http://127.0.0.1:8000/api/cart/customer/1/active"
      );

      if (!response.ok) {
        setCartId(null);
        setCart([]);
        setCartTotal(0);
        return;
      }

      const data = await response.json();

      const rawItems = Array.isArray(
        data?.items
      )
        ? data.items
        : [];

      const normalizedItems =
        rawItems.map(
          normalizeCartItem
        );

      setCartId(
        data?.id
          ? safeNumber(data.id)
          : null
      );

      setCart(normalizedItems);

      const total =
        normalizedItems.reduce(
          (
            sum: number,
            item: CartItem
          ) => {
            const price = safeNumber(
              item.price
            );

            const quantity =
              safeNumber(
                item.quantity,
                1
              );

            const subtotal =
              safeNumber(
                item.subtotal,
                price * quantity
              );

            return sum + subtotal;
          },
          0
        );

      setCartTotal(
        safeNumber(total)
      );
    } catch (error) {
      console.error(
        "Could not load active cart:",
        error
      );

      setCartId(null);
      setCart([]);
      setCartTotal(0);
    }
  }

  // =========================================================
  // INITIAL LOAD
  // =========================================================

  useEffect(() => {
    loadCart();
  }, []);

  // =========================================================
  // LOAD RAZORPAY
  // =========================================================

  useEffect(() => {
    const script =
      document.createElement(
        "script"
      );

    script.src =
      "https://checkout.razorpay.com/v1/checkout.js";

    script.async = true;

    document.body.appendChild(
      script
    );

    return () => {
      document.body.removeChild(
        script
      );
    };
  }, []);

  // =========================================================
  // ADD TO CART
  // =========================================================

  async function addToCart(
    productId: number
  ) {
    if (!cartId) {
      alert(
        "No active cart found"
      );
      return;
    }

    try {
      const response =
        await fetch(
          `http://127.0.0.1:8000/api/cart/${cartId}/items`,
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/json",
            },
            body: JSON.stringify({
              product_id:
                productId,
              quantity: 1,
            }),
          }
        );

      const data =
        await response.json();

      if (!response.ok) {
        alert(
          data.detail ||
            data.error ||
            "Could not add to cart"
        );
        return;
      }

      await loadCart();
    } catch (error) {
      console.error(error);

      alert(
        "Could not connect to cart"
      );
    }
  }

  // =========================================================
  // UPDATE CART ITEM
  // =========================================================

  async function updateCartItem(
    itemId: number,
    quantity: number
  ) {
    if (!cartId) {
      alert(
        "No active cart found"
      );
      return;
    }

    try {
      const response =
        await fetch(
          `http://127.0.0.1:8000/api/cart/${cartId}/items/${itemId}?quantity=${quantity}`,
          {
            method: "PATCH",
          }
        );

      const data =
        await response.json();

      if (!response.ok) {
        alert(
          data.detail ||
            data.error ||
            "Could not update cart"
        );
        return;
      }

      await loadCart();
    } catch (error) {
      console.error(error);

      alert(
        "Could not connect to cart"
      );
    }
  }

  // =========================================================
  // NORMAL CHECKOUT
  // =========================================================

  async function checkout(
    approvalAlreadyGiven = false
  ) {
    if (!cartId) {
      alert(
        "No active cart found"
      );
      return;
    }

    if (cart.length === 0) {
      alert(
        "Your cart is empty"
      );
      return;
    }

    if (
      !Number.isFinite(
        cartTotal
      ) ||
      cartTotal <= 0
    ) {
      alert(
        "Cart total is unavailable. Please refresh your cart."
      );
      return;
    }

    // Explicit approval before money action
    if (!approvalAlreadyGiven) {
      const approved =
        window.confirm(
          `Your total is ₹${cartTotal.toFixed(
            2
          )}.\n\nDo you approve proceeding to payment?`
        );

      if (!approved) {
        alert(
          "Payment cancelled. No payment was initiated."
        );
        return;
      }
    }

    try {
      // -----------------------------------------------------
      // 1. Create local order
      // -----------------------------------------------------

      const orderResponse =
        await fetch(
          `http://127.0.0.1:8000/api/orders/from-cart/${cartId}`,
          {
            method: "POST",
          }
        );

      const order =
        await orderResponse.json();

      if (!orderResponse.ok) {
        alert(
          order.detail ||
            "Could not create order"
        );
        return;
      }

      // -----------------------------------------------------
      // 2. Record explicit customer approval
      // -----------------------------------------------------

      const approvalResponse =
        await fetch(
          `http://127.0.0.1:8000/api/orders/${order.id}/approve`,
          {
            method: "POST",
          }
        );

      const approvalResult =
        await approvalResponse.json();

      if (!approvalResponse.ok) {
        alert(
          approvalResult.detail ||
            "Could not record payment approval"
        );
        return;
      }

      // -----------------------------------------------------
      // 3. Create Razorpay order
      // -----------------------------------------------------

      const razorpayResponse =
        await fetch(
          `http://127.0.0.1:8000/api/orders/${order.id}/razorpay`,
          {
            method: "POST",
          }
        );

      const razorpayOrder =
        await razorpayResponse.json();

      if (!razorpayResponse.ok) {
        alert(
          razorpayOrder.detail ||
            "Could not create Razorpay order"
        );
        return;
      }

      // -----------------------------------------------------
      // 4. Make sure Razorpay loaded
      // -----------------------------------------------------

      if (!window.Razorpay) {
        alert(
          "Razorpay Checkout is still loading. Please try again."
        );
        return;
      }

      // -----------------------------------------------------
      // 5. Razorpay Checkout
      // -----------------------------------------------------

      const options = {
        key:
          razorpayOrder.key_id,

        amount:
          razorpayOrder.amount,

        currency:
          razorpayOrder.currency,

        name:
          "Razorpay AI Merchant Agent",

        description:
          "AI-powered shopping checkout",

        order_id:
          razorpayOrder.razorpay_order_id,

        handler:
          async function (
            response: any
          ) {
            try {
              const verificationResponse =
                await fetch(
                  `http://127.0.0.1:8000/api/payments/${order.id}/verify`,
                  {
                    method: "POST",
                    headers: {
                      "Content-Type":
                        "application/json",
                    },
                    body: JSON.stringify({
                      razorpay_order_id:
                        response.razorpay_order_id,

                      razorpay_payment_id:
                        response.razorpay_payment_id,

                      razorpay_signature:
                        response.razorpay_signature,
                    }),
                  }
                );

              const result =
                await verificationResponse.json();

              if (
                !verificationResponse.ok
              ) {
                alert(
                  result.detail ||
                    "Payment verification failed"
                );
                return;
              }

              alert(
                "✅ Payment successful!"
              );

              await loadCart();
            } catch (error) {
              console.error(
                "Payment verification error:",
                error
              );

              alert(
                "Payment verification failed."
              );
            }
          },

        theme: {
          color: "#000000",
        },
      };

      const razorpay =
        new window.Razorpay(
          options
        );

      razorpay.on(
        "payment.failed",
        async function (
          response: any
        ) {
          console.error(
            "Payment failed:",
            response?.error
          );

          try {
            await fetch(
              `http://127.0.0.1:8000/api/payments/${order.id}/failed`,
              {
                method: "POST",
                headers: {
                  "Content-Type":
                    "application/json",
                },
                body: JSON.stringify({
                  razorpay_order_id:
                    response?.error
                      ?.metadata
                      ?.order_id ??
                    razorpayOrder.razorpay_order_id,

                  error_code:
                    response?.error
                      ?.code ?? null,

                  error_description:
                    response?.error
                      ?.description ?? null,

                  error_reason:
                    response?.error
                      ?.reason ?? null,
                }),
              }
            );
          } catch (error) {
            console.error(
              "Could not record payment failure:",
              error
            );
          }

          alert(
            "❌ Payment failed. Please try again."
          );
        }
      );

      razorpay.open();
    } catch (error) {
      console.error(error);

      alert(
        "Could not start checkout"
      );
    }
  }

  // =========================================================
  // AI BUYER CHECKOUT REQUEST
  // =========================================================

  async function requestAICheckout() {
    if (
      !cartId ||
      cart.length === 0
    ) {
      alert(
        "Your cart is empty."
      );
      return;
    }

    try {
      const response =
        await fetch(
          `http://127.0.0.1:8000/api/commerce/checkout/1`,
          {
            method: "POST",
          }
        );

      const data =
        await response.json();

      if (!response.ok) {
        alert(
          data.detail ||
            "Could not prepare AI checkout"
        );
        return;
      }

      setAICheckout(data);
    } catch (error) {
      console.error(
        "AI checkout request failed:",
        error
      );

      alert(
        "Could not connect to the AI commerce service."
      );
    }
  }

  async function approveAICheckout() {
    if (!aiCheckout) {
      return;
    }

    setAICheckout(null);

    await checkout(true);
  }

  function rejectAICheckout() {
    setAICheckout(null);

    alert(
      "AI buyer checkout rejected. No payment was initiated."
    );
  }

  // =========================================================
  // SEND MESSAGE
  // =========================================================

  async function sendMessage() {
    if (
      !input.trim() ||
      loading
    ) {
      return;
    }

    const userMessage =
      input.trim();

    setInput("");

    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        content:
          userMessage,
      },
    ]);

    setLoading(true);

    try {
      const response =
        await fetch(
          "http://127.0.0.1:8000/api/agent/chat",
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/json",
            },
            body: JSON.stringify({
              message:
                userMessage,

              history:
                messages,
            }),
          }
        );

      if (!response.ok) {
        throw new Error(
          "Agent request failed"
        );
      }

      const data =
        await response.json();

      console.log(
        "AI RESPONSE:",
        data
      );

      // =====================================================
      // AI APPROVED PAYMENT
      //
      // IMPORTANT:
      // The AI has approved the order, but the frontend must
      // still create the Razorpay order and OPEN the payment
      // interface.
      // =====================================================

      if (
        data.tool ===
          "approve_order" &&
        data.tool_result
          ?.success === true &&
        data.tool_result
          ?.order_id
      ) {
        const orderId =
          Number(
            data.tool_result
              .order_id
          );

        try {
          // -------------------------------------------------
          // 1. Create Razorpay order
          // -------------------------------------------------

          const razorpayResponse =
            await fetch(
              `http://127.0.0.1:8000/api/orders/${orderId}/razorpay`,
              {
                method: "POST",
              }
            );

          const razorpayOrder =
            await razorpayResponse.json();

          if (
            !razorpayResponse.ok
          ) {
            throw new Error(
              razorpayOrder.detail ||
                "Could not create Razorpay order"
            );
          }

          // -------------------------------------------------
          // 2. Check Razorpay SDK
          // -------------------------------------------------

          if (
            !window.Razorpay
          ) {
            throw new Error(
              "Razorpay Checkout is still loading. Please refresh and try again."
            );
          }

          // -------------------------------------------------
          // 3. Razorpay options
          // -------------------------------------------------

          const options = {
            key:
              razorpayOrder.key_id,

            amount:
              razorpayOrder.amount,

            currency:
              razorpayOrder.currency,

            name:
              "Razorpay AI Merchant Agent",

            description:
              "AI-powered shopping checkout",

            order_id:
              razorpayOrder
                .razorpay_order_id,

            handler:
              async function (
                paymentResponse: any
              ) {
                try {
                  // -----------------------------------------
                  // 4. Verify payment
                  // -----------------------------------------

                  const verificationResponse =
                    await fetch(
                      `http://127.0.0.1:8000/api/payments/${orderId}/verify`,
                      {
                        method: "POST",
                        headers: {
                          "Content-Type":
                            "application/json",
                        },
                        body: JSON.stringify({
                          razorpay_order_id:
                            paymentResponse.razorpay_order_id,

                          razorpay_payment_id:
                            paymentResponse.razorpay_payment_id,

                          razorpay_signature:
                            paymentResponse.razorpay_signature,
                        }),
                      }
                    );

                  const result =
                    await verificationResponse.json();

                  if (
                    !verificationResponse.ok
                  ) {
                    alert(
                      result.detail ||
                        "Payment verification failed"
                    );
                    return;
                  }

                  alert(
                    "✅ Payment successful!"
                  );

                  await loadCart();
                } catch (error) {
                  console.error(
                    "Payment verification error:",
                    error
                  );

                  alert(
                    "Payment verification failed."
                  );
                }
              },

            theme: {
              color: "#000000",
            },
          };

          // -------------------------------------------------
          // 5. Create Razorpay instance
          // -------------------------------------------------

          const razorpay =
            new window.Razorpay(
              options
            );

          // -------------------------------------------------
          // 6. Payment failure
          // -------------------------------------------------

          razorpay.on(
            "payment.failed",
            async function (
              paymentFailure: any
            ) {
              console.error(
                "Payment failed:",
                paymentFailure?.error
              );

              try {
                await fetch(
                  `http://127.0.0.1:8000/api/payments/${orderId}/failed`,
                  {
                    method: "POST",
                    headers: {
                      "Content-Type":
                        "application/json",
                    },
                    body: JSON.stringify({
                      razorpay_order_id:
                        paymentFailure
                          ?.error
                          ?.metadata
                          ?.order_id ??
                        razorpayOrder.razorpay_order_id,

                      error_code:
                        paymentFailure
                          ?.error
                          ?.code ??
                        null,

                      error_description:
                        paymentFailure
                          ?.error
                          ?.description ??
                        null,

                      error_reason:
                        paymentFailure
                          ?.error
                          ?.reason ??
                        null,
                    }),
                  }
                );
              } catch (error) {
                console.error(
                  "Could not record payment failure:",
                  error
                );
              }

              alert(
                "❌ Payment failed. Please try again."
              );
            }
          );

          // -------------------------------------------------
          // 7. OPEN RAZORPAY
          // -------------------------------------------------

          console.log(
            "Opening Razorpay checkout..."
          );

          razorpay.open();

          return;
        } catch (error) {
          console.error(
            "AI Razorpay checkout error:",
            error
          );

          alert(
            error instanceof Error
              ? error.message
              : "Could not start Razorpay checkout"
          );

          return;
        }
      }

      // =====================================================
      // NORMAL AI RESPONSE
      // =====================================================

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            data.response ||
            "Here are the results:",

          products:
            data.products || [],
        },
      ]);

      // Agent may have changed cart
      await loadCart();

    } catch (error) {
      console.error(error);

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "Sorry, I couldn't connect to the AI agent right now.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  // =========================================================
  // ENTER KEY
  // =========================================================

  function handleKeyDown(
    e: React.KeyboardEvent<HTMLInputElement>
  ) {
    if (e.key === "Enter") {
      sendMessage();
    }
  }

  // =========================================================
  // UI
  // =========================================================

  return (
    <main className="min-h-screen bg-gray-50 flex items-center justify-center p-6">

      <div className="w-full max-w-4xl h-[700px] bg-white rounded-2xl shadow-xl flex flex-col overflow-hidden">

        {/* Header */}

        <div className="bg-black text-white px-6 py-5">

          <h1 className="text-xl font-bold">
            Razorpay AI Merchant Agent
          </h1>

          <p className="text-sm text-gray-300 mt-1">
            AI-powered shopping &
            checkout assistant
          </p>

        </div>

        {/* Cart */}

        <div className="border-b bg-white px-6 py-4">

          <div className="flex items-center justify-between">

            <h2 className="font-semibold text-gray-900">
              🛒 Cart
            </h2>

            <span className="font-bold text-gray-900">
              ₹
              {safeNumber(
                cartTotal
              ).toFixed(2)}
            </span>

          </div>

          {cart.length === 0 ? (

            <p className="text-sm text-gray-600 mt-2">
              Your cart is empty.
            </p>

          ) : (

            <div className="mt-3 space-y-2">

              {cart.map(
                (item) => {

                  const price =
                    safeNumber(
                      item?.price
                    );

                  const quantity =
                    safeNumber(
                      item?.quantity,
                      1
                    );

                  const subtotal =
                    safeNumber(
                      item?.subtotal,
                      price *
                        quantity
                    );

                  return (
                    <div
                      key={item.id}
                      className="flex items-center justify-between bg-gray-50 border border-gray-200 rounded-xl p-3"
                    >

                      <div>

                        <p className="font-medium text-gray-900">
                          {item.name}
                        </p>

                        <p className="text-sm text-gray-600">
                          ₹
                          {price.toFixed(
                            2
                          )}{" "}
                          ×{" "}
                          {quantity}
                        </p>

                      </div>

                      <div className="flex items-center gap-4">

                        <div className="flex items-center border border-gray-300 rounded-lg bg-white overflow-hidden">

                          <button
                            onClick={() =>
                              updateCartItem(
                                item.id,
                                quantity -
                                  1
                              )
                            }
                            className="px-3 py-1 text-gray-700 hover:bg-gray-200"
                          >
                            −
                          </button>

                          <span className="px-3 text-gray-900 font-medium">
                            {quantity}
                          </span>

                          <button
                            onClick={() =>
                              updateCartItem(
                                item.id,
                                quantity +
                                  1
                              )
                            }
                            className="px-3 py-1 text-gray-700 hover:bg-gray-200"
                          >
                            +
                          </button>

                        </div>

                        <span className="font-semibold text-gray-900">
                          ₹
                          {subtotal.toFixed(
                            2
                          )}
                        </span>

                      </div>

                    </div>
                  );
                }
              )}

            </div>
          )}

          {cart.length > 0 && (
            <>

              <button
                onClick={() =>
                  checkout(false)
                }
                className="w-full mt-4 bg-black text-white py-3 rounded-xl font-semibold hover:bg-gray-800"
              >
                Pay ₹
                {safeNumber(
                  cartTotal
                ).toFixed(2)}
              </button>

              <div className="mt-3 border border-gray-200 rounded-2xl bg-gray-50 p-4">

                <div className="flex items-start gap-3">

                  <div className="text-xl">
                    🤖
                  </div>

                  <div className="flex-1">

                    <p className="font-semibold text-gray-900">
                      AI Buyer Checkout
                    </p>

                    <p className="text-sm text-gray-600 mt-1">
                      Let the AI prepare your checkout. Payment will not
                      happen until you explicitly approve it.
                    </p>

                    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-gray-600">

                      <span className="px-2.5 py-1 rounded-full bg-white border border-gray-200">
                        🔐 Customer approval required
                      </span>

                      <span className="px-2.5 py-1 rounded-full bg-white border border-gray-200">
                        💳 No automatic payment
                      </span>

                    </div>

                    <button
                      onClick={
                        requestAICheckout
                      }
                      className="w-full mt-3 bg-white border border-gray-300 text-gray-900 py-3 rounded-xl font-semibold hover:bg-gray-100"
                    >
                      🤖 Prepare Checkout with AI
                    </button>

                  </div>

                </div>

              </div>

            </>
          )}

        </div>

        {/* AI Buyer Checkout Request */}

        {aiCheckout && (

          <div className="border-b bg-gray-50 px-6 py-4">

            <div className="border border-gray-300 rounded-2xl bg-white p-5 shadow-sm">

              <div className="flex items-center justify-between">

                <div>

                  <h2 className="font-semibold text-gray-900">
                    🤖 AI Buyer wants to checkout
                  </h2>

                  <p className="text-sm text-gray-600 mt-1">
                    The AI has prepared this purchase. Review it before approving any payment.
                  </p>

                </div>

                <span className="text-xs font-semibold bg-gray-100 text-gray-700 px-3 py-1 rounded-full">
                  Approval required
                </span>

              </div>

              <div className="mt-4 space-y-2">

                {aiCheckout.items.map(
                  (item) => (

                    <div
                      key={
                        item.product_id
                      }
                      className="flex items-center justify-between text-sm"
                    >

                      <span className="text-gray-700">
                        {item.quantity} ×{" "}
                        {item.name}
                      </span>

                      <span className="font-medium text-gray-900">
                        ₹
                        {safeNumber(
                          item.subtotal
                        ).toFixed(2)}
                      </span>

                    </div>

                  )
                )}

              </div>

              <div className="border-t mt-4 pt-3 flex items-center justify-between">

                <div>

                  <span className="font-semibold text-gray-900">
                    Total
                  </span>

                  <p className="text-xs text-gray-500 mt-1">
                    Payment starts only after your approval.
                  </p>

                </div>

                <span className="text-lg font-bold text-gray-900">
                  ₹
                  {safeNumber(
                    aiCheckout.total
                  ).toFixed(2)}
                </span>

              </div>

              <div className="mt-4 flex gap-3">

                <button
                  onClick={
                    rejectAICheckout
                  }
                  className="flex-1 border border-gray-300 text-gray-800 py-2.5 rounded-xl font-semibold hover:bg-gray-100"
                >
                  Reject
                </button>

                <button
                  onClick={
                    approveAICheckout
                  }
                  className="flex-1 bg-black text-white py-2.5 rounded-xl font-semibold hover:bg-gray-800"
                >
                  Approve & Pay
                </button>

              </div>

            </div>

          </div>

        )}

        {/* Messages */}

        <div className="flex-1 overflow-y-auto p-6 space-y-6">

          {messages.map(
            (
              message,
              index
            ) => (

              <div key={index}>

                <div
                  className={`flex ${
                    message.role ===
                    "user"
                      ? "justify-end"
                      : "justify-start"
                  }`}
                >

                  <div
                    className={`max-w-[75%] rounded-2xl px-4 py-3 whitespace-pre-wrap ${
                      message.role ===
                      "user"
                        ? "bg-black text-white"
                        : "bg-gray-100 text-gray-900"
                    }`}
                  >
                    {
                      message.content
                    }
                  </div>

                </div>

                {/* Product cards */}

                {message.products &&
                  message.products
                    .length >
                    0 && (

                    <div className="mt-4 grid gap-4 sm:grid-cols-2">

                      {message.products.map(
                        (
                          product
                        ) => (

                          <div
                            key={
                              product.id
                            }
                            className="border rounded-2xl p-5 bg-white shadow-sm"
                          >

                            <h3 className="text-lg font-semibold text-gray-900">
                              {
                                product.name
                              }
                            </h3>

                            <p className="text-sm text-gray-600 mt-2">
                              {
                                product.description
                              }
                            </p>

                            <div className="flex items-center justify-between mt-4">

                              <span className="text-xl font-bold text-black">
                                ₹
                                {safeNumber(
                                  product.price
                                ).toFixed(
                                  2
                                )}
                              </span>

                              <span className="text-sm text-gray-500">
                                {
                                  product.stock
                                }{" "}
                                in stock
                              </span>

                            </div>

                            <button
                              onClick={() =>
                                addToCart(
                                  product.id
                                )
                              }
                              className="w-full mt-4 bg-black text-white py-2.5 rounded-xl hover:bg-gray-800"
                            >
                              Add to Cart
                            </button>

                          </div>

                        )
                      )}

                    </div>
                  )}

              </div>

            )
          )}

          {loading && (

            <div className="flex justify-start">

              <div className="bg-gray-100 rounded-2xl px-4 py-3 text-gray-500">
                Thinking...
              </div>

            </div>

          )}

        </div>

        {/* Input */}

        <div className="border-t p-4 flex gap-3">

          <input
            value={input}
            onChange={(e) =>
              setInput(
                e.target.value
              )
            }
            onKeyDown={
              handleKeyDown
            }
            placeholder="Ask me what you'd like to buy..."
            className="flex-1 border border-gray-300 bg-white text-gray-900 placeholder:text-gray-500 rounded-xl px-4 py-3 outline-none focus:ring-2 focus:ring-black"
            disabled={loading}
          />

          <button
            onClick={
              sendMessage
            }
            disabled={
              loading ||
              !input.trim()
            }
            className="bg-black text-white px-6 py-3 rounded-xl hover:bg-gray-800 disabled:bg-gray-300 disabled:text-gray-600"
          >
            Send
          </button>

        </div>

      </div>

    </main>
  );
}
