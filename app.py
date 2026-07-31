import streamlit as st
import pandas as pd
import plotly.express as px
import base64
import re
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# --- PAGE CONFIGURATION ---
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

    df = pd.DataFrame(salary_records)
    
    if not df.empty:
        df['Date'] = pd.to_datetime(df['Month'], format='%b-%Y', errors='coerce')
        df = df.dropna(subset=['Date'])
        df = df.sort_values('Date').reset_index(drop=True)
        df['Year'] = df['Date'].dt.year
        # Extract just the 3-letter month name and make it uppercase (e.g., 'JUL')
        df['Month_Name'] = df['Date'].dt.strftime('%b').str.upper()
    
    return df

def main():
    if check_password():
        # --- TOP HEADER ---
        st.title("📊 AGL Salary & Compensation Portal")
        
        with st.spinner("Securely synchronizing with Gmail..."):
            df = fetch_salary_data()

        if df.empty:
            st.warning("No valid pay slip data could be parsed. Check email formatting.")
            return

        # --- SIDEBAR FILTERS ---
        st.sidebar.title("Controls")
        
        # 1. Year Filter
        years = sorted(df['Year'].unique(), reverse=True)
        selected_years = st.sidebar.multiselect("Filter by Year", options=years, default=years)
        
        # 2. Month Filter (Sorted chronologically instead of alphabetically)
        month_order = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
        available_months = df['Month_Name'].unique().tolist()
        sorted_months = sorted(available_months, key=lambda x: month_order.index(x) if x in month_order else 12)
        selected_months = st.sidebar.multiselect("Filter by Month", options=sorted_months, default=sorted_months)
        
        # Apply both filters to the dataframe
        df_filtered = df[(df['Year'].isin(selected_years)) & (df['Month_Name'].isin(selected_months))]
        
        if df_filtered.empty:
            st.warning("No data matches the selected filters.")
            return

        latest_record = df_filtered.iloc[-1]

        # --- TOP LEVEL METRICS ---
        st.markdown("### 📈 Latest Month Snapshot")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Net Pay Transferred", f"Rs. {latest_record['Net Pay']:,.0f}")
        col2.metric("Gross Pay", f"Rs. {latest_record['Gross Pay']:,.0f}")
        col3.metric("Total Deductions", f"Rs. {latest_record['Total Deductions']:,.0f}")
        col4.metric("Annual Leave Balance", f"{latest_record['Leave Balance']} Days")
        
        st.markdown("---")

        # --- ORGANIZED TABS ---
        tab1, tab2, tab3, tab4 = st.tabs([
            "💰 Pay Overview", 
            "🏠 Living & Allowances", 
            "🚀 Wealth & Forecast", 
            "🗄️ Raw Data & Export"
        ])

        with tab1:
            col_chart1, col_chart2 = st.columns([2, 1])
            
            with col_chart1:
                st.subheader("Net Pay History")
                fig_net = px.line(df_filtered, x="Month", y="Net Pay", markers=True, template="plotly_white")
                fig_net.update_traces(line_color='#2ca02c', line_width=3, marker=dict(size=8))
                st.plotly_chart(fig_net, use_container_width=True)

            with col_chart2:
                st.subheader("Deduction Breakdown")
                deduction_labels = ['Mess Bill', 'PF Deduction', 'Income Tax', 'Club Bill', 'House Rent Deduction', 'EOBI']
                deduction_values = [latest_record[label] for label in deduction_labels]
                
                fig_pie = px.pie(names=deduction_labels, values=deduction_values, hole=0.4, template="plotly_white")
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                fig_pie.update_layout(showlegend=False)
                st.plotly_chart(fig_pie, use_container_width=True)

        with tab2:
            st.subheader("Site Expenses vs. Hard Area Allowance")
            st.markdown("Comparing your monthly Mess & Club bills against your site allowance.")
            
            fig_living = px.line(df_filtered, x="Month", y=["Hard Area", "Mess Bill", "Club Bill"], 
                                 markers=True, template="plotly_white")
            fig_living.update_layout(yaxis_title="Rupees (PKR)", legend_title="Category")
            st.plotly_chart(fig_living, use_container_width=True)

        with tab3:
            col_pf, col_forecast = st.columns([2, 1])
            
            with col_pf:
                st.subheader("Provident Fund Growth")
                fig_pf = px.area(df_filtered, x="Month", y=["PF Employee Bal", "PF Company Bal"], 
                                 template="plotly_white", color_discrete_sequence=['#1f77b4', '#aec7e8'])
                fig_pf.update_layout(yaxis_title="Total Balance (PKR)", legend_title="Contribution Source")
                st.plotly_chart(fig_pf, use_container_width=True)
            
            with col_forecast:
                st.subheader("Annualized Run Rate")
                st.markdown("Based on your most recent payslip, here is your trajectory for a 12-month fiscal year:")
                st.info(f"**Projected Net Take-Home:** Rs. {latest_record['Net Pay'] * 12:,.0f}")
                st.warning(f"**Projected Tax Burden:** Rs. {latest_record['Income Tax'] * 12:,.0f}")
                
                # Check for zero Gross Pay to avoid division by zero errors
                if latest_record['Gross Pay'] > 0:
                    savings_rate = (latest_record['PF Deduction'] / latest_record['Gross Pay']) * 100
                    st.success(f"**Current PF Savings Rate:** {savings_rate:.1f}% of Gross Pay")
                else:
                    st.success("**Current PF Savings Rate:** N/A")

        with tab4:
            st.subheader("Raw Extracted Data")
            # Drop the extra helper columns before displaying the table
            display_df = df_filtered.drop(columns=['Date', 'Year', 'Month_Name'])
            st.dataframe(display_df, use_container_width=True)
            
            csv = display_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Data as CSV",
                data=csv,
                file_name=f"agl_salary_data_{latest_record['Month']}.csv",
                mime="text/csv",
            )

if __name__ == '__main__':
    main()
