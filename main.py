import subprocess
import json
import os
import xml.etree.ElementTree as ET
from googleapiclient.discovery import build
from google.oauth2 import service_account
from dotenv import load_dotenv
import requests
import csv


load_dotenv()

# Google Sheets API setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = "credentials.json"  # Path to your service account file
SPREADSHEET_ID = os.getenv("SHEET_ID")  # Replace with your spreadsheet ID
SHEET_NAME = 'Sheet1'  # Replace with your sheet name


creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)

audits = []

with open('audits.csv', mode='r') as file:
    csv_reader = csv.DictReader(file)
    audits = [row['URL'] for row in csv_reader]  # List comprehension inside the 'with' block


def audit_page(url):
    report_path = f"reports/{url.replace('https://', '').replace('/', '_')}.json"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    lighthouse_path = os.getenv("LIGHTHOUSE_PATH")  # Path to Lighthouse CLI

    try:
        # Run Lighthouse to audit the page
        command = [
            lighthouse_path,
            url,
            "--output=json",
            "--output-path=" + report_path,
            "--only-categories=accessibility",
            "--chrome-flags=--headless"
        ]
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        return -1

    # Load and parse the Lighthouse report
    with open(report_path, "r", encoding="utf-8") as report_file:
        report_data = json.load(report_file)
        accessibility_score = report_data["categories"]["accessibility"]["score"]

    return accessibility_score

def write_issues(index, url):
    report_path = f"reports/{url.replace('https://', '').replace('/', '_')}.json"
    with open(report_path, "r", encoding="utf-8") as report_file:
        report_data = json.load(report_file)
        allIssues = report_data["audits"]

    issues = []
    for issue in allIssues:
        if allIssues[issue]["score"] == 0:
            issues.append(allIssues[issue]["title"])
    
    sheet = service.spreadsheets()

    issue_str = "\n".join(issues)
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"Sheet1!D{index}",
        valueInputOption="USER_ENTERED",
        body={"values": [[issue_str]]}
    ).execute()

    return

def write_results(index, url, accessibility_score):
    sheet = service.spreadsheets()
    sheet_name = url.split('//')[1].split('.')[0]

    #Add a new sheet to the spreadsheet if it doesn't exist
    try:
        sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f"Sheet1!A1").execute()
    except:
        sheet.batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={
                "requests": [
                    {
                        "addSheet": {
                            "properties": {
                                "title": "Sheet1",
                            }
                        }
                    }
                ]
            }
        ).execute()

    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"Sheet1!A1:D1",
        valueInputOption="USER_ENTERED",
        body={"values": [["Site", "URL", "Accessibility Score", "Issues"]]}
    ).execute()

    # Writing the URL, accessibility score, and report path back to the Google Sheet
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"Sheet1!A{index}:C{index}",
        valueInputOption="USER_ENTERED",
        body={"values": [[sheet_name, url, accessibility_score]]}
    ).execute()

    # Write back the issues to the Google Sheet
    if accessibility_score != -1:
        return write_issues(index, url)

    return

def parse_xml(limit):

    page_audits = []

    current_limit = 0
     
    for url in audits:

        try:
            response = requests.get(url+"/sitemap.xml")
            response.raise_for_status()

            #parse the xml file
            root = ET.fromstring(response.content)

            for sub_url in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):

                if '?' in sub_url.text:
                    continue

                if current_limit == limit:
                    current_limit = 0
                    break

                current_limit += 1

                page_audits.append(sub_url.text)
    
        
        except requests.exceptions.RequestException as e:
            print(e)
    

    return page_audits


def delete_reports():
    # Get list of sheets
    sheet_metadata = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    all_sheets = sheet_metadata.get("sheets", [])

    # Ensure there is more than one sheet to delete
    if len(all_sheets) > 1:
        # Delete all sheets except the first one
        for sheet in all_sheets[1:]:
            sheet_id = sheet["properties"]["sheetId"]
            service.spreadsheets().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={
                    "requests": [
                        {
                            "deleteSheet": {
                                "sheetId": sheet_id
                            }
                        }
                    ]
                }
            ).execute()


    #Clear the first sheet
    sheet_name = all_sheets[0]["properties"]["title"]
    sheet = service.spreadsheets()
    sheet.values().clear(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet_name}!A1:Z1000"
    ).execute()

    #rename the first sheet to Sheet1
    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": all_sheets[0]["properties"]["sheetId"],
                            "title": "Sheet1"
                        },
                        "fields": "title"
                    }
                }
            ]
        }
    ).execute()

    print("All reports have been deleted")

def main():

    options = None

    print("1. Run audit only on routes")
    print("2. Run audit on sitemap.xml")
    print("3. Delete all reports")
    options = int(input("Enter your choice: "))


    if options == 1:
        pass
    
    elif options == 2:
        print("Enter the limit of URLs you would like to audit in the sitemaps")
        limit = int(input("Enter the limit:"))
        audits = parse_xml(limit)

    elif options == 3:
        delete_reports()
        return
    
    else:
        print("Invalid choice")
        return

    idx = 2
    for url in audits:
        accessibility_score = audit_page(url)
        if accessibility_score != -1:
            write_results(idx, url, accessibility_score)
            idx += 1

if __name__ == "__main__":
    main()