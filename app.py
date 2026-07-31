import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import base64
import re
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="AGL Salary Portal", page_icon="💳", layout="wide")

# --- CONCEPTZILLA DRIBBBLE STYLING (CUSTOM CSS) ---
st.markdown("""
<style>
    /* Import Inter Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    /* Global App Background & Font */
    .stApp {
        background-color: #F4F7FE;
        font-family: 'Inter', sans-serif;
    }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        box-shadow: 2px 0 20px rgba(0,0,0,0.03);
    }
    
    /* Headers (Deep Navy) */
    h1, h2, h3, h4 {
        color: #2B3674 !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: -0.5px;
    }
    
    /* Metric Cards (Floating White Cards) */
    div[data-testid="metric-container"] {
        background-color: #FFFFFF;
        padding: 20px 25px;
        border-radius: 20px;
        box-shadow: 0px 10px 20px rgba(211, 218, 230, 0.4);
        border: none;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-5px);
        box-shadow: 0px 15px 25px rgba(211, 218, 230, 0.6);
    }
    
    /* Metric Card Labels (Muted Blue-Grey) */
    div[data-testid="metric-container"] label {
        color: #A3AED0 !important;
        font-weight: 500 !important;
        font-size: 15px !important;
    }
    
    /* Metric Card Values (Deep Navy) */
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] > div {
        color: #2B3674 !important;
        font-weight: 800 !important;
        font-size: 32px !important;
    }
    
    /* Metric Card Delta (Emerald Green) */
    div[data-testid="stMetricDelta"] svg {
        color: #01B574 !important;
    }
    div[data-testid="stMetricDelta"] > div {
        color: #01B574 !important;
        font-weight: 600 !important;
    }
    
    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 20px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        border-radius: 10px;
        color: #A3AED0;
        font-weight: 600;
        padding: 10px 20px;
        border: none !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: #4318FF !important;
        color: white !important;
        border-radius: 12px !important;
        box-shadow: 0px 4px 10px rgba(67, 24, 255, 0.3);
    }
    
    /* Divider */
    hr {
        border-color: #E6EDF9 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- THEME COLORS FOR PLOTLY ---
COLOR_PRIMARY = "#4318FF"  # Electric Purple
COLOR_SECONDARY = "#6AD2FF" # Vibrant Cyan
COLOR_SUCCESS = "#01B574"  # Emerald Green
COLOR_WARNING = "#FFB547"  # Orange
COLOR_DANGER = "#EE5D50"   # Red
COLOR_TEXT = "#2B3674"
COLOR_GRID = "#E6EDF9"

def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["DASHBOARD_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"] 
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("<h2 style='text-align: center; color: #4318FF !important;'>🔒 Secure Login</h2>", unsafe_allow_html=True)
        st.text_input("Enter Dashboard Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align: center; color: #4318FF !important;'>🔒 Secure Login</h2>", unsafe_allow_html=True)
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

# Helper to style Plotly charts
def style_plotly_fig(fig):
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Inter, sans-serif", color="#A3AED0"),
        title_font=dict(color=COLOR_TEXT, size=18, family="Inter, sans-serif"),
        legend=dict(font=dict(color="#A3AED0")),
        xaxis=dict(gridcolor=COLOR_GRID, zerolinecolor=COLOR_GRID),
        yaxis=dict(gridcolor=COLOR_GRID, zerolinecolor=COLOR_GRID)
    )
    return fig

def main():
    if check_password():
        # --- BRANDING & HEADER ---
        st.markdown(f"<h1>💳 AgriTech Executive <span style='color:{COLOR_PRIMARY};'>Finances</span></h1>", unsafe_allow_html=True)
        
        with st.spinner("Synchronizing securely with Gmail..."):
            df = fetch_salary_data()

        if df.empty:
            st.warning("No valid pay slip data could be parsed. Check email formatting.")
            return

        # --- SIDEBAR CONTROLS ---
        st.sidebar.markdown(f"<h2 style='color:{COLOR_PRIMARY} !important;'>⚙️ Engine Controls</h2>", unsafe_allow_html=True)
        
        available_fys = sorted(df['FY'].unique(), reverse=True)
        selected_fy = st.sidebar.selectbox("1. Select Financial Year", options=available_fys)
        
        df_fy = df[df['FY'] == selected_fy]
        
        available_months = df_fy['Month_Name'].unique().tolist()
        fy_month_order = ['JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC', 'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN']
        sorted_months = sorted(available_months, key=lambda x: fy_month_order.index(x) if x in fy_month_order else 12)
        
        selected_month = st.sidebar.selectbox("2. Select Focus Month", options=sorted_months, index=len(sorted_months)-1)
        
        month_data = df_fy[df_fy['Month_Name'] == selected_month].iloc[0]

        # --- YoY INCREMENT DETECTOR ---
        prev_year_month = df[(df['Month_Name'] == selected_month) & (df['Year'] == month_data['Year'] - 1)]
        if not prev_year_month.empty:
            prev_basic = prev_year_month.iloc[0]['Basic Pay']
            delta_basic = month_data['Basic Pay'] - prev_basic
            delta_pct = f"{(delta_basic / prev_basic) * 100:.1f}% YoY" if prev_basic > 0 else None
        else:
            delta_pct = None

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
        col_m1.metric("Basic Pay", f"Rs. {month_data['Basic Pay']:,.0f}", delta=delta_pct)
        col_m2.metric("Monthly Net Pay", f"Rs. {month_data['Net Pay']:,.0f}")
        col_m3.metric("Monthly Income Tax", f"Rs. {month_data['Income Tax']:,.0f}")
        col_m4.metric("Leave Balance", f"{month_data['Leave Balance']} Days")

        st.markdown("<br>", unsafe_allow_html=True)

        # --- SECTION 3: TABS & CHARTS ---
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Pay & Tax Trends", 
            "🏠 Site Housing & Living", 
            "🎓 Master's Fund Tracker",
            "🗄️ Raw Data Export"
        ])

        with tab1:
            col_chart1, col_chart2 = st.columns([2, 1])
            with col_chart1:
                st.markdown("<div style='background: white; padding: 20px; border-radius: 20px; box-shadow: 0px 10px 20px rgba(211,218,230,0.4);'>", unsafe_allow_html=True)
                st.subheader(f"Earnings Curve ({selected_fy})")
                fig_net = px.line(df_fy, x="Month", y=["Gross Pay", "Net Pay"], markers=True)
                fig_net.update_traces(line_color=COLOR_PRIMARY, selector=dict(name="Gross Pay"), line_width=4, marker=dict(size=8))
                fig_net.update_traces(line_color=COLOR_SECONDARY, selector=dict(name="Net Pay"), line_width=4, marker=dict(size=8))
                fig_net.update_layout(yaxis_title="Rupees (PKR)", legend_title="", margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(style_plotly_fig(fig_net), use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
                
            with col_chart2:
                st.markdown("<div style='background: white; padding: 20px; border-radius: 20px; box-shadow: 0px 10px 20px rgba(211,218,230,0.4);'>", unsafe_allow_html=True)
                st.subheader("Deduction Slice")
                deduction_labels = ['Mess Bill', 'PF Deduction', 'Income Tax', 'Club Bill', 'House Rent Deduction', 'EOBI']
                fy_deduction_values = [month_data[label] for label in deduction_labels]
                
                fig_pie = px.pie(names=deduction_labels, values=fy_deduction_values, hole=0.6, 
                                 color_discrete_sequence=[COLOR_PRIMARY, COLOR_SECONDARY, COLOR_SUCCESS, COLOR_WARNING, COLOR_DANGER, "#A3AED0"])
                fig_pie.update_traces(textposition='inside', textinfo='none', hoverinfo='label+percent')
                fig_pie.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5))
                st.plotly_chart(style_plotly_fig(fig_pie), use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

        with tab2:
            col_house1, col_house2 = st.columns(2)
            with col_house1:
                st.markdown("<div style='background: white; padding: 20px; border-radius: 20px; box-shadow: 0px 10px 20px rgba(211,218,230,0.4);'>", unsafe_allow_html=True)
                st.subheader("Married Quarter Housing Monitor")
                housing_spread = month_data['House Rent Allowance'] - month_data['House Rent Deduction']
                st.metric("Net Housing Benefit", f"Rs. {housing_spread:,.0f}", help="House Rent Allowance minus House Rent Deduction")
                st.markdown("<br>", unsafe_allow_html=True)
                
                st.subheader(f"Site Expenses ({selected_fy})")
                fig_living = px.bar(df_fy, x="Month", y=["Mess Bill", "Club Bill"], barmode="stack", color_discrete_sequence=[COLOR_SECONDARY, COLOR_WARNING])
                fig_living.add_scatter(x=df_fy["Month"], y=df_fy["Hard Area"], mode='lines+markers', name='Hard Area Allowance', line=dict(color=COLOR_SUCCESS, width=4))
                fig_living.update_layout(yaxis_title="Rupees (PKR)", legend_title="", margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(style_plotly_fig(fig_living), use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
                
            with col_house2:
                st.markdown("<div style='background: white; padding: 20px; border-radius: 20px; box-shadow: 0px 10px 20px rgba(211,218,230,0.4);'>", unsafe_allow_html=True)
                st.subheader("Expense-to-Income Ratio")
                total_site_expense = month_data['Mess Bill'] + month_data['Club Bill']
                hard_area_allowance = month_data['Hard Area']
                ratio = (total_site_expense / hard_area_allowance) * 100 if hard_area_allowance > 0 else 0
                
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = ratio,
                    number = {'suffix': "%", 'font': {'color': COLOR_TEXT, 'size': 40}},
                    gauge = {
                        'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': COLOR_GRID},
                        'bar': {'color': COLOR_TEXT},
                        'bgcolor': "white",
                        'borderwidth': 0,
                        'steps': [
                            {'range': [0, 50], 'color': "rgba(1, 181, 116, 0.2)"}, 
                            {'range': [50, 80], 'color': "rgba(255, 181, 71, 0.2)"}, 
                            {'range': [80, 100], 'color': "rgba(238, 93, 80, 0.2)"}], 
                        'threshold': {'line': {'color': COLOR_DANGER, 'width': 4}, 'thickness': 0.75, 'value': ratio}
                    }
                ))
                fig_gauge.update_layout(height=350, margin=dict(l=20, r=20, t=50, b=20))
                st.plotly_chart(style_plotly_fig(fig_gauge), use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

        with tab3:
            st.markdown("<div style='background: white; padding: 25px; border-radius: 20px; box-shadow: 0px 10px 20px rgba(211,218,230,0.4);'>", unsafe_allow_html=True)
            st.subheader("🎓 Master's Degree Fund (PF Accumulation)")
            st.markdown("<p style='color: #A3AED0;'>Tracking your total all-time Provident Fund wealth against an academic savings milestone.</p>", unsafe_allow_html=True)
            
            MASTERS_TARGET = 3000000  # 3 Million PKR Target
            current_total_pf = month_data['PF Employee Bal'] + month_data['PF Company Bal']
            progress_pct = min((current_total_pf / MASTERS_TARGET), 1.0)
            
            # Custom styled progress bar wrapper
            st.markdown(f"""
            <div style="width: 100%; background-color: #E6EDF9; border-radius: 10px; margin-top: 10px; margin-bottom: 5px;">
              <div style="width: {progress_pct*100}%; background-color: {COLOR_PRIMARY}; height: 12px; border-radius: 10px;"></div>
            </div>
            <p style='color: {COLOR_PRIMARY}; font-weight: bold;'>{progress_pct*100:.1f}% towards Rs. {MASTERS_TARGET:,.0f} goal</p>
            """, unsafe_allow_html=True)
            
            fig_pf = px.area(df, x="Month", y=["PF Employee Bal", "PF Company Bal"], color_discrete_sequence=[COLOR_PRIMARY, COLOR_SECONDARY])
            fig_pf.update_layout(yaxis_title="Total Balance (PKR)", legend_title="", margin=dict(t=20))
            st.plotly_chart(style_plotly_fig(fig_pf), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with tab4:
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
