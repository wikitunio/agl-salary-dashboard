@st.cache_data(ttl=60) # Changed to 60 seconds so it updates faster for you!
def fetch_expense_data():
    sharepoint_url = "https://muet14-my.sharepoint.com/:x:/g/personal/18ch37_students_muet_edu_pk/IQBicSNMjahzTYvn03-bpK36AVWD3NXpwKCBih5ZlUJxSiE?download=1"
    df_exp = pd.DataFrame()
    error_msg = ""
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x86) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(sharepoint_url, headers=headers)
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
            error_msg = f"SharePoint fetch failed, and local file missing. Error: {str(e)}"

    if not df_exp.empty:
        expected_columns = ['Date', 'Salary Month', 'Category', 'Sub-Category / Person', 'Amount (PKR)', 'Notes']
        available_columns = [col for col in expected_columns if col in df_exp.columns]
        df_exp = df_exp[available_columns]
        
        if 'Amount (PKR)' in df_exp.columns:
            df_exp = df_exp.dropna(subset=['Amount (PKR)'])

        # --- THE FIX: SMART TEXT CLEANING ---
        if 'Salary Month' in df_exp.columns:
            # 1. Convert to string and force UPPERCASE (fixes Jun vs JUN)
            df_exp['Salary Month'] = df_exp['Salary Month'].astype(str).str.upper().str.strip()
            
            # 2. Replace '-25' with '-2025' and '-26' with '-2026'
            df_exp['Salary Month'] = df_exp['Salary Month'].str.replace(r'-25$', '-2025', regex=True)
            df_exp['Salary Month'] = df_exp['Salary Month'].str.replace(r'-26$', '-2026', regex=True)
        # ------------------------------------
            
    return df_exp, error_msg
