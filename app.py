import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- NEW: Import our background functions from our new file ---
from data_loader import fetch_salary_data, fetch_expense_data

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

def render_executive_kpi(df):
    st.markdown("### 📊 Lifetime Executive Summary")
    
    # --- Calculations ---
    total_earnings = df['Gross Pay'].sum()
    total_tax = df['Income Tax'].sum()
    
    # Assuming PF Company Match is equal to Employee Deduction
    total_pf_saved = (df['PF Deduction'].sum()) * 2 
    
    avg_gross = df['Gross Pay'].mean()
    avg_net = df['Net Pay'].mean()
    
    # Find the row with the highest gross salary
    highest_salary_row = df.loc[df['Gross Pay'].idxmax()]
    highest_month = highest_salary_row['Month']
    highest_amount = highest_salary_row['Gross Pay']
    
    # --- UI Layout ---
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    
    kpi1.metric("Total Career Earnings", f"Rs. {total_earnings:,.0f}")
    kpi2.metric("Total Tax Paid", f"Rs. {total_tax:,.0f}")
    kpi3.metric("Total PF Saved", f"Rs. {total_pf_saved:,.0f}", help="Employee + Company")
    
    kpi4.metric("Avg Monthly Net", f"Rs. {avg_net:,.0f}", f"Gross: {avg_gross:,.0f}", delta_color="off")
    kpi5.metric("Highest Salary", f"Rs. {highest_amount:,.0f}", f"{highest_month}", delta_color="off")
    
    st.divider()

def main():
    if check_password():
        # --- BRANDING & HEADER ---
        st.markdown("<h1>🏭 AgriTech Ltd <span style='font-size:24px; color:gray;'>| Executive Compensation Portal</span></h1>", unsafe_allow_html=True)
        
        with st.spinner("Synchronizing securely with Gmail..."):
            df = fetch_salary_data()

        if df.empty:
            st.warning("No valid pay slip data could be parsed. Check email formatting.")
            return

        # ---> NEW: INJECT KPI DASHBOARD HERE <---
        render_executive_kpi(df)

        # --- SIDEBAR CONTROLS ---
        st.sidebar.markdown("### ⚙️ Financial Engine")
        st.sidebar.markdown("Isolate a specific tax cycle.")
        # ... (keep the rest of your main function exactly as it is)
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
                
                st.markdown("###### Main Categories Logged")
                
                def get_cat_mom_delta(cat, curr_val):
                    if not prev_exp.empty and cat in prev_exp['Category'].values:
                        prev_val = prev_exp[prev_exp['Category'] == cat]['Amount (PKR)'].sum()
                        diff = curr_val - prev_val
                        sign = "+" if diff >= 0 else "-"
                        return f"{sign} Rs. {abs(diff):,.0f} MoM"
                    return None
                    
                # --- NEW LAYOUT: PIE CHART + METRICS GRID ---
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
                                cat = categories[i+j]
                                val = category_sums[cat]
                                cols[j].metric(cat, f"Rs. {val:,.0f}", delta=get_cat_mom_delta(cat, val), delta_color="inverse")
                # --------------------------------------------

            else:
                st.info(f"No manual expenses logged yet for {month_data['Month']}.")
                
        elif exp_error:
            st.error(f"⚠️ {exp_error}")

        st.markdown("<br>", unsafe_allow_html=True)

        # --- SECTION 3: TABS ---
        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
            "📊 Pay & Tax Trends", 
            "🏠 Site Housing & Living", 
            "🎓 Master's Fund Tracker",
            "⚖️ Compare Months",
            "🗄️ Raw Data Export",
            "💸 Pocket Expenses (Log)",
            "🏛️ Tax Analytics"
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
                
                fig_pie = px.pie(names=deduction_labels, values=fy_deduction_values, hole=0.5, template="plotly_white")
                fig_pie.update_traces(textposition='inside', textinfo='percent')
                fig_pie.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5))
                st.plotly_chart(fig_pie, use_container_width=True)

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
            all_months_sorted = df.sort_values('Date', ascending=False)['Month'].unique()
            col_comp1, col_comp2 = st.columns(2)
            with col_comp1:
                month_a = st.selectbox("Baseline Month (Month A)", options=all_months_sorted, index=min(1, len(all_months_sorted)-1))
            with col_comp2:
                month_b = st.selectbox("Comparison Month (Month B)", options=all_months_sorted, index=0)
                
            if month_a and month_b:
                data_a = df[df['Month'] == month_a].iloc[0]
                data_b = df[df['Month'] == month_b].iloc[0]
                
                st.markdown(f"#### 💰 Earnings & Allowances")
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

        with tab5:
            st.subheader("Raw Extracted Data")
            display_df = df.drop(columns=['Date', 'Month_Name'])
            st.dataframe(display_df, use_container_width=True)
            csv = display_df.to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 Download Complete History as CSV", data=csv, file_name=f"agl_complete_salary_history.csv", mime="text/csv")

        with tab6:
            st.subheader("💸 Detailed Pocket Expenses")
            if df_exp.empty:
                st.warning("⚠️ Expense file could not be read.")
            else:
                curr_exp = df_exp[df_exp['Salary Month'] == month_data['Month']]
                if not curr_exp.empty:
                    st.dataframe(curr_exp[['Date', 'Category', 'Sub-Category / Person', 'Amount (PKR)', 'Notes']], use_container_width=True, hide_index=True)
                else:
                    st.info("No detailed breakdown available for this month.")
with tab7:
            st.subheader(f"🏛️ Advanced Tax Analytics ({selected_fy})")
            
            # Extract month specific variables
            gross = month_data['Gross Pay']
            basic = month_data['Basic Pay']
            tax = month_data['Income Tax']
            
            # Calculate Analytics
            effective_rate = (tax / gross * 100) if gross > 0 else 0
            tax_pct_basic = (tax / basic * 100) if basic > 0 else 0
            cum_tax_fy = df_fy['Income Tax'].sum()
            
            st.markdown(f"#### 🔎 Tax Snapshot: {month_data['Month']}")
            tx1, tx2, tx3, tx4 = st.columns(4)
            tx1.metric("Income Tax Deducted", f"Rs. {tax:,.0f}")
            tx2.metric("Effective Tax Rate", f"{effective_rate:.2f}%", help="Tax as a percentage of Total Gross Pay")
            tx3.metric("Tax % of Basic Pay", f"{tax_pct_basic:.2f}%")
            tx4.metric(f"Cumulative Tax ({selected_fy})", f"Rs. {cum_tax_fy:,.0f}")
            
            st.divider()
            
            st.markdown("#### 📈 Monthly Tax Deduction Trend")
            fig_tax = px.bar(df_fy, x="Month", y="Income Tax", text="Income Tax", template="plotly_white", color_discrete_sequence=['#d62728'])
            fig_tax.update_traces(texttemplate='Rs. %{text:,.0f}', textposition='outside')
            fig_tax.update_layout(yaxis_title="Tax Paid (PKR)", margin=dict(t=30, b=0, l=0, r=0))
            st.plotly_chart(fig_tax, use_container_width=True)

if __name__ == '__main__':
    main()
