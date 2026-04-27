import streamlit as st
import pandas as pd
import pdfplumber
import re
import json
import io
import time
from datetime import datetime
import gspread
from invoice_intelligence import (
    parse_invoice_intelligent,
    get_invoice_complexity_badge,
    get_corrections_summary,
    get_itc_status,
    save_vendor_script,
)

# ============================================================
# SECTION: TDS & GST COMPLIANCE ENGINE
# ============================================================
TDS_RULES_FULL = {
    "192":   {"desc": "Salary", "rate": 0.0, "old_rate": 0.0, "limit": 250000, "new_code": "1001/1002", "new_sec": "392", "notes": "Rate per income tax slab."},
    "193":   {"desc": "Interest on Securities (Debentures/Bonds)", "rate": 0.10, "old_rate": 0.10, "limit": 10000, "new_code": "1019", "new_sec": "393(1)", "notes": "10% on interest."},
    "194":   {"desc": "Dividend from Domestic Company", "rate": 0.10, "old_rate": 0.10, "limit": 5000, "new_code": "1029", "new_sec": "393(1)", "notes": "10% on dividends."},
    "194A":  {"desc": "Interest (other than Securities) — FD, Bank, Post Office", "rate": 0.10, "old_rate": 0.10, "limit": 40000, "new_code": "1020/1021/1022", "new_sec": "393(1)", "notes": "Limit Rs.40,000 for others, Rs.50,000 for senior citizens."},
    "194B":  {"desc": "Winnings from Lottery / Crossword Puzzle / Card Game", "rate": 0.30, "old_rate": 0.30, "limit": 10000, "new_code": "1058", "new_sec": "393(3)", "notes": "30% flat on aggregate winnings > Rs.10,000 in a FY."},
    "194BA": {"desc": "Winnings from Online Games", "rate": 0.30, "old_rate": 0.30, "limit": 0, "new_code": "1060", "new_sec": "393(3)", "notes": "30% on net winnings."},
    "194BB": {"desc": "Winnings from Horse Racing", "rate": 0.30, "old_rate": 0.30, "limit": 10000, "new_code": "1062", "new_sec": "393(3)", "notes": "30% flat on winnings per race > Rs.10,000."},
    "194C":  {"desc": "Payment to Contractor / Sub-Contractor / Housekeeping / Transport", "rate": 0.02, "old_rate": 0.02, "limit": 30000, "new_code": "1023/1024", "new_sec": "393(1)", "notes": "2% for companies/firms, 1% for individual/HUF."},
    "194D":  {"desc": "Insurance Commission", "rate": 0.05, "old_rate": 0.05, "limit": 15000, "new_code": "1005", "new_sec": "393(1)", "notes": "5% if commission > Rs.15,000 p.a."},
    "194DA": {"desc": "Life Insurance Policy Maturity Payment", "rate": 0.05, "old_rate": 0.05, "limit": 100000, "new_code": "1030", "new_sec": "393(1)", "notes": "5% on taxable portion."},
    "194E":  {"desc": "Payment to Non-Resident Sportsman / Artist / Association", "rate": 0.20, "old_rate": 0.20, "limit": 0, "new_code": "1090", "new_sec": "393(3)", "notes": "20% flat."},
    "194EE": {"desc": "Payment from National Savings Scheme (NSS)", "rate": 0.10, "old_rate": 0.10, "limit": 2500, "new_code": "1066", "new_sec": "393(3)", "notes": "10% on withdrawal > Rs.2,500."},
    "194F":  {"desc": "Repurchase of Units by Mutual Fund / UTI", "rate": 0.20, "old_rate": 0.20, "limit": 0, "new_code": "1091", "new_sec": "393(3)", "notes": "20% flat."},
    "194G":  {"desc": "Commission on Sale of Lottery Tickets", "rate": 0.05, "old_rate": 0.05, "limit": 15000, "new_code": "1063", "new_sec": "393(1)", "notes": "5% on commission > Rs.15,000 p.a."},
    "194H":  {"desc": "Commission or Brokerage (Not insurance/securities)", "rate": 0.02, "old_rate": 0.05, "limit": 20000, "new_code": "1006", "new_sec": "393(1)", "notes": "Rate reduced to 2% from 5% for FY 26-27. Threshold Rs.20,000."},
    "194I":  {"desc": "Rent — Land, Building, Furniture & Fittings", "rate": 0.10, "old_rate": 0.10, "limit": 240000, "new_code": "1008/1009", "new_sec": "393(1)", "notes": "10% on rent for land/building/furniture. 2% for machinery (194I-a)."},
    "194IA": {"desc": "TDS on Purchase of Immovable Property (Non-Agricultural)", "rate": 0.01, "old_rate": 0.01, "limit": 5000000, "new_code": "1011", "new_sec": "393(1)", "notes": "1% on property purchase > Rs.50 Lakh."},
    "194IB": {"desc": "Rent by Individual/HUF (not tax audit liable) — High Rent", "rate": 0.05, "old_rate": 0.05, "limit": 50000, "new_code": "N/A", "new_sec": "393(1)", "notes": "5% if monthly rent > Rs.50,000."},
    "194IC": {"desc": "Payment under Joint Development Agreement (JDA)", "rate": 0.10, "old_rate": 0.10, "limit": 0, "new_code": "N/A", "new_sec": "393(1)", "notes": "10% on cash/monetary consideration paid to land owner."},
    "194J":  {"desc": "Professional / Technical Services / Director Fees / Royalty", "rate": 0.02, "old_rate": 0.10, "limit": 50000, "new_code": "1026/1027/1028", "new_sec": "393(1)", "notes": "Technical/Royalty reduced to 2%. Professional remains 10%. Threshold Rs.50,000."},
    "194K":  {"desc": "Income from Units of Mutual Funds", "rate": 0.10, "old_rate": 0.10, "limit": 5000, "new_code": "1013", "new_sec": "393(1)", "notes": "10% on income/dividend from MF units > Rs.5,000 p.a."},
    "194LA": {"desc": "Compensation on Compulsory Acquisition of Immovable Property", "rate": 0.10, "old_rate": 0.10, "limit": 250000, "new_code": "1012", "new_sec": "393(1)", "notes": "10% if compensation > Rs.2.5 Lakh."},
    "194LB": {"desc": "Interest from Infrastructure Debt Fund (NRI)", "rate": 0.05, "old_rate": 0.05, "limit": 0, "new_code": "1014/1015/1016", "new_sec": "396", "notes": "5% for NRIs."},
    "194LC": {"desc": "Interest from Indian Company / Business Trust — Long-term Bonds (NRI)", "rate": 0.05, "old_rate": 0.05, "limit": 0, "new_code": "N/A", "new_sec": "396", "notes": "5% for NRIs on long-term bonds."},
    "194LD": {"desc": "Interest on Rupee-Denominated Bonds / Govt Securities (FII/QFI)", "rate": 0.05, "old_rate": 0.05, "limit": 0, "new_code": "N/A", "new_sec": "396", "notes": "5% for FIIs."},
    "194M":  {"desc": "Payment by Individual/HUF to Contractor or Professional > Rs.50L", "rate": 0.02, "old_rate": 0.05, "limit": 5000000, "new_code": "N/A", "new_sec": "393(1)", "notes": "Reduced to 2% for FY 26-27."},
    "194N":  {"desc": "Cash Withdrawal from Bank / Post Office above threshold", "rate": 0.02, "old_rate": 0.02, "limit": 2000000, "new_code": "1064/1065", "new_sec": "393(3)", "notes": "2% on cash withdrawal above Rs.20L."},
    "194O":  {"desc": "TDS on E-Commerce Participants (by e-commerce operators)", "rate": 0.001, "old_rate": 0.01, "limit": 500000, "new_code": "1035", "new_sec": "393(1)", "notes": "Reduced to 0.1% for FY 26-27."},
    "194P":  {"desc": "TDS on Senior Citizens aged 75+ (Pension + Interest — Bank)", "rate": 0.0, "old_rate": 0.0, "limit": 0, "new_code": "1032", "new_sec": "392", "notes": "Specified bank computes tax."},
    "194Q":  {"desc": "TDS on Purchase of Goods above Rs.50L (Buyer's obligation)", "rate": 0.001, "old_rate": 0.001, "limit": 5000000, "new_code": "1031", "new_sec": "393(1)", "notes": "0.1% on purchase value above Rs.50L p.a."},
    "194R":  {"desc": "TDS on Benefit / Perquisite from Business or Profession", "rate": 0.10, "old_rate": 0.10, "limit": 20000, "new_code": "1033", "new_sec": "393(1)", "notes": "10% on FMV of benefit/perquisite > Rs.20,000 p.a."},
    "194S":  {"desc": "TDS on Transfer of Virtual Digital Asset (Crypto / NFT)", "rate": 0.01, "old_rate": 0.01, "limit": 10000, "new_code": "1037", "new_sec": "393(3)", "notes": "1% on consideration for transfer of VDA."},
    "194T":  {"desc": "Payment by Partnership Firm to Partners", "rate": 0.10, "old_rate": 0.10, "limit": 20000, "new_code": "1067", "new_sec": "393(1)", "notes": "10% on salary/bonus paid to partners > Rs.20,000 p.a."},
    "195":   {"desc": "Payment to Non-Resident / Foreign Company (Software/FTS/Royalty)", "rate": 0.10, "old_rate": 0.30, "limit": 0, "new_code": "1092/1093", "new_sec": "396", "notes": "10% under DTAA (most treaties)."},
    "196B":  {"desc": "Income from Units (Offshore Fund) — Non-Resident", "rate": 0.10, "old_rate": 0.10, "limit": 0, "new_code": "N/A", "new_sec": "396", "notes": "10% on income from units of offshore fund."},
    "196C":  {"desc": "Income from Foreign Currency Bonds / GDRs — Non-Resident", "rate": 0.10, "old_rate": 0.10, "limit": 0, "new_code": "N/A", "new_sec": "396", "notes": "10% on income from foreign currency bonds."},
    "196D":  {"desc": "Income from Securities — Foreign Institutional Investors (FII)", "rate": 0.20, "old_rate": 0.20, "limit": 0, "new_code": "N/A", "new_sec": "396", "notes": "20% on income from securities held by FIIs."},
}

TDS_RULES = {sec: {"rate": info["rate"], "limit": info["limit"]} for sec, info in TDS_RULES_FULL.items()}

TDS_KEYWORD_MAP = [
    (["rent", "lease", "leave and license", "rental", "renting of premises", "office space", "accommodation", "leave & license", "license fees", "license fee"], "194I", 90),
    (["professional", "consultancy", "advisory", "legal", "audit", "chartered accountant", "architect", "interior design", "software development", "software license", "technology fee", "subscription fee", "platform fee", "saas", "royalty", "intellectual property", "bse", "exchange", "annual listing fee", "convin", "feed forward", "karix", "telecom software", "management fee", "technical support", "crif", "credit information", "bureau", "cibil", "highmark", "equifax"], "194J", 85),
    (["contractor", "sub-contractor", "housekeeping", "cleaning", "facility management", "manpower", "security", "catering", "printing", "advertising", "transport", "logistics", "freight", "courier", "rudra", "rlfs", "labour supply", "staffing", "civil work", "repair", "maintenance", "payment gateway", "razorpay", "cashfree", "paytm", "stripe", "commission on card", "commission on all methods"], "194C", 80),
    (["commission", "brokerage", "referral fee", "agent fee", "distribution fee", "collection agent", "portfolio", "payout", "collection commission"], "194H", 75),
    (["e-commerce", "amazon", "flipkart", "marketplace", "online platform", "meesho", "nykaa", "myntra"], "194O", 75),
    (["jio", "airtel", "vodafone", "bsnl", "broadband", "tata tele", "tata teleservices", "fonada", "shivtel", "internet service", "data service", "sms usage", "dlt charges"], "194J", 80),
    (["dividend"], "194", 80),
    (["interest on fd", "interest on deposit", "bank interest", "fd interest", "fixed deposit interest"], "194A", 80),
    (["purchase of goods", "supply of goods", "goods purchase"], "194Q", 70),
    (["immovable property", "purchase of flat", "purchase of plot", "land purchase", "property purchase"], "194IA", 90),
    (["crypto", "virtual digital asset", "vda", "bitcoin", "ethereum", "nft", "web3"], "194S", 95),
    (["insurance commission", "life insurance commission"], "194D", 90),
    (["benefit", "perquisite", "free sample", "gift voucher", "sponsored trip", "sponsored event"], "194R", 75),
    (["partner salary", "partner interest", "profit sharing", "partner commission", "partnership firm payment"], "194T", 80),
    (["nri", "foreign payment", "overseas", "remittance", "foreign company", "non-resident", "linkedin singapore", "singapore pte"], "195", 85),
    (["joint development", "jda", "land owner"], "194IC", 90),
    (["cash withdrawal", "atm withdrawal"], "194N", 90),
]

VALID_GST_RATES_PCT = {0, 5, 12, 18, 28, 40, 3, 6, 9, 14}
USD_TO_INR = 83.5

RCM_KEYWORDS = [
    "gta", "goods transport agency", "freight", "advocate", "legal service",
    "director service", "import of service", "foreign service", "sponsorship",
    "arbitral tribunal", "renting of motor vehicle", "security service",
    "support service government", "director fees", "anthropic", "cursor",
    "openai", "linkedin singapore", "google cloud", "aws", "amazon web services",
    "software subscription", "rcm invoice", "reverse charge",
    # Kapish is RCM (collection commission from UP-based firm)
    "kapish enterprises",
]

FOREIGN_VENDORS = [
    "Anthropic", "Cursor", "LinkedIn Singapore", "LinkedIn Singapore Pte Ltd",
    "OpenAI", "Google Cloud", "AWS", "Amazon Web Services", "Microsoft Ireland", "DigitalOcean"
]

RCM_VENDORS = [
    "Collekt Tech", "Anthropic", "Cursor", "LinkedIn Singapore",
    "LinkedIn Singapore Pte Ltd", "OpenAI", "Google Cloud", "AWS",
    "Kapish Enterprises", "KAPISH ENTERPRISES",
]

# ══════════════════════════════════════════════════════════════════════════
# BUG FIX #1: CORRECT SELF-GSTIN (was "27ABMCS9033K1ZQ" → WRONG!)
# Apollo Finvest India Limited real GSTIN = 27AAACA0952A1ZD
# Without this fix, Apollo's GSTIN is never filtered → code climbs
# up from bill-to section → finds PAN line → vendor = "PAN/IT No : AAACA0952A"
# ══════════════════════════════════════════════════════════════════════════
SELF_GSTIN = "27AAACA0952A1ZD"   # ← FIXED
SELF_COMPANY_NAMES = ["APOLLO FINVEST", "APOLLO FINVEST INDIA LIMITED", "APOLLO FINVEST (INDIA) LIMITED"]
SELF_PAN = "AAACA0952A"

# Vendor name lines that must ALWAYS be rejected
VENDOR_LINE_REJECT_PATTERNS = [
    r'(?i)^pan[/\s]?(?:it|no|number)',    # "PAN/IT No", "PAN No"
    r'(?i)^gstin\b',                        # "GSTIN: ..."
    r'(?i)^irn\b',                          # "IRN: ..."
    r'(?i)^ack(?:nowledg)?',                # "Ack No"
    r'(?i)^state\s+name',                   # "State Name: ..."
    r'(?i)^place\s+of\s+supply',
    r'(?i)^buyer',
    r'(?i)^bill\s+to',
    r'(?i)^ship\s+to',
    r'(?i)^invoice\s+type',
    r'(?i)^supply\s+type',
    r'(?i)^b2b\b',
    r'(?i)^subject\s*:',
    r'(?i)^usage\s+period',
    r'(?i)^powered\s+by',
    r'(?i)^authorized',
    r'(?i)^thank',
    r'(?i)^note\s*:',
    r'(?i)^due\s+date',
    r'(?i)^invoice\s+date',
]

# Invoice number values that are invalid
INV_NO_BLACKLIST = {
    "dated", "date", "not detected", "", "none", "original", "duplicate",
    "2024", "2025", "2026", "2027", "2028", "1", "2", "3", "na", "n/a",
}

PREVENTION_FILE = "prevention_memory.csv"

def load_prevention_memory():
    try:
        import os
        if os.path.exists(PREVENTION_FILE):
            return pd.read_csv(PREVENTION_FILE).to_dict('records')
    except: pass
    return []

def save_prevention_data(vendor, field, status, text_snippet):
    try:
        import os
        clean_snippet = re.sub(r'[^A-Za-z0-9\s]', '', text_snippet[:150])
        new_data = pd.DataFrame([{
            "Vendor": vendor, "Field": field, "Status": status,
            "Snippet": clean_snippet, "Timestamp": datetime.now().strftime("%Y-%m-%d")
        }])
        if not os.path.exists(PREVENTION_FILE):
            new_data.to_csv(PREVENTION_FILE, index=False)
        else:
            new_data.to_csv(PREVENTION_FILE, mode='a', header=False, index=False)
    except: pass

@st.cache_data(ttl=60)
def get_master_vendor_mapping(_sh):
    if not _sh: return {}
    try:
        ws = _sh.worksheet("Vendor_Master")
        records = ws.get_all_records()
        return {str(r.get("GST Number", "")).strip().upper(): r.get("Vendor Name", "Unknown") for r in records if r.get("GST Number")}
    except: return {}

def run_real_prevention_analysis(audit_data):
    learned_count = 0
    if not audit_data: return 0
    for audit in audit_data:
        try:
            acc_str = str(audit.get("Accuracy", "0")).replace('%', '')
            acc_val = int(float(acc_str))
        except: acc_val = 0
        if "❌" in str(audit.get("Validation", "")) or acc_val < 90:
            save_prevention_data(audit.get('Vendor', 'Unknown'), "Name", "Rubbish/Code", audit.get('Snippet', ''))
            learned_count += 1
    return learned_count

ITC_BLOCKED_KEYWORDS = [
    "motor vehicle", "passenger vehicle", "outdoor catering", "beauty treatment",
    "health service", "cosmetic surgery", "membership of club", "gym membership",
    "travel benefit", "life insurance", "health insurance", "construction of building",
    "works contract for immovable", "free sample", "gift"
]

GSTIN_REGEX = re.compile(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1})\b")

# ══════════════════════════════════════════════════════════════════════════
# BUG FIX #2: GSTIN OCR CORRECTION
# Common OCR mistakes: O→0, I→1, S→5 in numeric positions of GSTIN
# Kapish: "OZKNJPSAA9AEIZB" should be "07KNJPS4494E1ZB"
# ══════════════════════════════════════════════════════════════════════════
def fix_gstin_ocr(gstin: str) -> str:
    """Fix common OCR character swaps in GSTIN."""
    if not gstin or len(gstin) != 15:
        return gstin
    g = list(gstin.upper())
    # Positions 0,1 → must be digits
    digit_fix = {'O': '0', 'o': '0', 'I': '1', 'l': '1', 'S': '5', 'Z': '2', 'B': '8'}
    for i in [0, 1, 7, 8, 9, 10]:
        if i < len(g) and g[i] in digit_fix:
            g[i] = digit_fix[g[i]]
    # Position 13 must be 'Z'
    if len(g) > 13:
        g[13] = 'Z'
    return ''.join(g)


def extract_pan(text: str, gstin: str = "") -> str:
    # 1. Direct PAN Regex
    pan_matches = re.findall(r"\b([A-Z]{5}\d{4}[A-Z]{1})\b", text.upper())
    if pan_matches: return pan_matches[0]
    # 2. Extract from GSTIN (chars 2 to 12)
    if gstin and len(gstin) == 15:
        return gstin[2:12].upper()
    return ""

def validate_gstin(gstin: str) -> tuple:
    fixed = fix_gstin_ocr(gstin)
    if not fixed or len(fixed) != 15: return False, f"Invalid length ({len(fixed) if fixed else 0}). Must be 15 chars."
    if not GSTIN_REGEX.match(fixed.upper()): return False, "Format invalid (Expected: 2 Digits + 10 Alphanum + 1 Digit + Z + 1 Alphanum)."
    return True, "Valid Format"


def extract_gstin(text: str) -> str:
    """Extract vendor GSTIN, filtering out Apollo's own GSTIN."""
    matches = GSTIN_REGEX.findall(text.upper())
    if not matches: return ""
    # Filter Apollo's own GSTIN and any self-company GSTINs
    self_gstin_set = {SELF_GSTIN, fix_gstin_ocr(SELF_GSTIN)}
    filtered = [fix_gstin_ocr(m) for m in matches if m.upper() not in self_gstin_set and fix_gstin_ocr(m) not in self_gstin_set]
    return filtered[0] if filtered else fix_gstin_ocr(matches[0])


def validate_gst(base, cgst, sgst, igst, invoice_text=""):
    results = {}
    total_gst = cgst + sgst + igst
    if cgst > 0 and sgst > 0:
        ok = abs(cgst - sgst) < 1.0
        results["G1_CGST_EQUALS_SGST"] = (ok, "CGST matches SGST" if ok else f"CGST({cgst}) ≠ SGST({sgst})")
    results["G2_TAX_EXCLUSIVITY"] = (not (igst > 0 and (cgst > 0 or sgst > 0)), "Tax exclusivity compliant")
    if base > 0 and total_gst > 0:
        eff_rate = round((total_gst / base) * 100)
        results["G3_VALID_GST_RATE"] = (eff_rate in VALID_GST_RATES_PCT, f"Rate {eff_rate}% check")
    results["G4_GST_BELOW_BASE"] = (total_gst <= base if base > 0 else True, "GST vs Base check")
    results["G5_NO_NEGATIVES"] = (all(v >= 0 for v in [base, cgst, sgst, igst]), "Negative value check")
    gstin = extract_gstin(invoice_text)
    if gstin: results["G6_GSTIN_VALID"] = validate_gstin(gstin)
    return results


def validate_tds(base, tds_section, tds_deducted, tds_amt, invoice_text="", invoice_date=""):
    results = {}
    rule = TDS_RULES_FULL.get(tds_section, TDS_RULES_FULL["194C"])
    threshold = rule["limit"]
    rate = rule["rate"]
    if base >= threshold or threshold == 0:
        results["T1_THRESHOLD"] = (tds_deducted, f"TDS deduction check vs threshold {threshold}")
    if tds_deducted and base > 0 and rate > 0:
        actual = round(tds_amt / base, 4)
        ok = abs(actual - rate) < 0.005
        results["T2_TDS_RATE"] = (ok, f"Rate {actual*100:.1f}% check vs {rate*100:.1f}%")
    return results


def compute_compliance_score(gst_res, tds_res):
    total, passed = 0, 0
    for status, _ in {**gst_res, **tds_res}.values():
        if status is True: passed += 1; total += 1
        elif status is False: total += 1
    score = int((passed / total) * 100) if total > 0 else 100
    if score >= 90: label = "🟢 Fully Compliant"
    elif score >= 70: label = "🟡 Minor Issues"
    else: label = "🔴 Review Required"
    return score, f"{label} ({score}/100)"


def classify_tds_section(text, vendor=""):
    combined = (text + " " + vendor).lower()
    best_sec, best_score = "194C", 0
    for keywords, section, score in TDS_KEYWORD_MAP:
        if any(kw in combined for kw in keywords):
            if score > best_score: best_score, best_sec = score, section
    return best_sec, best_score


def get_tds_section_options():
    return [f"{sec} - {info['desc'][:50]} (New: {info['new_code']})" for sec, info in TDS_RULES_FULL.items()]

def get_section_code(display):
    return display.split(" - ")[0].strip()


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

@st.cache_resource
def init_log_connection():
    import os
    try:
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            credentials_dict = dict(st.secrets["connections"]["gsheets"])
            credentials_dict.pop("spreadsheet", None)
            gc = gspread.service_account_from_dict(credentials_dict)
        elif "gcp_service_account" in st.secrets:
            credentials_dict = dict(st.secrets["gcp_service_account"])
            gc = gspread.service_account_from_dict(credentials_dict)
        else:
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

try:
    from st_gsheets_connection import GSheetsConnection
    HAS_GSHEETS = True
except ImportError:
    HAS_GSHEETS = False

# ── UI ────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Compliance Intelligence Hub", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #fafafa; }
    [data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    .stButton>button {
        background: linear-gradient(135deg, #1ed760 0%, #0d8a39 100%) !important;
        color: white !important; font-weight: 600 !important;
        border-radius: 8px !important; border: none !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease !important;
    }
    .stButton>button:hover { transform: translateY(-2px) !important; box-shadow: 0 4px 12px rgba(30,215,96,0.4) !important; }
    h1 { background: -webkit-linear-gradient(45deg,#1ed760,#ffffff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800; }
    h2, h3 { color: #1ed760; }
    .stDataFrame { border: 1px solid #30363d; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    [data-testid="stFileUploadDropzone"] { border: 2px dashed #1ed760 !important; border-radius: 12px !important; background-color: #1c2128 !important; }
    </style>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
# EXTRACTION ENGINE
# ══════════════════════════════════════════════════════════════════════════
def extract_raw_data(file, first_page_only=False):
    try:
        with pdfplumber.open(file) as pdf:
            if not pdf.pages: return ""
            pages_to_scan = [pdf.pages[0]] if (first_page_only and len(pdf.pages) > 0) else pdf.pages
            text = "\n".join([page.extract_text() or "" for page in pages_to_scan])
            if len(text.strip()) < 50:
                reader = get_ocr_reader()
                if reader:
                    st.info(f"Scanning {'first page' if first_page_only else 'image'} via OCR...")
                    ocr_text = ""
                    for page in pages_to_scan:
                        try:
                            pil_image = page.to_image(resolution=150).original
                            img_array = np.array(pil_image)
                            result = reader.readtext(img_array, detail=0, paragraph=True)
                            ocr_text += "\n".join(result) + "\n"
                        except Exception as e:
                            st.warning(f"OCR failed on a page: {e}")
                    return ocr_text
                else:
                    st.warning("⚠️ Scanned PDF detected. Install easyocr for OCR support.")
            return text
    except Exception as e:
        st.error(f"Error reading {file.name}: {e}")
        return ""


# ══════════════════════════════════════════════════════════════════════════
# BUG FIX #3: COMPLETE REWRITE OF parse_financials()
# All vendor-specific handlers corrected with ground-truth values
# ══════════════════════════════════════════════════════════════════════════
def parse_financials(text, vendor):
    data = {
        "base": 0.0, "cgst": 0.0, "sgst": 0.0, "igst": 0.0,
        "date": "Not Detected", "invoice_no": "Not Detected",
        "sec": "194C", "currency": "INR", "detected_total": 0.0
    }
    clean_text = text.replace(',', '')

    # Currency Detection
    is_usd = "$" in text or "USD" in text.upper() or any(v.lower() in vendor.lower() for v in ["Anthropic", "Cursor", "OpenAI"])
    if is_usd: data["currency"] = "USD"

    # Remove Indian number format spaces: '4 38 900.00' → '438900.00'
    clean_text = re.sub(r'(?<=\d)\s+(?=\d{2,3}(?:\.\d{1,2})?\b)', '', clean_text)
    clean_text = re.sub(r'(?<=\d)\s+(?=\d{2,3}(?:\.\d{1,2})?\b)', '', clean_text)

    # ── BUG FIX: Invoice Number Extraction ────────────────────────────────
    # Strict pattern: label → separator → value (must have digit, reject blacklist)
    strict_pattern = r"(?:Invoice\s*(?:No|Number|#)|Bill\s*(?:No|Number)|Receipt\s*No|Invoice)[\.\s\:\#\-]*([A-Za-z0-9][A-Za-z0-9\-\/\\]{1,28})"
    inv_matches = re.findall(strict_pattern, clean_text, re.IGNORECASE)
    for m in inv_matches:
        m_clean = m.strip()
        # Must contain a digit, must not be in blacklist
        if (re.search(r'\d', m_clean) and
                m_clean.lower() not in INV_NO_BLACKLIST and
                len(m_clean) >= 3 and
                not re.match(r'^(dated?|date|original|duplicate)$', m_clean, re.IGNORECASE)):
            data["invoice_no"] = m_clean
            break

    if data["invoice_no"] == "Not Detected":
        # Fallback: pattern like "71/2025-26" or "67/25-26"
        fallback = re.search(r"\b(\d{1,5}\/20\d{2}\-\d{2}|\d{1,5}\/\d{2}\-\d{2}|\d{2,5}\/\d{2,4})\b", clean_text)
        if fallback:
            data["invoice_no"] = fallback.group(1).strip()

    if data["invoice_no"] == "Not Detected":
        # Fallback for pure numeric invoice IDs (Karix: 2603028399, CRIF: 7152125532)
        num_id = re.search(r"(?:Invoice\s*No|Invoice\s*Number|Invoice\s*#)\s*[:\s]*(\d{8,15})\b", clean_text, re.IGNORECASE)
        if num_id:
            data["invoice_no"] = num_id.group(1).strip()

    # ── Date Extraction ────────────────────────────────────────────────────
    date_match = re.search(
        r"(?:Invoice\s*Date|Bill\s*Date|Date|Dated|Invoice\s*Dt\.?)[\s\:\|-]*"
        r"(\d{1,2}[\s\-\/\.](?:[a-zA-Z]{3,9}|\d{1,2})[\s\-\/\.]\d{2,4})",
        clean_text, re.IGNORECASE)
    if not date_match:
        date_match = re.search(
            r"\b(\d{1,2}[-\/](?:0?[1-9]|1[0-2]|[a-zA-Z]{3,9})[-\/](?:20\d{2}))\b", clean_text)
    # Razorpay / LinkedIn style: "3/11/2026", "3/15/2026"
    if not date_match:
        date_match = re.search(r"\bBill\s*Date\s*[:\s]*(\d{1,2}\/\d{1,2}\/\d{4})\b", clean_text, re.IGNORECASE)
    if not date_match:
        date_match = re.search(r"\bInvoice\s*Dt\.?\s*[:\s]*(\d{1,2}[\/\.\-]\d{1,2}[\/\.\-]\d{4})\b", clean_text, re.IGNORECASE)
    if date_match:
        extracted = date_match.group(1).strip()
        if not re.search(r"\.\d{2,}", extracted):  # avoid version numbers
            data["date"] = extracted

    # ── Intelligent Line-Based Amount Hunter ──────────────────────────────
    def get_amount(keywords, check_next=True, break_early=True, exclude_keywords=None):
        """Find the most relevant amount near given keywords."""
        exclude_keywords = exclude_keywords or []
        amounts = []
        lines = clean_text.split('\n')
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(k.lower() in line_lower for k in keywords):
                # Skip if exclude keyword also present (e.g., "AMOUNT TRANSACTED" vs "CHARGES")
                if any(ek.lower() in line_lower for ek in exclude_keywords):
                    continue
                nums = re.findall(r"(\d+(?:\.\d{1,2})?)", line)

                def is_valid(n):
                    f = float(n)
                    if f < 3.0: return False
                    if n in ['9', '18', '5', '12', '28', '2', '4']: return False
                    if '.' not in n:
                        if len(n) == 4 and n.startswith(('202', '203')): return False  # year
                        if len(n) in [6, 8]: return False  # HSN
                        if len(n) >= 9: return False  # account/phone
                    else:
                        if f > 100_000_000: return False
                    return True

                valid = [float(n) for n in nums if is_valid(n)]

                if (not valid or not break_early) and check_next:
                    for j in range(1, 6):
                        if i + j < len(lines):
                            nxt = re.findall(r"(\d+(?:\.\d{1,2})?)", lines[i + j])
                            valid_nxt = [float(n) for n in nxt if is_valid(n)]
                            if valid_nxt:
                                valid.extend(valid_nxt)
                                if break_early: break

                if valid:
                    amounts.append(max(valid))
        return max(amounts) if amounts else 0.0

    vl = vendor.lower()

    # ══════════════════════════════════════════════════════════════════════
    # VENDOR-SPECIFIC PARSERS (ground-truth verified)
    # ══════════════════════════════════════════════════════════════════════

    # ── Razorpay ──────────────────────────────────────────────────────────
    # CRITICAL: Razorpay invoices state "All Invoice values are INCLUSIVE of GST"
    # Must extract base = Total taxable (NOT grand total)
    if "razorpay" in vl:
        # Page 2 has explicit taxable breakdown; page 1 has grand total only
        # Look for "Total" line that has the base amount (before the Tax column)
        # Pattern: Total ₹31053.38  ...IGST...₹5587.95  ₹36641.33
        razorpay_base = get_amount(["Total Taxable", "Taxable Amount", "Taxable Value"])
        razorpay_igst = get_amount(["IGST @ 18%", "Tax Total", "IGST"])
        razorpay_grand = get_amount(["Grand Total", "Total ₹", "Total"])

        if razorpay_base > 0:
            data["base"] = razorpay_base
            data["igst"] = razorpay_igst
        elif razorpay_igst > 0 and razorpay_grand > 0:
            data["base"] = round(razorpay_grand - razorpay_igst, 2)
            data["igst"] = razorpay_igst
        elif razorpay_grand > 0:
            # Only grand total found — back-calculate base (18% IGST)
            data["base"] = round(razorpay_grand / 1.18, 2)
            data["igst"] = round(data["base"] * 0.18, 2)
        data["detected_total"] = razorpay_grand
        data["sec"] = "194C"  # payment gateway = contractor

    # ── Cashfree ──────────────────────────────────────────────────────────
    # Small amounts. "Taxable Sub Total" is the base. IGST@18%.
    elif "cashfree" in vl:
        data["base"] = get_amount(["Taxable Sub Total", "Taxable Amount"])
        data["igst"] = get_amount(["IGST @ 18%", "IGST"])
        data["detected_total"] = get_amount(["Total Amount Received", "Grand Total", "Total"])
        data["sec"] = "194C"

    # ── CRIF High Mark ────────────────────────────────────────────────────
    # Invoice EXPLICITLY states "TDS @ 2% u/s 194J-technical service"
    elif "crif" in vl or "highmark" in vl or "high mark" in vl:
        data["base"] = get_amount(["Total net Amount", "net Amount", "Taxable Amount"])
        data["cgst"] = get_amount(["CGST"])
        data["sgst"] = get_amount(["SGST"])
        data["igst"] = get_amount(["IGST"])
        data["detected_total"] = get_amount(["Total Gross Amount", "Grand Total"])
        data["sec"] = "194J"  # explicitly stated on invoice

    # ── LinkedIn Singapore ─────────────────────────────────────────────────
    # Foreign vendor (Singapore). Subtotal = taxable base. GST 18% = IGST (RCM).
    elif "linkedin" in vl:
        data["base"] = get_amount(["Subtotal", "Sub Total", "Sub-total"])
        data["igst"] = get_amount(["GST", "GST :"])
        data["detected_total"] = get_amount(["Total :"])
        data["sec"] = "195"  # non-resident payment

    # ── Kapish Enterprises ────────────────────────────────────────────────
    # RCM invoice. Layout: Portfolio AMOUNT | PERCENTAGE | PAYOUT
    # PAYOUT = what Apollo pays Kapish = the invoice amount (base)
    # AMOUNT = total portfolio (NOT the invoice amount — do NOT use this!)
    elif "kapish" in vl:
        data["base"] = get_amount(
            ["TOTAL", "PAYOUT"],
            exclude_keywords=["AMOUNT", "PERCENTAGE"]  # avoid portfolio amount
        )
        # Cross-check: if detected base looks like portfolio (>100000), use TOTAL line
        if data["base"] > 100000:
            # Try to find TOTAL row which should be the payout total
            total_row = get_amount(["TOTAL"])
            if 0 < total_row < data["base"]:
                data["base"] = total_row
        data["cgst"] = 0.0
        data["sgst"] = 0.0
        data["igst"] = 0.0  # RCM invoice — no GST charged by vendor
        data["detected_total"] = data["base"]
        data["sec"] = "194H"  # commission

    # ── Rakesh Roshan (Rent) ───────────────────────────────────────────────
    elif "rakesh" in vl or "roshan" in vl:
        data["base"] = get_amount(["Taxable Value", "Leave & License", "Leave & License Charges"], break_early=False)
        if data["base"] == 0.0:
            # Fallback: look for the large rent amount (e.g., 4,38,900)
            data["base"] = get_amount(["Leave & License Charges", "License Charges", "Taxable"])
        data["cgst"] = get_amount(["CGST 9%", "CGST"])
        data["sgst"] = get_amount(["SGST 9%", "SGST"])
        data["detected_total"] = get_amount(["Total ₹", "Total"])
        data["sec"] = "194I"

    # ── Decfin Tech ───────────────────────────────────────────────────────
    # Inter-state (KA→MH) → IGST only. Sub Total = base.
    elif "decfin" in vl or "decpay" in vl:
        data["base"] = get_amount(["Sub Total"])
        data["igst"] = get_amount(["IGST18", "IGST"])
        data["detected_total"] = get_amount(["Total ₹", "Balance Due", "Total"])
        data["sec"] = "194J"

    # ── Karix Mobile (SMS/Telecom) ────────────────────────────────────────
    elif "karix" in vl:
        data["base"] = get_amount(["Total Taxable Amount", "Taxable Amount"])
        data["igst"] = get_amount(["IGST @ 18%", "IGST"])
        data["detected_total"] = get_amount(["Total"])
        data["sec"] = "194J"

    # ── Tata ──────────────────────────────────────────────────────────────
    elif "tata" in vl:
        data["base"] = get_amount(["Total Amount Before Tax", "Sub Total (INR)", "Taxable Value"])
        data["sec"] = "194J"

    # ── Jio / Reliance Jio ────────────────────────────────────────────────
    elif "jio" in vl:
        data["base"] = get_amount(["Current Taxable Charges"])
        data["sec"] = "194J"

    # ── Fonada / Shivtel ──────────────────────────────────────────────────
    elif "fonada" in vl or "shivtel" in vl:
        data["base"] = get_amount(["Sub Total"])
        data["sec"] = "194C"

    # ── BSE Limited ───────────────────────────────────────────────────────
    elif "bse" in vl:
        data["base"] = get_amount(["EQUITY SHARE", "ALF payable", "Listing Fees", "CAPITAL"])
        data["sec"] = "194J"

    # ── Rudra Lines / RLFS ────────────────────────────────────────────────
    elif "rudra" in vl or "rlfs" in vl:
        data["base"] = get_amount(["Housekeeping boy", "Housekeeping", "Rate Per Head", "Sub Total", "Taxable Value"])
        if data["base"] == 0.0:
            total = get_amount(["Total Rs", "Rs.", "Total"])
            if total > 0:
                cgst = get_amount(["CGST"])
                sgst = get_amount(["SGST"])
                calc_base = total - cgst - sgst
                if calc_base > 0:
                    data["base"] = calc_base
                    if cgst > 0: data["cgst"] = cgst
                    if sgst > 0: data["sgst"] = sgst
        data["sec"] = "194C"

    # ── Convin / Feed Forward ─────────────────────────────────────────────
    elif "convin" in vl or "feed forward" in vl:
        data["base"] = get_amount(["Sub Total", "Taxable Amount", "Base Value"])
        data["sec"] = "194J"

    # ══════════════════════════════════════════════════════════════════════
    # GENERIC EXTRACTION (for unknown vendors)
    # ══════════════════════════════════════════════════════════════════════
    total_val = get_amount(["Total Amount", "Gross Amount", "Net Amount", "Grand Total", "Total Gross Amount", "Total"])
    data["detected_total"] = max(data["detected_total"], total_val)

    if data["base"] == 0.0:
        data["base"] = get_amount(["Taxable Amount", "Taxable Value", "Taxable Total",
                                   "Sub Total", "Basic Value", "Current Taxable Charges",
                                   "Taxable Sub Total", "Total net Amount"])

    if data["base"] == 0.0 and total_val > 0:
        generic_cgst = get_amount(["CGST"])
        generic_sgst = get_amount(["SGST"])
        generic_igst = get_amount(["IGST"])
        tax_sum = generic_cgst + generic_sgst + generic_igst
        if tax_sum > 0 and tax_sum < total_val:
            data["base"] = round(total_val - tax_sum, 2)
            data["cgst"], data["sgst"], data["igst"] = generic_cgst, generic_sgst, generic_igst
        else:
            data["base"] = total_val

    # ── GST Extraction (only if not already set by vendor block) ──────────
    def extract_taxes(base_val):
        if base_val <= 0: return 0.0, 0.0, 0.0
        all_nums = [float(n) for n in re.findall(r"(\d+(?:\.\d{1,2})?)", clean_text) if float(n) > 0]
        has_cgst = "CGST" in clean_text.upper()
        has_sgst = "SGST" in clean_text.upper()
        has_igst = "IGST" in clean_text.upper()

        if has_cgst or has_sgst:
            for rate in [0.09, 0.06, 0.025, 0.14]:
                expected = base_val * rate
                matched = [n for n in all_nums if abs(n - expected) <= max(0.5, expected * 0.01)]
                if matched:
                    return max(matched), max(matched), 0.0

        if has_igst and not (has_cgst or has_sgst):
            for rate in [0.18, 0.12, 0.05, 0.28]:
                expected = base_val * rate
                matched = [n for n in all_nums if abs(n - expected) <= max(0.5, expected * 0.01)]
                if matched:
                    return 0.0, 0.0, max(matched)

        cgst = get_amount(["CGST"])
        if cgst >= base_val: cgst = 0.0
        sgst = get_amount(["SGST"])
        if sgst >= base_val: sgst = 0.0
        igst = get_amount(["IGST"])
        if igst >= base_val: igst = 0.0

        total_tax_on_inv = get_amount(["Total Tax", "Tax Amount", "Total GST"])
        if total_tax_on_inv > 0:
            current_total = cgst + sgst + igst
            if abs(current_total - total_tax_on_inv) > 2.0:
                if abs(igst - total_tax_on_inv) < 1.0:
                    cgst, sgst = 0.0, 0.0
                elif abs((cgst + sgst) - total_tax_on_inv) < 1.0:
                    igst = 0.0

        return cgst, sgst, igst

    if data["cgst"] == 0.0 and data["sgst"] == 0.0 and data["igst"] == 0.0:
        data["cgst"], data["sgst"], data["igst"] = extract_taxes(data["base"])
    else:
        total_existing = data["cgst"] + data["sgst"] + data["igst"]
        if total_existing > data["base"] and data["base"] > 0:
            data["cgst"], data["sgst"], data["igst"] = extract_taxes(data["base"])

    # ── IGST/CGST Mutual Exclusivity ──────────────────────────────────────
    if data["igst"] > 0 and (data["cgst"] > 0 or data["sgst"] > 0):
        if data["igst"] >= (data["cgst"] + data["sgst"]):
            data["cgst"] = data["sgst"] = 0.0
        else:
            data["igst"] = 0.0

    # ── TDS Section Classification (if not set by vendor block) ──────────
    if data["sec"] == "194C":
        sec_guess, _ = classify_tds_section(text, vendor)
        if sec_guess != "194C":
            data["sec"] = sec_guess

    # ── USD conversion ────────────────────────────────────────────────────
    if data["currency"] == "USD":
        for k in ["base", "cgst", "sgst", "igst"]:
            data[k] = round(data[k] * USD_TO_INR, 2)

    return data


def parse_financials_ai(text, vendor):
    api_key = st.session_state.get('ai_key', st.secrets.get("AI_API_KEY", ""))
    if not api_key: return None
    try:
        prompt = f"""
Extract financial details from this invoice text for vendor '{vendor}'.
Return ONLY a raw JSON object (no markdown, no backticks).
Schema: {{"base": float, "cgst": float, "sgst": float, "igst": float, "detected_total": float, "date": "string", "invoice_no": "string", "sec": "string"}}
Rules:
- 'detected_total' is the Grand Total / Gross Amount shown on the invoice.
- 'base' is taxable amount BEFORE taxes. If missing, calculate detected_total minus taxes.
- For Razorpay: base = detected_total / 1.18. IGST = detected_total - base.
- For Kapish Enterprises: base = PAYOUT column, NOT the AMOUNT/portfolio column.
- 'sec': 194J for tech/professional, 194I for rent, 194C for contractor, 194H for commission, 195 for foreign.
Text:
{text}
"""
        res_text = ""
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
        start_idx = res_text.find('{')
        end_idx = res_text.rfind('}') + 1
        if start_idx != -1 and end_idx != 0:
            res_text = res_text[start_idx:end_idx]
        data = json.loads(res_text)
        for k in ["base", "cgst", "sgst", "igst", "detected_total"]:
            data[k] = float(data.get(k, 0.0))
        if not data.get("date"): data["date"] = "Not Detected"
        if not data.get("invoice_no"): data["invoice_no"] = "Not Detected"
        if data["detected_total"] == 0.0:
            data["detected_total"] = round(data["base"] + data["cgst"] + data["sgst"] + data["igst"], 2)
        if not data.get("sec"): data["sec"] = "194C"
        return data
    except Exception as e:
        st.toast(f"AI Fallback Failed: {e}")
        return None


def run_verifier_approver(text, vendor_name):
    verifier_vals = parse_financials(text, vendor_name)
    approver_vals = parse_financials_ai(text, vendor_name)

    if not approver_vals:
        return verifier_vals, "Verifier (Local Heuristics)"

    v_total = float(verifier_vals.get("detected_total", 0))
    a_total = float(approver_vals.get("detected_total", 0))
    v_calc = round(verifier_vals["base"] + verifier_vals["cgst"] + verifier_vals["sgst"] + verifier_vals["igst"], 2)
    a_calc = round(approver_vals["base"] + approver_vals["cgst"] + approver_vals["sgst"] + approver_vals["igst"], 2)

    status = "Verified"
    final_vals = approver_vals.copy()

    if abs(v_total - a_total) > 1.0:
        # Use calculated totals if detected totals are missing
        v_eff = v_total if v_total > 0 else v_calc
        a_eff = a_total if a_total > 0 else a_calc
        
        v_diff = abs(v_calc - v_eff)
        a_diff = abs(a_calc - a_eff)
        if a_diff < v_diff and a_diff < 2.0:
            final_vals = approver_vals.copy()
            status = "✅ Math-Verified (Approver)"
        elif v_diff < a_diff and v_diff < 2.0:
            final_vals = verifier_vals.copy()
            status = "✅ Math-Verified (Verifier)"
        else:
            status = f"❌ Total Mismatch (V:{v_total} vs A:{a_total})"

    for field in ["invoice_no", "date"]:
        if final_vals.get(field) == "Not Detected" and verifier_vals.get(field) != "Not Detected":
            final_vals[field] = verifier_vals[field]

    return final_vals, status


# ── DATA ACCURACY ENGINE ──────────────────────────────────────────────────
def calculate_data_accuracy(row, detected_total):
    points = 0
    v = str(row.get("Vendor", ""))
    inv_no = str(row.get("Invoice Number", ""))
    v_clean = re.sub(r'[^A-Z0-9]', '', v.upper())
    inv_clean = re.sub(r'[^A-Z0-9]', '', inv_no.upper())
    is_id_like = len(re.findall(r'\d', v)) > 3
    is_inv_match = (v_clean in inv_clean or inv_clean in v_clean) if (v_clean and inv_clean) else False
    if (v != "Vendor" and len(v) > 3 and not re.match(r'^\d', v) and
            "invoice" not in v.lower() and not is_id_like and not is_inv_match and
            "pan" not in v.lower() and "gstin" not in v.lower()):
        points += 1
    inv_no_str = str(inv_no)
    if (inv_no_str not in ["Not Detected", "", "None"] and
            inv_no_str.lower() not in INV_NO_BLACKLIST and
            len(inv_no_str) > 2 and re.search(r'\d', inv_no_str)):
        points += 1
    dt = str(row.get("Invoice Date", ""))
    if dt not in ["Not Detected", "", "None"] and re.search(r'\d', dt):
        points += 1
    base = row.get("Base Value", 0)
    if isinstance(base, (int, float)) and base > 0:
        s_base = f"{base:.10f}".rstrip('0').rstrip('.')
        if '.' not in s_base or len(s_base.split('.')[-1]) <= 2:
            points += 1
    cgst, sgst, igst = row.get("CGST", 0), row.get("SGST", 0), row.get("IGST", 0)
    gst_ok = False
    if cgst > 0 and sgst > 0:
        if abs(cgst - sgst) < 1.0 and igst == 0: gst_ok = True
    elif igst > 0 and cgst == 0 and sgst == 0: gst_ok = True
    elif cgst == 0 and sgst == 0 and igst == 0: gst_ok = True
    if gst_ok: points += 1
    sec = row.get("TDS Section", "")
    if sec and sec != "Not Detected":
        points += 1
    calc_total = round(float(row.get("Base Value", 0)) + float(row.get("CGST", 0)) + float(row.get("SGST", 0)) + float(row.get("IGST", 0)), 2)
    # Bank detail checks (+3 possible points)
    if row.get("Bank Name") not in ["", "Not Detected", None]: points += 1
    if row.get("Bank Account") not in ["", "Not Detected", None]: points += 1
    if row.get("IFSC") not in ["", "Not Detected", None]: points += 1
    return int((points / 10) * 100)


# ══════════════════════════════════════════════════════════════════════════
# ACCESS CONTROL / LOGIN
# ══════════════════════════════════════════════════════════════════════════
if not st.session_state.get('auth'):
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center;'>🔐 Compliance Hub Login</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #888;'>Enter your name to access the intelligence hub</p>", unsafe_allow_html=True)
        with st.container(border=True):
            user_name = st.text_input("Full Name", placeholder="e.g. John Doe")
            if st.button("🚀 Enter Dashboard", use_container_width=True):
                if user_name:
                    if isinstance(log_worksheet, str):
                        st.error("Connection error, but proceeding...")
                    else:
                        try:
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            log_worksheet.append_row([user_name, timestamp])
                        except: pass
                    st.session_state.update({"auth": "User", "user": user_name})
                    st.rerun()
                else:
                    st.warning("Please enter your name.")
        st.markdown("""
            <div style="position: fixed; bottom: 20px; right: 20px; opacity: 0.2; font-size: 0.7rem;">
                <a href="#" style="color: #666; text-decoration: none;">Staff Portal</a>
            </div>""", unsafe_allow_html=True)
        with st.expander("Admin Access", expanded=False):
            dev_id = st.text_input("Admin ID")
            dev_pass = st.text_input("Password", type="password")
            if st.button("Unlock Admin"):
                if dev_id == "Chirag" and dev_pass == st.secrets.get("dev_password", "1234"):
                    st.session_state.update({"auth": "Developer", "user": "Chirag"})
                    st.rerun()
    st.stop()

with st.sidebar:
    st.title("Settings")
    st.markdown(f"**User:** {st.session_state['user']} ({st.session_state['auth']})")
    if "AI_API_KEY" in st.secrets and st.secrets["AI_API_KEY"].strip() != "":
        st.success("✅ AI Engine Active")
    else:
        api_key_input = st.text_input("AI API Key (Optional)", type="password")
        if api_key_input: st.session_state['ai_key'] = api_key_input
    if st.button("Logout", use_container_width=True):
        st.session_state['auth'] = None
        st.rerun()

for key in ['dup_decisions', 'processing_approved', 'vendor_master']:
    if key not in st.session_state:
        st.session_state[key] = {} if key != 'processing_approved' else False

@st.cache_data(ttl=60)
def load_existing_invoices(_sh):
    try:
        ws = _sh.worksheet("Invoices")
        return ws.get_all_records()
    except Exception:
        return []


def extract_vendor_info(text: str, vendor_name: str) -> dict:
    info = {"Vendor Name": vendor_name, "GST Number": "", "Address": "", "MSME/Udyam Number": "", "PAN": ""}
    gstin_match = re.search(r'\b(\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1})\b', text.upper())
    if gstin_match:
        info["GST Number"] = fix_gstin_ocr(gstin_match.group(1))
    if info["GST Number"]:
        info["PAN"] = info["GST Number"][2:12]
    else:
        pan_match = re.search(r'\b([A-Z]{5}\d{4}[A-Z]{1})\b', text.upper())
        if pan_match: info["PAN"] = pan_match.group(1)
    udyam_match = re.search(r'\b(UDYAM-[A-Z]{2}-\d{2}-\d{7})\b', text.upper())
    if udyam_match: info["MSME/Udyam Number"] = udyam_match.group(1)
    addr_match = re.search(r'(?:address|registered office|office)\s*[:\-]?\s*(.{10,150})', text, re.IGNORECASE)
    if addr_match: info["Address"] = addr_match.group(1).strip()[:200]
    return info


# ══════════════════════════════════════════════════════════════════════════
# MAIN PROCESSING
# ══════════════════════════════════════════════════════════════════════════
st.title("Compliance Intelligence Hub")
files = st.file_uploader("Upload Invoices", accept_multiple_files=True)

if st.button("Proceed") and files:
    if 'results' in st.session_state:
        del st.session_state['results']

    sh = None
    existing_invoices = []
    if not isinstance(log_worksheet, str):
        sh = log_worksheet.spreadsheet
        existing_invoices = load_existing_invoices(sh)

    def norm_inv(s: str) -> str:
        return re.sub(r'[\s\-\/\\]', '', str(s)).upper().strip()

    existing_inv_nos = {
        norm_inv(r.get("Invoice Number", "")): r
        for r in existing_invoices
        if r.get("Invoice Number", "") not in ("", "Not Detected", None)
    }

    st.session_state['dup_decisions'] = {}
    duplicates_found = []

    with st.spinner("Pre-scanning for duplicates..."):
        for f in files:
            full_txt = extract_raw_data(f, first_page_only=True)
            clean_scan = re.sub(r'[ \t]{2,}', ' ', full_txt)
            clean_scan = re.sub(r'(?<=[A-Z0-9])\s(?=[A-Z0-9])', '', clean_scan)
            INV_PATTERNS = [
                r'(?:Invoice|Inv)[\s\.]*(?:No|Number|#|No\.)[\s:\-#\.]*([A-Z0-9][\w\-\/]{2,28})',
                r'(?:Bill|Receipt|Tax Invoice)[\s]*(?:No|Number|#)[\s:\-#]*([A-Z0-9][\w\-\/]{2,28})',
                r'(?:Ref(?:erence)?|Order)[\s]*(?:No|Number)[\s:\-#]*([A-Z0-9][\w\-\/]{2,28})',
                r'\b([A-Z]{2,6}[\-\/]?\d{4,6}[\-\/]?\d{0,6})\b',
            ]
            quick_inv_no = None
            for pattern in INV_PATTERNS:
                m = re.search(pattern, clean_scan, re.IGNORECASE)
                if m:
                    candidate = norm_inv(m.group(1))
                    if len(candidate) >= 4 and not re.fullmatch(r'\d{4,6}', candidate):
                        quick_inv_no = candidate
                        break
            if quick_inv_no and quick_inv_no in existing_inv_nos:
                duplicates_found.append((f.name, quick_inv_no, existing_inv_nos[quick_inv_no]))
            else:
                st.session_state['dup_decisions'][f.name] = 'process'

    if duplicates_found:
        st.markdown("---")
        st.subheader("⚠️ Duplicate Invoice Alert — Your Review Required")
        for fname, inv_no, old_row in duplicates_found:
            with st.expander(f"🔴 Possible Duplicate: **{fname}** — Invoice No: `{inv_no}`", expanded=True):
                col_old, col_new = st.columns(2)
                with col_old:
                    st.markdown("**📁 EXISTING RECORD (in Google Sheets)**")
                    for label, key in [("Invoice No", "Invoice Number"), ("Vendor", "Vendor"), ("Date", "Invoice Date"), ("Base Value", "Base Value"), ("Net Payable", "Net Payable"), ("Processed By", "Processed By"), ("Timestamp", "Timestamp")]:
                        st.markdown(f"- **{label}:** {old_row.get(key, 'N/A')}")
                with col_new:
                    st.markdown("**📄 NEW UPLOAD**")
                    st.info("Values extracted during processing. Review old record and decide.")
                decision = st.radio(
                    f"What to do with `{fname}`?",
                    options=["⏭️ SKIP — Duplicate", "✅ FORCE PROCESS — Corrected/different invoice"],
                    key=f"dup_{fname}"
                )
                st.session_state['dup_decisions'][fname] = 'skip' if decision.startswith('⏭️') else 'process'
        st.markdown("---")
        if st.button("✅ Confirm & Start Processing", type="primary"):
            st.session_state['processing_approved'] = True
            st.rerun()
        st.stop()

    st.session_state['processing_approved'] = True


if st.session_state.get('processing_approved') and files:
    sh = None
    if not isinstance(log_worksheet, str):
        sh = log_worksheet.spreadsheet

    my_bar = st.progress(0, text="Operation in progress...")
    batch_all_rows = []
    batch_journal_rows = []
    batch_vendor_info_rows = []
    batch_failed_invoices = []
    batch_accuracy_audit = []

    for idx, f in enumerate(files):
        my_bar.progress(idx / len(files), text=f"⏳ Processing: {f.name}")

        if st.session_state['dup_decisions'].get(f.name) == 'skip':
            continue

        txt = extract_raw_data(f)
        txt_lower = txt.lower()

        # ══════════════════════════════════════════════════════════════════
        # BUG FIX #4: VENDOR DETECTION — Multi-pass with proper filters
        # ══════════════════════════════════════════════════════════════════
        v = "Vendor"
        address_keywords = r'(?i)(mumbai|road|street|plot|sector|near|opp|behind|west|east|north|south|maharashtra|state|supply|place|pin|pincode|floor|building|marg|tardeo|nagar|estate|lane|payment|received|release|terms|account|bank|ifsc|branch|service provider|place of supply|andheri|bengaluru|bangalore|delhi|hyderabad|kolkata|chennai)'

        def is_bad_vendor_line(line: str) -> bool:
            """Return True if this line should NOT be used as vendor name."""
            line = line.strip()
            # Check reject patterns
            if any(re.search(p, line) for p in VENDOR_LINE_REJECT_PATTERNS):
                return True
            # Contains Apollo's PAN or GSTIN
            if SELF_PAN in line.upper() or SELF_GSTIN in line.upper():
                return True
            # Is self company
            if any(sn in line.upper() for sn in SELF_COMPANY_NAMES):
                return True
            # Is an address line
            if re.search(address_keywords, line):
                return True
            # Too many digits (likely an ID/reference line)
            if len(re.findall(r'\d', line)) > 5:
                return True
            # Ends with colon (label line)
            if line.endswith(':') and len(line.split()) <= 3:
                return True
            return False

        # Pass A: GSTIN proximity (climb up from vendor GSTIN)
        gst_found = extract_gstin(txt)
        if gst_found:
            lines = [l.strip() for l in txt.split('\n') if l.strip()]
            for i, line in enumerate(lines):
                if gst_found in line.upper():
                    for offset in range(1, 13):
                        if i - offset >= 0:
                            candidate = lines[i - offset]
                            is_header = re.search(r'(?i)(tax invoice|bill|page|original|duplicate|irn|ack no|acknowledgment|suptype|b2b|qr code)', candidate)
                            if (len(candidate) > 3 and not is_header and
                                    not is_bad_vendor_line(candidate) and
                                    not any(char.isdigit() for char in candidate[:5])):
                                v = candidate
                                break
                    if v != "Vendor": break

        # Pass B: First meaningful header line
        if v == "Vendor":
            for line in txt.split('\n')[:25]:
                line = line.strip()
                if len(line) > 4:
                    is_header = re.search(r'(?i)(tax invoice|bill no|gstin|gst|date|number|original|duplicate|reference|customer|payment|bank|irn|ack|suptype|b2b)', line)
                    if (not is_header and not is_bad_vendor_line(line) and
                            not any(char.isdigit() for char in line[:3])):
                        v = line
                        break

        # Pass C: Keyword shortcuts for known vendors
        if v == "Vendor" or len(re.findall(r'\d', v)) > 4 or is_bad_vendor_line(v):
            vendor_keywords = [
                ("razorpay", "Razorpay Payments Private Limited"),
                ("cashfree", "Cashfree Payments India Pvt. Ltd."),
                ("crif high mark", "CRIF High Mark Credit Information Services"),
                ("crif", "CRIF High Mark Credit Information Services"),
                ("linkedin singapore", "LinkedIn Singapore Pte Ltd"),
                ("linkedin", "LinkedIn Singapore Pte Ltd"),
                ("kapish enterprises", "Kapish Enterprises"),
                ("decfin", "Decfin Tech Private Limited"),
                ("karix", "Karix Mobile Private Limited"),
                ("rakesh roshan", "Rakesh Roshan"),
                ("rudra", "Rudra Lines"),
                ("rlfs", "Rudra Lines"),
                ("bse limited", "BSE Limited"),
                ("bse ", "BSE Limited"),
                ("convin", "Convin"),
                ("feed forward", "Feed Forward"),
                ("tata motors", "Tata Motors"),
                ("infosys", "Infosys"),
                ("axis bank", "Axis Bank"),
                ("icici bank", "ICICI Bank"),
                ("hdfc bank", "HDFC Bank"),
                ("collekt tech", "Collekt Tech"),
                ("fonada", "Fonada"),
                ("shivtel", "Shivtel"),
                ("jio", "Reliance Jio"),
            ]
            for kw, name in vendor_keywords:
                if kw in txt_lower:
                    v = name
                    break

        # Pass D: Regex fallback
        if v == "Vendor":
            v_match = re.search(r"(?:From|Seller|Vendor|Supplier|Company Name)[\s\:]*([A-Z][A-Za-z\s\.&\(\)]{3,50})", txt[:2000])
            if v_match: v = v_match.group(1).strip()

        v = re.sub(r'\s+', ' ', v).strip()

        # ── Vision-First AI Extraction ────────────────────────────────────
        api_key = st.session_state.get('ai_key', st.secrets.get("AI_API_KEY", ""))
        try:
            vals, validation_status = parse_invoice_intelligent(
                file=f, api_key=api_key, vendor_name=v, raw_text=txt,
            )
            st.caption(f"📄 {f.name} → {get_invoice_complexity_badge(vals)}")
        except Exception:
            vals, validation_status = run_verifier_approver(txt, v)

        # ── Vendor Relevance Validation ───────────────────────────────────
        is_relevant = True
        company_suffixes = ["LTD", "LIMITED", "PVT", "LLP", "SERVICES", "ENTERPRISES", "PRIVATE", "CORP", "INC"]
        v_upper = v.upper()
        has_suffix = any(s in v_upper for s in company_suffixes)
        
        # Less strict if it has a company suffix
        max_digits = 10 if has_suffix else 4
        
        if v == "Vendor" or len(re.findall(r'\d', v)) > max_digits or is_bad_vendor_line(v):
            is_relevant = False
        
        if vals.get("invoice_no", "Not Detected") != "Not Detected":
            v_clean = re.sub(r'[^A-Z0-9]', '', v.upper())
            inv_clean = re.sub(r'[^A-Z0-9]', '', vals["invoice_no"].upper())
            if v_clean and inv_clean and (v_clean == inv_clean):
                is_relevant = False

        if not is_relevant:
            gst_found_now = extract_gstin(txt)
            master_map = get_master_vendor_mapping(sh)
            if gst_found_now and gst_found_now in master_map:
                candidate_v = master_map[gst_found_now]
                if len(re.findall(r'\d', candidate_v)) <= 10 and not is_bad_vendor_line(candidate_v):
                    v = candidate_v
                    validation_status = "✅ Auto-Corrected via Vendor Master"
                    is_relevant = True
            if not is_relevant:
                validation_status = (validation_status + " | ❌ Irrelevant Vendor").lstrip(" | ")

        if not is_relevant:
            save_prevention_data(v, "Vendor/Name", "Failure", txt[:150])

        # ── Tax Mutual Exclusivity ────────────────────────────────────────
        if (vals.get("cgst", 0) + vals.get("sgst", 0)) > vals.get("igst", 0):
            vals["igst"] = 0.0
        elif vals.get("igst", 0) > 0:
            vals["cgst"] = 0.0
            vals["sgst"] = 0.0

        # ── Log base = 0 failures ─────────────────────────────────────────
        if vals.get("base", 0) == 0.0:
            st.warning(f"Could not detect Base Value for {f.name}. Saved to Failed_Invoices.")
            batch_failed_invoices.append([f.name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), txt])
            with st.expander(f"View Raw Text from {f.name}"):
                st.text(txt if txt.strip() else "NO TEXT DETECTED")

        # ── TDS Applicability ─────────────────────────────────────────────
        sec = vals.get("sec", "194C")
        limit = TDS_RULES.get(sec, TDS_RULES["194C"])["limit"]
        is_app = vals.get("base", 0) >= limit
        tds_reason = "Applicable" if is_app else "Below Limit"

        if not is_app and vals.get("date", "Not Detected") != "Not Detected":
            month_match = re.search(r'(?i)(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', vals["date"])
            month_num = None
            if month_match:
                months = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]
                month_num = months.index(month_match.group(1).lower()) + 1
            else:
                parts = re.split(r'[-/.\s]', vals["date"])
                if len(parts) >= 2:
                    try:
                        m = int(parts[1])
                        if 1 <= m <= 12: month_num = m
                    except: pass
            if month_num and 4 <= month_num <= 9:
                months_remaining = 16 - month_num
                if vals.get("base", 0) * months_remaining >= limit:
                    is_app = True
                    tds_reason = "Future Planning"

        # ── Bank Detail Extraction ─────────────────────────────────────────
        bank_name = vals.get("bank_name", "")
        bank_acc = vals.get("bank_account", "")
        ifsc = vals.get("ifsc", "")

        # ── TDS Calculations ──────────────────────────────────────────────
        sec = vals.get("sec", "194C")
        sec_info = TDS_RULES_FULL.get(sec, TDS_RULES_FULL["194C"])
        limit = sec_info["limit"]
        is_app = vals.get("base", 0) >= limit
        tds_new_rate = sec_info["rate"]
        tds_old_rate = sec_info.get("old_rate", 0.0)
        tds_amt = round(vals.get("base", 0) * tds_new_rate, 2) if is_app else 0.0
        
        # ── RCM Detection & Tax Accrual ─────────────────────────────────────
        is_rcm = (
            any(kw in txt_lower for kw in RCM_KEYWORDS) or
            v in FOREIGN_VENDORS or
            any(rv.lower() in v.lower() for rv in RCM_VENDORS) or
            "rcm invoice" in txt_lower or
            "reverse charge" in txt_lower
        )

        gst_reason = "Applicable"
        if is_rcm:
            charged_gst = vals.get("cgst", 0) + vals.get("sgst", 0) + vals.get("igst", 0)
            if charged_gst > 0:
                gst_reason = f"RCM Alert: Vendor charged ₹{charged_gst} GST"
                validation_status = "RCM Compliance Alert"
            else:
                gst_reason = "RCM (Reverse Charge)"
                # Ensure main tax columns stay 0 for RCM invoices
                vals["cgst"] = 0.0
                vals["sgst"] = 0.0
                vals["igst"] = 0.0
            
            # Net Payable: Base - TDS
            net_payable = vals.get("base", 0) - tds_amt
        else:
            gst_applicable = vals.get("cgst", 0) > 0 or vals.get("sgst", 0) > 0 or vals.get("igst", 0) > 0
            gst_reason = "Applicable" if gst_applicable else "Not Applicable"
            # Net Payable: Base + GST - TDS
            net_payable = vals.get("base", 0) + vals.get("cgst", 0) + vals.get("sgst", 0) + vals.get("igst", 0) - tds_amt

        # ── Final Row Construction ─────────────────────────────────────────
        gstin = vals.get("vendor_gstin", "")
        pan = vals.get("pan", "") or extract_pan(txt, gstin)
        
        row = {
            "Sr. No.": idx + 1,
            "Vendor": vals.get("vendor_name", v),
            "ITA 2025 Sec": sec_info.get("new_sec", "N/A"),
            "Nature Code (2026)": sec_info.get("new_code", "N/A"),
            "TDS Section (Old)": sec,
            "GST Number": gstin,
            "PAN": pan,
            "Invoice Number": vals.get("invoice_no", "Not Detected"),
            "Invoice Date": vals.get("date", "Not Detected"),
            "Base Value": round(vals.get("base", 0), 2),
            "CGST": round(vals.get("cgst", 0), 2),
            "SGST": round(vals.get("sgst", 0), 2),
            "IGST": round(vals.get("igst", 0), 2),
            "TDS Section Desc": sec_info.get("desc", ""),
            "Complexity": vals.get("complexity_level", "simple").title(),
            "ITC Status": vals.get("itc_eligibility", "eligible").title(),
            "Bank Name": bank_name,
            "Bank Account": bank_acc,
            "IFSC": ifsc,
            "TDS Deducted": "Yes" if is_app else "No",
            "TDS Old Rate": f"{tds_old_rate * 100:.1f}%",
            "TDS New Rate": f"{tds_new_rate * 100:.2f}%",
            "TDS Amount": round(tds_amt, 2),
            "TDS Reason": tds_reason,
            "GST Reason": gst_reason,
            "Net Payable": round(net_payable, 2),
            "Validation Status": validation_status,
            "Processed By": st.session_state['user'],
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        gst_res = validate_gst(vals.get("base", 0), vals.get("cgst", 0), vals.get("sgst", 0), vals.get("igst", 0), txt)
        tds_res = validate_tds(vals.get("base", 0), sec, is_app, tds_amt, txt, vals.get("date", ""))
        score, score_label = compute_compliance_score(gst_res, tds_res)
        row["Compliance Score"] = score
        row["Compliance Status"] = score_label

        accuracy_score = calculate_data_accuracy(row, vals.get("detected_total", 0))
        row["Accuracy Score"] = f"{accuracy_score}%"

        if accuracy_score < 90 or "❌" in str(validation_status):
            batch_accuracy_audit.append({
                "Filename": f.name, "Vendor": v,
                "Accuracy": f"{accuracy_score}%", "Inv No": vals.get("invoice_no", ""),
                "Validation": validation_status,
                "Snippet": txt[:500].replace('\n', ' '),
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            save_prevention_data(v, "Vendor/Accuracy", validation_status, txt[:200])

        batch_all_rows.append(row)
        vinfo = {
            "Vendor Name": vals.get("vendor_name", v),
            "GST Number": gstin,
            "PAN": pan,
            "MSME/Udyam Number": vals.get("vendor_msme", ""),
            "Address": vals.get("vendor_address", ""),
            "Invoice Number": vals.get("invoice_no", ""),
            "Invoice Date": vals.get("date", "")
        }
        batch_vendor_info_rows.append(vinfo)

        # ── Journal Entries ───────────────────────────────────────────────
        je_ref = f"JE-{idx+1}-{vals.get('invoice_no', v) if vals.get('invoice_no', 'Not Detected') != 'Not Detected' else v}"
        batch_journal_rows.append({"Reference": je_ref, "Date": vals.get("date", ""), "Account": "Expense A/c", "Debit": round(vals.get("base", 0), 2), "Credit": 0.0})
        if is_rcm:
            if vals.get("igst", 0) > 0:
                batch_journal_rows.append({"Reference": je_ref, "Date": vals.get("date", ""), "Account": "IGST Input (RCM) A/c", "Debit": round(vals["igst"], 2), "Credit": 0.0})
                batch_journal_rows.append({"Reference": je_ref, "Date": vals.get("date", ""), "Account": "IGST Output (RCM) A/c", "Debit": 0.0, "Credit": round(vals["igst"], 2)})
        else:
            if vals.get("cgst", 0) > 0: batch_journal_rows.append({"Reference": je_ref, "Date": vals.get("date", ""), "Account": "CGST Input A/c", "Debit": round(vals["cgst"], 2), "Credit": 0.0})
            if vals.get("sgst", 0) > 0: batch_journal_rows.append({"Reference": je_ref, "Date": vals.get("date", ""), "Account": "SGST Input A/c", "Debit": round(vals["sgst"], 2), "Credit": 0.0})
            if vals.get("igst", 0) > 0: batch_journal_rows.append({"Reference": je_ref, "Date": vals.get("date", ""), "Account": "IGST Input A/c", "Debit": round(vals["igst"], 2), "Credit": 0.0})
        batch_journal_rows.append({"Reference": je_ref, "Date": vals.get("date", ""), "Account": f"{v} A/c", "Debit": 0.0, "Credit": round(net_payable, 2)})
        debit_total = round(vals.get("base", 0) + (vals.get("igst", 0) if is_rcm else (vals.get("cgst", 0) + vals.get("sgst", 0) + vals.get("igst", 0))), 2)
        credit_total = round(net_payable + (vals.get("igst", 0) if is_rcm else 0), 2)
        batch_journal_rows.append({"Reference": je_ref, "Date": "", "Account": "TOTAL", "Debit": debit_total, "Credit": credit_total})
        batch_journal_rows.append({"Reference": None, "Date": None, "Account": None, "Debit": None, "Credit": None})

    my_bar.progress(1.0, text="✅ Processing Complete!")
    st.balloons()

    st.session_state['results'] = {
        'all_rows': batch_all_rows, 'journal_rows': batch_journal_rows,
        'vendor_info_rows': batch_vendor_info_rows, 'failed_invoices': batch_failed_invoices,
        'accuracy_audit': batch_accuracy_audit
    }

    # ── Google Sheets Sync ────────────────────────────────────────────────
    if sh is not None:
        try:
            with st.status("🚀 Syncing to Google Sheets...", expanded=True) as status:
                df_sync = pd.DataFrame(batch_all_rows)
                st.write("📂 Invoices sheet...")
                try: invoice_ws = sh.worksheet("Invoices")
                except Exception:
                    invoice_ws = sh.add_worksheet(title="Invoices", rows=2000, cols=30)
                    invoice_ws.append_row(df_sync.columns.tolist())
                if len(df_sync) > 0:
                    df_to_upload = df_sync.fillna("").astype(str)
                    invoice_ws.append_rows(df_to_upload.values.tolist())

                if batch_vendor_info_rows:
                    st.write("🏢 Vendor Master...")
                    try: vendor_ws = sh.worksheet("Vendor_Master")
                    except Exception:
                        vendor_ws = sh.add_worksheet(title="Vendor_Master", rows=1000, cols=11)
                        vendor_ws.append_row(["Sr. No.", "Vendor Name", "GST Number", "PAN", "MSME/Udyam Number", "Address", "Invoice Number", "Invoice Date", "Added On", "RCM Applicable"])
                    existing_records = vendor_ws.get_all_records()
                    existing_vendors = {r.get("GST Number", "") for r in existing_records}
                    next_sr_no = len(existing_records) + 1
                    new_vendor_rows = []
                    for vi in batch_vendor_info_rows:
                        gst = vi.get("GST Number", "")
                        v_name = vi.get("Vendor Name", "Vendor")
                        is_valid_name = (v_name != "Vendor" and not re.match(r'^[\d\-\_\/\.\s]+$', v_name) and
                                         len(v_name) > 2 and len(re.findall(r'\d', v_name)) <= 4 and
                                         not is_bad_vendor_line(v_name))
                        if gst and gst not in existing_vendors and is_valid_name:
                            is_v_rcm = "Yes" if (any(kw in v_name.lower() for kw in RCM_KEYWORDS) or v_name in FOREIGN_VENDORS) else "No"
                            new_vendor_rows.append([next_sr_no, v_name, gst, vi.get("PAN", ""), vi.get("MSME/Udyam Number", ""), vi.get("Address", ""), vi.get("Invoice Number", ""), vi.get("Invoice Date", ""), datetime.now().strftime("%Y-%m-%d %H:%M"), is_v_rcm])
                            existing_vendors.add(gst)
                            next_sr_no += 1
                    if new_vendor_rows:
                        vendor_ws.append_rows(new_vendor_rows)

                if batch_failed_invoices:
                    st.write("⚠️ Failed invoices...")
                    try: failed_ws = sh.worksheet("Failed_Invoices")
                    except Exception:
                        failed_ws = sh.add_worksheet(title="Failed_Invoices", rows=1000, cols=3)
                        failed_ws.append_row(["Filename", "Timestamp", "Extracted Raw Text"])
                    failed_ws.append_rows(batch_failed_invoices)

                if batch_accuracy_audit:
                    st.write("🎯 Accuracy Audit...")
                    try: audit_ws = sh.worksheet("Accuracy_Audit")
                    except Exception:
                        audit_ws = sh.add_worksheet(title="Accuracy_Audit", rows=2000, cols=7)
                        audit_ws.append_row(["Filename", "Vendor", "Accuracy", "Inv No", "Validation", "Raw Snippet", "Timestamp"])
                    audit_ws.append_rows(pd.DataFrame(batch_accuracy_audit).values.tolist())

                status.update(label="✅ Sync Complete!", state="complete", expanded=False)
                st.toast("Data synchronized!")
                time.sleep(1.5)
        except Exception as e:
            st.error(f"Google Sheets Sync Failure: {e}")

    st.session_state['processing_approved'] = False
    st.session_state['dup_decisions'] = {}
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# RESULTS DASHBOARD
# ══════════════════════════════════════════════════════════════════════════
if 'results' in st.session_state:
    res = st.session_state['results']
    all_rows = res['all_rows']
    journal_rows = res['journal_rows']
    vendor_info_rows = res['vendor_info_rows']

    tab_main, tab_compliance = st.tabs(["📊 Main Data Screen", "🛡️ Compliance & Accuracy Dashboard"])

    with tab_main:
        col_res_a, col_res_b = st.columns([0.8, 0.2])
        with col_res_a:
            st.subheader("📋 Extracted Invoices Data")
        with col_res_b:
            if st.button("🗑️ Clear Results", use_container_width=True):
                del st.session_state['results']
                st.rerun()
        df = pd.DataFrame(all_rows)
        st.dataframe(df, use_container_width=True)
        je_df = pd.DataFrame(journal_rows)
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Invoice Data (CSV)", data=csv, file_name='invoices_data.csv', mime='text/csv', use_container_width=True)
        with dl_col2:
            je_csv = je_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Journal Entries (CSV)", data=je_csv, file_name='journal_entries.csv', mime='text/csv', use_container_width=True)
        
        with st.expander("📒 View Journal Entries"):
            st.dataframe(je_df, use_container_width=True)

        st.markdown("---")
        st.markdown("---")
        # --- Advanced GST Intelligence First ---
        st.subheader("📊 Advanced GST Intelligence")
        gst_summary = {"CGST": 0.0, "SGST": 0.0, "IGST": 0.0, "RCM": 0.0}
        counts = {"CGST": 0, "SGST": 0, "IGST": 0, "RCM": 0}
        total_gst_val = 0.0
        vendor_gst = []
        for row in all_rows:
            v_name = row.get("Vendor", "Unknown")
            c, s, i = float(row.get("CGST", 0)), float(row.get("SGST", 0)), float(row.get("IGST", 0))
            base = float(row.get("Base Value", 0))
            is_r = "RCM" in str(row.get("GST Reason", ""))
            total_gst_val += (c + s + i)
            if c > 0: gst_summary["CGST"] += c; counts["CGST"] += 1
            if s > 0: gst_summary["SGST"] += s; counts["SGST"] += 1
            if i > 0:
                if is_r: gst_summary["RCM"] += i; counts["RCM"] += 1
                else: gst_summary["IGST"] += i; counts["IGST"] += 1
            tax_rate = round(((c + s + i) / base * 100), 0) if base > 0 else 0
            vendor_gst.append({"GSTIN of Supplier": row.get("GST Number", "N/A"), "Trade/Legal Name": v_name, "Invoice Number": row.get("Invoice Number", ""), "Invoice Date": row.get("Invoice Date", ""), "Invoice Value(₹)": row.get("Net Payable", 0), "Reverse Charge": "Y" if is_r else "N", "Taxable Value (₹)": base, "Integrated Tax(₹)": i, "Central Tax(₹)": c, "State/UT Tax(₹)": s, "Cess(₹)": 0, "Tax Rate (%)": f"{tax_rate}%", "ITC Availability": "Available"})
        
        gm_c1, gm_c2 = st.columns(2)
        gm_c1.metric("Total GST Liability", f"₹{total_gst_val:,.2f}")
        gm_c2.metric("RCM Impact", f"₹{gst_summary['RCM']:,.2f}")
        
        gst_df = pd.DataFrame([
            {"Component": "CGST (Intra-state)", "Total Amount (₹)": round(gst_summary["CGST"], 2), "Invoices": counts["CGST"]},
            {"Component": "SGST (Intra-state)", "Total Amount (₹)": round(gst_summary["SGST"], 2), "Invoices": counts["SGST"]},
            {"Component": "IGST (Inter-state)", "Total Amount (₹)": round(gst_summary["IGST"], 2), "Invoices": counts["IGST"]},
            {"Component": "RCM Liability", "Total Amount (₹)": round(gst_summary["RCM"], 2), "Invoices": counts["RCM"]},
        ])
        st.dataframe(gst_df, use_container_width=True, hide_index=True)
        if vendor_gst:
            with st.expander("📂 GSTR-Ready Summary"):
                st.dataframe(pd.DataFrame(vendor_gst), use_container_width=True)
                csv_gst = pd.DataFrame(vendor_gst).to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download GST Filing Report", data=csv_gst, file_name='gst_filing_report.csv', mime='text/csv')

        st.markdown("---")
        # --- Advanced TDS Intelligence Second ---
        st.subheader("📊 Advanced TDS Intelligence")
        tds_summary = {}
        exempt_count = 0
        total_tds_val = 0.0
        for row in all_rows:
            if row.get("TDS Deducted") == "Yes":
                sec = row.get("TDS Section (Old)", "NA")
                t_amt = float(row.get("TDS Amount", 0) or 0)
                total_tds_val += t_amt
                if sec not in tds_summary:
                    tds_summary[sec] = {"Section (Old)": sec, "New Sec (2025)": TDS_RULES_FULL.get(sec, {}).get("new_sec", "N/A"), "Nature Code": TDS_RULES_FULL.get(sec, {}).get("new_code", "N/A"), "Count": 0, "Taxable Base (₹)": 0.0, "TDS Liability (₹)": 0.0}
                tds_summary[sec]["Count"] += 1
                tds_summary[sec]["Taxable Base (₹)"] += float(row.get("Base Value", 0) or 0)
                tds_summary[sec]["TDS Liability (₹)"] += t_amt
            else:
                exempt_count += 1
        
        tm_c1, tm_c2 = st.columns(2)
        tm_c1.metric("Total TDS Payable", f"₹{total_tds_val:,.2f}")
        tm_c2.metric("Compliance Rate", f"{int((len(all_rows)-exempt_count)/len(all_rows)*100) if all_rows else 100}%")
        if tds_summary:
            st.dataframe(pd.DataFrame(list(tds_summary.values())), use_container_width=True, hide_index=True)
        with st.expander("💡 Compliance Insights"):
            st.write(f"✅ {exempt_count} invoices exempted from TDS.")
            st.caption("TDS must be deposited by 7th of the following month.")

        st.markdown("---")
        st.subheader("🏢 Vendor Information Register")
        st.dataframe(pd.DataFrame(vendor_info_rows), use_container_width=True)

    with tab_compliance:
        st.subheader("🛡️ Compliance & Accuracy Dashboard")
        for row in all_rows:
            inv_name = row.get("Invoice Number", "Invoice")
            vendor_name = row.get("Vendor", "")
            base = row["Base Value"]
            cgst, sgst, igst = row["CGST"], row["SGST"], row["IGST"]
            sec = row["TDS Section (Old)"]
            is_tds = row["TDS Deducted"] == "Yes"
            tds_a = row["TDS Amount"]
            status = row["Compliance Status"]
            with st.expander(f"{status} — {vendor_name} | Invoice: {inv_name}"):
                gst_res = validate_gst(base, cgst, sgst, igst)
                tds_res = validate_tds(base, sec, is_tds, tds_a)
                tab1, tab2, tab3, tab4 = st.tabs(["GST Checks", "TDS Checks", "Section Reference", "🤖 AI Corrections"])
                with tab1:
                    for rule, (passed, msg) in gst_res.items():
                        if passed is True: st.success(msg)
                        elif passed is False: st.error(msg)
                        else: st.warning(msg)
                with tab2:
                    for rule, (passed, msg) in tds_res.items():
                        if passed is True: st.success(msg)
                        elif passed is False: st.error(msg)
                        else: st.info(msg)
                with tab3:
                    sec_info = TDS_RULES_FULL.get(sec, {})
                    st.markdown(f"**Section {sec} (New: {sec_info.get('new_sec', 'N/A')} | Nature Code: {sec_info.get('new_code', 'N/A')}): {sec_info.get('desc', 'N/A')}**")
                    st.markdown(f"- **Rate:** {sec_info.get('rate', 0)*100:.1f}% | **Threshold:** ₹{sec_info.get('limit', 0):,.0f}")
                with tab4:
                    corrections = row.get("auto_corrections", [])
                    if isinstance(corrections, list) and corrections:
                        for c in corrections: st.warning(f"⚙️ {c}")
                    else:
                        st.success("✅ No math corrections needed.")
                    st.info(f"Complexity: {row.get('Complexity', 'Simple')} | ITC: {row.get('ITC Status', 'Eligible')}")

        st.markdown("---")
        st.subheader("🎯 Data Accuracy Analysis")
        accuracy_data = [{"Invoice": r.get("Invoice Number", "N/A"), "Vendor": r.get("Vendor", "N/A"), "Accuracy Score": r.get("Accuracy Score", "0%"), "Status": "✅ Perfect" if r.get("Accuracy Score") == "100%" else "⚠️ Review"} for r in all_rows]
        st.table(pd.DataFrame(accuracy_data))

        if res.get('accuracy_audit'):
            st.markdown("---")
            st.subheader("🕵️ Accuracy Audit (Low Accuracy Patterns)")
            audit_df_view = pd.DataFrame(res['accuracy_audit'])
            st.dataframe(audit_df_view[["Filename", "Vendor", "Accuracy", "Validation", "Timestamp"]], use_container_width=True)
            if st.button("🔧 Trigger Prevention Script Analysis", use_container_width=True):
                st.info(f"Analyzing {len(res['accuracy_audit'])} patterns...")
                count = run_real_prevention_analysis(res['accuracy_audit'])
                time.sleep(1)
                st.success(f"✅ {count} patterns learned for future prevention.")
