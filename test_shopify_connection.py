import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Shopify API Configuration
SHOP_NAME = os.getenv("SHOP_NAME", "tatt-2-away.myshopify.com")
API_KEY = os.getenv("API_KEY", "8d236638adbd963ec050de036c97d2bc")
PASSWORD = os.getenv("PASSWORD", "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")
API_VERSION = os.getenv("API_VERSION", "2025-04")

# API Base URL
API_BASE_URL = f"https://{SHOP_NAME}/admin/api/{API_VERSION}"

# Request Headers
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

# Disable SSL verification globally for the requests library
requests.packages.urllib3.disable_warnings()
old_merge_environment_settings = requests.Session.merge_environment_settings


# Override merge_environment_settings to always disable verification
def merge_environment_settings(self, url, proxies, stream, verify, cert):
    settings = old_merge_environment_settings(self, url, proxies, stream, verify, cert)
    settings["verify"] = False
    return settings


# Apply the patch
requests.Session.merge_environment_settings = merge_environment_settings


def test_shopify_connection():
    """Test connection to Shopify API with SSL verification disabled."""
    print("Testing connection to Shopify API...")

    # Create a session with auth
    session = requests.Session()
    session.auth = (API_KEY, PASSWORD)
    session.headers.update(HEADERS)
    session.verify = False  # Belt and suspenders approach

    # Try to access a simple endpoint
    try:
        endpoint = f"{API_BASE_URL}/shop.json"
        response = session.get(endpoint)
        response.raise_for_status()

        # Print the response
        shop_data = response.json().get("shop", {})
        print(f"✅ Successfully connected to Shopify API!")
        print(f"Shop name: {shop_data.get('name')}")
        print(f"Shop ID: {shop_data.get('id')}")
        print(f"Shop domain: {shop_data.get('domain')}")
        print(f"Shop email: {shop_data.get('email')}")
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


if __name__ == "__main__":
    test_shopify_connection()
