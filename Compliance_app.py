import streamlit as st
import pandas as pd
import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes
import re
import os
import socket
from datetime import datetime

# --- 1. SYSTEM CONFIGURATION & CLOUD UI ---
st.set_page_config(page_title="Compliance Intelligence Hub", layout="wide")

# Modern Onyx & Emerald Theme
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
    .stTextInput>div>div>input { background-color: #121212; color: #ffffff; border: 1px solid #333333; }
    .stDataFrame { border: 1px solid #1ed760; }
    div[data-testid="stExpander"] { background-color: #0a0a0a; border: 1px solid #333333; }
    </style>
    """, unsafe_allow_html=True)

# CLOUD ENGINE CONFIGURATION
# Note: Windows paths are commented out for Streamlit Cloud deployment
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
POPPLER_PATH = None 
LOG_FILE = "usage_audit.csv"

TDS_RULES = {
    "194J": {"rate": 0.10, "limit": 30000},
    "194C": {"rate": 0.02, "limit": 30000},
    "194I": {"rate": 0.10, "limit": 240000},
    "194H": {"rate": 0.05, "limit": 15000}
}

# --- 2. ACCURACY & ASSURANCE SCRIPTS ---
def extract_content(file):
    """Hybrid extraction with accuracy assurance."""
    f_bytes = file.read()
    with pdfplumber.open(file) as pdf:
        text = " ".join([page.extract_text() or "" for page in pdf.pages])
    
    # Trigger OCR for scanned documents (e.g., Rakesh Roshan invoice)
    if len(text.strip()) < 50:
        images = convert_from_bytes(f_bytes, poppler_path=POPPLER_PATH)
        text = " ".join([pytesseract.image_to_string(img) for img in images])
    return text

def get_vendor_assured(text):
    """Verifies vendor name against known entity patterns for precision[cite: 83, 55, 5]."""
    known = {
        "rakesh roshan": "Rakesh Roshan", 
        "anthropic": "Anthropic, PBC", 
        "miracle technologies": "Miracle Technologies", 
        "apollo finvest": "Apollo Finvest Ltd"
    }
    for key, val in known.items():
        if key in text.lower(): return val
    
    lines = [line.strip() for line in text.split('\n') if len(line.strip()) > 5]
    ignore = ["TAX INVOICE", "INVOICE", "ZD", "PBC", "MUMBAI", "E-INVOICE"]
    for line in lines[:5]:
        if not any(word in line.upper() for word in ignore): return line
    return "Unknown Vendor"

def get_date_assured(text):
    """Regex-based script for high-accuracy date detection."""
    patterns = [r"\w+\s\d{1,2},\s\d{4}", r"\d{1,2}-\w{3,9}-\d{2,4}", r"\d{1,2}/\d{1,2}/\d{2,4}"]
    for p in patterns:
        match = re.search(p, text, re.IGNORECASE)
        if match: return match.group(0)
    return "Not Found"

def analyze_logic(text):
    """Accounting logic and GST/TDS segregation."""
    res = {"base": 0.0, "cgst": 0.0, "sgst": 0.0, "igst": 0.0, "rcm": "No", "sec": "194C"}
    
    # Financial Value Extraction
    val_m = re.search(r"(?:Value|Subtotal|Total Amount|Amount)\s*[:\-]?\s*(?:\$|INR|Rs|₹)?\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
    if val_m: res["base"] = float(val_m.group(1).replace(',', ''))
    
    # GST Bifurcation
    res["cgst"] = sum([float(x.replace(',','')) for x in re.findall(r"CGST.*?([\d,]+\.\d{2})", text, re.IGNORECASE)])
    res["sgst"] = sum([float(x.replace(',','')) for x in re.findall(r"SGST.*?([\d,]+\.\d{2})", text, re.IGNORECASE)])
    res["igst"] = sum([float(x.replace(',','')) for x in re.findall(r"IGST.*?([\d,]+\.\d{2})", text, re.IGNORECASE)])
    
    # TDS Section Selection Logic
    t_low = text.lower()
    if any(x in t_low for x in ["license", "rent", "lease"]): res["sec"] = "194I"
    elif any(x in t_low for x in ["software", "professional", "consult"]): res["sec"] = "194J"
    
    if "legal" in t_low or "transport" in t_low: res["rcm"] = "Yes (RCM)"
    return res

# --- 3. DUAL LOGIN INTERFACE ---
if 'auth' not in st.session_state: st.session_state['auth'] = None

with st.sidebar:
    st.markdown("### User Access")
    # NORMAL LOGIN
    with st.expander("Normal Login", expanded=st.session_state['auth'] is None):
        n_name = st.text_input("Enter Name", key="n_name")
        if st.button("Proceed", key="n_btn"):
            if n_name:
                st.session_state['auth'], st.session_state['user'] = "User", n_name
                st.rerun()

    st.markdown("---")
    # DEVELOPER LOGIN
    with st.expander("Developer Login", expanded=False):
        d_id = st.text_input("User ID")
        d_pw = st.text_input("Password", type="password")
        if st.button("Proceed", key="d_btn"):
            if d_id == "Chirag" and d_pw == "Chirag":
                st.session_state['auth'], st.session_state['user'] = "Developer", "Chirag"
                st.rerun()
            else: st.error("Unauthorized")

if not st.session_state['auth']:
    st.title("Compliance Intelligence Hub")
    st.info("Log in to proceed.")
    st.stop()

# --- 4. MAIN DASHBOARD ---
st.title("Compliance Intelligence Hub")
st.caption(f"User: {st.session_state['user']} | Identity: {st.session_state['auth']}")

files = st.file_uploader("Upload Vendor Invoices", accept_multiple_files=True, type=['pdf'])

if st.button("Proceed") and files:
    final_data = []
    for i, f in enumerate(files):
        txt = extract_content(f)
        d = analyze_logic(txt)
        calc_gst = d["cgst"] + d["sgst"] + d["igst"]
        
        # TDS Calculations
        sec = d["sec"]
        rate = TDS_RULES[sec]["rate"]
        is_app = d["base"] >= TDS_RULES[sec]["limit"]
        tds_ded = d["base"] * rate if is_app else 0.0

        final_data.append({
            "Sr. No.": i + 1,
            "Vendor Name": get_vendor_assured(txt),
            "File Name": f.name,
            "Invoice Date": get_date_assured(txt),
            "Base Value": d["base"],
            "CGST": d["cgst"], "SGST": d["sgst"], "IGST": d["igst"],
            "TDS Section": sec, "TDS Rate": f"{rate*100}%",
            "TDS Deducted": tds_ded, "RCM Status": d["rcm"],
            "TDS Applicability": "Yes" if is_app else "No (Threshold)",
            "GST Applicability": "Forward" if calc_gst > 0 else "Exempt/RCM",
            "Journal": [
                {"Account": "Expense Account", "Dr": d["base"], "Cr": 0},
                {"Account": "GST Input", "Dr": calc_gst, "Cr": 0},
                {"Account": "TDS Payable", "Dr": 0, "Cr": tds_ded},
                {"Account": "Vendor Payable", "Dr": 0, "Cr": (d["base"]+calc_gst)-tds_ded}
            ]
        })

    # Display Automated Report
    st.dataframe(pd.DataFrame(final_data).drop(columns=["Journal"]), use_container_width=True, hide_index=True)
    
    st.subheader("Journal Entries")
    cols = st.columns(2)
    for i, item in enumerate(final_data):
        with cols[i%2].expander(f"Post: {item['Vendor Name']}"):
            st.table(pd.DataFrame(item["Journal"]))

    # LOGGING
    pd.DataFrame([{"Time": datetime.now(), "User": st.session_state['user']}]).to_csv(LOG_FILE, mode='a', index=False, header=False)

# AUDIT VIEW FOR DEVELOPER ONLY
if st.session_state['auth'] == "Developer":
    st.sidebar.markdown("---")
    if st.sidebar.checkbox("View Audit Logs"):
        if os.path.exists(LOG_FILE): st.sidebar.dataframe(pd.read_csv(LOG_FILE).tail(15))