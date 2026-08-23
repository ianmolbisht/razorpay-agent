from app.services.groq_buyer import run_buyer


result = run_buyer(
    "Buy me 100 running shoes."
)

print("\n==============================")
print("FINAL AI BUYER RESPONSE")
print("==============================")
print(result)