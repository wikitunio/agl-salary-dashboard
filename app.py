import streamlit as st
import pandas as pd
import plotly.express as px
import base64
import re
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="AGL Salary Portal", page_icon="📈", layout="wide")

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

# REMOVED CACHE HERE TO PREVENT BROKEN PIPE ERRORS
def authenticate_gmail():
    creds = Credentials(
        token=None,
        refresh_token=st.secrets["GMAIL_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=st.secrets["GMAIL_CLIENT_ID"],
        client_secret=st.secrets["GMAIL_CLIENT_SECRET"]
    )
    return build('gmail', 'v1', credentials=creds)

# ADDED 1-HOUR TIME LIMIT (TTL) TO KEEP DATA FRESH
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
        df['Month_Name'] = df['Date'].dt.strftime('%b').str.upper()
        
        # Financial Year Logic (July to June)
        def get_fy(date):
            if date.month >= 7:
                return f"FY {date.year}-{str(date.year + 1)[-2:]}"
            else:
                return f"FY {date.year - 1}-{str(date.year)[-2:]}"
                
        df['FY'] = df['Date'].apply(get_fy)
    
    return df

def main():
    if check_password():
        st.title("📈 AGL Salary & Compensation Portal")
        
        with st.spinner("Securely synchronizing with Gmail..."):
            df = fetch_salary_data()

        if df.empty:
            st.warning("No valid pay slip data could be parsed. Check email formatting.")
            return

        # --- SIDEBAR CONTROLS ---
        st.sidebar.title("📅 Timeline Controls")
        st.sidebar.markdown("Isolate a specific tax cycle.")
        
        # 1. FY Dropdown
        available_fys = sorted(df['FY'].unique(), reverse=True)
        selected_fy = st.sidebar.selectbox("1. Select Financial Year", options=available_fys)
        
        df_fy = df[df['FY'] == selected_fy]
        
        # 2. Month Dropdown (Sorted July -> June)
        available_months = df_fy['Month_Name'].unique().tolist()
        fy_month_order = ['JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC', 'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN']
        sorted_months = sorted(available_months, key=lambda x: fy_month_order.index(x) if x in fy_month_order else 12)
        
        selected_month = st.sidebar.selectbox("2. Select Focus Month", options=sorted_months, index=len(sorted_months)-1)
        
        # Get exact data for the chosen month
        month_data = df_fy[df_fy['Month_Name'] == selected_month].iloc[0]

        # --- SECTION 1: FINANCIAL YEAR CUMULATIVE ---
        st.markdown(f"### 🏛️ {selected_fy} Financial Year (To Date)")
        st.markdown("Cumulative totals calculated from July 1st of the selected tax year.")
        
        col_fy1, col_fy2, col_fy3, col_fy4 = st.columns(4)
        col_fy1.metric("Gross Pay (FY)", f"Rs. {df_fy['Gross Pay'].sum():,.0f}")
        col_fy2.metric("Total Tax Deducted", f"Rs. {df_fy['Income Tax'].sum():,.0f}")
        col_fy3.metric("Net Pay Transferred", f"Rs. {df_fy['Net Pay'].sum():,.0f}")
        col_fy4.metric("PF Saved This Year", f"Rs. {df_fy['PF Deduction'].sum():,.0f}")
        
        st.divider()

        # --- SECTION 2: FOCUS MONTH ---
        st.markdown(f"### 📄 Payslip Snapshot: {month_data['Month']}")
        
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Monthly Net Pay", f"Rs. {month_data['Net Pay']:,.0f}")
        col_m2.metric("Monthly Income Tax", f"Rs. {month_data['Income Tax']:,.0f}")
        col_m3.metric("Hard Area Allowance", f"Rs. {month_data['Hard Area']:,.0f}")
        col_m4.metric("Leave Balance", f"{month_data['Leave Balance']} Days")

        st.markdown("<br>", unsafe_allow_html=True)

        # --- SECTION 3: TABS & CHARTS ---
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 FY Pay Trends", 
            "💸 FY Deduction Breakdown", 
            "🏠 Site Living Expenses", 
            "🚀 All-Time Wealth Growth"
        ])

        with tab1:
            st.subheader(f"Earnings Curve ({selected_fy})")
            fig_net = px.line(df_fy, x="Month", y=["Gross Pay", "Net Pay"], markers=True, template="plotly_white")
            fig_net.update_layout(yaxis_title="Rupees (PKR)", legend_title="")
            st.plotly_chart(fig_net, use_container_width=True)

        with tab2:
            col_pie1, col_pie2 = st.columns([1, 1])
            with col_pie1:
                st.subheader(f"Total Deductions ({selected_fy})")
                deduction_labels = ['Mess Bill', 'PF Deduction', 'Income Tax', 'Club Bill', 'House Rent Deduction', 'EOBI']
                # Sums up the deductions for the entire FY
                fy_deduction_values = [df_fy[label].sum() for label in deduction_labels]
                
                fig_pie = px.pie(names=deduction_labels, values=fy_deduction_values, hole=0.4, template="plotly_white")
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                fig_pie.update_layout(showlegend=False)
                st.plotly_chart(fig_pie, use_container_width=True)
            with col_pie2:
                st.subheader("Raw Deduction Data")
                st.dataframe(df_fy[['Month'] + deduction_labels], use_container_width=True, hide_index=True)

        with tab3:
            st.subheader(f"Site Expenses vs Allowances ({selected_fy})")
            fig_living = px.bar(df_fy, x="Month", y=["Mess Bill", "Club Bill"], title="Monthly Site Deductions", template="plotly_white", barmode="stack")
            fig_living.add_scatter(x=df_fy["Month"], y=df_fy["Hard Area"], mode='lines+markers', name='Hard Area Allowance', line=dict(color='green', width=3))
            fig_living.update_layout(yaxis_title="Rupees (PKR)")
            st.plotly_chart(fig_living, use_container_width=True)

        with tab4:
            st.subheader("Provident Fund Accumulation (All-Time)")
            st.markdown("Unlike the other tabs, this chart ignores the FY filter to show the entire lifespan of your PF growth.")
            # Uses the unfiltered 'df' to show all-time history
            fig_pf = px.area(df, x="Month", y=["PF Employee Bal", "PF Company Bal"], template="plotly_white", color_discrete_sequence=['#1f77b4', '#aec7e8'])
            fig_pf.update_layout(yaxis_title="Total Balance (PKR)", legend_title="Contribution Source")
            st.plotly_chart(fig_pf, use_container_width=True)
            
            st.divider()
            
            # Export Option
            display_df = df.drop(columns=['Date', 'Month_Name'])
            csv = display_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Complete History as CSV",
                data=csv,
                file_name=f"agl_complete_salary_history.csv",
                mime="text/csv",
            )

if __name__ == '__main__':
    main()
    
