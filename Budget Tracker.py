import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
from datetime import datetime

# --- 1. LOCAL STORAGE SETUP ---
LOG_FILE = "compliance_audit.csv"
MY_STATE = "MAHARASHTRA"

# --- 2. TDS KNOWLEDGE BASE (Section Dictionary) ---
# This serves as your "Local Internet" for TDS rules
TDS_SECTIONS = {
    "194J": {"name": "Professional/Technical", "threshold": 30000, "rate": 0.10},
    "194C": {"name": "Contractor/Sub-contractor", "threshold": 30000, "rate": 0.02},
    "194I": {"name": "Rent (Plant/Machinery)", "threshold": 240000, "rate": 0.02},
    "194IA": {"name": "Transfer of Immovable Property", "threshold": 5000000, "rate": 0.01},
    "194H": {"name": "Commission/Brokerage", "threshold": 15000, "rate": 0.05}
}

def extract_financials(text):
    data = {
        "base_amount": 0.0, "cgst": 0.0, "sgst": 0.0, "igst": 0.0, 
        "gst_rate": 0, "state": "UNKNOWN", "nature": "Unknown"
    }

    # 1. Capture Base/Taxable Value (Looks for 'Taxable Value' or 'Subtotal')
    # Matches values like 13,500.00 or $20.00
    base_match = re.search(r"(?:Taxable Value|Subtotal|Base Amount)\s*(?:\$|INR|Rs|₹)?\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
    if base_match:
        data["base_amount"] = float(base_match.group(1).replace(',', ''))
    else:
        # Fallback to general amount if labels are missing
        alt_match = re.search(r"Amount\s*(?:\$|INR|Rs|₹)?\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
        if alt_match: data["base_amount"] = float(alt_match.group(1).replace(',', ''))

    # 2. State Detection for GST Segregation
    state_match = re.search(r"Place of Supply\s*[:\-]\s*(\w+)", text, re.IGNORECASE)
    if state_match:
        data["state"] = state_match.group(1).upper()
    
    # 3. Tax Extraction (Finds CGST, SGST, IGST individually)
    cgst_val = re.search(r"CGST\s*[\d,]+\.\d{2}", text)
    sgst_val = re.search(r"SGST\s*[\d,]+\.\d{2}", text)
    igst_val = re.search(r"IGST\s*[\d,]+\.\d{2}", text)
    
    if cgst_val: data["cgst"] = float(re.findall(r"[\d,]+\.\d{2}", cgst_val.group())[0].replace(',',''))
    if sgst_val: data["sgst"] = float(re.findall(r"[\d,]+\.\d{2}", sgst_val.group())[0].replace(',',''))
    if igst_val: data["igst"] = float(re.findall(r"[\d,]+\.\d{2}", igst_val.group())[0].replace(',',''))

    # 4. Logic for TDS Nature
    if any(x in text.lower() for x in ["software", "professional", "technical"]):
        data["nature"] = "194J"
    elif any(x in text.lower() for x in ["subscription", "cloud", "ai"]):
        data["nature"] = "194J" # SaaS usually falls under 194J (Fees for Technical Services)
    
    return data

# --- STREAMLIT UI ---
st.title("Enterprise Compliance Script V2 ⚖️")

uploaded_files = st.file_uploader("Upload Invoices", type="pdf", accept_multiple_files=True)

if st.button("Run Advanced Compliance Check") and uploaded_files:
    all_results = []
    for file in uploaded_files:
        with pdfplumber.open(file) as pdf:
            content = " ".join([page.extract_text() for page in pdf.pages if page.extract_text()])
        
        raw = extract_financials(content)
        
        # Automatic Segregation Logic
        # If State is same as MY_STATE, it MUST be CGST/SGST. If different, IGST.
        is_interstate = raw["state"] != "UNKNOWN" and raw["state"] != MY_STATE
        
        # TDS Calculation using Dictionary
        tds_calc = 0.0
        sec = raw["nature"]
        if sec in TDS_SECTIONS:
            if raw["base_amount"] >= TDS_SECTIONS[sec]["threshold"]:
                tds_calc = raw["base_amount"] * TDS_SECTIONS[sec]["rate"]

        all_results.append({
            "File": file.name,
            "Base Amt": raw["base_amount"],
            "CGST": raw["cgst"],
            "SGST": raw["sgst"],
            "IGST": raw["igst"],
            "TDS Sec": sec,
            "TDS Deducted": tds_calc,
            "Total Payable": (raw["base_amount"] + raw["cgst"] + raw["sgst"] + raw["igst"]) - tds_calc
        })

    df = pd.DataFrame(all_results)
    st.dataframe(df, use_container_width=True)
    
    # Save to Local CSV
    df.to_csv("processed_compliance.csv", mode='a', index=False)
    st.success("Successfully processed and saved to processed_compliance.csv")
