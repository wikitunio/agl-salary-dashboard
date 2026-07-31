import streamlit as st
import pandas as pd
import plotly.express as px
import base64
import re
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# --- PAGE CONFIGURATION (Makes it look wide and professional) ---
st.set_page_config(page_title="AGL Salary Portal", page_icon="💸", layout="wide")

def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["DASHBOARD_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"] 
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("<h2 style='text-align: center;'>🔒 Secure Login</h2>", unsafe_allow_html=True)
        st.text_input("Enter Dashboard Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align: center;'>🔒 Secure Login</h2>", unsafe_allow_html=True)
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

    def extract_amount(label, text):
        # NEW REGEX FIX: \D*? ignores all hidden symbols (like | or line breaks) until it hits the digits
        pattern = rf"{label}\D*?([\d,]+)"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
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
        # Gets the email body and strips out HTML code if present to leave clean text
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
                        body_text += re.sub('<[^<]+>', ' ', html_text) # Strip HTML tags
        else:
            data = msg_data['payload']['body'].get('data')
            if data:
                html_text = base64.urlsafe_b64decode(data).decode('utf-8')
                body_text = re.sub('<[^<]+>', ' ', html_text)

        salary_records.append({
            "Month": month,
            "Basic Pay": extract_amount("Basic Salary", body_text),
            "Gross Pay": extract_amount("Gross Pay", body_text),
            "Total Deductions": extract_amount("Total Deductions", body_text),
            "Net Pay": extract_amount("Net Pay Transferred to Bank", body_text)
        })

    df = pd.DataFrame(salary_records)
    
    # NEW FIX: Convert Month strings to actual dates and sort them chronologically
    if not df.empty:
        df['Date'] = pd.to_datetime(df['Month'], format='%b-%Y', errors='coerce')
        df = df.dropna(subset=['Date']) # Removes "Unknown Month" errors
        df = df.sort_values('Date').reset_index(drop=True)
    
    return df

def main():
    if check_password():
        st.title("📊 AGL Salary & Compensation Portal")
        st.markdown("---")

        with st.spinner("Securely synchronizing with Gmail..."):
            df = fetch_salary_data()

        if not df.empty:
            st.subheader(f"Latest Overview: {df['Month'].iloc[-1]}")
            
            # Formatted Metrics
            col1, col2, col3 = st.columns(3)
            col1.metric("Net Pay Transferred", f"Rs. {df['Net Pay'].iloc[-1]:,}")
            col2.metric("Gross Pay", f"Rs. {df['Gross Pay'].iloc[-1]:,}")
            col3.metric("Total Deductions", f"Rs. {df['Total Deductions'].iloc[-1]:,}")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Side-by-side Charts
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                st.subheader("Net Pay History")
                fig_net = px.line(df, x="Month", y="Net Pay", markers=True, template="plotly_white")
                fig_net.update_traces(line_color='#2ca02c', line_width=3, marker=dict(size=8))
                fig_net.update_layout(xaxis_title="", yaxis_title="Rupees (PKR)", plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_net, use_container_width=True)

            with col_chart2:
                st.subheader("Earnings vs Deductions")
                fig_bar = px.bar(df, x="Month", y=["Gross Pay", "Total Deductions"], barmode="group", template="plotly_white")
                fig_bar.update_layout(xaxis_title="", yaxis_title="Rupees (PKR)", legend_title="", plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_bar, use_container_width=True)
            
            st.markdown("---")
            with st.expander("View Raw Data Table"):
                # Hide the helper 'Date' column from the final table
                display_df = df.drop(columns=['Date'])
                st.dataframe(display_df, use_container_width=True)
        else:
            st.warning("No valid pay slip data could be parsed. Check email formatting.")

if __name__ == '__main__':
    main()
