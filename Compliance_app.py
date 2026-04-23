import streamlit as st
import pandas as pd
import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes
import re
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- 1. UI & THEME RESTORATION ---
st.set_page_config(page_title="Compliance Intelligence Hub", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #000000; color: #ffffff; }
    [data-testid="stSidebar"] { background-color: #0a0a0a; border-right: 2px solid #1ed760; }
    .stButton>button { 
        background-color: #1ed760 !important; 
        color: black !important; 
        font-weight: bold !important; 
        border-radius: 5px !important;
    }
    .stDataFrame { border: 1px solid #1ed760; border-radius: 10px; }
    div[data-testid="stExpander"] { background-color: #0a0a0a; border: 1px solid #333; }
    h1, h2, h3 { color: #1ed760; }
    </style>
    """, unsafe_allow_html=True)

TDS_RULES = {"194J": {"rate": 0.10, "limit": 30000}, "194C": {"rate": 0.02, "limit": 30000}}

# --- 2. HIGH-ACCURACY EXTRACTION ---
def extract_raw_data(file):
    f_bytes = file.read()
    all_text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            all_text += (page.extract_text() or "") + "\n"
            for table in page.extract_tables():
                for row in table:
                    all_text += " | ".join([str(cell) for cell in row if cell]) + "\n"
    
    if len(all_text.strip()) < 100:
        images = convert_from_bytes(f_bytes)
        all_text = " ".join([pytesseract.image_to_string(img) for img in images])
    return all_text

def get_vendor(text):
    t = text.lower()
    if "reliance jio" in t: return "Reliance Jio Infocomm Ltd"
    if "karix" in t: return "Karix Mobile Pvt Ltd"
    if "decfin" in t: return "Decfin Tech Pvt Ltd"
    if "shivtel" in t or "fonada" in t: return "Shivtel Communications"
    if "tata tele" in t or "ttns" in t: return "Tata Tele Business Services"
    return "Unknown Vendor"

def parse_financials(text, vendor):
    data = {"base": 0.0, "cgst": 0.0, "sgst": 0.0, "igst": 0.0, "sec": "194C", "date": "Not Detected"}
    
    # Strengthened Date Regex for Tata & Decfin
    date_patterns = [
        r"(?:Invoice|Bill|Date|Period)\s*(?:Date)?\s*[:\|-]?\s*(\d{1,2}[-\/\s]\w{3,9}[-\/\s]\d{2,4})",
        r"(?:Invoice|Bill|Date|Period)\s*(?:Date)?\s*[:\|-]?\s*(\d{1,2}/\d{1,2}/\d{2,4})"
    ]
    for p in date_patterns:
        match = re.search(p, text, re.IGNORECASE)
        if match:
            data["date"] = match.group(1).strip()
            break

    # Targeted Value Extraction
    if "shivtel" in vendor.lower():
        m = re.search(r"Sub Total\s*(?:\|)?\s*([\d,]+\.\d{2})", text)
        if m: data["base"] = float(m.group(1).replace(',', ''))
    elif "jio" in vendor.lower():
        m = re.search(r"Current Taxable Charges\s*(?:\|)?\s*([\d,]+\.\d{2})", text)
        if m: data["base"] = float(m.group(1).replace(',', ''))
    else:
        m = re.search(r"(?:Sub Total|Taxable Amount|Total Value)\s*[:\|-]?\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
        if m: data["base"] = float(m.group(1).replace(',', ''))

    data["cgst"] = sum([float(x.replace(',','')) for x in re.findall(r"CGST.*?([\d,]+\.\d{2})", text, re.IGNORECASE)])
    data["sgst"] = sum([float(x.replace(',','')) for x in re.findall(r"SGST.*?([\d,]+\.\d{2})", text, re.IGNORECASE)])
    data["igst"] = sum([float(x.replace(',','')) for x in re.findall(r"IGST.*?([\d,]+\.\d{2})", text, re.IGNORECASE)])
    return data

# --- 3. CLOUD SYNC LOGIC (FORCED APPEND) ---
def sync_to_gsheet(data_list):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        # Create a clean log dataframe without Journal lists
        log_df = pd.DataFrame(data_list).drop(columns=["Journal"])
        
        # Read current sheet
        try:
            existing_data = conn.read(ttl=0)
            updated_df = pd.concat([existing_data, log_df], ignore_index=True)
        except:
            updated_df = log_df # If sheet is empty
            
        conn.update(data=updated_df)
        st.success("Successfully logged all rows to Cloud Database.")
    except Exception as e:
        st.error(f"Cloud Logging Error: {e}")

# --- 4. APP FLOW ---
if 'auth' not in st.session_state: st.session_state['auth'] = None

with st.sidebar:
    st.title("Access Control")
    if st.session_state['auth'] is None:
        u = st.text_input("Username")
        if st.button("Login"):
            st.session_state.update({"auth": "User", "user": u})
            st.rerun()
    else:
        st.write(f"Logged in as: **{st.session_state['user']}**")
        if st.button("Logout"):
            st.session_state['auth'] = None
            st.rerun()

if not st.session_state['auth']: st.stop()

st.title("Compliance Intelligence Hub")
files = st.file_uploader("Upload Invoices", accept_multiple_files=True, type=['pdf'])

if st.button("Proceed") and files:
    all_rows = []
    for idx, f in enumerate(files):
        raw_text = extract_raw_data(f)
        v = get_vendor(raw_text)
        vals = parse_financials(raw_text, v)
        
        total_tax = vals["cgst"] + vals["sgst"] + vals["igst"]
        limit = TDS_RULES[vals["sec"]]["limit"]
        is_app = vals["base"] >= limit
        tds_amt = vals["base"] * TDS_RULES[vals["sec"]]["rate"] if is_app else 0.0

        row = {
            "Sr. No.": idx + 1,
            "Vendor": v,
            "Date": vals["date"],
            "Base Value": vals["base"],
            "CGST": vals["cgst"] or "NA",
            "SGST": vals["sgst"] or "NA",
            "IGST": vals["igst"] or "NA",
            "TDS Sec": vals["sec"] if is_app else "NA",
            "TDS Amt": tds_amt if is_app else "NA",
            "TDS Reason": f"Applicable (>{limit})" if is_app else f"Below Limit (<{limit})",
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        row["Journal"] = [
            {"Account": "Expense A/c", "Dr": vals["base"], "Cr": 0},
            {"Account": "GST Input", "Dr": total_tax, "Cr": 0},
            {"Account": "TDS Payable", "Dr": 0, "Cr": tds_amt},
            {"Account": "Vendor A/c", "Dr": 0, "Cr": (vals["base"]+total_tax)-tds_amt}
        ]
        all_rows.append(row)

    # Main Data Display
    display_df = pd.DataFrame(all_rows).drop(columns=["Journal", "Timestamp"])
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Journal Entries Restoration
    st.subheader("Journal Entries")
    cols = st.columns(2)
    for i, item in enumerate(all_rows):
        with cols[i%2].expander(f"Invoice: {item['Vendor']} ({item['Date']})"):
            st.table(pd.DataFrame(item["Journal"]))

    # Cloud Logging
    sync_to_gsheet(all_rows)
