# Lighthouse Auditor

A Python-based automation tool that audits websites for accessibility using Google Lighthouse and records the results in a Google Sheets document. This tool is designed to streamline accessibility checks for multiple websites by automatically capturing scores and details, saving them in a centralized spreadsheet for easy review and tracking.

## Features

- Runs Google Lighthouse audits on a list of URLs provided in Google Sheets.
- Audits are focused on accessibility scoring.
- Results are written back to Google Sheets, including audit scores and details

## Requirements

- Python 3.x
- npm 10.x
- Google Cloud project set up with Sheets API and OAuth credentials

## Setup

### 1. Clone the repository
```bash
git clone git@github.com:Abejithp/lighthouse-auditor.git
cd lighthouse-auditor
```

### 2. Set up a Google Cloud Project

1. **Create a new project** in the [Google Cloud Console](https://console.cloud.google.com/).
   
2. **Enable the Google Sheets API** for the project:
   - In the **APIs & Services** section, click **Library**.
   - Search for "Google Sheets API" and enable it for your project.

3. **Generate and Service credentials**:
   - Go to **APIs & Services > Credentials**.
   - Click **Create Credentials** and select **Service Account**.
   - Complete the Service Account details and provide it with owner permissions
   - Click on your created Service Account and go to **Keys**
   - Create a new key in json format
   
4. **Save the credentials**:
   - Rename the downloaded file to `credentials.json`.
   - Place `credentials.json` in the root of your project directory.

5. **Add Service Account**
   - copy the email of the service account you have created.
   - create a new **google sheet** and share the sheet to the copied email with **editor** permissions

### 3. Install dependencies

Set up a virtual environment and install the required libraries:

```bash
pip install -r requirements.txt
```

```bash
npm install -g lighthouse
```

### 4. Configure Environment Variables

Create a `.env` file in the root of your project directory to store environment variables needed for the script. Add the following entries:

```plaintext
SPREADSHEET_ID=<Your Google Sheets spreadsheet ID>
LIGHTHOUSE_PATH=<Path to your Lighthouse CLI binary>
```

The spreadsheet id can be found within the link of the google sheet you have created

```plaintext
https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit?gid=0#gid=0
```
On windows the lighthouse path is typically at:
```plaintext
C:\Users\<YourUsername>\AppData\Roaming\npm\lighthouse.cmd
```

on linux or mac use the following command to find the path:
```bash
which lighthouse
```
### 5. Prepare the Audit Configuration

The tool uses an `audit.csv` file to configure the websites to be audited. This file includes one column of URLS to be audited. Simply add any additional URLs to this file that you would like to audit.

The tool includes `config.json` where you can specify the categories you want to target for the lighthouse audit. To enable a category simply modify the values to be `true`

## Usage

To begin the auditing process, run the following command in your terminal and follow the interactive prompts:

```bash
python main.py 
```


### Check the Results

After the auditing process completes, results will be saved in a reports folder generated at the root of the project. Each issue found during the audit will also be documented in your specified Google Sheet.

### Modify as Needed

Feel free to modify the code or configuration files to better suit your specific requirements or to add additional functionality.
