#!/usr/bin/env python3
"""
Quick script to run the catch-up process for missing weeks since 06-01.
This will fill in all the missing weeks in your Google Sheets.
"""

import subprocess
import sys
import os


def main():
    print("🔄 Running Shopify catch-up process to fill missing weeks since 06-01...")
    print("This will update your Google Sheets with all missing data.")
    print()

    # Check if the main script exists
    if not os.path.exists("shopify_reports.py"):
        print("❌ Error: shopify_reports.py not found in current directory")
        sys.exit(1)

    # Check if credentials exist
    if not os.path.exists("supple-life-437019-e0-f2c2876fac24.json"):
        print("❌ Error: Google service account credentials not found")
        print(
            "Please ensure supple-life-437019-e0-f2c2876fac24.json is in the current directory"
        )
        sys.exit(1)

    # Check for spreadsheet ID
    spreadsheet_id = None
    if os.path.exists("spreadsheet_config.txt"):
        with open("spreadsheet_config.txt", "r") as f:
            spreadsheet_id = f.read().strip()
        print(f"📊 Using existing spreadsheet ID: {spreadsheet_id}")
    else:
        print("⚠️  No existing spreadsheet ID found. Will create new spreadsheet.")

    # Run the catch-up process
    try:
        cmd = ["python", "shopify_reports.py", "--mode", "catch-up"]
        if spreadsheet_id:
            cmd.extend(["--spreadsheet-id", spreadsheet_id])

        print(f"🚀 Running command: {' '.join(cmd)}")
        print()

        result = subprocess.run(cmd, capture_output=False, text=True)

        if result.returncode == 0:
            print()
            print("✅ Catch-up process completed successfully!")
            print("📊 Your Google Sheets should now be updated with all missing weeks.")

            # Check if summary was created
            if os.path.exists("reports/historical_summary.json"):
                print("📋 Summary report created in reports/historical_summary.json")
        else:
            print()
            print("❌ Catch-up process failed with return code:", result.returncode)
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⏹️  Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error running catch-up process: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
