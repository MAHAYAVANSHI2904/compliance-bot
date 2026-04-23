import streamlit as st
import pandas as pd
import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes
import re
import os
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- 1. SYSTEM CONFIGURATION & UI ---
st.set_page_config(page_title="Compliance Intelligence Hub", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #000000; color: #ffffff; }
    [data-testid="stSidebar"] { background-color: #0a0a0a; border-right: 1px solid #1ed760; }
    .stButton>button { 
        background-color: #1ed760 !important; 
        color: black !important; 
        font-weight: bold !important; 
        border-radius: 5px !important;
        width: 100%;
    }
    .stTextInput>div>div>input { background-color: #121212; color: #ffffff; border: 1px solid #333; }
    .stDataFrame { border: 1px solid #1ed760; border-radius: 10px; }
    div[data-testid="stExpander"] { background-color: #0a0a0a; border: 1px solid #333; }
    h1 { color: #1ed760; }
    </style>
    """, unsafe_allow_html=True)

# Path Setup
POPPLER_PATH = None 

TDS_RULES = {
    "194J": {"rate": 0.10, "limit": 30000},
    "194C": {"rate": 0.02, "limit": 30000},
    "194I": {"rate": 0.10, "limit": 240000}
}

# --- 2. PRECISION EXTRACTION ENGINE ---
def extract_raw_data(file):
    f_bytes = file.read()
    all_text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            page_text = page.extract_text() or ""
            all_text += page_text + "\n"
            for table in tables:
                for row in table:
                    all_text += " | ".join([str(cell) for cell in row if cell]) + "\n"
    
    if len(all_text.strip()) < 100:
        images = convert_from_bytes(f_bytes, poppler_path=POPPLER_PATH)
        all_text = " ".join([pytesseract.image_to_string(img) for img in images])
    return all_text

def get_vendor_assured(text):
    t = text.lower()
    if "reliance jio" in t or "jio platforms" in t: return "Reliance Jio Infocomm Ltd"
    if "karix" in t: return "Karix Mobile Pvt Ltd"
    if "decfin" in t: return "Decfin Tech Pvt Ltd"
    if "shivtel" in t or "fonada" in t: return "Shivtel Communications"
    if "tata tele" in t or "ttns" in t: return "Tata Tele Business Services"
    return "Unknown Vendor"

def parse_financials(text, vendor):
    data = {"base": 0.0, "cgst": 0.0, "sgst": 0.0, "igst": 0.0, "sec": "194C", "date": "Not Detected"}
    
    # IMPROVED DATE EXTRACTION
    date_patterns = [
        r"(?:Invoice|Bill|Statement|Date)\s*(?:Date)?\s*[:\|-]?\s*(\d{1,2}[-\/\s]\w{3,9}[-\/\s]\d{2,4})",
        r"(?:Invoice|Bill|Statement|Date)\s*(?:Date)?\s*[:\|-]?\s*(\d{1,2}/\d{1,2}/\d{2,4})"
    ]
    for p in date_patterns:
        match = re.search(p, text, re.IGNORECASE)
        if match:
            data["date"] = match.group(1).strip()
            break

    # VENDOR SPECIFIC DATA CAPTURE
    if "shivtel" in vendor.lower() or "fonada" in text.lower():
        match = re.search(r"Sub Total\s*(?:\|)?\s*([\d,]+\.\d{2})", text)
        if match: data["base"] = float(match.group(1).replace(',', ''))
    elif "jio" in vendor.lower():
        match = re.search(r"Current Taxable Charges\s*(?:\|)?\s*([\d,]+\.\d{2})", text)
        if match: data["base"] = float(match.group(1).replace(',', ''))
    elif "karix" in vendor.lower():
        match = re.search(r"Total Taxable Amount\s*(?:\|)?\s*([\d,]+\.\d{2})", text)
        if match: data["base"] = float(match.group(1).replace(',', ''))
        data["sec"] = "194J"
    elif any(x in vendor.lower() for x in ["decfin", "tata"]):
        match = re.search(r"(?:Sub Total|Taxable Amount)\s*(?:\(INR\))?\s*(?:\|)?\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
        if match: data["base"] = float(match.group(1).replace(',', ''))

    data["cgst"] = sum([float(x.replace(',','')) for x in re.findall(r"CGST.*?([\d,]+\.\d{2})", text, re.IGNORECASE)])
    data["sgst"] = sum([float(x.replace(',','')) for x in re.findall(r"SGST.*?([\d,]+\.\d{2})", text, re.IGNORECASE)])
    data["igst"] = sum([float(x.replace(',','')) for x in re.findall(r"IGST.*?([\d,]+\.\d{2})", text, re.IGNORECASE)])

    return data

# --- 3. CLOUD LOGGING FUNCTION ---
def log_to_gsheet(user, action):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        try:
            df_existing = conn.read(ttl=0)
        except:
            df_existing = pd.DataFrame(columns=["Timestamp", "User", "Action"])
        
        new_log = pd.DataFrame([{
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "User": user,
            "Action": action
        }])
        updated_df = pd.concat([df_existing, new_log], ignore_index=True)
        conn.update(data=updated_df)
    except Exception as e:
        st.sidebar.error(f"GSheet Log Error: {e}")

# --- 4. ACCESS CONTROL ---
if 'auth' not in st.session_state: st.session_state['auth'] = None

with st.sidebar:
    st.markdown("### Access Control")
    with st.expander("Normal Login", expanded=st.session_state['auth'] is None):
        u_name = st.text_input("Enter Name", key="u_name")
        if st.button("Proceed", key="u_btn"):
            if u_name:
                st.session_state.update({"auth": "User", "user": u_name})
                log_to_gsheet(u_name, "User Login")
                st.rerun()
    st.markdown("---")
    with st.expander("Developer Login", expanded=False):
        d_id = st.text_input("User ID", key="d_id")
        d_pw = st.text_input("Password", type="password", key="d_pw")
        if st.button("Proceed", key="d_btn"):
            if d_id == "Chirag" and d_pw == "Chirag":
                st.session_state.update({"auth": "Developer", "user": "Chirag"})
                log_to_gsheet("Chirag", "Developer Login")
                st.rerun()
            else: st.error("Invalid Credentials")

if not st.session_state['auth']:
    st.title("Compliance Intelligence Hub")
    st.info("Log in to proceed.")
    st.stop()

# --- 5. MAIN HUB ---
st.title("Compliance Intelligence Hub")
st.caption(f"Logged in: {st.session_state['user']} | GSheet Sync Active")

files = st.file_uploader("Upload Invoices", accept_multiple_files=True, type=['pdf'])

if st.button("Proceed") and files:
    results = []
    for idx, f in enumerate(files):
        raw_text = extract_raw_data(f)
        v = get_vendor_assured(raw_text)
        vals = parse_financials(raw_text, v)
        
        total_tax = vals["cgst"] + vals["sgst"] + vals["igst"]
        sec = vals["sec"]
        is_app = vals["base"] >= TDS_RULES[sec]["limit"]
        tds_amt = vals["base"] * TDS_RULES[sec]["rate"] if is_app else 0.0

        results.append({
            "Sr. No.": idx + 1,
            "Name of Vendor": v,
            "File Name": f.name,
            "Invoice Date": vals["date"],
            "Base Value": vals["base"],
            "CGST": vals["cgst"] if vals["cgst"] > 0 else "NA",
            "SGST": vals["sgst"] if vals["sgst"] > 0 else "NA",
            "IGST": vals["igst"] if vals["igst"] > 0 else "NA",
            "TDS Section": sec if is_app else "NA",
            "TDS Deducted": tds_amt if is_app else "NA",
            "TDS Reason": f"Applicable (> {TDS_RULES[sec]['limit']})" if is_app else f"Below Limit (< {TDS_RULES[sec]['limit']})",
            "GST Reason": "Forward Charge" if total_tax > 0 else "Exempt/RCM",
            "Journal": [
                {"Account": "Expense A/c", "Dr": vals["base"], "Cr": 0},
                {"Account": "GST Input A/c", "Dr": total_tax if total_tax > 0 else 0, "Cr": 0},
                {"Account": "TDS Payable A/c", "Dr": 0, "Cr": tds_amt if is_app else 0},
                {"Account": "Vendor Payable A/c", "Dr": 0, "Cr": (vals["base"]+total_tax)-tds_amt}
            ]
        })

    st.dataframe(pd.DataFrame(results).drop(columns=["Journal"]), use_container_width=True, hide_index=True)

    st.subheader("Journal Entries")
    cols = st.columns(2)
    for i, res in enumerate(results):
        with cols[i%2].expander(f"Entry: {res['Name of Vendor']} ({res['File Name']})"):
            st.table(pd.DataFrame(res["Journal"]))

    log_to_gsheet(st.session_state['user'], f"Audit Processed: {len(files)} files")

if st.session_state['auth'] == "Developer":
    st.sidebar.markdown("---")
    if st.sidebar.checkbox("View Real-time Cloud Logs"):
        conn = st.connection("gsheets", type=GSheetsConnection)
        st.sidebar.dataframe(conn.read(ttl=0).tail(15))
