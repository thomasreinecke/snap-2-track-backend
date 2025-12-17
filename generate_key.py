# generate_key.py
import secrets

def generate_api_key():
    # Generates a URL-safe text string, containing 32 random bytes.
    # The text length will be approx 43 characters.
    key = secrets.token_urlsafe(32)
    print(f"\n🔑 Your new API Key:\n\n{key}\n")
    print("👉 Add this to your .env files as API_KEY=...\n")

if __name__ == "__main__":
    generate_api_key()