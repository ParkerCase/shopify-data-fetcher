import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Shopify API Configuration
SHOP_NAME = os.getenv('SHOP_NAME', 'your-store.myshopify.com')
API_KEY = os.getenv('API_KEY', 'your-api-key')
PASSWORD = os.getenv('PASSWORD', 'your-api-password')
API_VERSION = os.getenv('API_VERSION', '2023-10')

# API Base URL
API_BASE_URL = f"https://{SHOP_NAME}/admin/api/{API_VERSION}"

# Request Headers
HEADERS = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

# Time periods
DAYS_LOOKBACK = 30  # For orders and other time-sensitive data
