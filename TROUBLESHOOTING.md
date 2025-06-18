# Troubleshooting Guide

## Google Sheets Not Updating Issue (Fixed)

### Problem

Your Google Sheets weren't being updated weekly despite GitHub Actions showing successful runs. The issue was that the `historical-incremental` mode only processed the current and previous week, missing weeks since 06-01.

### Root Cause

1. **Incremental Mode Limitation**: The original `historical-incremental` mode only processed current and previous week
2. **Missing Catch-up Logic**: No mechanism to fill gaps when weeks were missed
3. **Workflow Configuration**: GitHub Actions was using incremental mode by default

### Solution Implemented

#### 1. Enhanced Incremental Mode

- Added catch-up logic to automatically fill missing weeks since 06-01
- Now processes current week, previous week, AND all missing weeks in between

#### 2. New "Catch-up" Mode

- Dedicated mode specifically for filling missing weeks
- Can be run manually or automatically

#### 3. Improved GitHub Actions Workflow

- Better error handling and logging
- Uses saved spreadsheet ID from config file
- Verifies Google Sheets updates actually occurred

### How to Fix Missing Weeks

#### Option 1: Run Catch-up Script (Recommended)

```bash
python run_catchup.py
```

#### Option 2: Manual GitHub Actions Run

1. Go to your GitHub repository
2. Click "Actions" tab
3. Select "Weekly Shopify Report" workflow
4. Click "Run workflow"
5. Select "catch-up" mode
6. Click "Run workflow"

#### Option 3: Command Line

```bash
python shopify_reports.py --mode catch-up --spreadsheet-id YOUR_SPREADSHEET_ID
```

### Prevention Measures

#### 1. Updated Default Mode

- GitHub Actions now uses "catch-up" mode by default for scheduled runs
- This ensures missing weeks are automatically filled

#### 2. Better Error Handling

- Workflow now verifies Google Sheets updates actually occurred
- Fails fast if updates don't work

#### 3. Enhanced Logging

- More detailed logs to identify issues
- Spreadsheet ID tracking and verification

### Verification Steps

After running the catch-up process:

1. **Check GitHub Actions Logs**:

   - Look for "✅ Historical summary found" message
   - Verify spreadsheet ID is being used correctly

2. **Check Google Sheets**:

   - Open your spreadsheet
   - Look for "Weekly_Trends" worksheet
   - Verify weeks since 06-01 are now populated

3. **Check Local Files**:
   - `reports/historical_summary.json` should exist
   - `spreadsheet_config.txt` should contain your spreadsheet ID

### Future Prevention

The enhanced system will now:

- Automatically catch up on missing weeks during regular runs
- Provide better error messages if updates fail
- Save and reuse spreadsheet IDs consistently
- Verify updates actually occurred before marking as successful

### If Issues Persist

1. **Check Credentials**: Ensure Google service account key is valid
2. **Check Permissions**: Verify the service account has write access to the spreadsheet
3. **Check Rate Limits**: The script includes delays to respect Shopify API limits
4. **Check Network**: Ensure GitHub Actions can reach both Shopify and Google APIs

### Contact

If you continue to have issues, check:

1. GitHub Actions logs for specific error messages
2. The `reports/historical_summary.json` file for processing details
3. Your Google Sheets sharing permissions
