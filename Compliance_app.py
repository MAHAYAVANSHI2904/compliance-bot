import streamlit as st
import pandas as pd
import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes
import re
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- 1. UI & THEME ---
st.set_page_config(page_title="Compliance Intelligence Hub", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #000000; color: #ffffff; }
    [data-testid="stSidebar"] { background-color: #0a0a0a; border-right: 2px solid #1ed760; }
    .stButton>button { background-color: #1ed760 !important; color: black !important; font-weight: bold !important; border-radius: 5px !important; }
    .stDataFrame { border: 1px solid #1ed760; border-radius: 10px; }
    div[data-testid="stExpander"] { background-color: #0a0a0a; border: 1px solid #333; }
    h1, h2, h3 { color: #1ed760; }
    </style>
    """, unsafe_allow_html=True)

TDS_RULES = {"194J": {"rate": 0.10, "limit": 30000}, "194C": {"rate": 0.02, "limit": 30000}}

# --- 2. EXTRACTION ENGINE ---
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
    
    # Date Detection
    date_patterns = [
        r"(?:Invoice|Bill|Date|Period)\s*(?:Date)?\s*[:\|-]?\s*(\d{1,2}[-\/\s]\w{3,9}[-\/\s]\d{2,4})",
        r"(?:Invoice|Bill|Date|Period)\s*(?:Date)?\s*[:\|-]?\s*(\d{1,2}/\d{1,2}/\d{2,4})"
    ]
    for p in date_patterns:
        match = re.search(p, text, re.IGNORECASE)
        if match:
            data["date"] = match.group(1).strip()
            break

    # HIGH-ACCURACY TATA & SHIVTEL LOGIC
    if "tata" in vendor.lower():
        # Specifically looking for the "Total Charge" or "Amount" in Tata layout
        m = re.search(r"(?:Total Charges|Total Current Charges|Invoice Amount)\s*[:\|-]?\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
        if m: data["base"] = float(m.group(1).replace(',', ''))
    elif "shivtel" in vendor.lower():
        m = re.search(r"Sub Total\s*(?:\|)?\s*([\d,]+\.\d{2})", text)
        if m: data["base"] = float(m.group(1).replace(',', ''))
    else:
        m = re.search(r"(?:Sub Total|Taxable Amount|Total Value)\s*[:\|-]?\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
        if m: data["base"] = float(m.group(1).replace(',', ''))

    # GST Extraction
    data["cgst"] = sum([float(x.replace(',','')) for x in re.findall(r"CGST.*?([\d,]+\.\d{2})", text, re.IGNORECASE)])
    data["sgst"] = sum([float(x.replace(',','')) for x in re.findall(r"SGST.*?([\d,]+\.\d{2})", text, re.IGNORECASE)])
    data["igst"] = sum([float(x.replace(',','')) for x in re.findall(r"IGST.*?([\d,]+\.\d{2})", text, re.IGNORECASE)])
    return data

# --- 3. CLOUD SYNC (FORCED KEY FIX) ---
def sync_to_gsheet(data_list):
    try:
        # INTERNAL KEY FIX FOR PEM ERROR
        if "connections" in st.secrets and "gsheets" in st.secrets.connections:
            # This line removes the problematic \n strings and replaces them with real line breaks
            st.secrets.connections.gsheets.private_key = st.secrets.connections.gsheets.private_key.replace("\\n", "\n")
        
        conn = st.connection("gsheets", type=GSheetsConnection)
        log_df = pd.DataFrame(data_list).drop(columns=["Journal"])
        try:
            existing = conn.read(ttl=0)
            updated = pd.concat([existing, log_df], ignore_index=True)
        except:
            updated = log_df
        conn.update(data=updated)
        st.success("Cloud Database Updated!")
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
        txt = extract_raw_data(f)
        v = get_vendor(txt)
        vals = parse_financials(txt, v)
        total_tax = vals["cgst"] + vals["sgst"] + vals["igst"]
        is_app = vals["base"] >= TDS_RULES[vals["sec"]]["limit"]
        tds_amt = vals["base"] * TDS_RULES[vals["sec"]]["rate"] if is_app else 0.0

        row = {
            "Sr. No.": idx + 1, "Vendor": v, "Date": vals["date"], "Base Value": vals["base"],
            "CGST": vals["cgst"] or "NA", "SGST": vals["sgst"] or "NA", "IGST": vals["igst"] or "NA",
            "TDS Sec": vals["sec"] if is_app else "NA", "TDS Amt": tds_amt if is_app else "NA",
            "TDS Reason": "Applicable" if is_app else "Below Limit",
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        row["Journal"] = [
            {"Account": "Expense", "Dr": vals["base"], "Cr": 0},
            {"Account": "GST In", "Dr": total_tax, "Cr": 0},
            {"Account": "TDS Pay", "Dr": 0, "Cr": tds_amt},
            {"Account": "Vendor", "Dr": 0, "Cr": (vals["base"]+total_tax)-tds_amt}
        ]
        all_rows.append(row)

    st.dataframe(pd.DataFrame(all_rows).drop(columns=["Journal", "Timestamp"]), use_container_width=True, hide_index=True)
    
    st.subheader("Journal Entries")
    cols = st.columns(2)
    for i, item in enumerate(all_rows):
        with cols[i%2].expander(f"Post: {item['Vendor']}"):
            st.table(pd.DataFrame(item["Journal"]))

    sync_to_gsheet(all_rows)
