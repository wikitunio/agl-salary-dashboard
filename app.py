import streamlit as st
import pandas as pd
import plotly.express as px
import base64
import re
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["DASHBOARD_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"] 
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Enter Dashboard Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Enter Dashboard Password", type="password", on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    else:
        return True

@st.cache_resource
def authenticate_gmail():
    creds = Credentials(
        token=None,
        refresh_token=st.secrets["GMAIL_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=st.secrets["GMAIL_CLIENT_ID"],
        client_secret=st.secrets["GMAIL_CLIENT_SECRET"]
    )
    return build('gmail', 'v1', credentials=creds)

@st.cache_data
def fetch_salary_data():
    service = authenticate_gmail()
    query = 'label:agl-pay-slips OR from:payroll@pafl.com.pk'
    results = service.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])

    salary_records = []

    def extract_amount(pattern, text):
        match = re.search(pattern, text)
        if match:
            return int(match.group(1).replace(',', ''))
        return 0

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
                        body_text = base64.urlsafe_b64decode(data).decode('utf-8')
        else:
            data = msg_data['payload']['body'].get('data')
            if data:
                body_text = base64.urlsafe_b64decode(data).decode('utf-8')

        salary_records.append({
            "Month": month,
            "Basic Pay": extract_amount(r"Basic Salary.*?([\d,]+)", body_text),
            "Gross Pay": extract_amount(r"Gross Pay.*?([\d,]+)", body_text),
            "Total Deductions": extract_amount(r"Total Deductions.*?([\d,]+)", body_text),
            "Net Pay": extract_amount(r"Net Pay Transferred to Bank.*?([\d,]+)", body_text)
        })

    return pd.DataFrame(salary_records)

def main():
    if check_password():
        st.title("💸 Salary & Compensation Dashboard")
        st.markdown("Data automatically pulled from Gmail")

        with st.spinner("Fetching data securely from Gmail..."):
            df = fetch_salary_data()

        if not df.empty:
            st.subheader("Latest Month Overview")
            col1, col2, col3 = st.columns(3)
            col1.metric("Net Pay", f"Rs. {df['Net Pay'].iloc[0]:,}")
            col2.metric("Basic Pay", f"Rs. {df['Basic Pay'].iloc[0]:,}")
            col3.metric("Total Deductions", f"Rs. {df['Total Deductions'].iloc[0]:,}")
            
            st.divider()
            st.subheader("Salary Trends")
            fig_net = px.line(df, x="Month", y="Net Pay", title="Net Pay History", markers=True)
            st.plotly_chart(fig_net, use_container_width=True)
            
            st.divider()
            st.subheader("Raw Data")
            st.dataframe(df)
        else:
            st.warning("No pay slips found under the specified label.")

if __name__ == '__main__':
    main()
