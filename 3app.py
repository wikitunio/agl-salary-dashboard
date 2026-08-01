import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import base64
import re
import requests
import io
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="AGL Salary Portal", page_icon="🏭", layout="wide")

# --- CONSTANTS ---
RECONCILIATION_THRESHOLD = 5.0   # Rs. tolerance for the Gross - Deductions = Net Pay identity check
DEFAULT_MASTERS_TARGET = 3_000_000
NUMERIC_FIELDS = [
    "Basic Pay", "Hard Area", "House Rent Allowance", "Other Earnings",
    "Salary Arrears", "Gross Pay", "Mess Bill", "Club Bill", "Income Tax",
    "House Rent Deduction", "EOBI", "PF Deduction", "Total Deductions",
    "Net Pay", "PF Employee Bal", "PF Company Bal", "Leave Balance",
]


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


def get_manual_corrections():
    """
    Manual salary-record overrides/additions, loaded from Streamlit secrets
    instead of being hardcoded in source. Use this for any month where Gmail
    parsing fails, is incomplete, or needs correcting — this keeps real salary
    figures out of a file that gets committed to GitHub.

    In .streamlit/secrets.toml (or the Streamlit Cloud secrets editor):

        [[manual_corrections]]
        Month = "MAR-2025"          # must be "MMM-YYYY", e.g. JAN-2026
        "Basic Pay" = 33265.0
        "Gross Pay" = 326121.0
        "Net Pay" = 296859.0
        # include only the fields you need to set — anything omitted
        # defaults to 0.0 for a brand-new month, or keeps its parsed
        # value if the month was already found in Gmail.

        [[manual_corrections]]
        Month = "APR-2025"
        "Net Pay" = 301500.0
    """
    try:
        raw = st.secrets.get("manual_corrections", [])
        return [dict(item) for item in raw]
    except Exception:
        return []


@st.cache_data(ttl=3600)
def fetch_salary_data():
    """Pull payslip emails from Gmail, parse them, merge in any manual
    corrections from secrets, run a data-quality reconciliation check,
    and return a validated DataFrame."""
    try:
        service = authenticate_gmail()
        query = 'label:agl-pay-slips OR from:payroll@pafl.com.pk'

        messages = []
        page_token = None
        while True:
            resp = service.users().messages().list(
                userId='me', q=query, pageToken=page_token
            ).execute()
            messages.extend(resp.get('messages', []))
            page_token = resp.get('nextPageToken')
            if not page_token:
                break
    except Exception as e:
        st.session_state['salary_fetch_error'] = str(e)
        return pd.DataFrame()

    def extract_amount(label, text):
        pattern = rf"{label}\D*?([\d,\.]+)"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            try:
                return float(match.group(1).replace(',', ''))
            except ValueError:
                return 0.0
        return 0.0

    salary_records = []
    for msg in messages:
        try:
            msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        except Exception:
            continue  # skip one bad message rather than failing the whole sync

        headers = msg_data['payload']['headers']
        subject = next((header['value'] for header in headers if header['name'] == 'Subject'), "")
        month_match = re.search(r"Payslip\s+([A-Z]{3}-\d{4})", subject, re.IGNORECASE)
        month = month_match.group(1).upper() if month_match else "Unknown Month"

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

    unparsed_count = sum(1 for r in salary_records if r["Month"] == "Unknown Month")
    if unparsed_count:
        st.session_state['salary_unparsed_count'] = unparsed_count
    else:
        st.session_state.pop('salary_unparsed_count', None)

    # --- Merge in manual corrections (replaces the old hardcoded record) ---
    records_by_month = {r["Month"]: r for r in salary_records}
    for correction in get_manual_corrections():
        month = correction.get("Month")
        if not month:
            continue
        month = str(month).upper().strip()
        correction["Month"] = month
        if month in records_by_month:
            records_by_month[month].update(correction)
        else:
            records_by_month[month] = correction

    for month, rec in records_by_month.items():
        for field in NUMERIC_FIELDS:
            rec.setdefault(field, 0.0)
        rec.setdefault("Month", month)
    salary_records = list(records_by_month.values())

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

        # --- Data-quality reconciliation check: Gross - Deductions should equal Net Pay ---
        df['Reconciliation Diff'] = df['Gross Pay'] - df['Total Deductions'] - df['Net Pay']
        df['Needs Review'] = df['Reconciliation Diff'].abs() > RECONCILIATION_THRESHOLD

        # --- Effective tax rate ---
        df['Effective Tax Rate'] = df.apply(
            lambda r: (r['Income Tax'] / r['Gross Pay'] * 100) if r['Gross Pay'] else 0.0, axis=1
        )

    st.session_state['salary_last_synced'] = datetime.now()
    st.session_state.pop('salary_fetch_error', None)
    return df


@st.cache_data(ttl=60)  # Updates every 60 seconds
def fetch_expense_data():
    sharepoint_url = st.secrets.get("SHAREPOINT_EXPENSE_URL", "")
    df_exp = pd.DataFrame()
    error_msg = ""

    try:
        if not sharepoint_url:
            raise RuntimeError("No SHAREPOINT_EXPENSE_URL configured in secrets")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x86) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(sharepoint_url, headers=headers, timeout=15)
        response.raise_for_status()

        xls = pd.ExcelFile(io.BytesIO(response.content))
        if 'Form1' in xls.sheet_names:
            df_exp = pd.read_excel(xls, sheet_name='Form1')
        elif 'Salary_Expenses' in xls.sheet_names:
            df_exp = pd.read_excel(xls, sheet_name='Salary_Expenses')

    except Exception as e:
        try:
            xls = pd.ExcelFile("Salary_Expenses.xlsx")
            if 'Form1' in xls.sheet_names:
                df_exp = pd.read_excel(xls, sheet_name='Form1')
            elif 'Salary_Expenses' in xls.sheet_names:
                df_exp = pd.read_excel(xls, sheet_name='Salary_Expenses')
        except Exception:
            error_msg = f"SharePoint fetch failed ({str(e)}), and local fallback file missing."

    if not df_exp.empty:
        expected_columns = ['Date', 'Salary Month', 'Category', 'Sub-Category / Person', 'Amount (PKR)', 'Notes']
        available_columns = [col for col in expected_columns if col in df_exp.columns]
        df_exp = df_exp[available_columns]

        if 'Amount (PKR)' in df_exp.columns:
            df_exp = df_exp.dropna(subset=['Amount (PKR)'])

        # --- SMART TEXT CLEANING ---
        if 'Salary Month' in df_exp.columns:
            df_exp['Salary Month'] = df_exp['Salary Month'].astype(str).str.upper().str.strip()
            df_exp['Salary Month'] = df_exp['Salary Month'].str.replace(r'-25$', '-2025', regex=True)
            df_exp['Salary Month'] = df_exp['Salary Month'].str.replace(r'-26$', '-2026', regex=True)
            df_exp['Salary Month'] = df_exp['Salary Month'].str.replace(r'-27$', '-2027', regex=True)

    st.session_state['expense_last_synced'] = datetime.now()
    return df_exp, error_msg


def build_annual_summary(df):
    """Per-financial-year totals: Gross/Net/Tax/PF, effective tax rate, YoY growth."""
    summary = df.groupby('FY', as_index=False).agg({
        'Gross Pay': 'sum',
        'Income Tax': 'sum',
        'Net Pay': 'sum',
        'PF Deduction': 'sum',
        'Month': 'count',
    })
    summary = summary.rename(columns={'Month': 'Months Recorded'})

    fy_order = df.groupby('FY')['Date'].min().sort_values().index.tolist()
    summary['FY'] = pd.Categorical(summary['FY'], categories=fy_order, ordered=True)
    summary = summary.sort_values('FY').reset_index(drop=True)

    summary['Effective Tax Rate %'] = (summary['Income Tax'] / summary['Gross Pay'] * 100).round(1)
    summary['Gross Pay YoY %'] = summary['Gross Pay'].pct_change().mul(100).round(1)
    return summary


def to_excel_bytes(sheets: dict) -> bytes:
    """Bundle one or more DataFrames into a single multi-sheet .xlsx file in memory."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, sheet_df in sheets.items():
            sheet_df.to_excel(writer, sheet_name=str(sheet_name)[:31], index=False)
    return output.getvalue()


def estimate_masters_eta(df, target):
    """Rough ETA to a PF savings target, based on average positive monthly PF growth."""
    d = df.sort_values('Date').copy()
    d['Total PF'] = d['PF Employee Bal'] + d['PF Company Bal']
    if len(d) < 2:
        return None
    growth = d['Total PF'].diff().dropna()
    growth = growth[growth > 0]
    if growth.empty:
        return None
    avg_growth = growth.mean()
    current = d['Total PF'].iloc[-1]
    remaining = target - current
    if remaining <= 0:
        return 0, 0, avg_growth
    months_left = remaining / avg_growth
    years, months = int(months_left // 12), int(round(months_left % 12))
    return years, months, avg_growth


def generate_insights(df, df_fy, month_data, prev_month_data, curr_exp, prev_exp):
    """A few plain-language takeaways for the selected month."""
    insights = []

    if not curr_exp.empty:
        total_spent = curr_exp['Amount (PKR)'].sum()
        net_pay = month_data['Net Pay']
        savings_rate = ((net_pay - total_spent) / net_pay * 100) if net_pay else 0

        if not prev_exp.empty and prev_month_data is not None and prev_month_data['Net Pay']:
            prev_spent = prev_exp['Amount (PKR)'].sum()
            prev_savings_rate = (prev_month_data['Net Pay'] - prev_spent) / prev_month_data['Net Pay'] * 100
            delta = savings_rate - prev_savings_rate
            direction = "improved" if delta >= 0 else "dropped"
            insights.append(f"💰 Savings rate **{direction} {abs(delta):.1f} pts** MoM, now **{savings_rate:.1f}%**.")
        else:
            insights.append(f"💰 You saved **{savings_rate:.1f}%** of net pay this month.")

        top_cat = curr_exp.groupby('Category')['Amount (PKR)'].sum().idxmax()
        top_val = curr_exp.groupby('Category')['Amount (PKR)'].sum().max()
        share = (top_val / total_spent * 100) if total_spent else 0
        insights.append(f"🛍️ **{top_cat}** was your biggest expense category (**{share:.0f}%** of spending).")

    gross = month_data['Gross Pay']
    tax = month_data['Income Tax']
    if gross:
        insights.append(f"🧾 Effective tax rate this month: **{tax / gross * 100:.1f}%** of gross pay.")

    if len(df_fy) > 1 and month_data['Net Pay'] == df_fy['Net Pay'].max():
        insights.append("📈 This is your **highest take-home pay** so far this financial year.")

    if bool(month_data['Needs Review']):
        insights.append("⚠️ This month failed the payslip reconciliation check — treat the numbers above with caution.")

    return insights


def main():
    if check_password():
        # --- SIDEBAR: sync controls ---
        st.sidebar.markdown("### ⚙️ Financial Engine")
        col_refresh, col_logout = st.sidebar.columns(2)
        if col_refresh.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        if col_logout.button("🚪 Logout", use_container_width=True):
            st.session_state["password_correct"] = False
            st.rerun()

        # --- BRANDING & HEADER ---
        st.markdown("<h1>🏭 AgriTech Ltd <span style='font-size:24px; color:gray;'>| Executive Compensation Portal</span></h1>", unsafe_allow_html=True)

        with st.spinner("Synchronizing securely with Gmail..."):
            df = fetch_salary_data()

        last_synced = st.session_state.get('salary_last_synced')
        if last_synced:
            st.sidebar.caption(f"🕒 Salary synced: {last_synced.strftime('%d %b %Y, %I:%M %p')}")
        if st.session_state.get('salary_fetch_error'):
            st.sidebar.error(f"Sync issue: {st.session_state['salary_fetch_error']}")

        if df.empty:
            st.warning("No valid pay slip data could be parsed. Check email formatting, your Gmail label/query, or add a manual correction in secrets.")
            return

        # --- CAREER SNAPSHOT (ALL-TIME) ---
        st.markdown("### 🧭 Career Snapshot (All-Time)")
        snap1, snap2, snap3, snap4 = st.columns(4)
        snap1.metric("Months Tracked", f"{len(df)}")
        snap2.metric("Total Gross Earned", f"Rs. {df['Gross Pay'].sum():,.0f}")
        snap3.metric("Total Tax Paid", f"Rs. {df['Income Tax'].sum():,.0f}")
        latest_row = df.iloc[-1]
        snap4.metric("Current PF Balance", f"Rs. {(latest_row['PF Employee Bal'] + latest_row['PF Company Bal']):,.0f}")
        st.divider()

        # --- DATA QUALITY CHECK ---
        flagged = df.loc[df['Needs Review'], 'Month'].tolist()
        unparsed_count = st.session_state.get('salary_unparsed_count', 0)
        if flagged or unparsed_count:
            issue_count = len(flagged) + (1 if unparsed_count else 0)
            with st.expander(f"⚠️ Data Quality: {issue_count} issue(s) found", expanded=False):
                if flagged:
                    st.write("Gross Pay − Total Deductions doesn't match Net Pay for these months (likely a parsing mismatch against the payslip email format):")
                    st.write(", ".join(flagged))
                if unparsed_count:
                    st.write(f"{unparsed_count} email(s) matched your Gmail search but the subject line didn't match the expected 'Payslip MMM-YYYY' format, so they were skipped.")
                st.caption("Add a manual correction for any of these months via `manual_corrections` in Streamlit secrets — see `get_manual_corrections()` in the code.")

        # --- SIDEBAR: FY / Month selectors ---
        st.sidebar.divider()
        st.sidebar.markdown("Isolate a specific tax cycle.")

        available_fys = sorted(df['FY'].unique(), reverse=True)
        selected_fy = st.sidebar.selectbox("1. Select Financial Year", options=available_fys)

        df_fy = df[df['FY'] == selected_fy]

        available_months = df_fy['Month_Name'].unique().tolist()
        fy_month_order = ['JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC', 'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN']
        sorted_months = sorted(available_months, key=lambda x: fy_month_order.index(x) if x in fy_month_order else 12)

        selected_month = st.sidebar.selectbox("2. Select Focus Month", options=sorted_months, index=len(sorted_months) - 1)

        month_data = df_fy[df_fy['Month_Name'] == selected_month].iloc[0]

        # --- SIDEBAR: Goals ---
        st.sidebar.divider()
        st.sidebar.markdown("### 🎓 Goals")
        masters_target = st.sidebar.number_input(
            "Master's Fund Target (PKR)", min_value=0,
            value=int(st.session_state.get('masters_target', DEFAULT_MASTERS_TARGET)),
            step=50000, key='masters_target'
        )

        # --- DELTA ENGINE (YoY & MoM) ---
        prev_year_month = df[(df['Month_Name'] == selected_month) & (df['Year'] == month_data['Year'] - 1)]
        current_index = df[df['Date'] == month_data['Date']].index[0]
        prev_month_data = df.iloc[current_index - 1] if current_index > 0 else None

        def get_yoy_delta(metric):
            if not prev_year_month.empty:
                prev_val = prev_year_month.iloc[0][metric]
                curr_val = month_data[metric]
                if prev_val > 0:
                    pct = ((curr_val - prev_val) / prev_val) * 100
                    sign = "+" if pct >= 0 else ""
                    return f"{sign}{pct:.1f}% YoY"
            return None

        def get_mom_delta(metric):
            if prev_month_data is not None:
                prev_val = prev_month_data[metric]
                curr_val = month_data[metric]
                diff = curr_val - prev_val
                sign = "+" if diff >= 0 else "-"

                if metric == "Leave Balance":
                    return f"{sign} {abs(diff):,.0f} Days MoM"
                else:
                    return f"{sign} Rs. {abs(diff):,.0f} MoM"
            return None

        if bool(month_data['Needs Review']):
            st.warning(f"⚠️ {month_data['Month']} failed the Gross − Deductions = Net Pay check by Rs. {abs(month_data['Reconciliation Diff']):,.0f}. Figures below may be inaccurate — consider adding a manual correction.")

        # --- SECTION 1: FINANCIAL YEAR CUMULATIVE ---
        st.markdown(f"### 🏛️ {selected_fy} Financial Year (To Date)")
        col_fy1, col_fy2, col_fy3, col_fy4 = st.columns(4)
        col_fy1.metric("Gross Pay (FY)", f"Rs. {df_fy['Gross Pay'].sum():,.0f}")
        col_fy2.metric("Total Tax Deducted", f"Rs. {df_fy['Income Tax'].sum():,.0f}")
        col_fy3.metric("Net Pay Transferred", f"Rs. {df_fy['Net Pay'].sum():,.0f}")
        col_fy4.metric("PF Saved This Year", f"Rs. {df_fy['PF Deduction'].sum():,.0f}")
        st.divider()

        # --- SECTION 2A: FOCUS MONTH SNAPSHOT ---
        st.markdown(f"### 📄 Payslip Snapshot: {month_data['Month']}")
        st.markdown("##### 💰 Earnings (Year-over-Year Tracking)")
        earn1, earn2, earn3, earn4 = st.columns(4)
        earn1.metric("Gross Pay", f"Rs. {month_data['Gross Pay']:,.0f}", delta=get_yoy_delta("Gross Pay"))
        earn2.metric("Basic Pay", f"Rs. {month_data['Basic Pay']:,.0f}", delta=get_yoy_delta("Basic Pay"))
        earn3.metric("Hard Area", f"Rs. {month_data['Hard Area']:,.0f}", delta=get_yoy_delta("Hard Area"))
        earn4.metric("House Rent", f"Rs. {month_data['House Rent Allowance']:,.0f}", delta=get_yoy_delta("House Rent Allowance"))

        earn5, earn6, earn7, earn8 = st.columns(4)
        earn5.metric("Other Earnings", f"Rs. {month_data['Other Earnings']:,.0f}", delta=get_yoy_delta("Other Earnings"))
        earn6.metric("Salary Arrears", f"Rs. {month_data['Salary Arrears']:,.0f}", delta=get_yoy_delta("Salary Arrears"))
        earn7.metric("Other Allowances", f"Rs. {month_data['Other Allowances']:,.0f}", delta=get_yoy_delta("Other Allowances"))
        earn8.metric("Effective Tax Rate", f"{month_data['Effective Tax Rate']:.1f}%")

        st.markdown("##### 💸 Deductions (Month-over-Month Tracking)")
        ded1, ded2, ded3, ded4, ded5 = st.columns(5)
        ded1.metric("Income Tax", f"Rs. {month_data['Income Tax']:,.0f}", delta=get_mom_delta("Income Tax"), delta_color="inverse")
        ded2.metric("Mess Bill", f"Rs. {month_data['Mess Bill']:,.0f}", delta=get_mom_delta("Mess Bill"), delta_color="inverse")
        ded3.metric("Club Bill", f"Rs. {month_data['Club Bill']:,.0f}", delta=get_mom_delta("Club Bill"), delta_color="inverse")
        ded4.metric("Rent Deduction", f"Rs. {month_data['House Rent Deduction']:,.0f}", delta=get_mom_delta("House Rent Deduction"), delta_color="inverse")
        ded5.metric("EOBI", f"Rs. {month_data['EOBI']:,.0f}", delta=get_mom_delta("EOBI"), delta_color="inverse")

        st.markdown("##### 🏦 Net Transfer & Balance")
        net1, net2, net3 = st.columns(3)
        net1.metric("Total Deductions", f"Rs. {month_data['Total Deductions']:,.0f}", delta=get_mom_delta("Total Deductions"), delta_color="inverse")
        net2.metric("Net Pay (Take Home)", f"Rs. {month_data['Net Pay']:,.0f}", delta=get_mom_delta("Net Pay"))
        net3.metric("Leave Balance", f"{month_data['Leave Balance']} Days", delta=get_mom_delta("Leave Balance"))
        st.markdown("<br>", unsafe_allow_html=True)

        # --- SECTION 2B: MAIN DASHBOARD EXPENSES ---
        df_exp, exp_error = fetch_expense_data()
        curr_exp = pd.DataFrame()
        prev_exp = pd.DataFrame()

        expense_last_synced = st.session_state.get('expense_last_synced')
        if expense_last_synced:
            st.sidebar.caption(f"🕒 Expenses synced: {expense_last_synced.strftime('%d %b %Y, %I:%M %p')}")

        if not df_exp.empty:
            df_exp['Salary Month'] = df_exp['Salary Month'].astype(str).str.strip()
            curr_exp = df_exp[df_exp['Salary Month'] == month_data['Month']]

            prev_exp_month_name = prev_month_data['Month'] if prev_month_data is not None else None
            prev_exp = df_exp[df_exp['Salary Month'] == prev_exp_month_name] if prev_exp_month_name else pd.DataFrame()

            st.markdown("##### 🛍️ Out-of-Pocket Expenses (Month-over-Month Tracking)")

            if not curr_exp.empty:
                category_sums = curr_exp.groupby('Category')['Amount (PKR)'].sum()
                total_spent = category_sums.sum()
                net_pay = month_data['Net Pay']
                remaining_cash = net_pay - total_spent

                # Total MoM Calculation
                total_mom_str = None
                if not prev_exp.empty:
                    prev_total = prev_exp['Amount (PKR)'].sum()
                    diff = total_spent - prev_total
                    sign = "+" if diff >= 0 else "-"
                    total_mom_str = f"{sign} Rs. {abs(diff):,.0f} MoM"

                ex_cols = st.columns(4)
                ex_cols[0].metric("Total Spent", f"Rs. {total_spent:,.0f}", delta=total_mom_str, delta_color="inverse")
                ex_cols[1].metric("Remaining Cash", f"Rs. {remaining_cash:,.0f}")
                savings_rate = (remaining_cash / net_pay * 100) if net_pay else 0
                ex_cols[2].metric("Savings Rate", f"{savings_rate:.1f}%")

                if remaining_cash < 0:
                    st.warning(f"⚠️ Expenses exceeded net pay this month by Rs. {abs(remaining_cash):,.0f}.")

                st.markdown("###### Main Categories Logged")

                def get_cat_mom_delta(cat, curr_val):
                    if not prev_exp.empty and cat in prev_exp['Category'].values:
                        prev_val = prev_exp[prev_exp['Category'] == cat]['Amount (PKR)'].sum()
                        diff = curr_val - prev_val
                        sign = "+" if diff >= 0 else "-"
                        return f"{sign} Rs. {abs(diff):,.0f} MoM"
                    return None

                # --- LAYOUT: PIE CHART + METRICS GRID ---
                pie_col, met_col = st.columns([1, 1.5])

                with pie_col:
                    fig_main_pie = px.pie(curr_exp, values='Amount (PKR)', names='Category', hole=0.4, template="plotly_white")
                    fig_main_pie.update_traces(textposition='inside', textinfo='percent+label')
                    fig_main_pie.update_layout(showlegend=False, margin=dict(t=10, b=10, l=0, r=0))
                    st.plotly_chart(fig_main_pie, use_container_width=True)

                with met_col:
                    categories = category_sums.index.tolist()
                    for i in range(0, len(categories), 2):
                        cols = st.columns(2)
                        for j in range(2):
                            if i + j < len(categories):
                                cat = categories[i + j]
                                val = category_sums[cat]
                                cols[j].metric(cat, f"Rs. {val:,.0f}", delta=get_cat_mom_delta(cat, val), delta_color="inverse")

            else:
                st.info(f"No manual expenses logged yet for {month_data['Month']}.")

        elif exp_error:
            st.error(f"⚠️ {exp_error}")

        st.markdown("<br>", unsafe_allow_html=True)

        # --- SECTION 2C: QUICK INSIGHTS ---
        insights = generate_insights(df, df_fy, month_data, prev_month_data, curr_exp, prev_exp)
        if insights:
            st.markdown("##### 🧠 Quick Insights")
            for line in insights:
                st.markdown(f"- {line}")
            st.markdown("<br>", unsafe_allow_html=True)

        # --- SECTION 3: TABS ---
        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
            "📊 Pay & Tax Trends",
            "🏠 Site Housing & Living",
            "🎓 Master's Fund Tracker",
            "📅 Annual Summary",
            "⚖️ Compare Months",
            "🗄️ Raw Data Export",
            "💸 Pocket Expenses (Details)"
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

                known_sum = sum(fy_deduction_values)
                unaccounted_deductions = month_data['Total Deductions'] - known_sum
                if unaccounted_deductions > 5:
                    deduction_labels.append("⚠️ Unmapped Deductions")
                    fy_deduction_values.append(unaccounted_deductions)
                    st.warning(f"Detected Rs. {unaccounted_deductions:,.0f} in unmapped deductions this month!")
                elif unaccounted_deductions < -5:
                    st.warning(f"⚠️ Line-item deductions exceed Total Deductions by Rs. {abs(unaccounted_deductions):,.0f} — check for a duplicate label match in the parser.")

                fig_pie = px.pie(names=deduction_labels, values=fy_deduction_values, hole=0.5, template="plotly_white")
                fig_pie.update_traces(textposition='inside', textinfo='percent')
                fig_pie.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5))
                st.plotly_chart(fig_pie, use_container_width=True)

            st.divider()
            st.subheader("Leave Balance Trend")
            fig_leave = px.line(df_fy, x="Month", y="Leave Balance", markers=True, template="plotly_white")
            fig_leave.update_layout(yaxis_title="Days Remaining", margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig_leave, use_container_width=True)

        with tab2:
            col_house1, col_house2 = st.columns(2)
            with col_house1:
                st.subheader("Married Quarter Housing Monitor")
                housing_spread = month_data['House Rent Allowance'] - month_data['House Rent Deduction']
                st.metric("Net Housing Benefit", f"Rs. {housing_spread:,.0f}", help="House Rent Allowance minus House Rent Deduction")
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
                    mode="gauge+number",
                    value=ratio,
                    number={'suffix': "%"},
                    title={'text': "Site Expenses vs. Hard Area Allowance"},
                    gauge={
                        'axis': {'range': [None, 100], 'tickwidth': 1},
                        'bar': {'color': "rgba(0,0,0,0)"},
                        'bgcolor': "white",
                        'borderwidth': 2,
                        'bordercolor': "gray",
                        'steps': [
                            {'range': [0, 50], 'color': "rgba(44, 160, 44, 0.6)"},
                            {'range': [50, 80], 'color': "rgba(255, 165, 0, 0.6)"},
                            {'range': [80, 100], 'color': "rgba(214, 39, 40, 0.6)"}],
                        'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': ratio}
                    }
                ))
                fig_gauge.update_layout(height=350, margin=dict(l=20, r=20, t=50, b=20))
                st.plotly_chart(fig_gauge, use_container_width=True)

        with tab3:
            st.subheader("🎓 Master's Degree Fund (PF Accumulation)")
            current_total_pf = month_data['PF Employee Bal'] + month_data['PF Company Bal']
            progress_pct = min((current_total_pf / masters_target), 1.0) if masters_target else 0.0
            st.progress(progress_pct)
            st.caption(f"**Current Milestone Progress:** {progress_pct * 100:.1f}% towards Rs. {masters_target:,.0f} goal.")

            eta = estimate_masters_eta(df, masters_target)
            if eta:
                years, months, avg_growth = eta
                if years == 0 and months == 0:
                    st.success("🎉 Target already reached!")
                else:
                    parts = [f"{years} yr" for _ in [1] if years] + [f"{months} mo" for _ in [1] if months]
                    eta_str = ", ".join(parts) if parts else "under a month"
                    st.info(f"📈 At your average monthly PF growth of Rs. {avg_growth:,.0f}, you'll reach this goal in ~{eta_str}.")

            fig_pf = px.area(df, x="Month", y=["PF Employee Bal", "PF Company Bal"], template="plotly_white", color_discrete_sequence=['#1f77b4', '#aec7e8'])
            fig_pf.update_layout(yaxis_title="Total Balance (PKR)", legend_title="Contribution Source")
            st.plotly_chart(fig_pf, use_container_width=True)

        with tab4:
            st.subheader("📅 Financial Year Summary")
            annual_df = build_annual_summary(df)

            st.dataframe(
                annual_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Gross Pay': st.column_config.NumberColumn(format="Rs. %,.0f"),
                    'Income Tax': st.column_config.NumberColumn(format="Rs. %,.0f"),
                    'Net Pay': st.column_config.NumberColumn(format="Rs. %,.0f"),
                    'PF Deduction': st.column_config.NumberColumn(format="Rs. %,.0f"),
                    'Effective Tax Rate %': st.column_config.NumberColumn(format="%.1f%%"),
                    'Gross Pay YoY %': st.column_config.NumberColumn(format="%.1f%%"),
                }
            )

            fig_annual = px.bar(annual_df, x='FY', y=['Gross Pay', 'Net Pay', 'Income Tax'], barmode='group', template='plotly_white')
            fig_annual.update_layout(yaxis_title="Rupees (PKR)", legend_title="")
            st.plotly_chart(fig_annual, use_container_width=True)

            csv_annual = annual_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Annual Summary as CSV", data=csv_annual, file_name="agl_annual_summary.csv", mime="text/csv")

        with tab5:
            st.subheader("⚖️ Month-to-Month Comparison")
            all_months_sorted = df.sort_values('Date', ascending=False)['Month'].unique()
            col_comp1, col_comp2 = st.columns(2)
            with col_comp1:
                month_a = st.selectbox("Baseline Month (Month A)", options=all_months_sorted, index=min(1, len(all_months_sorted) - 1))
            with col_comp2:
                month_b = st.selectbox("Comparison Month (Month B)", options=all_months_sorted, index=0)

            if month_a and month_b:
                data_a = df[df['Month'] == month_a].iloc[0]
                data_b = df[df['Month'] == month_b].iloc[0]

                st.markdown("#### 💰 Earnings & Allowances")
                ec1, ec2, ec3, ec4 = st.columns(4)
                ec1.metric("Basic Pay", f"Rs. {data_b['Basic Pay']:,.0f}", f"{data_b['Basic Pay'] - data_a['Basic Pay']:,.0f}")
                ec2.metric("Hard Area Allowance", f"Rs. {data_b['Hard Area']:,.0f}", f"{data_b['Hard Area'] - data_a['Hard Area']:,.0f}")
                ec3.metric("House Rent Allowance", f"Rs. {data_b['House Rent Allowance']:,.0f}", f"{data_b['House Rent Allowance'] - data_a['House Rent Allowance']:,.0f}")
                ec4.metric("Gross Pay", f"Rs. {data_b['Gross Pay']:,.0f}", f"{data_b['Gross Pay'] - data_a['Gross Pay']:,.0f}")

                ec5, ec6, ec7, ec8 = st.columns(4)
                ec5.metric("Other Earnings", f"Rs. {data_b['Other Earnings']:,.0f}", f"{data_b['Other Earnings'] - data_a['Other Earnings']:,.0f}")
                ec6.metric("Salary Arrears", f"Rs. {data_b['Salary Arrears']:,.0f}", f"{data_b['Salary Arrears'] - data_a['Salary Arrears']:,.0f}")
                ec7.metric("Other Allowances", f"Rs. {data_b['Other Allowances']:,.0f}", f"{data_b['Other Allowances'] - data_a['Other Allowances']:,.0f}")

                st.divider()
                st.markdown("#### 💸 Deductions")
                dc1, dc2, dc3, dc4 = st.columns(4)
                dc1.metric("Income Tax", f"Rs. {data_b['Income Tax']:,.0f}", f"{data_b['Income Tax'] - data_a['Income Tax']:,.0f}", delta_color="inverse")
                dc2.metric("PF Deduction", f"Rs. {data_b['PF Deduction']:,.0f}", f"{data_b['PF Deduction'] - data_a['PF Deduction']:,.0f}", delta_color="inverse")
                dc3.metric("House Rent Deduction", f"Rs. {data_b['House Rent Deduction']:,.0f}", f"{data_b['House Rent Deduction'] - data_a['House Rent Deduction']:,.0f}", delta_color="inverse")
                dc4.metric("Total Deductions", f"Rs. {data_b['Total Deductions']:,.0f}", f"{data_b['Total Deductions'] - data_a['Total Deductions']:,.0f}", delta_color="inverse")

                st.markdown("<br>", unsafe_allow_html=True)
                dc5, dc6, dc7, dc8 = st.columns(4)
                dc5.metric("Mess Bill", f"Rs. {data_b['Mess Bill']:,.0f}", f"{data_b['Mess Bill'] - data_a['Mess Bill']:,.0f}", delta_color="inverse")
                dc6.metric("Club Bill", f"Rs. {data_b['Club Bill']:,.0f}", f"{data_b['Club Bill'] - data_a['Club Bill']:,.0f}", delta_color="inverse")
                dc7.metric("EOBI", f"Rs. {data_b['EOBI']:,.0f}", f"{data_b['EOBI'] - data_a['EOBI']:,.0f}", delta_color="inverse")
                dc8.metric("Net Pay (Take Home)", f"Rs. {data_b['Net Pay']:,.0f}", f"{data_b['Net Pay'] - data_a['Net Pay']:,.0f}")

        with tab6:
            st.subheader("Raw Extracted Data")
            display_df = df.drop(columns=['Date', 'Month_Name'])
            st.dataframe(display_df, use_container_width=True)

            dl1, dl2 = st.columns(2)
            csv = display_df.to_csv(index=False).encode('utf-8')
            dl1.download_button(label="📥 Download as CSV", data=csv, file_name="agl_complete_salary_history.csv", mime="text/csv", use_container_width=True)

            excel_sheets = {"Salary History": display_df, "Annual Summary": build_annual_summary(df)}
            if not df_exp.empty:
                excel_sheets["Expenses"] = df_exp
            excel_bytes = to_excel_bytes(excel_sheets)
            dl2.download_button(label="📊 Download as Excel (Multi-Sheet)", data=excel_bytes, file_name="agl_salary_full_export.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

        with tab7:
            st.subheader("💸 Detailed Pocket Expenses")
            if df_exp.empty:
                st.warning("⚠️ Expense file could not be read.")
            else:
                if not curr_exp.empty:
                    st.dataframe(curr_exp[['Date', 'Category', 'Sub-Category / Person', 'Amount (PKR)', 'Notes']], use_container_width=True, hide_index=True)
                else:
                    st.info("No detailed breakdown available for this month.")


if __name__ == '__main__':
    main()
