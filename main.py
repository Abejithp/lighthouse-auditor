import subprocess
import json
import os
import xml.etree.ElementTree as ET
from googleapiclient.discovery import build
from google.oauth2 import service_account
from dotenv import load_dotenv
import requests
import csv
from bs4 import BeautifulSoup
import time

# Load environment variables from .env file
load_dotenv()

# Google Sheets API setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = "credentials.json"  # Path to your service account file
SPREADSHEET_ID = os.getenv("SHEET_ID")  # Replace with your spreadsheet ID
SHEET_NAME = 'Sheet1'  # Replace with your sheet name
MAX_LIMIT = 100000

# Authenticate and build the Google Sheets service
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)

# Define categories and their corresponding columns in the spreadsheet
categories = {
    "performance": {"title": "Performance", "column": "C"},
    "accessibility": {"title": "Accessibility", "column": "E"},
    "best-practices": {"title": "Best Practices", "column": "F"},
    "seo": {"title": "SEO", "column": "H"},
}
columns = ["C", "E", "G", "H"]

# Load configuration from config.json
with open("config.json", "r", encoding="utf-8") as config:
    report_data = json.load(config)
    idx = 0
    for category in list(report_data["categories"]):
        if report_data["categories"][category] == 1:
            os.makedirs(f"reports/{category}", exist_ok=True)
            categories[category]["column"] = columns[idx]
            idx += 1
        else:
            categories.pop(category)

# Load URLs to be audited from audits.csv
with open('audits.csv', mode='r') as file:
    csv_reader = csv.DictReader(file)
    audits = [row['URL'] for row in csv_reader]

# Function to run Lighthouse audit on a given URL and category
def audit_page(url, category):
    report_path = f"reports/{category}/{url.replace('https://', '').replace('/', '_')}.json"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    lighthouse_path = os.getenv("LIGHTHOUSE_PATH")  # Path to Lighthouse CLI

    try:
        command = [
            lighthouse_path,
            url,
            "--output=json",
            "--output-path=" + report_path,
            "--only-categories=" + category,
            "--chrome-flags=--headless"
        ]
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError:
        return -1

    with open(report_path, "r", encoding="utf-8") as report_file:
        report_data = json.load(report_file)
        return report_data["categories"][category]["score"]

# Function to initialize headers in the Google Sheets
def init_headers():
    sheet = service.spreadsheets()
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A1:B1",
        valueInputOption="USER_ENTERED",
        body={"values": [["Site", "URL"]]}
    ).execute()

    for category in categories.values():
        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!{category['column']}1",
            valueInputOption="USER_ENTERED",
            body={"values": [[category["title"] + " Score"]]}
        ).execute()
        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!{chr(ord(category['column']) + 1)}1",
            valueInputOption="USER_ENTERED",
            body={"values": [[category["title"] + " Issues"]]}
        ).execute()

# Function to write audit results to the Google Sheets
def write_results(index, url, score, category):
    sheet = service.spreadsheets()
    sheet_name = url.split('//')[1].split('.')[0]
    issue_col = chr(ord(categories[category]["column"]) + 1)

    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A{index}:C{index}",
        valueInputOption="USER_ENTERED",
        body={"values": [[sheet_name, url]]}
    ).execute()

    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!{categories[category]['column']}{index}",
        valueInputOption="USER_ENTERED",
        body={"values": [[score]]}
    ).execute()

    report_path = f"reports/{category}/{url.replace('https://', '').replace('/', '_')}.json"
    with open(report_path, "r", encoding="utf-8") as report_file:
        report_data = json.load(report_file)
        issues = [audit["title"] for audit in report_data["audits"].values() if audit["score"] == 0]

    issue_str = "\n".join(issues)
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!{issue_col}{index}",
        valueInputOption="USER_ENTERED",
        body={"values": [[issue_str]]}
    ).execute()

# Function to parse sitemap.xml and extract URLs
def parse_xml(limit):
    page_audits = []
    sub_xml = []
    current_limit = 0

    for url in audits:
        try:
            response = requests.get(url + "/sitemap.xml")
            response.raise_for_status()
            root = ET.fromstring(response.content)

            for sub_url in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
                if '?' in sub_url.text:
                    sub_xml.append(sub_url.text)
                    continue   

                if current_limit == limit:
                    current_limit = 0
                    break
    
                page_audits.append(sub_url.text)
                current_limit += 1
                
        except requests.exceptions.RequestException as e:
            print(e)

        current_limit = 0


    for url in sub_xml:
        try:
            response = requests.get(url)
            response.raise_for_status()
            root = ET.fromstring(response.content)

            for sub_url in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
                if current_limit == limit:
                    current_limit = 0
                    break

                page_audits.append(sub_url.text)
                current_limit += 1

        except requests.exceptions.RequestException as e:
            print(e)

        current_limit = 0

    return page_audits

# Function to delete all reports from the Google Sheets
def delete_reports():
    sheet_metadata = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    all_sheets = sheet_metadata.get("sheets", [])

    if len(all_sheets) > 1:
        for sheet in all_sheets[1:]:
            sheet_id = sheet["properties"]["sheetId"]
            service.spreadsheets().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={"requests": [{"deleteSheet": {"sheetId": sheet_id}}]}
            ).execute()

    sheet_name = all_sheets[0]["properties"]["title"]
    sheet = service.spreadsheets()
    sheet.values().clear(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet_name}!A1:Z1000"
    ).execute()

    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": [{"updateSheetProperties": {"properties": {"sheetId": all_sheets[0]["properties"]["sheetId"], "title": "Sheet1"}, "fields": "title"}}]}
    ).execute()

    print("All reports have been deleted")

def write_broken(url, data, index):

    sheet = service.spreadsheets()

    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"Broken Links!A{index}:C{index}",
        valueInputOption="USER_ENTERED",
        body={"values": [[url, data[1], data[0]]]}
    ).execute()


def audit_links():

    sheet = service.spreadsheets()
    try:
        sheet.values().get(spreadsheetId=SPREADSHEET_ID, range="Broken Links!A1").execute()
        # Clear the existing data in the sheet:
        sheet.values().clear(
            spreadsheetId=SPREADSHEET_ID,
            range="Broken Links!A1:Z1000"
        ).execute()

    except:
        sheet.batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={
                "requests": [
                    {
                        "addSheet": {
                            "properties": {
                                "title": "Broken Links"
                            }
                        }
                    }
                ]
            }
        ).execute()

    #write headers
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range="Broken Links!A1:C1",
        valueInputOption="USER_ENTERED",
        body={"values": [["Base URL", "URL Text", "Broken URL"]]}
    ).execute()

    print("Parsing links from site map")

    links = parse_xml(20)
    audit = {}

    for link in links:
        audit[link] = []

    try:

        print("Finding search results pages")

        for link in links:
            response = requests.get(link)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')  

            base_url = link.split(".ca")[0] + ".ca"
            
            for a in soup.find_all('a', href=True):
                if('search-results' in a['href']):
                    if("http" in a['href']):
                        # check if the link is already in the audit
                        if a['href'] not in audit[link]:
                            audit[link].append(((a['href']), a.text))
                    else:
                        if (base_url + a['href'].replace(" ", "%20")) not in audit[link]:
                            audit[link].append(((base_url +  a['href'].replace(" ", "%20")), a.text))

    except requests.exceptions.RequestException as e:
        print(e)

    broken = {}
    index = 2

    for key in audit:
        broken[key] = []

    print("Auditing search results pages")

    for key in audit:
        urls = audit[key]

        for data in urls:
            url = data[0]
            print("Checking: " + url)

            try:
                response = requests.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')

                for p in soup.find_all('p'):
                    if('search returned no results' in p.text):
                        write_broken(key, data, index)
                        broken[key].append(data)
                        index += 1
            
            except requests.exceptions.RequestException as e:
                print(e)

            # add a delay to avoid getting blocked
            time.sleep(1)

    #write broken into a csv file
    open('broken_links.csv', 'w').close()
    with open('broken_links.csv', mode='w') as file:
        writer = csv.writer(file)
        writer.writerow(["Base URL", "URL Text", "Broken URL"])
        for key, value in broken.items():
            for v in value:
                writer.writerow([key, v[1], v[0]])

    print("Audit complete")

# Main function to run the script
def main():
    print("1. Run audit only on routes")
    print("2. Run audit on sitemap.xml")
    print("3. Delete all reports")
    print("4. Audit broken links")
    options = int(input("Enter your choice: "))

    if options == 1:
        pages = audits
    elif options == 2:
        limit = int(input("Enter the limit of URLs you would like to audit in the sitemaps: "))
        pages = parse_xml(limit)
    elif options == 3:
        delete_reports()
        return
    elif options == 4:
        audit_links()
        return
    else:
        print("Invalid choice")
        return

    init_headers()

    idx = 2
    for url in pages:
        for category in categories:
            score = audit_page(url, category)
            if score != -1:
                write_results(idx, url, score, category)
        idx += 1

if __name__ == "__main__":
    main()