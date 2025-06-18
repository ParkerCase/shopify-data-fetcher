# Shopify Weekly Reports

This script fetches data from Shopify's Admin API and creates weekly reports in both CSV format and Google Sheets.

## Features

- Fetches orders, products, customers, and fulfillments from Shopify
- Filters data by week (Monday to Sunday, Mountain Time)
- Exports CSV reports
- Uploads data to Google Sheets
- Maintains a Trends tab for week-by-week comparison
- Can be scheduled to run automatically using GitHub Actions

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up API Credentials

Create a `.env` file with your Shopify API credentials:

```
SHOP_NAME=tatt-2-away.myshopify.com
API_KEY=8d236638adbd963ec050de036c97d2bc
PASSWORD=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
API_VERSION=2025-04
```

### 3. Google Sheets Setup

1. Make sure your Google service account JSON file (`supple-life-437019-e0-f2c2876fac24.json`) is in the project directory
2. The script will create a spreadsheet and share it with your email

### 4. Running the Script

```bash
python shopify_reports.py
```

The script will:

1. Fetch data from Shopify for the previous week (Monday to Sunday, Mountain Time)
2. Save CSV files to the `reports` directory
3. Ask if you want to upload to Google Sheets
4. If yes, ask if you want to update an existing sheet or create a new one

### 5. Setting up Automated Weekly Reports with GitHub Actions

1. Create a GitHub repository for your script by following these steps:

   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/yourusername/shopify-reports.git
   git push -u origin main
   ```

2. In your GitHub repository, go to Settings > Secrets and Variables > Actions

3. Add the following secrets:

   - `SHOP_NAME`: Your Shopify store name (tatt-2-away.myshopify.com)
   - `API_KEY`: Your Shopify API key
   - `PASSWORD`: Your Shopify API password
   - `API_VERSION`: Your Shopify API version (2025-04)
   - `SPREADSHEET_ID`: ID of your Google Sheet (from the URL)
   - `GOOGLE_SERVICE_ACCOUNT_KEY`: The entire contents of your service account JSON file

4. Create a `.github/workflows` directory in your repository and add the provided workflow file:

   ```bash
   mkdir -p .github/workflows
   cp github-actions-workflow.yml .github/workflows/shopify-report.yml
   git add .github/workflows/shopify-report.yml
   git commit -m "Add GitHub Actions workflow"
   git push
   ```

5. The workflow will run automatically every Monday at 1:00 AM UTC (7:00 PM Sunday Mountain Time)

## Understanding the Weekly Reports Structure

The script creates a comprehensive Google Sheet with:

1. **Weekly Tabs**: Each tab named "Week YYYY-MM-DD" contains the complete data for that week

2. **Data Type Tabs**: There are separate tabs for Orders, Products, Customers, etc. that are updated with current data each run

3. **Trends Tab**: A special tab that tracks key metrics across all weeks for easy comparison:
   - Week Start Date
   - Total Orders
   - Total Revenue
   - Average Order Value
   - Total Customers
   - Active Customers
   - Total Fulfillments

This structure allows you to:

- See all details for a specific week in the weekly tabs
- Compare week-by-week performance in the Trends tab
- Look at all historical data for a specific data type (e.g., all orders)

## Customizing the Reports

If you need to modify the script to include additional metrics or change the format:

1. For new metrics, add them to the `summary` dictionary in the `generate_weekly_report()` function
2. To add them to the Trends tab, update the `trend_headers` and `week_trend_data` lists in `upload_to_google_sheets()`

## Troubleshooting

- If you see "You need access" errors, make sure your service account has properly shared the document with your email
- If you encounter SSL certificate issues, the script includes a workaround to disable SSL verification
- To test the GitHub Actions workflow without waiting for the scheduled time, you can manually trigger it from the Actions tab in your repository
