import streamlit as st
import pandas as pd
import pdfplumber
import re
import json
import io
from datetime import datetime
import gspread

try:
    import easyocr
    import numpy as np
    HAS_EASYOCR = True
except ImportError:
    HAS_EASYOCR = False

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

@st.cache_resource
def get_ocr_reader():
    if HAS_EASYOCR:
        return easyocr.Reader(['en'], gpu=False)
    return None

# --- GOOGLE SHEETS LOGIN LOGGING SETUP ---
@st.cache_resource
def init_log_connection():
    import os
    try:
        # Check for Streamlit Secrets first (for Streamlit Cloud)
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            # st.secrets["connections"]["gsheets"] used by st-gsheets-connection
            credentials_dict = dict(st.secrets["connections"]["gsheets"])
            credentials_dict.pop("spreadsheet", None) # remove non-gcp keys
            gc = gspread.service_account_from_dict(credentials_dict)
        elif "gcp_service_account" in st.secrets:
            credentials_dict = dict(st.secrets["gcp_service_account"])
            gc = gspread.service_account_from_dict(credentials_dict)
        else:
            # Fallback to local files, resolving path relative to this script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            filename = os.path.join(script_dir, 'credentials.json')
            if not os.path.exists(filename) and os.path.exists(os.path.join(script_dir, 'credentials.json.json')):
                filename = os.path.join(script_dir, 'credentials.json.json')
                
            gc = gspread.service_account(filename=filename)
            
        sh = gc.open_by_url("https://docs.google.com/spreadsheets/d/1j7U1Kw0NG2I77V19S0vIRqDqIFYCFdXIPE7wSDSfulQ/edit")
        try:
            log_ws = sh.worksheet("Login_Logs")
        except Exception:
            log_ws = sh.add_worksheet(title="Login_Logs", rows=1000, cols=2)
            log_ws.append_row(["User", "Timestamp"])
        return log_ws
    except Exception as e:
        return str(e)

log_worksheet = init_log_connection()

# --- 1. LIBRARY SAFETY SWITCH ---
try:
    from st_gsheets_connection import GSheetsConnection
    HAS_GSHEETS = True
except ImportError:
    HAS_GSHEETS = False

# --- 2. THEME & UI ---
st.set_page_config(page_title="Compliance Intelligence Hub", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #fafafa; }
    [data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    .stButton>button { 
        background: linear-gradient(135deg, #1ed760 0%, #0d8a39 100%) !important; 
        color: white !important; 
        font-weight: 600 !important; 
        border-radius: 8px !important; 
        border: none !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease !important;
    }
    .stButton>button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(30, 215, 96, 0.4) !important;
    }
    h1 { 
        background: -webkit-linear-gradient(45deg, #1ed760, #ffffff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }
    h2, h3 { color: #1ed760; }
    .stDataFrame { border: 1px solid #30363d; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    [data-testid="stFileUploadDropzone"] { border: 2px dashed #1ed760 !important; border-radius: 12px !important; background-color: #1c2128 !important; }
    </style>
    """, unsafe_allow_html=True)

TDS_RULES = {"194J": {"rate": 0.10, "limit": 30000}, "194C": {"rate": 0.02, "limit": 30000}, "194I": {"rate": 0.10, "limit": 240000}}

# --- 3. EXTRACTION ENGINE ---
def extract_raw_data(file):
    with pdfplumber.open(file) as pdf:
        text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        
        if len(text.strip()) < 50:
            reader = get_ocr_reader()
            if reader:
                st.info(f"Scanning image for {file.name} using EasyOCR...")
                ocr_text = ""
                for page in pdf.pages:
                    pil_image = page.to_image(resolution=150).original
                    img_array = np.array(pil_image)
                    result = reader.readtext(img_array, detail=0, paragraph=True)
                    ocr_text += "\n".join(result) + "\n"
                return ocr_text
            else:
                st.warning("⚠️ Scanned document detected, but 'easyocr' is not installed! Please run `pip install easyocr numpy` in your terminal to enable OCR.")
        return text

def parse_financials_ai(text, vendor):
    api_key = st.session_state.get('ai_key', st.secrets.get("AI_API_KEY", ""))
    
    if not api_key:
        return None
    
    try:
        prompt = f"""
        Extract financial details from this invoice text for vendor '{vendor}'.
        Return ONLY a raw JSON object (no markdown, no backticks).
        Schema: {{"base": float, "cgst": float, "sgst": float, "igst": float, "date": "string", "invoice_no": "string", "sec": "string"}}
        Rules:
        - 'base' is the taxable amount BEFORE taxes. If missing, calculate Total minus taxes.
        - 'sec' is TDS Section (194J for tech/professional, 194I for rent, 194C for contract/services/housekeeping).
        Text:
        {text}
        """
        
        res_text = ""
        # Determine which API to use based on key format
        if api_key.startswith("gsk_") and HAS_GROQ:
            client = Groq(api_key=api_key)
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            res_text = completion.choices[0].message.content
        elif HAS_GEMINI:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            res_text = response.text
        else:
            return parse_financials(text, vendor)
            
        res_text = res_text.replace('```json', '').replace('```', '').strip()
        # Find the first { and last } to avoid extra text
        start_idx = res_text.find('{')
        end_idx = res_text.rfind('}') + 1
        if start_idx != -1 and end_idx != 0:
            res_text = res_text[start_idx:end_idx]
            
        data = json.loads(res_text)
        
        # Ensure floats
        for k in ["base", "cgst", "sgst", "igst"]:
            data[k] = float(data.get(k, 0.0))
        if not data.get("date"): data["date"] = "Not Detected"
        if not data.get("invoice_no"): data["invoice_no"] = "Not Detected"
        if not data.get("sec"): data["sec"] = "194C"
        return data
    except Exception as e:
        st.toast(f"AI Fallback Failed: {e}")
        return None

def parse_financials(text, vendor):
    data = {"base": 0.0, "cgst": 0.0, "sgst": 0.0, "igst": 0.0, "date": "Not Detected", "invoice_no": "Not Detected", "sec": "194C"}
    clean_text = text.replace(',', '')
    
    # Pre-processing: remove spaces inside numbers like '4 38 900.00' to '438900.00'
    clean_text = re.sub(r'(?<=\d)\s+(?=\d{2,3}(?:\.\d{1,2})?\b)', '', clean_text)
    clean_text = re.sub(r'(?<=\d)\s+(?=\d{2,3}(?:\.\d{1,2})?\b)', '', clean_text)
    
    # 🎯 Invoice Number Extraction
    # Enforce that the invoice number MUST contain at least one digit. 
    # [\.\s\:\#\-]* eats up separators. ([A-Za-z0-9\-\/\\]*\d[A-Za-z0-9\-\/\\]*) matches the actual ID.
    strict_pattern = r"(?:Invoice No|Bill No|Invoice Number|Reference No|Receipt No|Invoice)[\.\s\:\#\-]*([A-Za-z0-9\-\/\\]*\d[A-Za-z0-9\-\/\\]*)"
    inv_matches = re.findall(strict_pattern, clean_text, re.IGNORECASE)
    for m in inv_matches:
        # Extra safety check to avoid just matching the year
        if len(m) >= 2 and m not in ["2024", "2025", "2026", "2027", "2028"]:
            data["invoice_no"] = m.strip()
            break
            
    if data["invoice_no"] == "Not Detected":
        # Table fallback for Rakesh Roshan style '71/2025-26'
        fallback = re.search(r"\b(\d{2,5}\/20\d{2}\-\d{2}|\d{2,5}\/\d{2,4})\b", clean_text)
        if fallback:
            data["invoice_no"] = fallback.group(1).strip()
        # Fallback for Reliance Jio long numeric IDs separated by table rows
        elif "jio" in vendor.lower():
            fallback_jio = re.search(r"(?:Bill No|Invoice No)[\s\S]{1,100}?\b(\d{9,15})\b", clean_text, re.IGNORECASE)
            if fallback_jio:
                data["invoice_no"] = fallback_jio.group(1).strip()
    
    # 🎯 Enhanced Date Detection
    date_match = re.search(r"(?:Invoice Date|Bill Date|Date|Dated|Period|Statement as on)[\s\:\|-]*(\d{1,2}[-\/\s][a-zA-Z]{3,9}[-\/\s]\d{2,4}|\d{1,2}[-\/\s]\d{1,2}[-\/\s]\d{2,4})", clean_text, re.IGNORECASE)
    if not date_match: 
        # Fallback
        date_match = re.search(r"\b(\d{1,2}[-\/\s](?:0?[1-9]|1[0-2]|[a-zA-Z]{3,9})[-\/\s](?:20\d{2}))\b", clean_text)
    if date_match: data["date"] = date_match.group(1)

    # 🎯 Intelligent Line-Based Value Hunting
    def get_largest_amount(keywords, check_next_line=True, break_early=True):
        amounts = []
        lines = clean_text.split('\n')
        for i, line in enumerate(lines):
            if any(k.lower() in line.lower() for k in keywords):
                nums = re.findall(r"(\d+(?:\.\d{1,2})?)", line)
                
                def is_valid(n):
                    f = float(n)
                    if f < 3.0: return False
                    if n in ['9', '18', '5', '12', '28']: return False
                    if '.' not in n:
                        if len(n) == 4 and n.startswith(('202', '203')): return False # year
                        if len(n) in [6, 8]: return False # HSN code
                        if len(n) >= 9: return False # Account/Phone/IRN
                    else:
                        if f > 100000000: return False # Ridiculously huge float
                    return True

                valid_nums = [float(n) for n in nums if is_valid(n)]
                
                # Table Header Fallback: Check up to 5 rows below
                if (not valid_nums or not break_early) and check_next_line:
                    for j in range(1, 6):
                        if i + j < len(lines):
                            nums_next = re.findall(r"(\d+(?:\.\d{1,2})?)", lines[i+j])
                            valid_nums_next = [float(n) for n in nums_next if is_valid(n)]
                            if valid_nums_next:
                                valid_nums.extend(valid_nums_next)
                                if break_early:
                                    break

                if valid_nums:
                    amounts.append(max(valid_nums))
        return max(amounts) if amounts else 0.0

    # Vendor specific overrides
    if "tata" in vendor.lower():
        data["base"] = get_largest_amount(["Total Amount Before Tax", "Sub Total (INR)", "Taxable Value"])
        data["sec"] = "194J"
    elif "jio" in vendor.lower():
        data["base"] = get_largest_amount(["Current Taxable Charges"])
        data["sec"] = "194J"
    elif "decfin" in vendor.lower() or "fonada" in vendor.lower() or "shivtel" in vendor.lower():
        data["base"] = get_largest_amount(["Sub Total"])
        data["sec"] = "194C"
    elif "karix" in vendor.lower():
        data["base"] = get_largest_amount(["Total Taxable Amount"])
        data["sec"] = "194J"
    elif "rakesh roshan" in vendor.lower():
        data["base"] = get_largest_amount(["Taxable Value", "Leave & License"], break_early=False)
        data["sec"] = "194I"
    elif "rudra" in vendor.lower() or "rlfs" in vendor.lower():
        data["base"] = get_largest_amount(["Housekeeping boy", "Housekeeping", "Rate Per Head"])
        if data["base"] == 0.0:
            total = get_largest_amount(["Total Rs", "Rs.", "Total"])
            if total > 0:
                cgst = get_largest_amount(["CGST"])
                sgst = get_largest_amount(["SGST"])
                data["base"] = total - cgst - sgst
        data["sec"] = "194C"
    elif "bse" in vendor.lower():
        data["base"] = get_largest_amount(["EQUITY SHARE", "ALF payable", "Listing Fees", "CAPITAL"])
        data["sec"] = "194J"
    elif "convin" in vendor.lower() or "feed forward" in vendor.lower():
        data["base"] = get_largest_amount(["Sub Total", "Taxable Amount", "Base Value"])
        data["sec"] = "194J"
    
    # Broad extraction for standard invoices
    if data["base"] == 0.0:
        data["base"] = get_largest_amount(["Taxable Amount", "Taxable Value", "Sub Total", "Basic Value", "Current Taxable Charges"])
        if data["base"] == 0.0:
            data["base"] = get_largest_amount(["Total Amount", "Gross Amount", "Net Amount", "Grand Total", "Total"])
    
    # 🎯 Mathematical GST Extraction
    def extract_taxes(base_val):
        if base_val <= 0: return 0.0, 0.0, 0.0
        all_nums = [float(n) for n in re.findall(r"(\d+(?:\.\d{1,2})?)", clean_text) if float(n) > 0]
        
        # Check IGST (18%, 12%, 5%, 28%)
        for rate in [0.18, 0.12, 0.05, 0.28]:
            expected = base_val * rate
            matched = [n for n in all_nums if abs(n - expected) <= 2.0]
            if matched and "IGST" in clean_text.upper():
                return 0.0, 0.0, max(matched)
                
        # Check CGST/SGST (9%, 6%, 2.5%, 14%)
        for rate in [0.09, 0.06, 0.025, 0.14]:
            expected = base_val * rate
            matched = [n for n in all_nums if abs(n - expected) <= 2.0]
            if matched:
                return max(matched), max(matched), 0.0
                
        # Fallback if mathematical doesn't match perfectly
        cgst = get_largest_amount(["CGST"])
        if cgst >= base_val: cgst = 0.0
        sgst = get_largest_amount(["SGST"])
        if sgst >= base_val: sgst = 0.0
        igst = get_largest_amount(["IGST"])
        if igst >= base_val: igst = 0.0
        
        return cgst, sgst, igst

    data["cgst"], data["sgst"], data["igst"] = extract_taxes(data["base"])
    
    return data

# --- 4. ACCESS CONTROL ---
if 'auth' not in st.session_state: st.session_state['auth'] = None

with st.sidebar:
    st.title("Access Control")
    if st.session_state['auth'] is None:
        with st.expander("Normal User"):
            name = st.text_input("Name")
            if st.button("Login"):
                if isinstance(log_worksheet, str):
                    st.error(f"Cannot log in: Google Sheets connection failed. Details: {log_worksheet}")
                else:
                    try:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        log_worksheet.append_row([name, timestamp])
                        st.session_state.update({"auth": "User", "user": name})
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to log into Google Sheet: {e}")
        with st.expander("Developer"):
            dev_id = st.text_input("Dev ID")
            dev_pass = st.text_input("Password", type="password")
            
            # Securely fetch developer password from Streamlit secrets (fallback to '1234' locally)
            expected_pass = st.secrets.get("dev_password", "1234")
            
            if st.button("Unlock Dev") and dev_id == "Chirag" and dev_pass == expected_pass:
                if isinstance(log_worksheet, str):
                    st.error(f"Cannot log in: Google Sheets connection failed. Details: {log_worksheet}")
                else:
                    try:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        log_worksheet.append_row([dev_id, timestamp])
                        st.session_state.update({"auth": "Developer", "user": "Chirag"})
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to log into Google Sheet: {e}")
    else:
        st.markdown(f"## Welcome, {st.session_state['user']}! 👋")
        st.write("You are securely logged in.")
        
        st.markdown("---")
        st.markdown("#### 🤖 AI Engine Settings")
        
        # Check if key is securely configured in secrets
        if "AI_API_KEY" in st.secrets and st.secrets["AI_API_KEY"].strip() != "":
            st.success("✅ AI Engine Active (Configured securely in backend!)")
        else:
            st.caption("Enter a **Groq API Key** (Llama 3) OR **Gemini API Key** for AI extraction.")
            st.caption("💡 *If left blank, it automatically uses the upgraded Python script (Free & Offline)!*")
            api_key_input = st.text_input("AI API Key (Groq/Gemini)", type="password")
            if api_key_input:
                st.session_state['ai_key'] = api_key_input
            elif 'ai_key' in st.session_state:
                st.success("✅ AI Engine Active!")
            
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Logout"):
            st.session_state['auth'] = None
            st.rerun()

if not st.session_state['auth']: st.stop()

# --- 5. DATA HUB ---
st.title("Compliance Intelligence Hub")
files = st.file_uploader("Upload Invoices", accept_multiple_files=True)

if st.button("Proceed") and files:
    # Beautiful progress UI
    progress_text = "Operation in progress. Please wait."
    my_bar = st.progress(0, text=progress_text)
    
    all_rows = []
    failed_invoices = []
    journal_rows = []
    for idx, f in enumerate(files):
        # Update progress bar
        my_bar.progress((idx) / len(files), text=f"⏳ Extracting data from: {f.name}")
        txt = extract_raw_data(f)
        
        # 1. Vendor Guessing from File Name
        v_guess = re.sub(r'(?i)(tax\s*invoice|invoice|bill|\.pdf).*', '', f.name).strip()
        v = "Tata Tele" if "tata" in txt.lower() else "Reliance Jio" if "jio" in txt.lower() else "Fonada" if "fonada" in txt.lower() or "shivtel" in txt.lower() else "Decfin" if "decfin" in txt.lower() else "Karix" if "karix" in txt.lower() else "Rakesh Roshan" if "rakesh roshan" in txt.lower() else "Rudra Lines" if "rudra" in txt.lower() or "rlfs" in txt.lower() else "BSE Limited" if "bse " in txt.lower() or "bse limited" in txt.lower() else "Convin" if "feed forward" in txt.lower() or "convin" in txt.lower() else v_guess.title() if v_guess else "Vendor"
        
        # 2. Try Pure Python Script Extraction First (Super Fast, Free)
        vals = parse_financials(txt, v)
        
        # 3. Smart AI Fallback logic
        failed_heuristics = (
            vals["base"] == 0.0 or 
            vals["invoice_no"] == "Not Detected" or 
            vals["date"] == "Not Detected" or
            (vals["cgst"] + vals["sgst"] + vals["igst"]) > vals["base"] or
            vals["base"] > 5000000 
        )
        
        if failed_heuristics:
            ai_vals = parse_financials_ai(txt, v)
            if ai_vals is not None:
                st.toast(f"Used AI Fallback for {f.name}")
                if ai_vals["base"] > 0.0: vals["base"] = ai_vals["base"]
                if ai_vals["cgst"] > 0.0: vals["cgst"] = ai_vals["cgst"]
                if ai_vals["sgst"] > 0.0: vals["sgst"] = ai_vals["sgst"]
                if ai_vals["igst"] > 0.0: vals["igst"] = ai_vals["igst"]
                if ai_vals["invoice_no"] != "Not Detected": vals["invoice_no"] = ai_vals["invoice_no"]
                if ai_vals["date"] != "Not Detected": vals["date"] = ai_vals["date"]
                vals["sec"] = ai_vals["sec"]
        
        if vals["base"] == 0.0:
            st.warning(f"Could not automatically detect Base Value for {f.name}. Saving to 'Failed_Invoices' for developer review.")
            failed_invoices.append([f.name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), txt])
            with st.expander(f"View Raw Extracted Text from {f.name}"):
                st.text(txt if txt.strip() else "NO TEXT DETECTED (This appears to be a scanned image, not a digital PDF)")
        
        is_app = vals["base"] >= TDS_RULES[vals["sec"]]["limit"]
        tds_amt = vals["base"] * TDS_RULES[vals["sec"]]["rate"] if is_app else 0.0
        
        gst_applicable = (vals["cgst"] > 0 or vals["sgst"] > 0 or vals["igst"] > 0)
        
        # As per user's accounting rules: Invoice value stays gross, TDS tracked separately
        net_payable = vals["base"] + vals["cgst"] + vals["sgst"] + vals["igst"]

        row = {
            "Sr. No.": idx + 1, 
            "Vendor": v, 
            "Invoice Number": vals["invoice_no"],
            "Invoice Date": vals["date"], 
            "Base Value": vals["base"],
            "CGST": vals["cgst"],
            "SGST": vals["sgst"],
            "IGST": vals["igst"],
            "TDS Section": vals["sec"],
            "TDS Deducted": "Yes" if is_app else "No",
            "TDS Rate": f"{int(TDS_RULES[vals['sec']]['rate'] * 100)}%" if is_app else "NA",
            "TDS Amount": tds_amt if is_app else 0.0,
            "TDS Reason": "Applicable" if is_app else "Below Limit",
            "GST Reason": "Applicable" if gst_applicable else "Not Applicable",
            "Net Payable": net_payable,
            "Processed By": st.session_state['user'],
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        all_rows.append(row)

        # Build Journal Entry Rows for DataFrame
        je_ref = f"JE-{idx+1}-{vals['invoice_no'] if vals['invoice_no'] != 'Not Detected' else v}"
        
        debit_total = round(vals["base"] + vals["cgst"] + vals["sgst"] + vals["igst"], 2)
        credit_total = round(net_payable, 2)
        
        journal_rows.append({"Reference": je_ref, "Date": vals["date"], "Account": "Expense A/c", "Debit": round(vals["base"], 2), "Credit": 0.0})
        if vals['cgst'] > 0: journal_rows.append({"Reference": je_ref, "Date": vals["date"], "Account": "CGST Input A/c", "Debit": round(vals['cgst'], 2), "Credit": 0.0})
        if vals['sgst'] > 0: journal_rows.append({"Reference": je_ref, "Date": vals["date"], "Account": "SGST Input A/c", "Debit": round(vals['sgst'], 2), "Credit": 0.0})
        if vals['igst'] > 0: journal_rows.append({"Reference": je_ref, "Date": vals["date"], "Account": "IGST Input A/c", "Debit": round(vals['igst'], 2), "Credit": 0.0})
        
        # Vendor is credited the GROSS amount
        journal_rows.append({"Reference": je_ref, "Date": vals["date"], "Account": f"{v} A/c", "Debit": 0.0, "Credit": round(net_payable, 2)})
        
        # TDS is now handled in a separate voucher entirely, so we remove it from this specific Journal Entry to keep Debit = Credit.
        # if is_app: journal_rows.append({"Reference": je_ref, "Date": vals["date"], "Account": f"TDS Payable A/c ({vals['sec']})", "Debit": 0.0, "Credit": round(tds_amt, 2)})
        
        # Add Totals row and an empty gap row
        journal_rows.append({"Reference": je_ref, "Date": "", "Account": "TOTAL", "Debit": debit_total, "Credit": credit_total})
        journal_rows.append({"Reference": None, "Date": None, "Account": None, "Debit": None, "Credit": None})

    # Finish progress bar
    my_bar.progress(1.0, text="✅ Processing Complete!")
    st.balloons()

    df = pd.DataFrame(all_rows)
    st.subheader("Extracted Invoices Data")
    st.dataframe(df, use_container_width=True)
    
    je_df = pd.DataFrame(journal_rows)
    
    col1, col2 = st.columns(2)
    with col1:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Download Data (CSV)", data=csv, file_name='invoices_data.csv', mime='text/csv')
    
    with st.expander("Show Journal Entries (Sheet View)"):
        st.dataframe(je_df, use_container_width=True)
        je_csv = je_df.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Download Journal Entries (CSV)", data=je_csv, file_name='journal_entries.csv', mime='text/csv')

    # Auto Cloud Sync using working gspread connection
    if not isinstance(log_worksheet, str): # ensure we have a valid connection
        try:
            st.info("Syncing data to Google Sheets...")
            sh = log_worksheet.spreadsheet
            try:
                invoice_ws = sh.worksheet("Invoices")
            except Exception:
                # If "Invoices" worksheet doesn't exist, create it and add headers
                invoice_ws = sh.add_worksheet(title="Invoices", rows=1000, cols=20)
                invoice_ws.append_row(df.columns.tolist())
            
            # Append the newly extracted rows to the "Invoices" sheet
            if len(df) > 0:
                df_to_upload = df.fillna("").astype(str)
                invoice_ws.append_rows(df_to_upload.values.tolist())
                st.success("✅ Processed invoices synced to Google Sheets!")
            
            # Save failed invoices for developer review
            if failed_invoices:
                try:
                    failed_ws = sh.worksheet("Failed_Invoices")
                except Exception:
                    failed_ws = sh.add_worksheet(title="Failed_Invoices", rows=1000, cols=3)
                    failed_ws.append_row(["Filename", "Timestamp", "Extracted Raw Text"])
                failed_ws.append_rows(failed_invoices)
                st.warning(f"⚠️ {len(failed_invoices)} complex invoice(s) were saved to the 'Failed_Invoices' sheet so the developer can create a script for them!")
                
        except Exception as e:
            st.error(f"Google Sheets Sync Failure: {e}")
