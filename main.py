import subprocess
import json
import os
from googleapiclient.discovery import build
from google.oauth2 import service_account
from dotenv import load_dotenv


load_dotenv()

# Google Sheets API setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = "lighthouse-auditor\credentials.json"  # Path to your service account file
SPREADSHEET_ID = os.getenv("SHEET_ID")  # Replace with your spreadsheet ID
SHEET_NAME = 'Sheet1'  # Replace with your sheet name

creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)

def audit_page(url):
    report_path = f"lighthouse-auditor/reports/{url.replace('https://', '').replace('/', '_')}.json"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    lighthouse_path = os.getenv("LIGHTHOUSE_PATH")  # Path to Lighthouse CLI

    # Run Lighthouse to audit the page
    command = [
        lighthouse_path,
        url,
        "--output=json",
        "--output-path=" + report_path,
        "--only-categories=accessibility",
        "--chrome-flags=--headless"
    ]
    subprocess.run(command)

    # Load and parse the Lighthouse report
    with open(report_path, "r") as report_file:
        report_data = json.load(report_file)
        accessibility_score = report_data["categories"]["accessibility"]["score"]
    
    return accessibility_score

def write_results(row, url, accessibility_score):
    sheet = service.spreadsheets()
    # Writing the URL, accessibility score, and report path back to the Google Sheet
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A{row}:b{row}",
        valueInputOption="USER_ENTERED",
        body={"values": [[url, accessibility_score]]}
    ).execute()

def main():

    urls = ["https://doris.digital.utsc.utoronto.ca/", "https://arabww.digital.utsc.utoronto.ca/"] # List of URLs to audit
    
    sheet = service.spreadsheets()
    # Clear the existing accessibility score data
    sheet.values().clear(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!B2:B",
    ).execute()

    # Write labels to the Google Sheet
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A1:B1",
        valueInputOption="USER_ENTERED",
        body={"values": [["Website", "Accessibility Score"]]}
    ).execute()


    for idx, url in enumerate(urls, start=2):  # Start from row 2 (assuming headers in row 1)
        accessibility_score = audit_page(url)
        write_results(idx, url, accessibility_score)  # Write results back to Google Sheet

if __name__ == "__main__":
    main()
