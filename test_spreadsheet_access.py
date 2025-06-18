#!/usr/bin/env python3
"""
Test script to diagnose Google Sheets access issues
"""

import json
from oauth2client.service_account import ServiceAccountCredentials
import gspread


def test_credentials():
    """Test if credentials can be loaded"""
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            "supple-life-437019-e0-f2c2876fac24.json",
            [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        print(f"✅ Credentials loaded successfully")
        print(f"📧 Service account email: {creds.service_account_email}")
        return creds
    except Exception as e:
        print(f"❌ Error loading credentials: {e}")
        return None


def test_spreadsheet_access(creds, spreadsheet_id):
    """Test if we can access the specific spreadsheet"""
    try:
        client = gspread.authorize(creds)
        print(f"✅ Successfully authorized with Google Sheets API")

        # Try to open the spreadsheet
        spreadsheet = client.open_by_key(spreadsheet_id)
        print(f"✅ Successfully accessed spreadsheet: {spreadsheet.title}")
        print(f"📊 Spreadsheet URL: {spreadsheet.url}")

        # List worksheets
        worksheets = spreadsheet.worksheets()
        print(f"📋 Found {len(worksheets)} worksheets:")
        for ws in worksheets:
            print(f"   - {ws.title}")

        return True

    except gspread.exceptions.SpreadsheetNotFound:
        print(f"❌ Spreadsheet not found with ID: {spreadsheet_id}")
        print("   This could mean:")
        print("   1. The spreadsheet ID is incorrect")
        print("   2. The service account doesn't have access")
        return False

    except Exception as e:
        if "Invalid JWT Signature" in str(e):
            print(f"❌ JWT Signature error - this usually means:")
            print("   1. The service account key is expired or revoked")
            print("   2. The service account doesn't have access to the spreadsheet")
            print("   3. The Google Cloud project is disabled")
        else:
            print(f"❌ Error accessing spreadsheet: {e}")
        return False


def main():
    print("🔍 Testing Google Sheets Access")
    print("=" * 50)

    # Test credentials
    creds = test_credentials()
    if not creds:
        return

    print()

    # Test spreadsheet access
    spreadsheet_id = "1myLxIKgWuaw3Ipza06I18opSGzB1S8hukUBcEDwX6k4"
    success = test_spreadsheet_access(creds, spreadsheet_id)

    print()
    print("=" * 50)

    if not success:
        print("🔧 TO FIX THIS ISSUE:")
        print()
        print("1. Open your Google Sheet:")
        print(f"   https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
        print()
        print("2. Click the 'Share' button (top right)")
        print()
        print("3. Add this email address:")
        print(f"   {creds.service_account_email}")
        print()
        print("4. Set permissions to 'Editor'")
        print()
        print("5. Click 'Send' (uncheck 'Notify people')")
        print()
        print("6. Run this test again to verify access")
    else:
        print("✅ Everything is working correctly!")
        print("Your Google Sheets integration should work now.")


if __name__ == "__main__":
    main()
