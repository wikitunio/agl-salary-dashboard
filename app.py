import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from groq import Groq

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
        
        available_fys = sorted(df['FY'].unique(), reverse=True)
        selected_fy = st.sidebar.selectbox("1. Select Financial Year", options=available_fys)
        
        df_fy = df[df['FY'] == selected_fy]
        
        available_months = df_fy['Month_Name'].unique().tolist()
        fy_month_order = ['JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC', 'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN']
        sorted_months = sorted(available_months, key=lambda x: fy_month_order.index(x) if x in fy_month_order else 12)
        
        selected_month = st.sidebar.selectbox("2. Select Focus Month", options=sorted_months, index=len(sorted_months)-1)
        
        month_data = df_fy[df_fy['Month_Name'] == selected_month].iloc[0]
        
        st.sidebar.markdown("---")
        st.sidebar.caption("✅ Version 3.1: Modular + Tax Tab")

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
        
        # --- SECTION 2B: CASH FLOW & FINANCIAL HEALTH ---
        df_exp, exp_error = fetch_expense_data()
        
        if not df_exp.empty:
            df_exp['Salary Month'] = df_exp['Salary Month'].astype(str).str.strip()
            curr_exp = df_exp[df_exp['Salary Month'] == month_data['Month']]
            
            prev_exp_month_name = prev_month_data['Month'] if prev_month_data is not None else None
            prev_exp = df_exp[df_exp['Salary Month'] == prev_exp_month_name] if prev_exp_month_name else pd.DataFrame()
            
            st.markdown("##### 🩺 Cash Flow & Financial Health Score")
            
            if not curr_exp.empty:
                category_sums = curr_exp.groupby('Category')['Amount (PKR)'].sum()
                total_spent = category_sums.sum()
                net_pay = month_data['Net Pay']
                remaining_cash = net_pay - total_spent
                
                # --- NEW: FINANCIAL HEALTH ENGINE ---
                # 1. Savings Rate Calculation
                savings_rate = (remaining_cash / net_pay * 100) if net_pay > 0 else 0
                
                # 2. PF Growth Rate Calculation
                total_pf = month_data['PF Deduction'] * 2 # Employee + Company Match
                pf_rate = (total_pf / month_data['Gross Pay'] * 100) if month_data['Gross Pay'] > 0 else 0
                
                # 3. Site Efficiency Calculation
                site_expenses = month_data['Mess Bill'] + month_data['Club Bill']
                hard_area = month_data['Hard Area']
                site_ratio = (site_expenses / hard_area * 100) if hard_area > 0 else 100
                
                # 4. Grading Logic
                score_savings = min(50, (max(0, savings_rate) / 30) * 50) # Target: 30% savings rate (50 pts)
                score_pf = min(30, (pf_rate / 10) * 30)                   # Target: 10% of gross in PF (30 pts)
                score_site = 20 if site_ratio <= 100 else max(0, 20 - (site_ratio - 100)) # Target: Mess/Club < Hard Area (20 pts)
                
                health_score = int(score_savings + score_pf + score_site)
                
                # 5. Star Rating Assessment
                if health_score >= 90: stars = "⭐⭐⭐⭐⭐ Excellent"
                elif health_score >= 70: stars = "⭐⭐⭐⭐ Good"
                elif health_score >= 50: stars = "⭐⭐⭐ Fair"
                else: stars = "⭐⭐ Needs Attention"
                # ------------------------------------
                
                # Total MoM Calculation
                total_mom_str = None
                if not prev_exp.empty:
                    prev_total = prev_exp['Amount (PKR)'].sum()
                    diff = total_spent - prev_total
                    sign = "+" if diff >= 0 else "-"
                    total_mom_str = f"{sign} Rs. {abs(diff):,.0f} MoM"
                
                # Render Executive Health Metrics
                ex_cols = st.columns(4)
                ex_cols[0].metric("Total Spent", f"Rs. {total_spent:,.0f}", delta=total_mom_str, delta_color="inverse")
                ex_cols[1].metric("Remaining Cash", f"Rs. {remaining_cash:,.0f}")
                ex_cols[2].metric("True Savings Rate", f"{savings_rate:.1f}%")
                ex_cols[3].metric("Financial Health", f"{health_score} / 100", stars, delta_color="off")
                
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
# --- SECTION 2C: SMART FINANCIAL INSIGHTS (AI POWERED) ---
        st.markdown("### 🤖 Smart Financial Insights")
        
        with st.expander(f"Click to view AI-Generated Insights for {month_data['Month']}", expanded=True):
            if prev_month_data is not None:
                # Define a unique memory key for this month so we only call the API once per month
                cache_key = f"insights_{selected_month}_{selected_fy}"
                
                if "ai_insights_cache" not in st.session_state:
                    st.session_state["ai_insights_cache"] = {}
                    
                if cache_key in st.session_state["ai_insights_cache"]:
                    # Show the memorized AI response instantly
                    st.markdown(st.session_state["ai_insights_cache"][cache_key])
                else:
                    st.markdown("Want a professional AI analysis of your Month-over-Month cash flow?")
                    if st.button(f"✨ Generate AI Insights for {month_data['Month']}"):
                        with st.spinner(f"AI is analyzing {month_data['Month']} vs {prev_month_data['Month']}..."):
                            try:
                                client = Groq(api_key=st.secrets["GROQ_API_KEY"]) 
                                
                                # --- Smart Model Selector ---
                                active_models = [m.id for m in client.models.list().data]
                                preferred_models = ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "llama-3.1-8b-instant"]
                                chosen_model = next((model for model in preferred_models if model in active_models), None)
                                if not chosen_model:
                                    valid_fallbacks = [m for m in active_models if "guard" not in m.lower() and "vision" not in m.lower()]
                                    chosen_model = valid_fallbacks[0] if valid_fallbacks else active_models[0]
                                    
                                # --- SAFE PRE-FORMATTED STRINGS ---
                                g_curr = "{:,.0f}".format(month_data['Gross Pay'])
                                n_curr = "{:,.0f}".format(month_data['Net Pay'])
                                t_curr = "{:,.0f}".format(month_data['Income Tax'])
                                s_curr = "{:,.0f}".format(month_data['Mess Bill'] + month_data['Club Bill'])
                                
                                exp_c_val = total_spent if 'total_spent' in locals() else 0
                                e_curr = "{:,.0f}".format(exp_c_val)
                                
                                g_prev = "{:,.0f}".format(prev_month_data['Gross Pay'])
                                n_prev = "{:,.0f}".format(prev_month_data['Net Pay'])
                                t_prev = "{:,.0f}".format(prev_month_data['Income Tax'])
                                s_prev = "{:,.0f}".format(prev_month_data['Mess Bill'] + prev_month_data['Club Bill'])
                                
                                exp_p_val = prev_exp['Amount (PKR)'].sum() if (not prev_exp.empty) else 0
                                e_prev = "{:,.0f}".format(exp_p_val)
                                
                                prompt = (
                                    "Act as a corporate financial advisor for an Executive Chemical Engineer at AgriTech Ltd. "
                                    f"Analyze the Month-over-Month changes between {selected_month} and {prev_month_data['Month']}:\n\n"
                                    f"[CURRENT MONTH: {selected_month}]\n"
                                    f"- Gross Pay: Rs. {g_curr}\n"
                                    f"- Net Pay (Take Home): Rs. {n_curr}\n"
                                    f"- Income Tax: Rs. {t_curr}\n"
                                    f"- Site Living (Mess+Club): Rs. {s_curr}\n"
                                    f"- Out of Pocket Expenses: Rs. {e_curr}\n\n"
                                    f"[PREVIOUS MONTH: {prev_month_data['Month']}]\n"
                                    f"- Gross Pay: Rs. {g_prev}\n"
                                    f"- Net Pay (Take Home): Rs. {n_prev}\n"
                                    f"- Income Tax: Rs. {t_prev}\n"
                                    f"- Site Living (Mess+Club): Rs. {s_prev}\n"
                                    f"- Out of Pocket Expenses: Rs. {e_prev}\n\n"
                                    "Write 3 to 4 concise, punchy bullet points using emojis. "
                                    "Highlight key changes in income, tax, spending habits, and overall savings efficiency. "
                                    "Explain what these differences mean practically. "
                                    "Do NOT write an introduction or conclusion. Output ONLY the bullet points."
                                )
                                
                                completion = client.chat.completions.create(
                                    model=chosen_model,
                                    messages=[{"role": "user", "content": prompt}],
                                    temperature=0.3,
                                    max_tokens=400
                                )
                                
                                result = completion.choices[0].message.content
                                result += f"\n\n*(Powered by {chosen_model})*"
                                
                                st.session_state["ai_insights_cache"][cache_key] = result
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"Groq API Error: {str(e)}")
            else:
                st.info("Not enough historical data to generate Month-over-Month insights. Select a month with a preceding record.")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        
        # --- AI INVESTMENT PLANNER (PAKISTAN OUTLOOK) ---
        st.divider()
        st.markdown("### 📈 AI Wealth & Investment Planner")
        
        if 'remaining_cash' in locals() and remaining_cash > 0:
            st.success(f"**Available Surplus Cash:** Rs. {remaining_cash:,.0f}")
            st.caption("Let AI generate a dynamic investment portfolio based on current macroeconomic conditions in Pakistan.")
            
            if st.button("🔮 Generate Pakistan Market Allocation"):
                with st.spinner("Analyzing Pakistan inflation, interest rates, and PSX trends..."):
                    try:
                        client = Groq(api_key=st.secrets["GROQ_API_KEY"]) 
                        
                        # --- Smart Model Selector ---
                        active_models = [m.id for m in client.models.list().data]
                        preferred_models = ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "llama-3.1-8b-instant"]
                        chosen_model = next((model for model in preferred_models if model in active_models), None)
                        if not chosen_model:
                            valid_fallbacks = [m for m in active_models if "guard" not in m.lower() and "vision" not in m.lower()]
                            chosen_model = valid_fallbacks[0] if valid_fallbacks else active_models[0]
                        
                        prompt = f"""
                        Act as an elite Wealth Manager based in Pakistan with deep knowledge of the Pakistan Stock Exchange (PSX), local Asset Management Companies (AMCs), and banking products.
                        Your client is an Executive Chemical Engineer who has Rs. {remaining_cash:,.0f} in surplus cash this month.
                        
                        Allocate the Rs. {remaining_cash:,.0f} into a smart portfolio. 
                        
                        CRITICAL INSTRUCTION: Do NOT use generic terms like "Stocks" or "Mutual Funds". You MUST name specific, well-known Pakistani assets. 
                        For example: Name specific dividend-paying PSX stocks (e.g., EFERT, HUBC, ENGRO, MEBL), specific ETFs (e.g., MZNP-ETF, NITG-ETF), specific Mutual Funds (e.g., Meezan Rozana Amdani Fund, UBL Al-Ameen Islamic, NBP Funds), and specific bank accounts (e.g., Meezan Asaan, Bank Islami).
                        
                        Output EXACTLY in this Markdown format:
                        
                        ### 📊 Recommended Pakistan Portfolio
                        | Asset Class | Specific Recommendation (Name) | Allocation % | Amount (PKR) | Rationale |
                        |---|---|---|---|---|
                        | Emergency Fund | [Specific Bank/Account] | X% | Rs. Y | ... |
                        | PSX Stocks/ETFs | [Specific Stock/ETF Ticker] | X% | Rs. Y | ... |
                        | Mutual Funds | [Specific Fund Name] | X% | Rs. Y | ... |
                        | High-Yield/Islamic | [Specific Product] | X% | Rs. Y | ... |
                        
                        *Note: Ensure the Allocation % adds up to 100% and Amounts exactly add up to {remaining_cash:,.0f}.*
                        
                        ### 📰 Market Outlook Rationale
                        Provide 3 punchy bullet points on why these specific assets make sense given the current economic climate in Pakistan.
                        
                        **⚠️ AI Disclaimer:** *This allocation is generated based on historical Pakistani market trends and blue-chip performance. Always verify current PSX live prices and Mutual Fund NAVs before investing.*
                        """
                        
                        completion = client.chat.completions.create(
                            model=chosen_model,
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.4,
                            max_tokens=600
                        )
                        
                        st.markdown(completion.choices[0].message.content)
                        st.caption(f"⚡ *Powered by {chosen_model} via Groq LPU*")
                        
                    except Exception as e:
                        st.error(f"AI Connection Error: {str(e)}")
        elif 'remaining_cash' in locals():
            st.warning("No surplus cash available this month to allocate. Focus on reducing expenses to build your investment pool!")  # -------------------------                              
        # --- SECTION 3: TABS ---
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
            "📊 Pay & Tax Trends", 
            "🏠 Site Housing & Living", 
            "🎓 Master's Fund Tracker",
            "⚖️ Compare Months",
            "🗄️ Raw Data Export",
            "💸 Pocket Expenses (Log)",
            "🏛️ Tax Analytics",
            "🔮 Salary Simulator",
            "🤖 AI Chat Assistant"
        ])
        with tab1:
            st.subheader("💧 Salary & Expense Waterfall")
            
            # Prepare initial variables
            wf_gross = month_data['Gross Pay']
            wf_tax = month_data['Income Tax']
            wf_pf = month_data['PF Deduction']
            wf_mess = month_data['Mess Bill']
            wf_club = month_data['Club Bill']
            wf_rent = month_data['House Rent Deduction']
            wf_eobi = month_data['EOBI']
            wf_net = month_data['Net Pay']
            
            # Safely fetch Pocket Expenses
            wf_expenses = 0
            if 'df_exp' in locals() and not df_exp.empty:
                curr_exp = df_exp[df_exp['Salary Month'] == month_data['Month']]
                if not curr_exp.empty:
                    wf_expenses = curr_exp['Amount (PKR)'].sum()
                    
            wf_savings = wf_net - wf_expenses
            
            # Dynamically build the chart sequence
            x_list = ["Gross Pay", "Income Tax", "PF Deduction", "Mess Bill", "Club Bill", "Rent", "EOBI"]
            y_list = [wf_gross, -wf_tax, -wf_pf, -wf_mess, -wf_club, -wf_rent, -wf_eobi]
            text_list = [f"{wf_gross:,.0f}", f"-{wf_tax:,.0f}", f"-{wf_pf:,.0f}", f"-{wf_mess:,.0f}", f"-{wf_club:,.0f}", f"-{wf_rent:,.0f}", f"-{wf_eobi:,.0f}"]
            measure_list = ["relative"] * 7
            
            # Catch unmapped payslip deductions automatically
            unmapped = month_data['Total Deductions'] - (wf_tax + wf_pf + wf_mess + wf_club + wf_rent + wf_eobi)
            if unmapped > 5:
                x_list.append("Other Deductions")
                y_list.append(-unmapped)
                text_list.append(f"-{unmapped:,.0f}")
                measure_list.append("relative")
                
            # Add the Net Pay checkpoint, the Expenses step, and the Final Cash total
            x_list.extend(["Net Pay", "Pocket Expenses", "Remaining Cash"])
            y_list.extend([wf_net, -wf_expenses, wf_savings])
            text_list.extend([f"{wf_net:,.0f}", f"-{wf_expenses:,.0f}", f"{wf_savings:,.0f}"])
            measure_list.extend(["total", "relative", "total"])
            
            # Build the Plotly Waterfall Chart
            fig_waterfall = go.Figure(go.Waterfall(
                name="Salary Flow", orientation="v",
                measure=measure_list,
                x=x_list,
                y=y_list,
                textposition="outside",
                text=text_list,
                connector={"line": {"color": "gray", "width": 1.5}},
                decreasing={"marker": {"color": "#ff4b4b"}},   # Streamlit Red for all deductions/expenses
                increasing={"marker": {"color": "#2ca02c"}},   # Green for starting Gross Pay
                totals={"marker": {"color": "#1f77b4"}}        # Blue for Net Pay and Final Cash
            ))
            
            fig_waterfall.update_layout(
                template="plotly_white", 
                margin=dict(t=30, b=20, l=0, r=0),
                yaxis_title="Rupees (PKR)",
                showlegend=False,
                height=500
            )
            st.plotly_chart(fig_waterfall, use_container_width=True)

        # --- NEW: SALARY GROWTH ANALYTICS ---
            st.markdown(f"### 📈 Salary Growth Analytics ({selected_fy})")
            
            df_fy_sorted = df_fy.sort_values('Date')
            if len(df_fy_sorted) >= 2:
                start_m = df_fy_sorted.iloc[0]
                end_m = df_fy_sorted.iloc[-1]
                
                # Standard Growth Formula: (New - Old) / Old * 100
                def calc_g(start, end):
                    return ((end - start) / start * 100) if start > 0 else 0
                
                g_gross = calc_g(start_m['Gross Pay'], end_m['Gross Pay'])
                g_basic = calc_g(start_m['Basic Pay'], end_m['Basic Pay'])
                g_net = calc_g(start_m['Net Pay'], end_m['Net Pay'])
                
                start_allow = start_m['Hard Area'] + start_m['House Rent Allowance'] + start_m['Other Allowances'] + start_m['Other Earnings']
                end_allow = end_m['Hard Area'] + end_m['House Rent Allowance'] + end_m['Other Allowances'] + end_m['Other Earnings']
                g_allow = calc_g(start_allow, end_allow)
                
                # Lifetime CAGR Calculation
                df_sorted_all = df.sort_values('Date')
                days_diff = (df_sorted_all.iloc[-1]['Date'] - df_sorted_all.iloc[0]['Date']).days
                total_years = max(days_diff / 365.25, 1.0) # Prevents inflation if less than 1 year of data
                
                first_gross = df_sorted_all.iloc[0]['Gross Pay']
                last_gross = df_sorted_all.iloc[-1]['Gross Pay']
                cagr = (((last_gross / first_gross) ** (1 / total_years)) - 1) * 100 if first_gross > 0 else 0
                
                st.caption(f"**Period Tracking:** {start_m['Month']} ➡️ {end_m['Month']}")
                
                gr1, gr2, gr3, gr4, gr5 = st.columns(5)
                gr1.metric("Gross Salary Growth", f"{'+' if g_gross >= 0 else ''}{g_gross:.1f}%")
                gr2.metric("Basic Salary Growth", f"{'+' if g_basic >= 0 else ''}{g_basic:.1f}%")
                gr3.metric("Allowance Growth", f"{'+' if g_allow >= 0 else ''}{g_allow:.1f}%")
                gr4.metric("Net Salary Growth", f"{'+' if g_net >= 0 else ''}{g_net:.1f}%")
                gr5.metric("Gross Salary CAGR", f"{'+' if cagr >= 0 else ''}{cagr:.1f}%", help=f"Lifetime Compound Annual Growth Rate ({total_years:.1f} years)")
                
            else:
                st.info(f"Not enough data in {selected_fy} to calculate growth metrics. Need at least 2 months of history.")
            
            st.divider()
            
            st.divider()
            
            # Keep original charts below the waterfall
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
            st.subheader("📝 Complete Expense Log")
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
        with tab8:
            st.subheader("🔮 Salary & Promotion Simulator")
            st.markdown("Play with the numbers below to see how a promotion, increment, or tax change affects your take-home pay.")
            
            sim_col1, sim_col2 = st.columns([1, 1])
            
            with sim_col1:
                st.markdown("#### 📈 Income Adjustments")
                sim_basic = st.number_input("Basic Salary", value=float(month_data['Basic Pay']), step=1000.0)
                sim_hard_area = st.number_input("Hard Area Allowance", value=float(month_data['Hard Area']), step=500.0)
                sim_hra = st.number_input("House Rent Allowance", value=float(month_data['House Rent Allowance']), step=500.0)
                sim_other_earn = st.number_input("Other Earnings / Allowances", value=float(month_data['Other Earnings'] + month_data['Other Allowances']), step=500.0)
                
                st.markdown("#### 📉 Deduction Adjustments")
                sim_tax = st.number_input("Estimated Income Tax", value=float(month_data['Income Tax']), step=500.0)
                sim_pf = st.number_input("PF Deduction", value=float(month_data['PF Deduction']), step=100.0)
                sim_mess_club = st.number_input("Estimated Mess & Club", value=float(month_data['Mess Bill'] + month_data['Club Bill']), step=500.0)
                sim_rent_ded = st.number_input("House Rent Deduction", value=float(month_data['House Rent Deduction']), step=100.0)
                sim_eobi = st.number_input("EOBI", value=float(month_data['EOBI']), step=10.0)

            with sim_col2:
                # Calculate Simulated Totals
                sim_gross = sim_basic + sim_hard_area + sim_hra + sim_other_earn
                sim_total_deductions = sim_tax + sim_pf + sim_mess_club + sim_rent_ded + sim_eobi
                sim_net = sim_gross - sim_total_deductions
                
                # Calculate Deltas (Differences from Current Month)
                diff_gross = sim_gross - month_data['Gross Pay']
                diff_net = sim_net - month_data['Net Pay']
                
                st.markdown("#### 📊 Projected Outcome")
                st.metric("Projected Gross Pay", f"Rs. {sim_gross:,.0f}", f"{'+' if diff_gross >=0 else ''}{diff_gross:,.0f} from current")
                st.metric("Projected Net Take-Home", f"Rs. {sim_net:,.0f}", f"{'+' if diff_net >=0 else ''}{diff_net:,.0f} from current")
                st.metric("Projected Total Deductions", f"Rs. {sim_total_deductions:,.0f}", delta_color="inverse")
                
                st.divider()
                
                # Mini Simulator Waterfall Chart
                fig_sim = go.Figure(go.Waterfall(
                    name="Simulation", orientation="v",
                    measure=["relative", "relative", "total"],
                    x=["Simulated Gross", "Total Deductions", "Simulated Net"],
                    textposition="outside",
                    text=[f"{sim_gross:,.0f}", f"-{sim_total_deductions:,.0f}", f"{sim_net:,.0f}"],
                    y=[sim_gross, -sim_total_deductions, sim_net],
                    connector={"line": {"color": "gray", "width": 1.5}},
                    decreasing={"marker": {"color": "#ff4b4b"}},
                    increasing={"marker": {"color": "#2ca02c"}},
                    totals={"marker": {"color": "#1f77b4"}}
                ))
                fig_sim.update_layout(template="plotly_white", margin=dict(t=20, b=20, l=0, r=0), height=350, showlegend=False)
                st.plotly_chart(fig_sim, use_container_width=True)

        with tab9:
            # --- CUSTOM CSS FOR GEMINI-LIKE UI ---
            st.markdown("""
            <style>
            .stChatMessage {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 14px;
                padding: 12px 16px;
                margin-bottom: 12px;
            }
            .gemini-badge {
                background: linear-gradient(135deg, #4285F4, #9B51E0, #D946EF);
                color: white;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 0.5px;
                display: inline-block;
            }
            </style>
            """, unsafe_allow_html=True)

            # --- HEADER BANNER ---
            head_col1, head_col2 = st.columns([4, 1])
            with head_col1:
                st.markdown("## ✨ Gemini Financial Assistant")
                st.markdown("<span class='gemini-badge'>⚡ Powered by Groq LPU • Live Payslip & Expense Intelligence</span>", unsafe_allow_html=True)
            with head_col2:
                if st.button("🗑️ Clear Chat", key="clear_chat_btn", use_container_width=True):
                    st.session_state["groq_chat_history"] = []
                    st.rerun()

            st.caption(f"Currently analyzing context for: **{month_data['Month']}** ({selected_fy})")
            st.divider()

            # Initialize chat history
            if "groq_chat_history" not in st.session_state:
                st.session_state["groq_chat_history"] = []

            # --- GEMINI-STYLE QUICK PROMPT CHIPS ---
            selected_chip = None
            if len(st.session_state["groq_chat_history"]) == 0:
                st.markdown("##### 💡 Suggested Prompts")
                chip_col1, chip_col2, chip_col3, chip_col4 = st.columns(4)
                
                if chip_col1.button("📉 Net Pay Analysis", use_container_width=True):
                    selected_chip = "Explain why my Net Pay is what it is this month and highlight the main deductions."
                if chip_col2.button("🏛️ Tax Breakdown", use_container_width=True):
                    selected_chip = "Give me a detailed breakdown of my income tax deduction and effective tax rate."
                if chip_col3.button("🏠 Site Living Audit", use_container_width=True):
                    selected_chip = "How much did I spend on site living (Mess + Club) and is it covered by my Hard Area allowance?"
                if chip_col4.button("🎓 Master's Fund Status", use_container_width=True):
                    selected_chip = "What is my current Provident Fund status and contribution progress toward my goal?"
                st.markdown("<br>", unsafe_allow_html=True)

            # --- 1. RENDER CHAT HISTORY (ALWAYS ABOVE THE INPUT BOX) ---
            for message in st.session_state["groq_chat_history"]:
                avatar = "👤" if message["role"] == "user" else "✨"
                with st.chat_message(message["role"], avatar=avatar):
                    st.markdown(message["content"])

            # --- 2. CHAT INPUT BOX ---
            user_input = st.chat_input("Ask Gemini anything about your salary, tax, or expenses...")
            prompt = selected_chip or user_input

            # --- 3. PROCESS NEW INPUT & REFRESH ---
            if prompt:
                # Add User Message to History
                st.session_state["groq_chat_history"].append({"role": "user", "content": prompt})

                # Build Context
                expense_context = f"Total out-of-pocket expenses logged: Rs. {total_spent:,.0f}" if 'total_spent' in locals() else "No manual expenses logged this month."
                
                system_context = f"""
                You are Gemini, an elite, highly intelligent Executive AI Financial Advisor for Waqar Ahmed Tunio, Shift Chemical Engineer at AgriTech Ltd.
                Your communication style is concise, highly articulate, polite, and executive-ready. 
                Use clean Markdown formatting, bold key numbers, bullet points, and brief tables where applicable.

                Current Active Financial Context for {month_data['Month']} ({selected_fy}):
                
                [PAYSLIP DATA]
                - Focus Month: {month_data['Month']}
                - Gross Pay: Rs. {month_data['Gross Pay']:,.0f}
                - Basic Salary: Rs. {month_data['Basic Pay']:,.0f}
                - Hard Area Allowance: Rs. {month_data['Hard Area']:,.0f}
                - House Rent Allowance: Rs. {month_data['House Rent Allowance']:,.0f}
                - Other Earnings / Arrears: Rs. {month_data['Other Earnings'] + month_data['Salary Arrears']:,.0f}
                - Income Tax Deducted: Rs. {month_data['Income Tax']:,.0f}
                - Provident Fund (PF Cont.): Rs. {month_data['PF Deduction']:,.0f}
                - Mess Bill: Rs. {month_data['Mess Bill']:,.0f}
                - Club Bill: Rs. {month_data['Club Bill']:,.0f}
                - House Rent Deduction: Rs. {month_data['House Rent Deduction']:,.0f}
                - EOBI: Rs. {month_data['EOBI']:,.0f}
                - Total Deductions: Rs. {month_data['Total Deductions']:,.0f}
                - Net Take-Home Pay: Rs. {month_data['Net Pay']:,.0f}
                - Leave Balance: {month_data['Leave Balance']} Days
                - {expense_context}

                Answer the user's inquiry strictly using these exact figures. Be accurate, clear, helpful, and insightful.
                """

                messages_for_api = [{"role": "system", "content": system_context}]
                messages_for_api.extend(st.session_state["groq_chat_history"])

                # Call Groq Engine
                try:
                    client = Groq(api_key=st.secrets["GROQ_API_KEY"]) 
                    
                    active_models = [m.id for m in client.models.list().data]
                    preferred_models = ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "llama-3.1-8b-instant"]
                    chosen_model = next((model for model in preferred_models if model in active_models), None)
                    if not chosen_model:
                        valid_fallbacks = [m for m in active_models if "guard" not in m.lower() and "vision" not in m.lower()]
                        chosen_model = valid_fallbacks[0] if valid_fallbacks else active_models[0]
                    
                    completion = client.chat.completions.create(
                        model=chosen_model, 
                        messages=messages_for_api,
                        temperature=0.4,
                        max_tokens=600
                    )
                    
                    response = completion.choices[0].message.content
                    
                    # Append Response to History
                    st.session_state["groq_chat_history"].append({"role": "assistant", "content": response})
                    
                    # FORCE INSTANT REFRESH TO MOVE MESSAGES ABOVE THE INPUT BOX
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Groq API Connection Error: {str(e)}")
if __name__ == '__main__':
    main()
