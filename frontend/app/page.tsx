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
  price: number;
  quantity: number;
  subtotal: number;
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

  // Load the customer's ACTIVE cart
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

      setCartId(data.id);
      setCart(data.items || []);

      // Calculate total ourselves in case backend doesn't return total
      const total = (data.items || []).reduce(
        (sum: number, item: CartItem) =>
          sum + Number(item.subtotal ?? item.price * item.quantity),
        0
      );

      setCartTotal(total);
    } catch {
      console.error("Could not load active cart");
    }
  }

  useEffect(() => {
    loadCart();
  }, []);

  // Load Razorpay Checkout script
  useEffect(() => {
    const script = document.createElement("script");

    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;

    document.body.appendChild(script);

    return () => {
      document.body.removeChild(script);
    };
  }, []);

  async function addToCart(productId: number) {
    if (!cartId) {
      alert("No active cart found");
      return;
    }

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/api/cart/${cartId}/items`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            product_id: productId,
            quantity: 1,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        alert(data.detail || data.error || "Could not add to cart");
        return;
      }

      await loadCart();
    } catch {
      alert("Could not connect to cart");
    }
  }

  async function updateCartItem(
    itemId: number,
    quantity: number
  ) {
    if (!cartId) {
      alert("No active cart found");
      return;
    }

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/api/cart/${cartId}/items/${itemId}?quantity=${quantity}`,
        {
          method: "PATCH",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        alert(data.detail || data.error || "Could not update cart");
        return;
      }

      await loadCart();
    } catch {
      alert("Could not connect to cart");
    }
  }

  async function checkout() {
    if (!cartId) {
      alert("No active cart found");
      return;
    }

    if (cart.length === 0) {
      alert("Your cart is empty");
      return;
    }

    try {
      // 1. Create our local order from the ACTIVE cart
      const orderResponse = await fetch(
        `http://127.0.0.1:8000/api/orders/from-cart/${cartId}`,
        {
          method: "POST",
        }
      );

      const order = await orderResponse.json();

      if (!orderResponse.ok) {
        alert(order.detail || "Could not create order");
        return;
      }

      // 2. Create corresponding Razorpay order
      const razorpayResponse = await fetch(
        `http://127.0.0.1:8000/api/orders/${order.id}/razorpay`,
        {
          method: "POST",
        }
      );

      const razorpayOrder = await razorpayResponse.json();

      if (!razorpayResponse.ok) {
        alert(
          razorpayOrder.detail ||
            "Could not create Razorpay order"
        );
        return;
      }

      if (!window.Razorpay) {
        alert(
          "Razorpay Checkout is still loading. Please try again."
        );
        return;
      }

      // 3. Open Razorpay Checkout
      const options = {
        key: razorpayOrder.key_id,
        amount: razorpayOrder.amount,
        currency: razorpayOrder.currency,
        name: "Razorpay AI Merchant Agent",
        description: "AI-powered shopping checkout",
        order_id: razorpayOrder.razorpay_order_id,

        handler: async function (response: any) {
          // 4. Verify payment on backend
          const verificationResponse = await fetch(
            `http://127.0.0.1:8000/api/payments/${order.id}/verify`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
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

          if (!verificationResponse.ok) {
            alert(
              result.detail ||
                "Payment verification failed"
            );
            return;
          }

          alert("✅ Payment successful!");

          // Old cart is now checked_out.
          // Reload to find the customer's next active cart.
          await loadCart();
        },
        
        theme: {
          color: "#000000",
        },
      };

      const razorpay = new window.Razorpay(options);

      razorpay.on(
        "payment.failed",
        function (response: any) {
          console.error(
            "Payment failed:",
            response.error
          );

          alert(
            "❌ Payment failed. Please try again."
          );
        }
      );

      razorpay.open();
    } catch (error) {
      console.error(error);
      alert("Could not start checkout");
    }
  }

  async function sendMessage() {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();

    setInput("");

    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        content: userMessage,
      },
    ]);

    setLoading(true);

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/api/agent/chat",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            message: userMessage,
          }),
        }
      );

      if (!response.ok) {
        throw new Error("Agent request failed");
      }

      const data = await response.json();

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            data.response || "Here are the results:",
          products: data.products || [],
        },
      ]);

      // Refresh cart because the AI agent may
      // have added something to it.
      await loadCart();
    } catch {
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

  function handleKeyDown(
    e: React.KeyboardEvent<HTMLInputElement>
  ) {
    if (e.key === "Enter") {
      sendMessage();
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
      <div className="w-full max-w-4xl h-[700px] bg-white rounded-2xl shadow-xl flex flex-col overflow-hidden">

        {/* Header */}
        <div className="bg-black text-white px-6 py-5">
          <h1 className="text-xl font-bold">
            Razorpay AI Merchant Agent
          </h1>

          <p className="text-sm text-gray-300 mt-1">
            AI-powered shopping & checkout assistant
          </p>
        </div>

        {/* Cart */}
        <div className="border-b bg-white px-6 py-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">
              🛒 Cart
            </h2>

            <span className="font-bold text-gray-900">
              ₹{cartTotal}
            </span>
          </div>

          {cart.length === 0 ? (
            <p className="text-sm text-gray-600 mt-2">
              Your cart is empty.
            </p>
          ) : (
            <div className="mt-3 space-y-2">
              {cart.map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between bg-gray-50 border border-gray-200 rounded-xl p-3"
                >
                  <div>
                    <p className="font-medium text-gray-900">
                      {item.name}
                    </p>

                    <p className="text-sm text-gray-600">
                      ₹{item.price} × {item.quantity}
                    </p>
                  </div>

                  <div className="flex items-center gap-4">

                    <div className="flex items-center border border-gray-300 rounded-lg bg-white overflow-hidden">

                      <button
                        onClick={() =>
                          updateCartItem(
                            item.id,
                            item.quantity - 1
                          )
                        }
                        className="px-3 py-1 text-gray-700 hover:bg-gray-200"
                      >
                        −
                      </button>

                      <span className="px-3 text-gray-900 font-medium">
                        {item.quantity}
                      </span>

                      <button
                        onClick={() =>
                          updateCartItem(
                            item.id,
                            item.quantity + 1
                          )
                        }
                        className="px-3 py-1 text-gray-700 hover:bg-gray-200"
                      >
                        +
                      </button>

                    </div>

                    <span className="font-semibold text-gray-900">
                      ₹{item.subtotal}
                    </span>

                  </div>
                </div>
              ))}
            </div>
          )}

          {cart.length > 0 && (
            <button
              onClick={checkout}
              className="w-full mt-4 bg-black text-white py-3 rounded-xl font-semibold hover:bg-gray-800"
            >
              Pay ₹{cartTotal}
            </button>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">

          {messages.map((message, index) => (
            <div key={index}>

              <div
                className={`flex ${
                  message.role === "user"
                    ? "justify-end"
                    : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[75%] rounded-2xl px-4 py-3 whitespace-pre-wrap ${
                    message.role === "user"
                      ? "bg-black text-white"
                      : "bg-gray-100 text-gray-900"
                  }`}
                >
                  {message.content}
                </div>
              </div>

              {/* Product cards */}
              {message.products &&
                message.products.length > 0 && (
                  <div className="mt-4 grid gap-4 sm:grid-cols-2">

                    {message.products.map((product) => (
                      <div
                        key={product.id}
                        className="border rounded-2xl p-5 bg-white shadow-sm"
                      >
                        <h3 className="text-lg font-semibold text-gray-900">
                          {product.name}
                        </h3>

                        <p className="text-sm text-gray-600 mt-2">
                          {product.description}
                        </p>

                        <div className="flex items-center justify-between mt-4">

                          <span className="text-xl font-bold text-black">
                            ₹{product.price}
                          </span>

                          <span className="text-sm text-gray-500">
                            {product.stock} in stock
                          </span>

                        </div>

                        <button
                          onClick={() =>
                            addToCart(product.id)
                          }
                          className="w-full mt-4 bg-black text-white py-2.5 rounded-xl hover:bg-gray-800"
                        >
                          Add to Cart
                        </button>

                      </div>
                    ))}

                  </div>
                )}

            </div>
          ))}

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
              setInput(e.target.value)
            }
            onKeyDown={handleKeyDown}
            placeholder="Ask me what you'd like to buy..."
            className="flex-1 border border-gray-300 bg-white text-gray-900 placeholder:text-gray-500 rounded-xl px-4 py-3 outline-none focus:ring-2 focus:ring-black"
            disabled={loading}
          />

          <button
            onClick={sendMessage}
            disabled={
              loading || !input.trim()
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