import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from groq import Groq
import datetime
import streamlit.components.v1 as components
import io

# Optional libraries for file parsing
try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

try:
    import PyPDF2
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

# --- Import our background functions ---
from data_loader import fetch_salary_data, fetch_expense_data

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="AGL Salary Portal", page_icon="🏭", layout="wide")

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if "pin_input" not in st.session_state:
        st.session_state["pin_input"] = ""

    if st.session_state["password_correct"]:
        return True

    st.markdown("<h2 style='text-align: center; font-family: sans-serif;'>🔒 Enter Passcode</h2>", unsafe_allow_html=True)
    
    pin_len = len(st.session_state["pin_input"])
    target_len = len(str(st.secrets["DASHBOARD_PASSWORD"]))
    pin_display = "● " * pin_len + "○ " * max(0, (target_len - pin_len))
    st.markdown(f"<h1 style='text-align: center; letter-spacing: 15px; color: #1f77b4;'>{pin_display}</h1>", unsafe_allow_html=True)

    def pin_press(digit):
        st.session_state["pin_input"] += str(digit)
        if st.session_state["pin_input"] == str(st.secrets["DASHBOARD_PASSWORD"]):
            st.session_state["password_correct"] = True
            st.session_state["pin_input"] = ""

    def pin_clear():
        st.session_state["pin_input"] = ""
        
    def pin_backspace():
        st.session_state["pin_input"] = st.session_state["pin_input"][:-1]

    st.markdown("""
        <style>
        div[data-testid="stButton"] button { height: 60px; font-size: 24px; border-radius: 30px; }
        </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1])
    with col2:
        st.button("1", on_click=pin_press, args=("1",), use_container_width=True)
        st.button("4", on_click=pin_press, args=("4",), use_container_width=True)
        st.button("7", on_click=pin_press, args=("7",), use_container_width=True)
        st.button("C", on_click=pin_clear, use_container_width=True)
    with col3:
        st.button("2", on_click=pin_press, args=("2",), use_container_width=True)
        st.button("5", on_click=pin_press, args=("5",), use_container_width=True)
        st.button("8", on_click=pin_press, args=("8",), use_container_width=True)
        st.button("0", on_click=pin_press, args=("0",), use_container_width=True)
    with col4:
        st.button("3", on_click=pin_press, args=("3",), use_container_width=True)
        st.button("6", on_click=pin_press, args=("6",), use_container_width=True)
        st.button("9", on_click=pin_press, args=("9",), use_container_width=True)
        st.button("⌫", on_click=pin_backspace, use_container_width=True)

    st.markdown("<br><hr>", unsafe_allow_html=True)
    
    def text_pwd():
        if st.session_state["text_pwd_input"] == str(st.secrets["DASHBOARD_PASSWORD"]):
            st.session_state["password_correct"] = True
            del st.session_state["text_pwd_input"]
            
    st.text_input("Or use full alphanumeric password", type="password", on_change=text_pwd, key="text_pwd_input")
    
    if pin_len >= target_len and st.session_state["pin_input"] != str(st.secrets["DASHBOARD_PASSWORD"]):
        st.error("Incorrect Passcode")
        st.session_state["pin_input"] = ""
        
    return False

def generate_pdf_report(month_data, df_exp, health_score, total_spent, savings_rate):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, txt=f"AGL Executive Financial Report: {month_data['Month']}", ln=True, align="C")
    pdf.ln(5)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(200, 10, txt="1. Executive Summary & KPIs", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.cell(200, 8, txt=f"Gross Pay: Rs. {month_data['Gross Pay']:,.0f}", ln=True)
    pdf.cell(200, 8, txt=f"Net Pay (Take Home): Rs. {month_data['Net Pay']:,.0f}", ln=True)
    pdf.cell(200, 8, txt=f"Total Out-of-Pocket Expenses: Rs. {total_spent:,.0f}", ln=True)
    pdf.cell(200, 8, txt=f"Savings Rate: {savings_rate:.1f}%", ln=True)
    pdf.cell(200, 8, txt=f"Financial Health Score: {health_score} / 100", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(200, 10, txt="2. Tax & PF Tracking", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.cell(200, 8, txt=f"Income Tax Deducted: Rs. {month_data['Income Tax']:,.0f}", ln=True)
    pdf.cell(200, 8, txt=f"Provident Fund (Employee): Rs. {month_data['PF Deduction']:,.0f}", ln=True)
    pdf.cell(200, 8, txt=f"Provident Fund (Total Accumulation): Rs. {month_data['PF Employee Bal'] + month_data['PF Company Bal']:,.0f}", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(200, 10, txt="3. Salary Components", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.cell(200, 8, txt=f"Basic Pay: Rs. {month_data['Basic Pay']:,.0f}", ln=True)
    pdf.cell(200, 8, txt=f"Hard Area Allowance: Rs. {month_data['Hard Area']:,.0f}", ln=True)
    pdf.cell(200, 8, txt=f"House Rent Allowance: Rs. {month_data['House Rent Allowance']:,.0f}", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(200, 10, txt="4. Site Living Deductions", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.cell(200, 8, txt=f"Mess Bill: Rs. {month_data['Mess Bill']:,.0f}", ln=True)
    pdf.cell(200, 8, txt=f"Club Bill: Rs. {month_data['Club Bill']:,.0f}", ln=True)
    pdf.ln(10)
    
    pdf.set_font("Arial", "I", 9)
    pdf.cell(200, 10, txt="Report generated automatically by the AGL Executive Portal.", ln=True, align="C")
    
    return pdf.output(dest="S").encode("latin-1")

def render_executive_kpi(df):
    st.markdown("### 📊 Lifetime Executive Summary")
    total_earnings = df['Gross Pay'].sum()
    total_tax = df['Income Tax'].sum()
    total_pf_saved = (df['PF Deduction'].sum()) * 2 
    avg_gross = df['Gross Pay'].mean()
    avg_net = df['Net Pay'].mean()
    highest_salary_row = df.loc[df['Gross Pay'].idxmax()]
    highest_month = highest_salary_row['Month']
    highest_amount = highest_salary_row['Gross Pay']
    
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("Total Career Earnings", f"Rs. {total_earnings:,.0f}")
    kpi2.metric("Total Tax Paid", f"Rs. {total_tax:,.0f}")
    kpi3.metric("Total PF Saved", f"Rs. {total_pf_saved:,.0f}")
    kpi4.metric("Avg Monthly Net", f"Rs. {avg_net:,.0f}", f"Gross: {avg_gross:,.0f}", delta_color="off")
    kpi5.metric("Highest Salary", f"Rs. {highest_amount:,.0f}", f"{highest_month}", delta_color="off")
    st.divider()

def main():
    if check_password():
        st.markdown("<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}</style>", unsafe_allow_html=True)
        st.markdown("<h1>🏭 AgriTech Ltd <span style='font-size:24px; color:gray;'>| Executive Compensation Portal</span></h1>", unsafe_allow_html=True)
        
        with st.spinner("Synchronizing securely with Gmail..."):
            df = fetch_salary_data()

        if df.empty:
            st.warning("No valid pay slip data could be parsed. Check email formatting.")
            return

        render_executive_kpi(df)

        # --- SIDEBAR CONTROLS ---
        if st.sidebar.button("🚪 Logout", use_container_width=True):
            st.session_state["password_correct"] = False
            st.rerun()
            
        st.sidebar.markdown("### ⚙️ Financial Engine")
        
        if st.sidebar.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.sidebar.markdown("### 🔍 Search Payslip")
        all_months_sorted = df.sort_values('Date', ascending=False)['Month'].unique()
        selected_month = st.sidebar.selectbox("Type to search (e.g. APR, 2025, Bonus)", options=all_months_sorted, index=0)
        
        month_data = df[df['Month'] == selected_month].iloc[0]
        selected_fy = month_data['FY']
        df_fy = df[df['FY'] == selected_fy]

        with st.sidebar.expander("🛠️ Advanced Filters", expanded=False):
            st.date_input("Custom Date Range", [])
            st.selectbox("Quarter", ["All", "Q1", "Q2", "Q3", "Q4"])
            st.selectbox("Calendar Year", ["All"] + sorted(list(df['Year'].unique()), reverse=True))
            st.selectbox("Department", ["All", "Urea Shift", "Ammonia Shift"])
            st.selectbox("Expense Category", ["All", "Essentials", "Leisure", "Investments"])
            st.caption("Filters apply to raw data export and aggregated timeline views.")

        st.sidebar.markdown("---")
        st.sidebar.caption("✅ Version 4.0: Live Sync & AI Widget")

        prev_year_month = df[(df['Month'] == selected_month) & (df['Year'] == month_data['Year'] - 1)]
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

        # --- SNAPSHOT UI ---
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
        
        # --- CASH FLOW & FINANCIAL HEALTH ---
        df_exp, exp_error = fetch_expense_data()
        
        remaining_cash = month_data['Net Pay']
        total_spent = 0
        curr_exp = pd.DataFrame()
        prev_exp = pd.DataFrame()
        health_score = 0
        savings_rate = 0
        
        if not df_exp.empty:
            target_month = str(month_data['Month']).strip().upper()
            curr_exp = df_exp[df_exp['Salary Month'] == target_month]
            
            prev_exp_month_name = prev_month_data['Month'] if prev_month_data is not None else None
            prev_target_month = str(prev_exp_month_name).strip().upper() if prev_exp_month_name else None
            prev_exp = df_exp[df_exp['Salary Month'] == prev_target_month] if prev_target_month else pd.DataFrame()
            
            st.markdown("##### 🩺 Cash Flow & Financial Health Score")
            
            if not curr_exp.empty:
                category_sums = curr_exp.groupby('Category')['Amount (PKR)'].sum()
                total_spent = category_sums.sum()
                net_pay = month_data['Net Pay']
                remaining_cash = net_pay - total_spent
                
                savings_rate = (remaining_cash / net_pay * 100) if net_pay > 0 else 0
                total_pf = month_data['PF Deduction'] * 2 
                pf_rate = (total_pf / month_data['Gross Pay'] * 100) if month_data['Gross Pay'] > 0 else 0
                site_expenses = month_data['Mess Bill'] + month_data['Club Bill']
                hard_area = month_data['Hard Area']
                site_ratio = (site_expenses / hard_area * 100) if hard_area > 0 else 100
                
                score_savings = min(50, (max(0, savings_rate) / 30) * 50) 
                score_pf = min(30, (pf_rate / 10) * 30)                   
                score_site = 20 if site_ratio <= 100 else max(0, 20 - (site_ratio - 100)) 
                health_score = int(score_savings + score_pf + score_site)
                
                if health_score >= 90: stars = "⭐⭐⭐⭐⭐ Excellent"
                elif health_score >= 70: stars = "⭐⭐⭐⭐ Good"
                elif health_score >= 50: stars = "⭐⭐⭐ Fair"
                else: stars = "⭐⭐ Needs Attention"
                
                total_mom_str = None
                if not prev_exp.empty:
                    prev_total = prev_exp['Amount (PKR)'].sum()
                    diff = total_spent - prev_total
                    sign = "+" if diff >= 0 else "-"
                    total_mom_str = f"{sign} Rs. {abs(diff):,.0f} MoM"
                
                ex_cols = st.columns([3,3,3,4,3])
                ex_cols[0].metric("Total Spent", f"Rs. {total_spent:,.0f}", delta=total_mom_str, delta_color="inverse")
                ex_cols[1].metric("Remaining Cash", f"Rs. {remaining_cash:,.0f}")
                ex_cols[2].metric("True Savings Rate", f"{savings_rate:.1f}%")
                ex_cols[3].metric("Financial Health", f"{health_score} / 100", stars, delta_color="off")
                
                with ex_cols[4]:
                    if FPDF_AVAILABLE:
                        pdf_bytes = generate_pdf_report(month_data, df_exp, health_score, total_spent, savings_rate)
                        st.download_button("📑 Generate Report", data=pdf_bytes, file_name=f"AGL_Report_{month_data['Month']}.pdf", mime="application/pdf", use_container_width=True)
                    else:
                        st.button("📑 Generate Report", disabled=True, help="Add 'fpdf' to requirements.txt to enable.")
                
                st.markdown("###### 📊 Expense Ranking & MoM Change")
                top_10 = category_sums.sort_values(ascending=False).head(10)
                mom_diffs = {}
                for cat, val in category_sums.items():
                    prev_val = prev_exp[prev_exp['Category'] == cat]['Amount (PKR)'].sum() if (not prev_exp.empty and cat in prev_exp['Category'].values) else 0
                    mom_diffs[cat] = val - prev_val
                    
                largest_increase_cat = max(mom_diffs, key=mom_diffs.get) if mom_diffs else "N/A"
                largest_decrease_cat = min(mom_diffs, key=mom_diffs.get) if mom_diffs else "N/A"
                
                rank_col1, rank_col2 = st.columns([1.5, 1])
                with rank_col1:
                    st.markdown("**Top 10 Expenses**")
                    st.dataframe(top_10.reset_index().rename(columns={'Amount (PKR)': 'Spent (Rs.)'}), use_container_width=True, hide_index=True)
                with rank_col2:
                    inc_val = mom_diffs.get(largest_increase_cat, 0)
                    dec_val = mom_diffs.get(largest_decrease_cat, 0)
                    st.metric("🔺 Largest Increase", largest_increase_cat, f"+{inc_val:,.0f} MoM", delta_color="inverse")
                    st.metric("🔻 Largest Decrease", largest_decrease_cat, f"{dec_val:,.0f} MoM", delta_color="inverse")
            else:
                st.info(f"No manual expenses logged yet for {month_data['Month']}.")
        elif exp_error:
            st.error(f"⚠️ {exp_error}")

        st.divider()

        # --- TABS ---
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
            "📊 Pay & Tax Trends", 
            "🏠 Site Housing & Living", 
            "🎓 Master's Fund Tracker",
            "⚖️ Compare Months",
            "🗄️ Raw Data Export",
            "💸 Pocket Expenses (Log)",
            "🏛️ Tax Analytics",
            "🔮 Salary Simulator"
        ])
        
        with tab1:
            st.subheader("💧 Salary & Expense Waterfall")
            
            sankey_tax = month_data['Income Tax']
            sankey_pf = month_data['PF Deduction']
            sankey_site = month_data['Mess Bill'] + month_data['Club Bill'] + month_data['House Rent Deduction']
            sankey_other = max(0, month_data['Total Deductions'] - (sankey_tax + sankey_pf + sankey_site))
            sankey_net = month_data['Net Pay']
            sankey_exp = min(total_spent, sankey_net) 
            sankey_sav = max(0, sankey_net - sankey_exp)
            
            fig_sankey = go.Figure(data=[go.Sankey(
                node = dict(pad=15, thickness=20, line=dict(color="black", width=0.5), label=["Gross Pay", "Income Tax", "PF Deduction", "Site Living", "Other Deductions", "Net Pay", "Pocket Expenses", "Savings"]),
                link = dict(source=[0, 0, 0, 0, 0, 5, 5], target=[1, 2, 3, 4, 5, 6, 7], value=[sankey_tax, sankey_pf, sankey_site, sankey_other, sankey_net, sankey_exp, sankey_sav])
            )])
            fig_sankey.update_layout(title_text="Cash Flow Sankey Diagram", height=350, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig_sankey, use_container_width=True)
            
            wf_gross = month_data['Gross Pay']
            wf_tax = month_data['Income Tax']
            wf_pf = month_data['PF Deduction']
            wf_mess = month_data['Mess Bill']
            wf_club = month_data['Club Bill']
            wf_rent = month_data['House Rent Deduction']
            wf_eobi = month_data['EOBI']
            wf_net = month_data['Net Pay']
            
            x_list = ["Gross Pay", "Income Tax", "PF Deduction", "Mess Bill", "Club Bill", "Rent", "EOBI"]
            y_list = [wf_gross, -wf_tax, -wf_pf, -wf_mess, -wf_club, -wf_rent, -wf_eobi]
            measure_list = ["relative"] * 7
            
            unmapped = month_data['Total Deductions'] - (wf_tax + wf_pf + wf_mess + wf_club + wf_rent + wf_eobi)
            if unmapped > 5:
                x_list.append("Other Deductions")
                y_list.append(-unmapped)
                measure_list.append("relative")
                
            x_list.append("Net Pay (Check)")
            y_list.append(wf_net)
            measure_list.append("total")
            
            wf_savings = wf_net
            if not curr_exp.empty:
                cat_sums = curr_exp.groupby('Category')['Amount (PKR)'].sum()
                for cat, val in cat_sums.items():
                    x_list.append(f"Exp: {cat}")
                    y_list.append(-val)
                    measure_list.append("relative")
                    wf_savings -= val
            else:
                x_list.append("No Logged Expenses")
                y_list.append(0)
                measure_list.append("relative")
                
            x_list.append("Remaining Cash")
            y_list.append(wf_savings)
            measure_list.append("total")
            
            text_list = []
            for v, m in zip(y_list, measure_list):
                if m == "total":
                    text_list.append(f"{v:,.0f}")
                else:
                    text_list.append(f"{v:,.0f}" if v < 0 else f"+{v:,.0f}")
            
            fig_waterfall = go.Figure(go.Waterfall(
                name="Detailed Salary Flow", orientation="v", measure=measure_list, x=x_list, y=y_list, textposition="outside", text=text_list,
                connector={"line": {"color": "gray", "width": 1.5}},
                decreasing={"marker": {"color": "#ff4b4b"}}, increasing={"marker": {"color": "#2ca02c"}}, totals={"marker": {"color": "#1f77b4"}}        
            ))
            fig_waterfall.update_layout(template="plotly_white", margin=dict(t=30, b=20, l=0, r=0), showlegend=False, height=500)
            st.plotly_chart(fig_waterfall, use_container_width=True)

            st.markdown(f"### 📈 Salary Growth Analytics ({selected_fy})")
            df_fy_sorted = df_fy.sort_values('Date')
            if len(df_fy_sorted) >= 2:
                start_m = df_fy_sorted.iloc[0]
                end_m = df_fy_sorted.iloc[-1]
                def calc_g(start, end): return ((end - start) / start * 100) if start > 0 else 0
                g_gross = calc_g(start_m['Gross Pay'], end_m['Gross Pay'])
                g_basic = calc_g(start_m['Basic Pay'], end_m['Basic Pay'])
                g_net = calc_g(start_m['Net Pay'], end_m['Net Pay'])
                start_allow = start_m['Hard Area'] + start_m['House Rent Allowance'] + start_m['Other Allowances'] + start_m['Other Earnings']
                end_allow = end_m['Hard Area'] + end_m['House Rent Allowance'] + end_m['Other Allowances'] + end_m['Other Earnings']
                g_allow = calc_g(start_allow, end_allow)
                
                df_sorted_all = df.sort_values('Date')
                days_diff = (df_sorted_all.iloc[-1]['Date'] - df_sorted_all.iloc[0]['Date']).days
                total_years = max(days_diff / 365.25, 1.0) 
                first_gross = df_sorted_all.iloc[0]['Gross Pay']
                last_gross = df_sorted_all.iloc[-1]['Gross Pay']
                cagr = (((last_gross / first_gross) ** (1 / total_years)) - 1) * 100 if first_gross > 0 else 0
                
                gr1, gr2, gr3, gr4, gr5 = st.columns(5)
                gr1.metric("Gross Salary Growth", f"{'+' if g_gross >= 0 else ''}{g_gross:.1f}%")
                gr2.metric("Basic Salary Growth", f"{'+' if g_basic >= 0 else ''}{g_basic:.1f}%")
                gr3.metric("Allowance Growth", f"{'+' if g_allow >= 0 else ''}{g_allow:.1f}%")
                gr4.metric("Net Salary Growth", f"{'+' if g_net >= 0 else ''}{g_net:.1f}%")
                gr5.metric("Gross Salary CAGR", f"{'+' if cagr >= 0 else ''}{cagr:.1f}%", help=f"Lifetime Compound Annual Growth Rate ({total_years:.1f} years)")
            else:
                st.info(f"Not enough data in {selected_fy} to calculate growth metrics.")

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
                    mode = "gauge+number", value = ratio, number = {'suffix': "%"}, title = {'text': "Site Expenses vs. Hard Area Allowance"},
                    gauge = {
                        'axis': {'range': [None, 100], 'tickwidth': 1}, 'bar': {'color': "rgba(0,0,0,0)"},
                        'bgcolor': "white", 'borderwidth': 2, 'bordercolor': "gray",
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
            MASTERS_TARGET = 3000000 
            current_total_pf = month_data['PF Employee Bal'] + month_data['PF Company Bal']
            progress_pct = min((current_total_pf / MASTERS_TARGET), 1.0)
            st.progress(progress_pct)
            st.caption(f"**Current Milestone Progress:** {progress_pct*100:.1f}% towards Rs. {MASTERS_TARGET:,.0f} goal.")
            
            fig_pf = px.area(df, x="Month", y=["PF Employee Bal", "PF Company Bal"], template="plotly_white", color_discrete_sequence=['#1f77b4', '#aec7e8'])
            fig_pf.update_layout(yaxis_title="Total Balance (PKR)", legend_title="Contribution Source")
            st.plotly_chart(fig_pf, use_container_width=True)

        with tab4:
            st.subheader("⚖️ Month-to-Month Comparison")
            col_comp1, col_comp2 = st.columns(2)
            with col_comp1: month_a = st.selectbox("Baseline Month (Month A)", options=all_months_sorted, index=min(1, len(all_months_sorted)-1))
            with col_comp2: month_b = st.selectbox("Comparison Month (Month B)", options=all_months_sorted, index=0)
                
            if month_a and month_b:
                data_a = df[df['Month'] == month_a].iloc[0]
                data_b = df[df['Month'] == month_b].iloc[0]
                
                st.markdown(f"#### 💰 Earnings & Allowances")
                ec1, ec2, ec3, ec4 = st.columns(4)
                ec1.metric("Basic Pay", f"Rs. {data_b['Basic Pay']:,.0f}", f"{data_b['Basic Pay'] - data_a['Basic Pay']:,.0f}")
                ec2.metric("Hard Area Allowance", f"Rs. {data_b['Hard Area']:,.0f}", f"{data_b['Hard Area'] - data_a['Hard Area']:,.0f}")
                ec3.metric("House Rent Allowance", f"Rs. {data_b['House Rent Allowance']:,.0f}", f"{data_b['House Rent Allowance'] - data_a['House Rent Allowance']:,.0f}")
                ec4.metric("Gross Pay", f"Rs. {data_b['Gross Pay']:,.0f}", f"{data_b['Gross Pay'] - data_a['Gross Pay']:,.0f}")

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

        with tab5:
            st.subheader("Raw Extracted Data")
            display_df = df.drop(columns=['Date', 'Month_Name'])
            st.dataframe(display_df, use_container_width=True)
            csv = display_df.to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 Download Complete History as CSV", data=csv, file_name=f"agl_complete_salary_history.csv", mime="text/csv")

        with tab6:
            st.subheader("📝 Complete Expense Log")
            if df_exp.empty: st.warning("⚠️ Expense file could not be read.")
            else:
                if not curr_exp.empty: st.dataframe(curr_exp[['Date', 'Category', 'Sub-Category / Person', 'Amount (PKR)', 'Notes']], use_container_width=True, hide_index=True)
                else: st.info("No detailed breakdown available for this month.")
                    
        with tab7:
            st.subheader(f"🏛️ Advanced Tax Analytics ({selected_fy})")
            gross = month_data['Gross Pay']
            basic = month_data['Basic Pay']
            tax = month_data['Income Tax']
            
            effective_rate = (tax / gross * 100) if gross > 0 else 0
            tax_pct_basic = (tax / basic * 100) if basic > 0 else 0
            cum_tax_fy = df_fy['Income Tax'].sum()
            
            tx1, tx2, tx3, tx4 = st.columns(4)
            tx1.metric("Income Tax Deducted", f"Rs. {tax:,.0f}")
            tx2.metric("Effective Tax Rate", f"{effective_rate:.2f}%")
            tx3.metric("Tax % of Basic Pay", f"{tax_pct_basic:.2f}%")
            tx4.metric(f"Cumulative Tax ({selected_fy})", f"Rs. {cum_tax_fy:,.0f}")
            
            st.divider()
            fig_tax = px.bar(df_fy, x="Month", y="Income Tax", text="Income Tax", template="plotly_white", color_discrete_sequence=['#d62728'])
            fig_tax.update_traces(texttemplate='Rs. %{text:,.0f}', textposition='outside')
            fig_tax.update_layout(yaxis_title="Tax Paid (PKR)", margin=dict(t=30, b=0, l=0, r=0))
            st.plotly_chart(fig_tax, use_container_width=True)
            
        with tab8:
            st.subheader("🔮 Salary & Promotion Simulator")
            sim_col1, sim_col2 = st.columns([1, 1])
            with sim_col1:
                st.markdown("#### 📈 Income Adjustments")
                sim_basic = st.number_input("Basic Salary", value=float(month_data['Basic Pay']), step=1000.0)
                sim_hard_area = st.number_input("Hard Area Allowance", value=float(month_data['Hard Area']), step=500.0)
                sim_hra = st.number_input("House Rent Allowance", value=float(month_data['House Rent Allowance']), step=500.0)
                sim_other_earn = st.number_input("Other Earnings", value=float(month_data['Other Earnings'] + month_data['Other Allowances']), step=500.0)
                
                st.markdown("#### 📉 Deduction Adjustments")
                sim_tax = st.number_input("Estimated Income Tax", value=float(month_data['Income Tax']), step=500.0)
                sim_pf = st.number_input("PF Deduction", value=float(month_data['PF Deduction']), step=100.0)
                sim_mess_club = st.number_input("Estimated Mess & Club", value=float(month_data['Mess Bill'] + month_data['Club Bill']), step=500.0)
                sim_rent_ded = st.number_input("House Rent Deduction", value=float(month_data['House Rent Deduction']), step=100.0)

            with sim_col2:
                sim_gross = sim_basic + sim_hard_area + sim_hra + sim_other_earn
                sim_total_deductions = sim_tax + sim_pf + sim_mess_club + sim_rent_ded + month_data['EOBI']
                sim_net = sim_gross - sim_total_deductions
                
                diff_gross = sim_gross - month_data['Gross Pay']
                diff_net = sim_net - month_data['Net Pay']
                
                st.markdown("#### 📊 Projected Outcome")
                st.metric("Projected Gross Pay", f"Rs. {sim_gross:,.0f}", f"{'+' if diff_gross >=0 else ''}{diff_gross:,.0f} from current")
                st.metric("Projected Net Take-Home", f"Rs. {sim_net:,.0f}", f"{'+' if diff_net >=0 else ''}{diff_net:,.0f} from current")
                st.metric("Projected Total Deductions", f"Rs. {sim_total_deductions:,.0f}", delta_color="inverse")


        # ===================================================================================================
        # --- FEATURE 6: FOOLPROOF JAVASCRIPT FLOATING AI WIDGET (ADNOC STYLE) ---
        # ===================================================================================================

        st.markdown("<style>div[data-testid='stPopover'] { display: none; }</style>", unsafe_allow_html=True)
        
        # 1. Inject DOM JS Hack to force the perfect circular button natively in the browser
        components.html("""
        <script>
        const huntForButton = setInterval(() => {
            const doc = window.parent.document;
            const buttons = doc.querySelectorAll('button');
            
            buttons.forEach(btn => {
                if (btn.innerText.includes('🤖')) {
                    clearInterval(huntForButton);
                    
                    // Force Circle Button (Overrides Streamlit's minimum width/bar shape)
                    btn.style.setProperty('background-color', '#0066FF', 'important');
                    btn.style.setProperty('border-radius', '50%', 'important');
                    btn.style.setProperty('width', '70px', 'important');
                    btn.style.setProperty('height', '70px', 'important');
                    btn.style.setProperty('min-width', '70px', 'important');
                    btn.style.setProperty('min-height', '70px', 'important');
                    btn.style.setProperty('padding', '0', 'important');
                    btn.style.setProperty('display', 'flex', 'important');
                    btn.style.setProperty('align-items', 'center', 'important');
                    btn.style.setProperty('justify-content', 'center', 'important');
                    btn.style.setProperty('box-shadow', '0px 8px 25px rgba(0, 102, 255, 0.4)', 'important');
                    btn.style.setProperty('border', 'none', 'important');
                    btn.style.setProperty('transition', 'transform 0.3s cubic-bezier(0.25, 0.8, 0.25, 1)', 'important');
                    
                    // Add Tooltip natively
                    btn.setAttribute('title', 'Ask AI');
                    
                    // Hover effects
                    btn.onmouseover = function() { 
                        this.style.setProperty('transform', 'scale(1.1) translateY(-5px)', 'important');
                        this.style.setProperty('box-shadow', '0px 12px 30px rgba(0, 102, 255, 0.6)', 'important');
                    }
                    btn.onmouseout = function() { 
                        this.style.setProperty('transform', 'scale(1.0) translateY(0)', 'important');
                        this.style.setProperty('box-shadow', '0px 8px 25px rgba(0, 102, 255, 0.4)', 'important');
                    }
                    
                    // Erase Streamlit Dropdown Arrow
                    const svg = btn.querySelector('svg');
                    if (svg) svg.style.setProperty('display', 'none', 'important');
                    
                    // Center the Robot Text
                    const p = btn.querySelector('p');
                    if (p) {
                        p.style.setProperty('font-size', '35px', 'important');
                        p.style.setProperty('margin', '0', 'important');
                        p.style.setProperty('color', 'white', 'important');
                    }
                    
                    // Float the Container
                    let container = btn.closest('div[data-testid="stPopover"]');
                    if (container) {
                        container.style.setProperty('display', 'block', 'important');
                        container.style.setProperty('position', 'fixed', 'important');
                        container.style.setProperty('bottom', '30px', 'important');
                        container.style.setProperty('right', '30px', 'important');
                        container.style.setProperty('z-index', '999999', 'important');
                    }
                }
            });
        }, 100);
        </script>
        """, height=0, width=0)

        # 2. Add CSS constraints for the Popup Body and Chat Bubbles
        st.markdown("""
        <style>
        /* Force Popup placement and size */
        div[data-testid="stPopoverBody"] {
            width: 380px !important;
            min-width: 380px !important;
            max-width: 95vw !important;
            height: 550px !important;
            min-height: 550px !important;
            border-radius: 20px !important;
            box-shadow: 0 15px 40px rgba(0,0,0,0.2) !important;
            border: 1px solid rgba(0,0,0,0.05) !important;
            padding: 0 !important;
            overflow: hidden !important;
            background: white !important;
            
            position: fixed !important;
            bottom: 110px !important;
            right: 30px !important;
            top: auto !important;
            left: auto !important;
            transform: none !important;
        }

        /* Hide avatars */
        div[data-testid="stChatMessage"] [data-testid="chatAvatarIcon-user"], 
        div[data-testid="stChatMessage"] [data-testid="chatAvatarIcon-assistant"] {
            display: none !important;
        }
        
        /* Base bubble */
        div[data-testid="stChatMessage"] {
            padding: 10px 14px !important;
            margin-bottom: 15px !important;
            width: fit-content !important;
            max-width: 85% !important;
            background-color: transparent !important;
            border: none !important;
        }
        
        /* User Bubble (Right) */
        div[data-testid="stChatMessage"]:has(.is-user) {
            background-color: #0066FF !important;
            border-radius: 18px 18px 4px 18px !important;
            margin-left: auto !important;
            margin-right: 15px !important;
        }
        div[data-testid="stChatMessage"]:has(.is-user) * { color: white !important; }
        
        /* AI Bubble (Left) */
        div[data-testid="stChatMessage"]:has(.is-ai) {
            background-color: #F0F2F5 !important;
            border-radius: 18px 18px 18px 4px !important;
            margin-right: auto !important;
            margin-left: 15px !important;
        }
        div[data-testid="stChatMessage"]:has(.is-ai) * { color: #1a1a1a !important; }

        .chat-time { font-size: 10px; opacity: 0.7; display: block; margin-top: 5px; text-align: right; }
        .bot-header { background: linear-gradient(135deg, #0066FF, #0047CC); padding: 20px; border-radius: 20px 20px 0 0; }
        .bot-header h3 { color: white !important; margin: 0; font-size: 20px; font-weight: 600; }
        .bot-header p { color: rgba(255,255,255,0.9) !important; margin: 5px 0 0 0; font-size: 12px; }
        </style>
        """, unsafe_allow_html=True)

        with st.popover("🤖"):
            st.markdown("""
            <div class="bot-header">
                <h3>🤖 AI Assistant</h3>
                <p>Ask anything about your salary, HR policies, leaves, expenses, or company info.</p>
            </div>
            """, unsafe_allow_html=True)
            
            tool_col1, tool_col2, tool_col3 = st.columns([1,1,1])
            with tool_col1:
                if st.button("🔄 Clear", key="clear_chat", use_container_width=True):
                    st.session_state["widget_chat_history"] = []
                    st.rerun()
            with tool_col2:
                with st.popover("📎 Attach"):
                    uploaded_file = st.file_uploader("Upload PDF, CSV, Excel", type=["pdf", "csv", "xlsx"])
            with tool_col3:
                chat_export = ""
                if "widget_chat_history" in st.session_state:
                    for m in st.session_state["widget_chat_history"]:
                        chat_export += f"[{m['timestamp']}] {m['role'].upper()}:\n{m['content']}\n\n"
                st.download_button("📥 Save", data=chat_export, file_name="AGL_Chat_Log.txt", mime="text/plain", use_container_width=True)

            if "widget_chat_history" not in st.session_state:
                st.session_state["widget_chat_history"] = []

            chat_container = st.container(height=320)
            
            with chat_container:
                suggested_prompt = None
                if len(st.session_state["widget_chat_history"]) == 0:
                    st.markdown("<br><p style='text-align:center; color:gray; font-size:12px;'>Suggested Questions</p>", unsafe_allow_html=True)
                    s_col1, s_col2 = st.columns(2)
                    if s_col1.button("💰 Salary Summary", use_container_width=True): suggested_prompt = "Give me a quick summary of my salary this month."
                    if s_col2.button("📈 Analyze Expenses", use_container_width=True): suggested_prompt = "Analyze my logged expenses for this month."
                    if s_col1.button("🏖 Leave Balance", use_container_width=True): suggested_prompt = "What is my current leave balance?"
                    if s_col2.button("🏭 Company Policies", use_container_width=True): suggested_prompt = "What are the standard HR policies for Shift Engineers?"

                for message in st.session_state["widget_chat_history"]:
                    with st.chat_message(message["role"]):
                        role_class = "is-user" if message["role"] == "user" else "is-ai"
                        st.markdown(f"<div class='{role_class}'></div>", unsafe_allow_html=True)
                        st.markdown(message["content"])
                        st.markdown(f"<span class='chat-time'>{message['timestamp']}</span>", unsafe_allow_html=True)

            user_input = st.chat_input("Ask me anything...")
            prompt = suggested_prompt or user_input

            if prompt:
                curr_time = datetime.datetime.now().strftime("%I:%M %p")
                st.session_state["widget_chat_history"].append({"role": "user", "content": prompt, "timestamp": curr_time})
                st.rerun()

            if len(st.session_state["widget_chat_history"]) > 0 and st.session_state["widget_chat_history"][-1]["role"] == "user":
                with chat_container:
                    with st.chat_message("assistant"):
                        st.markdown("<div class='is-ai'></div>", unsafe_allow_html=True)
                        with st.spinner("Thinking..."):
                            try:
                                file_context = ""
                                if uploaded_file is not None:
                                    file_context = "\n\n[USER UPLOADED FILE DATA]\n"
                                    if uploaded_file.name.endswith('.csv'):
                                        df_upload = pd.read_csv(uploaded_file)
                                        file_context += df_upload.to_string(max_rows=50)
                                    elif uploaded_file.name.endswith('.xlsx'):
                                        df_upload = pd.read_excel(uploaded_file)
                                        file_context += df_upload.to_string(max_rows=50)
                                    elif uploaded_file.name.endswith('.pdf') and PYPDF_AVAILABLE:
                                        pdf_reader = PyPDF2.PdfReader(uploaded_file)
                                        for i in range(min(3, len(pdf_reader.pages))): 
                                            file_context += pdf_reader.pages[i].extract_text()
                                    else:
                                        file_context += f"Filename: {uploaded_file.name}. (Content extraction requires specific python libraries)."
                                
                                expense_context = f"Total out-of-pocket expenses logged: Rs. {total_spent:,.0f}" if 'total_spent' in locals() else "No manual expenses logged this month."
                                system_context = f"""
                                You are Gemini, an elite Executive AI Financial Advisor for Waqar Ahmed Tunio at AgriTech Ltd.
                                Current Context for {month_data['Month']}: Gross Pay: Rs. {month_data['Gross Pay']:,.0f}, Net Pay: Rs. {month_data['Net Pay']:,.0f}.
                                Total Deductions: Rs. {month_data['Total Deductions']:,.0f}. 
                                Leave Balance: {month_data['Leave Balance']} days.
                                {expense_context}
                                {file_context}
                                
                                Use Markdown. Use bullet points and bold text for numbers.
                                """

                                client = Groq(api_key=st.secrets["GROQ_API_KEY"]) 
                                active_models = [m.id for m in client.models.list().data]
                                chosen_model = next((model for model in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"] if model in active_models), active_models[0])
                                
                                api_messages = [{"role": "system", "content": system_context}]
                                for msg in st.session_state["widget_chat_history"]:
                                    api_messages.append({"role": msg["role"], "content": msg["content"]})
                                
                                completion = client.chat.completions.create(model=chosen_model, messages=api_messages, temperature=0.4, max_tokens=600)
                                response_text = completion.choices[0].message.content
                                
                                st.session_state["widget_chat_history"].append({"role": "assistant", "content": response_text, "timestamp": datetime.datetime.now().strftime("%I:%M %p")})
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"AI Error: {str(e)}")

if __name__ == '__main__':
    main()
