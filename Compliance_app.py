import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- 1. UI THEME ---
st.set_page_config(page_title="Compliance Intelligence Hub", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #000000; color: #ffffff; }
    [data-testid="stSidebar"] { background-color: #0a0a0a; border-right: 2px solid #1ed760; }
    .stButton>button { background-color: #1ed760 !important; color: black !important; font-weight: bold !important; border-radius: 5px !important; }
    h1, h2, h3 { color: #1ed760; }
    </style>
    """, unsafe_allow_html=True)

TDS_RULES = {"194J": {"rate": 0.10, "limit": 30000}, "194C": {"rate": 0.02, "limit": 30000}}

# --- 2. EXTRACTION ENGINE ---
def extract_raw_data(file):
    with pdfplumber.open(file) as pdf:
        return "\n".join([page.extract_text() or "" for page in pdf.pages])

def parse_financials(text, vendor):
    data = {"base": 0.0, "cgst": 0.0, "sgst": 0.0, "igst": 0.0, "date": "Not Detected", "sec": "194C"}
    
    # Precise Date Detection
    date_match = re.search(r"(?:Bill|Invoice|Date|Period)\s*[:\|-]?\s*(\d{1,2}[-\/\s]\w{3,9}[-\/\s]\d{2,4})", text, re.IGNORECASE)
    if date_match: data["date"] = date_match.group(1)

    # Tata & Shivtel Base Value Fix
    clean_text = text.replace(',', '')
    if "tata" in vendor.lower() or "ttns" in vendor.lower():
        # Scans for Total Current Charges or Invoice Amount
        m = re.search(r"(?:Total Current Charges|Invoice Amount|Total Amount Due)\s*[:\|-]?\s*(\d+\.\d{2})", clean_text, re.IGNORECASE)
        if m: data["base"] = float(m.group(1))
    elif "shivtel" in vendor.lower():
        m = re.search(r"Sub Total\s*[:\|-]?\s*(\d+\.\d{2})", clean_text)
        if m: data["base"] = float(m.group(1))
    
    # GST Extraction
    data["cgst"] = sum([float(x) for x in re.findall(r"CGST.*?(\d+\.\d{2})", clean_text)])
    data["sgst"] = sum([float(x) for x in re.findall(r"SGST.*?(\d+\.\d{2})", clean_text)])
    data["igst"] = sum([float(x) for x in re.findall(r"IGST.*?(\d+\.\d{2})", clean_text)])
    return data

# --- 3. CLOUD LOGGING (FIXED FOR ATTRIBUTE ERROR) ---
def sync_to_cloud(rows):
    try:
        # We access the key without trying to "assign" or change the secret attribute
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = pd.DataFrame(rows)
        try:
            existing = conn.read(ttl=0)
            updated = pd.concat([existing, df], ignore_index=True)
        except:
            updated = df
        conn.update(data=updated)
        st.success("Cloud Database Updated!")
    except Exception as e:
        st.error(f"Cloud Sync Error: {e}")

# --- 4. APP FLOW ---
st.title("Compliance Intelligence Hub")
files = st.file_uploader("Upload Invoices", accept_multiple_files=True)

if st.button("Proceed") and files:
    all_rows = []
    for idx, f in enumerate(files):
        txt = extract_raw_data(f)
        v = "Tata Tele" if "tata" in txt.lower() or "ttns" in txt.lower() else "Shivtel" if "shivtel" in txt.lower() else "Vendor"
        vals = parse_financials(txt, v)
        
        total_tax = vals["cgst"] + vals["sgst"] + vals["igst"]
        is_app = vals["base"] >= TDS_RULES[vals["sec"]]["limit"]
        tds_amt = vals["base"] * TDS_RULES[vals["sec"]]["rate"] if is_app else 0.0

        row = {
            "Sr. No.": idx + 1,
            "Vendor": v,
            "Date": vals["date"],
            "Base Value": vals["base"],
            "TDS Amt": tds_amt if is_app else "NA",
            "TDS Reason": "Applicable" if is_app else "Below Limit",
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        row["Journal"] = [
            {"Account": "Expense", "Dr": vals["base"], "Cr": 0},
            {"Account": "GST Input", "Dr": total_tax, "Cr": 0},
            {"Account": "TDS Payable", "Dr": 0, "Cr": tds_amt},
            {"Account": "Vendor", "Dr": 0, "Cr": (vals["base"]+total_tax)-tds_amt}
        ]
        all_rows.append(row)

    st.dataframe(pd.DataFrame(all_rows).drop(columns=["Journal", "Timestamp"]), use_container_width=True)
    
    st.subheader("Journal Entries")
    for item in all_rows:
        with st.expander(f"Post: {item['Vendor']} ({item['Date']})"):
            st.table(pd.DataFrame(item["Journal"]))

    sync_to_cloud([ {k:v for k,v in r.items() if k != "Journal"} for r in all_rows ])
