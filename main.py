import subprocess
import json
import os
import xml.etree.ElementTree as ET
from googleapiclient.discovery import build
from google.oauth2 import service_account
from dotenv import load_dotenv
import requests


load_dotenv()

# Google Sheets API setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = "credentials.json"  # Path to your service account file
SPREADSHEET_ID = os.getenv("SHEET_ID")  # Replace with your spreadsheet ID
SHEET_NAME = 'Sheet1'  # Replace with your sheet name


creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)

#load in json file from lighthouse-auditor/audits.json
with open('audits.json', 'r') as file:
    audits = json.load(file)


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

def write_issues(row, url):
    report_path = f"reports/{url.replace('https://', '').replace('/', '_')}.json"
    with open(report_path, "r", encoding="utf-8") as report_file:
        report_data = json.load(report_file)
        allIssues = report_data["audits"]

    issues = []
    for issue in allIssues:
        if allIssues[issue]["score"] == 0:
            issues.append(allIssues[issue]["title"])
    
    sheet = service.spreadsheets()
    sheet_name = url.split('//')[1].split('.')[0]


    #Add a new sheet to the spreadsheet if it doesn't exist
    try:
        sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f"{sheet_name}!A1").execute()
    except:
        sheet.batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={
                "requests": [
                    {
                        "addSheet": {
                            "properties": {
                                "title": sheet_name,
                            }
                        }
                    }
                ]
            }
        ).execute()

    # Add headers to the new sheet
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet_name}!A{row}:B{row}",
        valueInputOption="USER_ENTERED",
        body={"values": [["Issues"]]}
    ).execute()

    # Write back the issues to the Google Sheet
    for i, issue in enumerate(issues):
        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{sheet_name}!A{row+i+1}:B{row+i+1}",
            valueInputOption="USER_ENTERED",
            body={"values": [[issue]]}
        ).execute()

    return len(issues)


def write_results(row, url, accessibility_score):
    sheet = service.spreadsheets()
    sheet_name = url.split('//')[1].split('.')[0]

    #Add a new sheet to the spreadsheet if it doesn't exist
    try:
        sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f"{sheet_name}!A1").execute()
    except:
        sheet.batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={
                "requests": [
                    {
                        "addSheet": {
                            "properties": {
                                "title": sheet_name,
                            }
                        }
                    }
                ]
            }
        ).execute()


    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet_name}!A{row}:B{row}",
        valueInputOption="USER_ENTERED",
        body={"values": [["URL", "Accessibility Score"]]}
    ).execute()

    # Writing the URL, accessibility score, and report path back to the Google Sheet
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet_name}!A{row+1}:b{row+1}",
        valueInputOption="USER_ENTERED",
        body={"values": [[url, accessibility_score]]}
    ).execute()

    # Write back the issues to the Google Sheet
    if accessibility_score != -1:
        return write_issues(row+2, url)
    
    return 0

def parse_xml():

    LIMIT = 3
    websites = audits['websites']
    page_audits = {}
     

    for name in websites:
        page_audits[name] = []

        try:
            response = requests.get(websites[name])
            response.raise_for_status()

            #parse the xml file
            root = ET.fromstring(response.content)

            for url in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
                page_audits[name].append(url.text)
                
                if(len(page_audits[name]) >= LIMIT):
                    break
        
        except requests.exceptions.RequestException as e:
            print(e)
    

    return page_audits


def main():

    page_audits = parse_xml()

    for name in page_audits:
        urls = page_audits[name]
        count = 0
        for i , url in enumerate(urls):
            accessibility_score = audit_page(url)
            count += write_results(1+count+5*i, url, accessibility_score)

if __name__ == "__main__":
    main()
