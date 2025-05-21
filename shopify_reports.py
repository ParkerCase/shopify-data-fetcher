import requests
import pandas as pd
import datetime
import time
import json
import os
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread_dataframe import set_with_dataframe

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

# ------------------------------------------------------------------------------
# Date Range Utility Functions
# ------------------------------------------------------------------------------


def get_current_week_range():
    """Get date range for current week (Monday to Sunday, Mountain Time)."""
    # Define Mountain Time timezone
    import pytz

    mountain_tz = pytz.timezone("America/Denver")

    # Get current time in Mountain Time
    now = datetime.datetime.now(mountain_tz)
    today = now.date()

    # Calculate days since Monday (0 for Monday, 6 for Sunday)
    days_since_monday = today.weekday()

    # Find the last Monday (start of week)
    start_of_week = today - datetime.timedelta(days=days_since_monday)

    # End of week is Sunday (6 days after Monday)
    end_of_week = start_of_week + datetime.timedelta(days=6)

    # Return datetime objects with time set to beginning/end of day in Mountain Time
    start_datetime = mountain_tz.localize(
        datetime.datetime.combine(start_of_week, datetime.time.min)
    )
    end_datetime = mountain_tz.localize(
        datetime.datetime.combine(end_of_week, datetime.time.max)
    )

    return start_datetime, end_datetime


def get_previous_week_range():
    """Get date range for previous week (Monday to Sunday, Mountain Time)."""
    # Define Mountain Time timezone
    import pytz

    mountain_tz = pytz.timezone("America/Denver")

    # Get current time in Mountain Time
    now = datetime.datetime.now(mountain_tz)
    today = now.date()

    # Calculate days since Monday (0 for Monday, 6 for Sunday)
    days_since_monday = today.weekday()

    # Find the last Monday (start of current week)
    start_of_this_week = today - datetime.timedelta(days=days_since_monday)

    # Previous Monday is 7 days before
    start_of_prev_week = start_of_this_week - datetime.timedelta(days=7)

    # Previous Sunday is 6 days after previous Monday
    end_of_prev_week = start_of_prev_week + datetime.timedelta(days=6)

    # Return datetime objects with time set to beginning/end of day in Mountain Time
    start_datetime = mountain_tz.localize(
        datetime.datetime.combine(start_of_prev_week, datetime.time.min)
    )
    end_datetime = mountain_tz.localize(
        datetime.datetime.combine(end_of_prev_week, datetime.time.max)
    )

    return start_datetime, end_datetime


# ------------------------------------------------------------------------------
# Shopify API Functions
# ------------------------------------------------------------------------------


def get_session():
    """Create and return an authenticated session for Shopify API requests."""
    session = requests.Session()
    session.auth = (API_KEY, PASSWORD)
    session.headers.update(HEADERS)
    session.verify = False  # Explicitly disable SSL verification for this session
    return session


def handle_pagination(session, url, params=None):
    """Handle API pagination and return all results."""
    if params is None:
        params = {}

    all_data = []

    while url:
        try:
            # Add timeout parameter to each request to prevent hanging
            response = session.get(url, params=params, timeout=30)

            # Handle API rate limits
            if response.status_code == 429:  # Too Many Requests
                retry_after = int(response.headers.get("Retry-After", 5))
                print(f"Rate limited, waiting for {retry_after} seconds...")
                time.sleep(retry_after)
                continue

            response.raise_for_status()  # Raise exception for 4XX/5XX responses

            data = response.json()

            # Extract the main data (the key depends on the endpoint)
            # For example, orders endpoint returns {'orders': [...]}
            for key in data.keys():
                if isinstance(data[key], list):
                    all_data.extend(data[key])
                    print(
                        f"Retrieved {len(data[key])} records from {key} endpoint. Total: {len(all_data)}"
                    )
                    break

            # Check for Link header to handle pagination
            link_header = response.headers.get("Link", "")
            next_url = None

            if 'rel="next"' in link_header:
                links = link_header.split(",")
                for link in links:
                    if 'rel="next"' in link:
                        next_url = link.split(";")[0].strip("<> ")
                        params = {}  # Reset params as they're in the URL
                        break
            else:
                url = None

        except requests.exceptions.Timeout:
            print(
                f"Request timed out while fetching data. Returning data collected so far ({len(all_data)} records)."
            )
            break
        except Exception as e:
            print(f"Error during pagination: {e}")
            break

    return all_data


# ------------------------------------------------------------------------------
# Data Fetching Functions
# ------------------------------------------------------------------------------


def get_orders(session, week_range=None):
    """
    Fetch orders from a specific week (Sunday through Saturday).
    If week_range is None, defaults to current week.
    """
    if week_range is None:
        start_date, end_date = get_current_week_range()
    else:
        start_date, end_date = week_range

    print(
        f"Fetching orders from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}..."
    )

    # Format dates for API
    created_at_min = start_date.isoformat()
    created_at_max = end_date.isoformat()

    # Set up endpoint and parameters
    endpoint = f"{API_BASE_URL}/orders.json"
    params = {
        "status": "any",
        "created_at_min": created_at_min,
        "created_at_max": created_at_max,
        "limit": 250,  # Maximum allowed by Shopify
    }

    # Get all orders with pagination
    orders = handle_pagination(session, endpoint, params)

    print(f"Retrieved {len(orders)} orders for the selected week.")

    # Process orders into a clean DataFrame
    if not orders:
        return pd.DataFrame()

    # Extract relevant fields
    orders_data = []
    for order in orders:
        orders_data.append(
            {
                "id": order.get("id"),
                "order_number": order.get("order_number"),
                "created_at": order.get("created_at"),
                "customer_name": f"{order.get('customer', {}).get('first_name', '')} {order.get('customer', {}).get('last_name', '')}".strip(),
                "customer_email": order.get("customer", {}).get("email", ""),
                "financial_status": order.get("financial_status"),
                "fulfillment_status": order.get("fulfillment_status"),
                "total_price": order.get("total_price"),
                "currency": order.get("currency"),
                "item_count": sum(
                    item.get("quantity", 0) for item in order.get("line_items", [])
                ),
            }
        )

    # Create DataFrame
    df = pd.DataFrame(orders_data)

    # Convert date strings to datetime
    if "created_at" in df.columns and not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"], utc=True)

    return df


def get_products(session):
    """Fetch all products and their inventory levels."""
    print("Fetching products and inventory levels...")

    # Fetch products
    endpoint = f"{API_BASE_URL}/products.json"
    params = {"limit": 250}

    products = handle_pagination(session, endpoint, params)

    print(f"Retrieved {len(products)} products.")

    if not products:
        return pd.DataFrame()

    # Process products into a clean DataFrame
    products_data = []
    for product in products:
        for variant in product.get("variants", []):
            inventory_level = "Unknown"  # Default value

            # Get inventory level for this variant
            inventory_item_id = variant.get("inventory_item_id")
            if inventory_item_id:
                inventory_endpoint = f"{API_BASE_URL}/inventory_levels.json"
                inventory_params = {"inventory_item_ids": inventory_item_id}

                try:
                    inventory_response = session.get(
                        inventory_endpoint, params=inventory_params
                    )
                    inventory_response.raise_for_status()
                    inventory_data = inventory_response.json()

                    if (
                        "inventory_levels" in inventory_data
                        and inventory_data["inventory_levels"]
                    ):
                        inventory_level = inventory_data["inventory_levels"][0].get(
                            "available", "Unknown"
                        )
                except requests.exceptions.RequestException as e:
                    print(
                        f"Error fetching inventory for product {product.get('id')}, variant {variant.get('id')}: {e}"
                    )

            products_data.append(
                {
                    "product_id": product.get("id"),
                    "product_title": product.get("title"),
                    "variant_id": variant.get("id"),
                    "variant_title": variant.get("title"),
                    "sku": variant.get("sku", ""),
                    "price": variant.get("price"),
                    "available_quantity": inventory_level,
                    "created_at": product.get("created_at"),
                    "updated_at": product.get("updated_at"),
                    "product_type": product.get("product_type", ""),
                    "vendor": product.get("vendor", ""),
                }
            )

    # Create DataFrame
    df = pd.DataFrame(products_data)

    # Convert date strings to datetime
    for date_col in ["created_at", "updated_at"]:
        if date_col in df.columns and not df.empty:
            df[date_col] = pd.to_datetime(df[date_col], utc=True)

    return df


def get_customers(session, week_range=None):
    """
    Fetch customer information with focus on customers who ordered in the specified week.

    Instead of fetching ALL customers (which could be thousands), this approach:
    1. First gets orders from the specified week
    2. Extracts customer IDs from those orders
    3. Only fetches full customer details for those specific customers

    This is much more efficient for weekly reporting.
    """
    if week_range is None:
        start_date, end_date = get_current_week_range()
    else:
        start_date, end_date = week_range

    print(
        f"Fetching customers who ordered from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}..."
    )

    # Step 1: Get orders for the specified week
    orders_endpoint = f"{API_BASE_URL}/orders.json"
    orders_params = {
        "status": "any",
        "created_at_min": start_date.isoformat(),
        "created_at_max": end_date.isoformat(),
        "limit": 250,
        "fields": "id,customer",  # Only get customer info from orders
    }

    try:
        # Get orders with pagination
        orders = handle_pagination(session, orders_endpoint, orders_params)

        if not orders:
            print("No orders found for the specified week.")
            return pd.DataFrame()

        # Step 2: Extract unique customer IDs from those orders
        customer_ids = set()
        customer_data_from_orders = {}

        for order in orders:
            if order.get("customer") and order.get("customer", {}).get("id"):
                customer_id = order.get("customer", {}).get("id")
                customer_ids.add(customer_id)

                # Store customer data from the order for later use
                customer_data_from_orders[customer_id] = order.get("customer", {})

        if not customer_ids:
            print("No customer IDs found in the orders for the specified week.")
            return pd.DataFrame()

        print(
            f"Found {len(customer_ids)} unique customers with orders in the specified week."
        )

        # Process customers into a DataFrame using data from orders
        customers_data = []
        for customer_id, customer in customer_data_from_orders.items():
            customers_data.append(
                {
                    "id": customer.get("id"),
                    "first_name": customer.get("first_name", ""),
                    "last_name": customer.get("last_name", ""),
                    "email": customer.get("email", ""),
                    "phone": customer.get("phone", ""),
                    "orders_count": customer.get("orders_count", 0),
                    "total_spent": customer.get("total_spent", "0.00"),
                    "created_at": customer.get("created_at"),
                    "updated_at": customer.get("updated_at"),
                    "tags": customer.get("tags", ""),
                    "verified_email": customer.get("verified_email", False),
                    "ordered_this_week": True,  # These are all active customers by definition
                }
            )

        # Create DataFrame
        df = pd.DataFrame(customers_data)

        # Convert date strings to datetime and numeric values
        for date_col in ["created_at", "updated_at"]:
            if date_col in df.columns and not df.empty:
                df[date_col] = pd.to_datetime(df[date_col], utc=True, errors="coerce")

        for num_col in ["orders_count", "total_spent"]:
            if num_col in df.columns and not df.empty:
                df[num_col] = pd.to_numeric(df[num_col], errors="coerce")

        return df

    except requests.exceptions.Timeout:
        print(
            "Request timed out while fetching customer data. Creating empty customer dataset."
        )
        return pd.DataFrame()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error while fetching customer data: {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"Unexpected error while fetching customer data: {e}")
        return pd.DataFrame()


def get_analytics(session, week_range=None):
    """Fetch analytics data if available through the API."""
    if week_range is None:
        start_date, end_date = get_current_week_range()
    else:
        start_date, end_date = week_range

    print(
        f"Fetching analytics data for {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}..."
    )

    # Note: Shopify's Analytics API might be limited
    # Try to get reports that might contain analytics data
    endpoint = f"{API_BASE_URL}/reports.json"

    try:
        response = session.get(endpoint)
        response.raise_for_status()
        reports = response.json().get("reports", [])

        # Look for analytics-related reports
        analytics_reports = [
            report
            for report in reports
            if "traffic" in report.get("name", "").lower()
            or "analytic" in report.get("name", "").lower()
            or "conversion" in report.get("name", "").lower()
        ]

        if not analytics_reports:
            print(
                "No specific analytics reports found. This might require a different API approach."
            )
            return pd.DataFrame(
                {"note": ["Analytics data not available through this API endpoint."]}
            )

        # For each analytics report, try to get the data
        analytics_data = []
        for report in analytics_reports:
            report_id = report.get("id")
            report_endpoint = f"{API_BASE_URL}/reports/{report_id}.json"

            report_response = session.get(report_endpoint)
            if report_response.status_code == 200:
                report_data = report_response.json().get("report", {})
                # Process and add to analytics data
                analytics_data.append(
                    {
                        "report_id": report_id,
                        "report_name": report.get("name"),
                        "updated_at": report.get("updated_at"),
                        "report_data": json.dumps(report_data),
                    }
                )

        if analytics_data:
            df = pd.DataFrame(analytics_data)
            # Convert date columns
            if "updated_at" in df.columns and not df.empty:
                df["updated_at"] = pd.to_datetime(df["updated_at"], utc=True)
            return df
        else:
            print("No analytics data could be retrieved.")
            return pd.DataFrame({"note": ["No analytics data could be retrieved."]})

    except requests.exceptions.RequestException as e:
        print(f"Error fetching analytics: {e}")
        return pd.DataFrame({"error": [str(e)]})


def get_fulfillments(session, week_range=None):
    """
    Fetch fulfillment data for orders from a specific week.
    If week_range is None, defaults to current week.
    """
    if week_range is None:
        start_date, end_date = get_current_week_range()
    else:
        start_date, end_date = week_range

    print(
        f"Fetching fulfillments from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}..."
    )

    # First, get orders for the specified week
    orders_df = get_orders(session, week_range)

    if orders_df.empty:
        print("No orders found for the specified week to check fulfillments.")
        return pd.DataFrame()

    # Get fulfillments for each order
    fulfillments_data = []

    for order_id in orders_df["id"].unique():
        endpoint = f"{API_BASE_URL}/orders/{order_id}/fulfillments.json"

        try:
            response = session.get(endpoint)
            response.raise_for_status()
            order_fulfillments = response.json().get("fulfillments", [])

            for fulfillment in order_fulfillments:
                # Check if the fulfillment is within our date range
                created_at = fulfillment.get("created_at")
                if created_at:
                    fulfillment_date = datetime.datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    )
                    # Only include fulfillments created in the specified week
                    if start_date <= fulfillment_date <= end_date:
                        tracking_numbers = fulfillment.get("tracking_numbers", [])
                        tracking_urls = fulfillment.get("tracking_urls", [])

                        fulfillments_data.append(
                            {
                                "order_id": order_id,
                                "fulfillment_id": fulfillment.get("id"),
                                "status": fulfillment.get("status", ""),
                                "created_at": created_at,
                                "service": fulfillment.get("service", ""),
                                "tracking_number": (
                                    tracking_numbers[0] if tracking_numbers else ""
                                ),
                                "tracking_url": (
                                    tracking_urls[0] if tracking_urls else ""
                                ),
                                "line_items_count": len(
                                    fulfillment.get("line_items", [])
                                ),
                            }
                        )

        except requests.exceptions.RequestException as e:
            print(f"Error fetching fulfillments for order {order_id}: {e}")

    if not fulfillments_data:
        print("No fulfillments found for the specified week.")
        return pd.DataFrame()

    # Create DataFrame
    df = pd.DataFrame(fulfillments_data)

    # Convert date strings to datetime
    if "created_at" in df.columns and not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"], utc=True)

    # Merge with orders data to get more context
    if not df.empty and not orders_df.empty:
        df = df.merge(
            orders_df[["id", "order_number", "customer_name", "customer_email"]],
            left_on="order_id",
            right_on="id",
            how="left",
        )
        # Clean up columns
        if "id" in df.columns:
            df = df.drop(columns=["id"])

    return df


def get_reports(session):
    """Fetch available reports from the Shopify API."""
    print("Fetching available reports...")

    endpoint = f"{API_BASE_URL}/reports.json"

    try:
        reports = handle_pagination(session, endpoint)

        print(f"Retrieved {len(reports)} reports.")

        if not reports:
            return pd.DataFrame()

        # Process reports into a clean DataFrame
        reports_data = []
        for report in reports:
            reports_data.append(
                {
                    "id": report.get("id"),
                    "name": report.get("name", ""),
                    "category": report.get("category", ""),
                    "shopify_ql": report.get("shopify_ql", ""),
                    "updated_at": report.get("updated_at"),
                }
            )

        # Create DataFrame
        df = pd.DataFrame(reports_data)

        # Convert date strings to datetime
        if "updated_at" in df.columns and not df.empty:
            df["updated_at"] = pd.to_datetime(df["updated_at"], utc=True)

        return df

    except requests.exceptions.RequestException as e:
        print(f"Error fetching reports: {e}")
        return pd.DataFrame({"error": [str(e)]})


# ------------------------------------------------------------------------------
# Visualization and Output Functions
# ------------------------------------------------------------------------------


def display_dataframe(df, title):
    """Display a DataFrame in a clean, readable format."""
    print(f"\n{'=' * 50}")
    print(f"  {title}")
    print(f"{'=' * 50}")

    if df.empty:
        print("No data available.")
        return

    # Print DataFrame info
    print(f"\nDataFrame shape: {df.shape}")
    print("\nColumns:")
    for col in df.columns:
        print(f"  - {col}")

    # Print a sample of the data
    print("\nSample data (first 5 rows):")
    print(df.head().to_string())

    # Print some basic statistics for numeric columns
    numeric_cols = df.select_dtypes(include=["number"]).columns
    if not numeric_cols.empty:
        print("\nBasic statistics for numeric columns:")
        print(df[numeric_cols].describe().to_string())


# ------------------------------------------------------------------------------
# Google Sheets Integration
# ------------------------------------------------------------------------------


def upload_to_google_sheets(data_dict, week_range=None, spreadsheet_id=None):
    """
    Upload data to Google Sheets.

    Args:
        data_dict: Dictionary containing DataFrames to upload
        week_range: Tuple of (start_date, end_date) for the report period
        spreadsheet_id: Optional ID of an existing spreadsheet to update
    """
    if week_range is None:
        week_range = get_previous_week_range()

    start_date, end_date = week_range
    week_str = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"

    print(f"\nUploading data to Google Sheets for {week_str}...")

    # Set up Google Sheets credentials
    # Define the scope
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    # Load credentials from service account file
    credentials = ServiceAccountCredentials.from_json_keyfile_name(
        "supple-life-437019-e0-7d94cf81533f.json", scope
    )

    # Create gspread client
    client = gspread.authorize(credentials)

    # Spreadsheet handling
    if spreadsheet_id:
        # Use an existing spreadsheet
        try:
            # Clean the URL if a full URL was provided instead of just the ID
            if "spreadsheets/d/" in spreadsheet_id:
                spreadsheet_id = spreadsheet_id.split("spreadsheets/d/")[1].split("/")[
                    0
                ]

            spreadsheet = client.open_by_key(spreadsheet_id)
            print(f"Updating existing spreadsheet: {spreadsheet.title}")
        except Exception as e:
            print(f"Error opening spreadsheet with ID {spreadsheet_id}: {e}")
            print("Creating a new spreadsheet instead.")
            spreadsheet_id = None

    if not spreadsheet_id:
        # Create a new spreadsheet
        spreadsheet_name = f"Shopify Weekly Reports"
        try:
            # Try to open existing spreadsheet with this name
            spreadsheet = client.open(spreadsheet_name)
            print(f"Found existing spreadsheet: {spreadsheet_name}")
        except gspread.exceptions.SpreadsheetNotFound:
            # Create new spreadsheet if it doesn't exist
            spreadsheet = client.create(spreadsheet_name)
            print(f"Created new spreadsheet: {spreadsheet_name}")

            # Share with your email - Make sure this email matches your Google account
            spreadsheet.share("itsus@tatt2away.com", perm_type="user", role="writer")
            print(f"Shared spreadsheet with itsus@tatt2away.com")

    # Create a worksheet for this week's data
    week_tab_name = f"Week {start_date.strftime('%Y-%m-%d')}"

    try:
        # Check if worksheet for this week already exists
        week_worksheet = spreadsheet.worksheet(week_tab_name)
        print(f"Updating existing worksheet: {week_tab_name}")
        week_worksheet.clear()
    except gspread.exceptions.WorksheetNotFound:
        # Create a new worksheet for this week
        week_worksheet = spreadsheet.add_worksheet(
            title=week_tab_name, rows=500, cols=20
        )
        print(f"Created new worksheet: {week_tab_name}")

    # Add a summary to the main weekly tab
    week_worksheet.update_cell(
        1,
        1,
        f"Shopify Weekly Report: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
    )
    week_worksheet.format(
        "A1:E1", {"textFormat": {"bold": True}, "horizontalAlignment": "CENTER"}
    )
    week_worksheet.merge_cells("A1:E1")

    # Format summary data
    summary_data = data_dict["summary"]

    summary_rows = [
        ["Report Period", str(summary_data["report_period"])],
        ["Total Orders", int(summary_data["total_orders"])],
        ["Total Revenue", f"${float(summary_data['total_revenue']):.2f}"],
        ["Average Order Value", f"${float(summary_data['avg_order_value']):.2f}"],
        ["Total Products", int(summary_data["total_products"])],
        ["Total Variants", int(summary_data["total_variants"])],
        ["Total Customers", int(summary_data["total_customers"])],
        ["Active Customers This Week", int(summary_data["active_customers"])],
        ["Total Fulfillments", int(summary_data["total_fulfillments"])],
    ]

    # Add 2 blank rows after the title
    week_worksheet.update(values=summary_rows, range_name="A3:B11")
    week_worksheet.format("A3:A11", {"textFormat": {"bold": True}})

    # Add section headings and data for each dataframe
    current_row = 13  # Start after summary

    # Process each dataframe
    for sheet_name, df in data_dict.items():
        if isinstance(df, pd.DataFrame) and not df.empty and sheet_name != "summary":
            print(
                f"Adding {sheet_name} data to the weekly worksheet ({len(df)} rows)..."
            )

            # Add section header
            week_worksheet.update_cell(current_row, 1, sheet_name.upper())
            week_worksheet.format(
                f"A{current_row}:E{current_row}",
                {
                    "textFormat": {"bold": True},
                    "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                },
            )
            current_row += 1

            # Convert dataframe for upload
            df_copy = df.copy()

            # Convert pandas-specific types to Python native types
            for col in df_copy.select_dtypes(include=["number"]).columns:
                df_copy[col] = (
                    df_copy[col].astype(float).fillna(0).apply(lambda x: float(x))
                )

            # Convert datetime columns to string
            for col in df_copy.columns:
                if pd.api.types.is_datetime64_any_dtype(df_copy[col]):
                    df_copy[col] = df_copy[col].dt.strftime("%Y-%m-%d %H:%M:%S")

            # Get column headers and values
            headers = df_copy.columns.tolist()
            values = df_copy.values.tolist()

            # Add headers
            week_worksheet.update(
                values=[headers],
                range_name=f"A{current_row}:{chr(65+len(headers)-1)}{current_row}",
            )
            week_worksheet.format(
                f"A{current_row}:{chr(65+len(headers)-1)}{current_row}",
                {
                    "textFormat": {"bold": True},
                    "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
                },
            )
            current_row += 1

            # Add data - limit to first 100 rows to avoid exceeding cell limits
            if values:
                data_to_add = values[:100]  # Limit to 100 rows per section
                end_row = current_row + len(data_to_add) - 1
                range_notation = f"A{current_row}:{chr(65+len(headers)-1)}{end_row}"
                week_worksheet.update(range_notation, data_to_add)
                current_row = end_row + 2  # Add a blank row between sections
            else:
                current_row += 1  # Just move to next row if no data

    # Also create detail worksheets for each data type
    for sheet_name, df in data_dict.items():
        if isinstance(df, pd.DataFrame) and not df.empty and sheet_name != "summary":
            # Convert dataframe for upload
            df_copy = df.copy()

            # Convert pandas-specific types to Python native types
            for col in df_copy.select_dtypes(include=["number"]).columns:
                df_copy[col] = (
                    df_copy[col].astype(float).fillna(0).apply(lambda x: float(x))
                )

            # Convert datetime columns to string
            for col in df_copy.columns:
                if pd.api.types.is_datetime64_any_dtype(df_copy[col]):
                    df_copy[col] = df_copy[col].dt.strftime("%Y-%m-%d %H:%M:%S")

            detail_tab_name = f"{sheet_name.capitalize()}"

            try:
                # Try to get existing worksheet
                detail_worksheet = spreadsheet.worksheet(detail_tab_name)
                detail_worksheet.clear()
            except gspread.exceptions.WorksheetNotFound:
                # Create new worksheet if it doesn't exist
                detail_worksheet = spreadsheet.add_worksheet(
                    title=detail_tab_name,
                    rows=len(df_copy) + 10,
                    cols=len(df_copy.columns) + 5,
                )

            # Upload the full dataframe to the detail worksheet
            set_with_dataframe(detail_worksheet, df_copy)

    # Update or create the Trends worksheet to track weekly data over time
    try:
        trends_worksheet = spreadsheet.worksheet("Trends")
        print("Updating existing Trends worksheet")
    except gspread.exceptions.WorksheetNotFound:
        # Create new Trends worksheet
        trends_worksheet = spreadsheet.add_worksheet(title="Trends", rows=200, cols=20)
        print("Created new Trends worksheet")

        # Add header for the Trends worksheet
        trends_worksheet.update_cell(1, 1, "Shopify Weekly Report Trends")
        trends_worksheet.format(
            "A1:J1", {"textFormat": {"bold": True}, "horizontalAlignment": "CENTER"}
        )
        trends_worksheet.merge_cells("A1:J1")

        # Add column headers
        trend_headers = [
            "Week Start Date",
            "Total Orders",
            "Total Revenue",
            "Average Order Value",
            "Total Customers",
            "Active Customers",
            "Total Fulfillments",
        ]
        trends_worksheet.update(values=[trend_headers], range_name="A3:G3")
        trends_worksheet.format(
            "A3:G3",
            {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
            },
        )

    # Get all existing trend data
    trends_data = trends_worksheet.get_all_values()

    # Find the current week in trends data (if it exists)
    current_week_start = start_date.strftime("%Y-%m-%d")
    week_exists = False
    row_to_update = len(trends_data) + 1

    if len(trends_data) > 3:  # If we have data rows (header + column names + data)
        for i, row in enumerate(trends_data[3:], 4):  # Start from row 4 (1-based)
            if row and row[0] == current_week_start:
                week_exists = True
                row_to_update = i
                break

    # Prepare the data for this week
    week_trend_data = [
        current_week_start,
        int(summary_data["total_orders"]),
        float(summary_data["total_revenue"]),
        float(summary_data["avg_order_value"]),
        int(summary_data["total_customers"]),
        int(summary_data["active_customers"]),
        int(summary_data["total_fulfillments"]),
    ]

    # Update or add this week's data
    if week_exists:
        # Update existing row
        trends_worksheet.update(
            values=[week_trend_data], range_name=f"A{row_to_update}:G{row_to_update}"
        )
    else:
        # Add new row
        trends_worksheet.append_row(week_trend_data)

    # Add charts to the Trends worksheet if they don't exist
    # (This would need to be implemented with Google Sheets API)
    # Currently the gspread library has limited chart creation abilities

    print(f"Successfully uploaded data to Google Sheets: {spreadsheet.title}")
    print(f"Spreadsheet URL: https://docs.google.com/spreadsheets/d/{spreadsheet.id}")

    return spreadsheet.id


# ------------------------------------------------------------------------------
# Main Reporting Functions
# ------------------------------------------------------------------------------


def generate_weekly_report(week_range=None):
    """Generate a report for a specific week."""
    if week_range is None:
        # Default to previous week
        week_range = get_previous_week_range()

    start_date, end_date = week_range

    # Create date-based filename for each week's report
    week_str = f"{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}"
    filename_prefix = f"shopify_report_{week_str}"

    print(
        f"\nShopify Weekly Report: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
    )
    print("=" * 75)

    # Create an authenticated session
    session = get_session()

    # First test connection to the shop
    try:
        shop_endpoint = f"{API_BASE_URL}/shop.json"
        shop_response = session.get(shop_endpoint)
        shop_response.raise_for_status()
        shop_data = shop_response.json().get("shop", {})
        print(
            f"Connected to Shopify store: {shop_data.get('name')} ({shop_data.get('domain')})"
        )
    except Exception as e:
        print(f"Error connecting to Shopify store: {e}")
        raise

    # Initialize DataFrames
    orders_df = pd.DataFrame()
    products_df = pd.DataFrame()
    customers_df = pd.DataFrame()
    analytics_df = pd.DataFrame()
    fulfillments_df = pd.DataFrame()
    reports_df = pd.DataFrame()

    # Try to fetch each type of data, but continue even if one fails

    # Orders
    try:
        orders_df = get_orders(session, week_range)
        display_dataframe(
            orders_df,
            f"Orders ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})",
        )
    except Exception as e:
        print(f"Error fetching orders: {e}")
        print("Continuing with other data...")

    # Products
    try:
        products_df = get_products(session)
        display_dataframe(products_df, "Products and Inventory (Current Snapshot)")
    except Exception as e:
        print(f"Error fetching products: {e}")
        print("Continuing with other data...")

    # Customers - this might fail with 500 error
    try:
        customers_df = get_customers(session, week_range)
        display_dataframe(customers_df, "Customers (with weekly activity flag)")
    except Exception as e:
        print(f"Error fetching customers: {e}")
        print("Skipping customers data due to Shopify API error...")

    # Analytics
    try:
        analytics_df = get_analytics(session, week_range)
        display_dataframe(
            analytics_df,
            f"Analytics ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})",
        )
    except Exception as e:
        print(f"Error fetching analytics: {e}")
        print("Continuing with other data...")

    # Fulfillments
    try:
        fulfillments_df = get_fulfillments(session, week_range)
        display_dataframe(
            fulfillments_df,
            f"Fulfillments ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})",
        )
    except Exception as e:
        print(f"Error fetching fulfillments: {e}")
        print("Continuing with other data...")

    # Reports
    try:
        reports_df = get_reports(session)
        display_dataframe(reports_df, "Available Reports")
    except Exception as e:
        print(f"Error fetching reports: {e}")
        print("Continuing with other data...")

    # Calculate weekly summary metrics
    summary = {
        "report_period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
        "total_orders": len(orders_df) if not orders_df.empty else 0,
        "total_revenue": (
            orders_df["total_price"].astype(float).sum() if not orders_df.empty else 0
        ),
        "avg_order_value": (
            orders_df["total_price"].astype(float).mean() if not orders_df.empty else 0
        ),
        "total_products": (
            len(products_df["product_id"].unique()) if not products_df.empty else 0
        ),
        "total_variants": len(products_df) if not products_df.empty else 0,
        "total_customers": len(customers_df) if not customers_df.empty else 0,
        "active_customers": (
            customers_df["ordered_this_week"].sum()
            if not customers_df.empty and "ordered_this_week" in customers_df.columns
            else 0
        ),
        "total_fulfillments": len(fulfillments_df) if not fulfillments_df.empty else 0,
    }

    # Print summary
    print("\n" + "=" * 50)
    print("  WEEKLY SUMMARY")
    print("=" * 50)
    for key, value in summary.items():
        if "total_revenue" in key or "avg_order_value" in key:
            print(f"{key}: ${value:.2f}")
        else:
            print(f"{key}: {value}")

    # Export data to CSV files
    print("\nExporting data to CSV files...")

    # Create output directory if it doesn't exist
    os.makedirs("reports", exist_ok=True)

    # Export data to CSV files
    if not orders_df.empty:
        orders_df.to_csv(f"reports/{filename_prefix}_orders.csv", index=False)

    if not products_df.empty:
        products_df.to_csv(f"reports/{filename_prefix}_products.csv", index=False)

    if not customers_df.empty:
        customers_df.to_csv(f"reports/{filename_prefix}_customers.csv", index=False)

    if not fulfillments_df.empty:
        fulfillments_df.to_csv(
            f"reports/{filename_prefix}_fulfillments.csv", index=False
        )

    # Export summary as a single-row DataFrame
    pd.DataFrame([summary]).to_csv(
        f"reports/{filename_prefix}_summary.csv", index=False
    )

    print(f"Data exported to reports/{filename_prefix}_*.csv files.")

    return {
        "orders": orders_df,
        "products": products_df,
        "customers": customers_df,
        "analytics": analytics_df,
        "fulfillments": fulfillments_df,
        "reports": reports_df,
        "summary": summary,
    }


def main():
    """Main function to execute the Shopify data retrieval process."""
    try:
        # Check if an environment variable or config file has a spreadsheet ID
        spreadsheet_id = os.getenv("SPREADSHEET_ID", None)

        # Default to previous week for the weekly report
        report_data = generate_weekly_report()

        print("\nWeekly report generation completed successfully!")
        print("CSV files have been saved to the 'reports' directory.")

        if not spreadsheet_id:
            # Ask user if they want to upload to Google Sheets
            upload_to_sheets = (
                input("\nDo you want to upload this data to Google Sheets? (y/n): ")
                .strip()
                .lower()
            )

            if upload_to_sheets == "y" or upload_to_sheets == "yes":
                # Ask if they want to update an existing sheet
                use_existing = (
                    input("Do you want to update an existing Google Sheet? (y/n): ")
                    .strip()
                    .lower()
                )

                if use_existing == "y" or use_existing == "yes":
                    spreadsheet_id = input(
                        "Enter the Google Spreadsheet ID (from the URL): "
                    ).strip()
                    if not spreadsheet_id:
                        print("No spreadsheet ID provided. Creating a new spreadsheet.")
                        spreadsheet_id = None
                else:
                    spreadsheet_id = None

                # Get previous week's date range
                week_range = get_previous_week_range()
                spreadsheet_id = upload_to_google_sheets(
                    report_data, week_range, spreadsheet_id
                )

                # Save the spreadsheet ID to a config file for future use
                with open("spreadsheet_config.txt", "w") as f:
                    f.write(spreadsheet_id)
                print(
                    f"Spreadsheet ID saved to 'spreadsheet_config.txt' for future use"
                )
            else:
                print("Skipping Google Sheets upload.")
        else:
            # If running automated, always upload to the spreadsheet
            print(f"Using existing spreadsheet ID: {spreadsheet_id}")
            week_range = get_previous_week_range()
            upload_to_google_sheets(report_data, week_range, spreadsheet_id)

        return report_data

    except Exception as e:
        print(f"\nAn error occurred: {e}")
        raise


if __name__ == "__main__":
    main()
