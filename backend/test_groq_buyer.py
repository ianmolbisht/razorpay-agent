from app.services.groq_buyer import run_buyer


result = run_buyer(
    "Add 1 running shoes to my cart."
)

print("\n==============================")
print("FINAL AI BUYER RESPONSE")
print("==============================")
print(result)