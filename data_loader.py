import streamlit as st
import pandas as pd
import base64
import re
import requests
import io
import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def authenticate_gmail():
    creds = Credentials(
        token=None,
        refresh_token=st.secrets["GMAIL_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=st.secrets["GMAIL_CLIENT_ID"],
        client_secret=st.secrets["GMAIL_CLIENT_SECRET"]
    )
    return build('gmail', 'v1', credentials=creds)

@st.cache_data(ttl=3600)
def fetch_salary_data():
    service = authenticate_gmail()
    query = 'label:agl-pay-slips OR from:payroll@pafl.com.pk'
    results = service.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])

    salary_records = []

    def extract_amount(label, text):
        pattern = rf"{label}\D*?([\d,\.]+)"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            try:
                return float(match.group(1).replace(',', ''))
            except ValueError:
                return 0.0
        return 0.0

    for msg in messages:
        msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        
        headers = msg_data['payload']['headers']
        subject = next((header['value'] for header in headers if header['name'] == 'Subject'), "")
        month_match = re.search(r"Payslip\s+([A-Z]{3}-\d{4})", subject, re.IGNORECASE)
        month = month_match.group(1) if month_match else "Unknown Month"

        body_text = ""
        if 'parts' in msg_data['payload']:
            for part in msg_data['payload']['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data')
                    if data:
                        body_text += base64.urlsafe_b64decode(data).decode('utf-8')
                elif part['mimeType'] == 'text/html':
                    data = part['body'].get('data')
                    if data:
                        html_text = base64.urlsafe_b64decode(data).decode('utf-8')
                        body_text += re.sub('<[^<]+>', ' ', html_text)
        else:
            data = msg_data['payload']['body'].get('data')
            if data:
                html_text = base64.urlsafe_b64decode(data).decode('utf-8')
                body_text = re.sub('<[^<]+>', ' ', html_text)

        salary_records.append({
            "Month": month,
            "Basic Pay": extract_amount("Basic Salary", body_text),
            "Hard Area": extract_amount("Hard Area Allowance", body_text),
            "House Rent Allowance": extract_amount("House Rent Allowance", body_text),
            "Other Earnings": extract_amount("Other Earnings", body_text),
            "Salary Arrears": extract_amount("Salary Arrears", body_text),
            "Gross Pay": extract_amount("Gross Pay", body_text),
            "Mess Bill": extract_amount("Mess Bill New", body_text),
            "Club Bill": extract_amount("Club Bill", body_text),
            "Income Tax": extract_amount("Income Tax", body_text),
            "House Rent Deduction": extract_amount("House Rent Deduction", body_text),
            "EOBI": extract_amount("EOBI", body_text),
            "PF Deduction": extract_amount("Provident Fund Employee Cont", body_text),
            "Total Deductions": extract_amount("Total Deductions", body_text),
            "Net Pay": extract_amount("Net Pay Transferred to Bank", body_text),
            "PF Employee Bal": extract_amount("PF Employee Contribution", body_text),
            "PF Company Bal": extract_amount("PF Company Contribution", body_text),
            "Leave Balance": extract_amount("Annual Leave", body_text)
        })

    # Manual Injection
    salary_records.append({
        "Month": "MAR-2025",
        "Basic Pay": 33265.0, "Hard Area": 13306.0, "House Rent Allowance": 9980.0,
        "Other Earnings": 266120.0, "Salary Arrears": 0.0, "Gross Pay": 326121.0,
        "Mess Bill": 9851.0, "Club Bill": 1790.0, "Income Tax": 14020.0,
        "House Rent Deduction": 750.0, "EOBI": 80.0, "PF Deduction": 2771.0,
        "Total Deductions": 29262.0, "Net Pay": 296859.0,
        "PF Employee Bal": 2771.0, "PF Company Bal": 2771.0, "Leave Balance": 0.0
    })

    df = pd.DataFrame(salary_records)
    
    if not df.empty:
        df['Date'] = pd.to_datetime(df['Month'], format='%b-%Y', errors='coerce')
        df = df.dropna(subset=['Date'])
        df = df.sort_values('Date').reset_index(drop=True)
        df['Month_Name'] = df['Date'].dt.strftime('%b').str.upper()
        df['Year'] = df['Date'].dt.year
        df['Other Allowances'] = df['Gross Pay'] - (df['Basic Pay'] + df['Hard Area'] + df['House Rent Allowance'] + df['Other Earnings'] + df['Salary Arrears'])
        df['Other Allowances'] = df['Other Allowances'].apply(lambda x: max(0, x))
        
        def get_fy(date):
            if date.month >= 7:
                return f"FY {date.year}-{str(date.year + 1)[-2:]}"
            else:
                return f"FY {date.year - 1}-{str(date.year)[-2:]}"
                
        df['FY'] = df['Date'].apply(get_fy)
    
    return df

@st.cache_data(ttl=60)
def fetch_expense_data():
    sharepoint_url = "https://muet14-my.sharepoint.com/:x:/g/personal/18ch37_students_muet_edu_pk/IQBicSNMjahzTYvn03-bpK36AVWD3NXpwKCBih5ZlUJxSiE?download=1"
    df_exp = pd.DataFrame()
    error_msg = ""
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(sharepoint_url, headers=headers, timeout=10)
        response.raise_for_status() 
        xls = pd.ExcelFile(io.BytesIO(response.content))
        
        if 'Form1' in xls.sheet_names:
            df_exp = pd.read_excel(xls, sheet_name='Form1')
        elif 'Salary_Expenses' in xls.sheet_names:
            df_exp = pd.read_excel(xls, sheet_name='Salary_Expenses')
        else:
            df_exp = pd.read_excel(xls, sheet_name=xls.sheet_names[0])
            
    except Exception as e:
        try:
            xls = pd.ExcelFile("Salary_Expenses.xlsx")
            if 'Form1' in xls.sheet_names:
                df_exp = pd.read_excel(xls, sheet_name='Form1')
            else:
                df_exp = pd.read_excel(xls, sheet_name=xls.sheet_names[0])
            error_msg = f"SharePoint issue (Using local copy): {str(e)}"
        except Exception:
            error_msg = f"Data fetch failed. Error: {str(e)}"

    if not df_exp.empty:
        expected_columns = ['Date', 'Salary Month', 'Category', 'Sub-Category / Person', 'Amount (PKR)', 'Notes']
        available_columns = [col for col in expected_columns if col in df_exp.columns]
        df_exp = df_exp[available_columns]
        
        if 'Amount (PKR)' in df_exp.columns:
            df_exp = df_exp.dropna(subset=['Amount (PKR)'])

        if 'Salary Month' in df_exp.columns:
            # --- ROBUST MONTH NORMALIZER ---
            def normalize_month(val):
                if pd.isna(val):
                    return ""
                
                if isinstance(val, (pd.Timestamp, datetime.datetime)):
                    return val.strftime('%b-%Y').upper()
                
                s = str(val).strip().upper()
                
                # Intercept Short Formats like 'JUN-26' and convert them instantly to 'JUN-2026'
                if re.match(r'^[A-Z]{3}-\d{2}$', s):
                    s = re.sub(r'-24$', '-2024', s)
                    s = re.sub(r'-25$', '-2025', s)
                    s = re.sub(r'-26$', '-2026', s)
                    s = re.sub(r'-27$', '-2027', s)
                    return s
                
                try:
                    dt = pd.to_datetime(s, errors='coerce')
                    if not pd.isna(dt):
                        return dt.strftime('%b-%Y').upper()
                except Exception:
                    pass
                
                s = re.sub(r'-24$', '-2024', s)
                s = re.sub(r'-25$', '-2025', s)
                s = re.sub(r'-26$', '-2026', s)
                s = re.sub(r'-27$', '-2027', s)
                return s

            df_exp['Salary Month'] = df_exp['Salary Month'].apply(normalize_month)
            
    return df_exp, error_msg
