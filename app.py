import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import base64
import re
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="AGL Salary Portal", page_icon="🏭", layout="wide")

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
        df['Year'] = df['Date'].dt.year
        
        def get_fy(date):
            if date.month >= 7:
                return f"FY {date.year}-{str(date.year + 1)[-2:]}"
            else:
                return f"FY {date.year - 1}-{str(date.year)[-2:]}"
                
        df['FY'] = df['Date'].apply(get_fy)
    
    return df

def main():
    if check_password():
        # --- BRANDING & HEADER ---
        st.markdown("<h1>🏭 AgriTech Ltd <span style='font-size:24px; color:gray;'>| Executive Compensation Portal</span></h1>", unsafe_allow_html=True)
        
        with st.spinner("Synchronizing securely with Gmail..."):
            df = fetch_salary_data()

        if df.empty:
            st.warning("No valid pay slip data could be parsed. Check email formatting.")
            return

        # --- SIDEBAR CONTROLS ---
        st.sidebar.markdown("### ⚙️ Financial Engine")
        st.sidebar.markdown("Isolate a specific tax cycle.")
        
        available_fys = sorted(df['FY'].unique(), reverse=True)
        selected_fy = st.sidebar.selectbox("1. Select Financial Year", options=available_fys)
        
        df_fy = df[df['FY'] == selected_fy]
        
        available_months = df_fy['Month_Name'].unique().tolist()
        fy_month_order = ['JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC', 'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN']
        sorted_months = sorted(available_months, key=lambda x: fy_month_order.index(x) if x in fy_month_order else 12)
        
        selected_month = st.sidebar.selectbox("2. Select Focus Month", options=sorted_months, index=len(sorted_months)-1)
        
        month_data = df_fy[df_fy['Month_Name'] == selected_month].iloc[0]

        # --- SECTION 1: FINANCIAL YEAR CUMULATIVE ---
        st.markdown(f"### 🏛️ {selected_fy} Financial Year (To Date)")
        
        col_fy1, col_fy2, col_fy3, col_fy4 = st.columns(4)
        col_fy1.metric("Gross Pay (FY)", f"Rs. {df_fy['Gross Pay'].sum():,.0f}")
        col_fy2.metric("Total Tax Deducted", f"Rs. {df_fy['Income Tax'].sum():,.0f}")
        col_fy3.metric("Net Pay Transferred", f"Rs. {df_fy['Net Pay'].sum():,.0f}")
        col_fy4.metric("PF Saved This Year", f"Rs. {df_fy['PF Deduction'].sum():,.0f}")
        
        st.divider()

        # --- SECTION 2: FOCUS MONTH ---
        st.markdown(f"### 📄 Payslip Snapshot: {month_data['Month']}")
        
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Basic Pay", f"Rs. {month_data['Basic Pay']:,.0f}")
        col_m2.metric("Monthly Net Pay", f"Rs. {month_data['Net Pay']:,.0f}")
        col_m3.metric("Monthly Income Tax", f"Rs. {month_data['Income Tax']:,.0f}")
        col_m4.metric("Leave Balance", f"{month_data['Leave Balance']} Days")

        st.markdown("<br>", unsafe_allow_html=True)

        # --- SECTION 3: TABS & CHARTS ---
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Pay & Tax Trends", 
            "🏠 Site Housing & Living", 
            "🎓 Master's Fund Tracker",
            "⚖️ Compare Months",
            "🗄️ Raw Data Export"
        ])

        with tab1:
            col_chart1, col_chart2 = st.columns([2, 1])
            with col_chart1:
                st.subheader(f"Earnings Curve ({selected_fy})")
                fig_net = px.line(df_fy, x="Month", y=["Gross Pay", "Net Pay"], markers=True, template="plotly_white")
                fig_net.update_layout(yaxis_title="Rupees (PKR)", legend_title="", margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig_net, use_container_width=True)
            with col_chart2:
                st.subheader("Deduction Slice")
                deduction_labels = ['Mess Bill', 'PF Deduction', 'Income Tax', 'Club Bill', 'House Rent Deduction', 'EOBI']
                fy_deduction_values = [month_data[label] for label in deduction_labels]
                
                fig_pie = px.pie(names=deduction_labels, values=fy_deduction_values, hole=0.5, template="plotly_white")
                fig_pie.update_traces(textposition='inside', textinfo='percent')
                fig_pie.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5))
                st.plotly_chart(fig_pie, use_container_width=True)

        with tab2:
            col_house1, col_house2 = st.columns(2)
            with col_house1:
                st.subheader("Married Quarter Housing Monitor")
                st.markdown("Tracking the spread between your rent allowance and your payroll deductions.")
                housing_spread = month_data['House Rent Allowance'] - month_data['House Rent Deduction']
                st.metric("Net Housing Benefit", f"Rs. {housing_spread:,.0f}", 
                          help="House Rent Allowance minus House Rent Deduction")
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                st.subheader(f"Site Expenses ({selected_fy})")
                fig_living = px.bar(df_fy, x="Month", y=["Mess Bill", "Club Bill"], template="plotly_white", barmode="stack")
                fig_living.add_scatter(x=df_fy["Month"], y=df_fy["Hard Area"], mode='lines+markers', name='Hard Area Allowance', line=dict(color='green', width=3))
                fig_living.update_layout(yaxis_title="Rupees (PKR)", legend_title="", margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig_living, use_container_width=True)
                
            with col_house2:
                st.subheader("Expense-to-Income Ratio")
                total_site_expense = month_data['Mess Bill'] + month_data['Club Bill']
                hard_area_allowance = month_data['Hard Area']
                ratio = (total_site_expense / hard_area_allowance) * 100 if hard_area_allowance > 0 else 0
                
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = ratio,
                    number = {'suffix': "%"},
                    title = {'text': "Site Expenses vs. Hard Area Allowance"},
                    gauge = {
                        'axis': {'range': [None, 100], 'tickwidth': 1},
                        'bar': {'color': "rgba(0,0,0,0)"},
                        'bgcolor': "white",
                        'borderwidth': 2,
                        'bordercolor': "gray",
                        'steps': [
                            {'range': [0, 50], 'color': "rgba(44, 160, 44, 0.6)"}, # Green
                            {'range': [50, 80], 'color': "rgba(255, 165, 0, 0.6)"}, # Orange
                            {'range': [80, 100], 'color': "rgba(214, 39, 40, 0.6)"}], # Red
                        'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': ratio}
                    }
                ))
                fig_gauge.update_layout(height=350, margin=dict(l=20, r=20, t=50, b=20))
                st.plotly_chart(fig_gauge, use_container_width=True)

        with tab3:
            st.subheader("🎓 Master's Degree Fund (PF Accumulation)")
            st.markdown("Tracking your total all-time Provident Fund wealth against an academic savings milestone.")
            
            # Master's Degree Milestone Target
            MASTERS_TARGET = 3000000  # 3 Million PKR Target (Adjustable)
            current_total_pf = month_data['PF Employee Bal'] + month_data['PF Company Bal']
            progress_pct = min((current_total_pf / MASTERS_TARGET), 1.0)
            
            st.progress(progress_pct)
            st.caption(f"**Current Milestone Progress:** {progress_pct*100:.1f}% towards Rs. {MASTERS_TARGET:,.0f} goal.")
            
            fig_pf = px.area(df, x="Month", y=["PF Employee Bal", "PF Company Bal"], template="plotly_white", color_discrete_sequence=['#1f77b4', '#aec7e8'])
            fig_pf.update_layout(yaxis_title="Total Balance (PKR)", legend_title="Contribution Source")
            st.plotly_chart(fig_pf, use_container_width=True)

        with tab4:
            st.subheader("⚖️ Month-to-Month Comparison")
            st.markdown("Select any two months from your entire history to see exact changes in your compensation.")
            
            # Use all available months sorted chronologically (newest first)
            all_months_sorted = df.sort_values('Date', ascending=False)['Month'].unique()
            
            col_comp1, col_comp2 = st.columns(2)
            with col_comp1:
                month_a = st.selectbox("Baseline Month (Month A)", options=all_months_sorted, index=min(1, len(all_months_sorted)-1))
            with col_comp2:
                month_b = st.selectbox("Comparison Month (Month B)", options=all_months_sorted, index=0)
                
            if month_a and month_b:
                data_a = df[df['Month'] == month_a].iloc[0]
                data_b = df[df['Month'] == month_b].iloc[0]
                
                st.markdown(f"#### 📈 Shift from {month_a} to {month_b}")
                
                mc1, mc2, mc3, mc4 = st.columns(4)
                # For earnings, higher is better (default delta color)
                mc1.metric("Basic Pay", f"Rs. {data_b['Basic Pay']:,.0f}", f"{data_b['Basic Pay'] - data_a['Basic Pay']:,.0f}")
                mc2.metric("Gross Pay", f"Rs. {data_b['Gross Pay']:,.0f}", f"{data_b['Gross Pay'] - data_a['Gross Pay']:,.0f}")
                mc3.metric("Net Pay", f"Rs. {data_b['Net Pay']:,.0f}", f"{data_b['Net Pay'] - data_a['Net Pay']:,.0f}")
                
                # For deductions, an increase is technically a negative impact on take-home pay, so we use delta_color="inverse"
                mc4.metric("Total Deductions", f"Rs. {data_b['Total Deductions']:,.0f}", f"{data_b['Total Deductions'] - data_a['Total Deductions']:,.0f}", delta_color="inverse")
                
                st.divider()
                st.markdown("#### 🔍 Detailed Breakdown")
                dc1, dc2, dc3, dc4 = st.columns(4)
                dc1.metric("Income Tax", f"Rs. {data_b['Income Tax']:,.0f}", f"{data_b['Income Tax'] - data_a['Income Tax']:,.0f}", delta_color="inverse")
                dc2.metric("Mess Bill", f"Rs. {data_b['Mess Bill']:,.0f}", f"{data_b['Mess Bill'] - data_a['Mess Bill']:,.0f}", delta_color="inverse")
                dc3.metric("Hard Area Allowance", f"Rs. {data_b['Hard Area']:,.0f}", f"{data_b['Hard Area'] - data_a['Hard Area']:,.0f}")
                dc4.metric("PF Deduction", f"Rs. {data_b['PF Deduction']:,.0f}", f"{data_b['PF Deduction'] - data_a['PF Deduction']:,.0f}", delta_color="inverse")

        with tab5:
            st.subheader("Raw Extracted Data")
            display_df = df.drop(columns=['Date', 'Month_Name'])
            st.dataframe(display_df, use_container_width=True)
            
            csv = display_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Complete History as CSV",
                data=csv,
                file_name=f"agl_complete_salary_history.csv",
                mime="text/csv",
            )

if __name__ == '__main__':
    main()
