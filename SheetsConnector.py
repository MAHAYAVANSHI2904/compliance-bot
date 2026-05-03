"""
SheetsConnector.py — Google Sheets integration for Invoice Compliance Hub
Sheets: Login_Logs | Vendor_Master | Error_Logs | Token_Usage
"""
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import streamlit as st
import sqlite3
import os

DB_PATH = "invoice_forensics.db"
SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
SHEET_ID = "1j7U1Kw0NG2I77V19S0vIRqDqIFYCFdXIPE7wSDSfulQ"
CREDS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")

def _client():
    """Authenticate — tries local credentials.json first, then Streamlit secrets."""
    try:
        if os.path.exists(CREDS_FILE):
            creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
        else:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        st.warning(f"⚠️ Google Sheets not connected: {e}")
        return None

def _get_or_create_sheet(spreadsheet, title, headers):
    """Get worksheet by title or create with headers."""
    try:
        ws = spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=title, rows=1000, cols=len(headers))
        ws.append_row(headers)
    return ws

def get_spreadsheet():
    gc = _client()
    if not gc:
        return None
    try:
        return gc.open_by_key(SHEET_ID)
    except Exception as e:
        st.warning(f"⚠️ Could not open spreadsheet: {e}")
        return None

# ── A. LOGIN LOGS ────────────────────────────────────────────
def log_login(user_name: str):
    try:
        ss = get_spreadsheet()
        if not ss: return
        ws = _get_or_create_sheet(ss, "Login_Logs", [
            "Timestamp", "User Name", "Date", "Time"
        ])
        now = datetime.now()
        ws.append_row([now.strftime("%Y-%m-%d %H:%M:%S"), user_name,
                       now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")])
    except Exception as e:
        st.warning(f"Login log failed: {e}")

# ── B. VENDOR MASTER ─────────────────────────────────────────
VENDOR_HEADERS = [
    "Last Updated", "Vendor Name", "GSTIN", "PAN", "State Code",
    "Address", "Email", "Phone",
    "Bank Name", "Account Number", "IFSC Code", "Branch",
    "MSME Registered", "Udyam Number",
    "Nature of Supply", "Default TDS Section", "Default HSN/SAC",
    "First Invoice Date", "Last Invoice Date", "Total Invoices",
    "Total Base Value", "Total TDS Deducted",
    "ITC Eligible", "RCM Applicable", "206AB Risk",
    "Outstanding Flags"
]

def _gstin_to_state(gstin):
    STATE_MAP = {
        "01":"J&K","02":"HP","03":"Punjab","04":"Chandigarh","05":"Uttarakhand",
        "06":"Haryana","07":"Delhi","08":"Rajasthan","09":"UP","10":"Bihar",
        "11":"Sikkim","12":"Arunachal","13":"Nagaland","14":"Manipur",
        "15":"Mizoram","16":"Tripura","17":"Meghalaya","18":"Assam",
        "19":"West Bengal","20":"Jharkhand","21":"Odisha","22":"Chhattisgarh",
        "23":"MP","24":"Gujarat","26":"DNH & DD","27":"Maharashtra",
        "28":"Andhra","29":"Karnataka","30":"Goa","31":"Lakshadweep",
        "32":"Kerala","33":"Tamil Nadu","34":"Puducherry","35":"A&N",
        "36":"Telangana","37":"Andhra New"
    }
    try:
        return STATE_MAP.get(str(gstin)[:2], "Unknown")
    except: return "Unknown"

def upsert_vendor(data: dict, audit: dict, is_non_filer: bool = False):
    """Insert or update vendor in Vendor_Master (no duplicates by GSTIN)."""
    try:
        ss = get_spreadsheet()
        if not ss: return
        ws = _get_or_create_sheet(ss, "Vendor_Master", VENDOR_HEADERS)

        gstin = str(data.get("vendor_gstin") or "N/A").strip()
        vendor_name = str(data.get("vendor") or "N/A").strip()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        inv_date = str(data.get("invoice_date") or "")
        base_val = float(data.get("base_value") or 0.0)

        tds_details = audit.get("tds_details", [])
        tds_sec = tds_details[0].get("old_section", "N/A") if tds_details else "N/A"
        total_tds = sum(float(t.get("amount", 0)) for t in tds_details)
        hsn = ""
        items = data.get("line_items") or []
        if items and isinstance(items, list) and len(items) > 0:
            hsn = str(items[0].get("hsn_sac") or "")

        flags = " | ".join(audit.get("flags", [])) or "None"

        # Check if vendor already exists (GSTIN is at index 2)
        all_vals = ws.get_all_values()
        target_gstin = gstin.strip().upper()
        
        # Find all rows that match this GSTIN
        matching_indices = []
        for i, row in enumerate(all_vals[1:], start=2):
            if len(row) > 2 and row[2].strip().upper() == target_gstin:
                matching_indices.append(i)

        if matching_indices:
            row_idx = matching_indices[0]
            row_data = all_vals[row_idx-1]
            
            # Update aggregates
            old_invoices = int(row_data[19] or 0) if len(row_data) > 19 else 0
            old_base = float(row_data[20] or 0.0) if len(row_data) > 20 else 0.0
            old_tds = float(row_data[21] or 0.0) if len(row_data) > 21 else 0.0

            new_row = [
                now, vendor_name, gstin,
                str(data.get("pan") or gstin[2:12] if len(gstin) >= 12 else "N/A"),
                _gstin_to_state(gstin),
                str(data.get("vendor_address") or (row_data[5] if len(row_data) > 5 else "N/A")),
                str(data.get("vendor_email") or (row_data[6] if len(row_data) > 6 else "N/A")),
                str(data.get("vendor_phone") or (row_data[7] if len(row_data) > 7 else "N/A")),
                str(data.get("bank_name") or (row_data[8] if len(row_data) > 8 else "N/A")),
                str(data.get("account_number") or (row_data[9] if len(row_data) > 9 else "N/A")),
                str(data.get("ifsc_code") or (row_data[10] if len(row_data) > 10 else "N/A")),
                str(data.get("bank_branch") or (row_data[11] if len(row_data) > 11 else "N/A")),
                str(data.get("msme_registered") or (row_data[12] if len(row_data) > 12 else "Unknown")),
                str(data.get("udyam_number") or (row_data[13] if len(row_data) > 13 else "N/A")),
                str(data.get("invoice_nature") or "N/A"),
                tds_sec, hsn,
                str(row_data[17] if len(row_data) > 17 else inv_date),  # first date unchanged
                inv_date,  # last date updated
                old_invoices + 1,
                old_base + base_val,
                old_tds + total_tds,
                "YES" if audit.get("itc_eligible") else "NO",
                "YES" if audit.get("rcm_alert") else "NO",
                "HIGH" if is_non_filer else "LOW",
                flags
            ]
            ws.update(f"A{row_idx}:Z{row_idx}", [new_row])
            
            # CRITICAL: Delete any extra duplicates found (from bottom to top)
            if len(matching_indices) > 1:
                for dup_idx in reversed(matching_indices[1:]):
                    ws.delete_row(dup_idx)
        else:
            new_row = [
                now, vendor_name, gstin,
                str(gstin[2:12] if len(gstin) >= 12 else "N/A"),  # PAN from GSTIN
                _gstin_to_state(gstin),
                str(data.get("vendor_address") or "N/A"),
                str(data.get("vendor_email") or "N/A"),
                str(data.get("vendor_phone") or "N/A"),
                str(data.get("bank_name") or "N/A"),
                str(data.get("account_number") or "N/A"),
                str(data.get("ifsc_code") or "N/A"),
                str(data.get("bank_branch") or "N/A"),
                str(data.get("msme_registered") or "Unknown"),
                str(data.get("udyam_number") or "N/A"),
                str(data.get("invoice_nature") or "N/A"),
                tds_sec, hsn,
                inv_date, inv_date,
                1, base_val, total_tds,
                "YES" if audit.get("itc_eligible") else "NO",
                "YES" if audit.get("rcm_alert") else "NO",
                "HIGH" if is_non_filer else "LOW",
                flags
            ]
            ws.append_row(new_row)
            
        # DUAL REDUNDANCY: Also sync to local SQLite
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            pan_val = str(data.get("pan") or gstin[2:12] if len(gstin) >= 12 else "N/A")
            nature_val = str(data.get("invoice_nature") or "N/A")
            risk_val = "HIGH" if is_non_filer else "LOW"
            
            c.execute("""
                INSERT INTO vendor_master (gstin, vendor_name, pan, nature_of_supply, default_tds_section, risk_206ab, msme_status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(gstin) DO UPDATE SET
                    vendor_name = excluded.vendor_name,
                    pan = excluded.pan,
                    nature_of_supply = excluded.nature_of_supply,
                    default_tds_section = excluded.default_tds_section,
                    risk_206ab = excluded.risk_206ab,
                    msme_status = excluded.msme_status,
                    last_sync = CURRENT_TIMESTAMP
            """, (gstin, vendor_name, pan_val, nature_val, tds_sec, risk_val, str(data.get("msme_registered") or "Unknown")))
            conn.commit()
            conn.close()
        except:
            pass
            
    except Exception as e:
        st.warning(f"Vendor master update failed: {e}")

def get_vendor_master() -> list:
    """Return all vendors from Vendor_Master sheet, fallback to SQLite."""
    try:
        ss = get_spreadsheet()
        if ss:
            ws = _get_or_create_sheet(ss, "Vendor_Master", VENDOR_HEADERS)
            records = ws.get_all_records()
            return records
    except Exception as e:
        st.sidebar.warning(f"Sheets fetch failed, falling back to SQL: {e}")
    
    # Fallback to local SQL
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM vendor_master")
        rows = c.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except:
        return []

# ── C. ERROR LOGS ────────────────────────────────────────────
def log_error(source: str, error: str, context: str = ""):
    """Log any crash/failure to Error_Logs sheet."""
    try:
        ss = get_spreadsheet()
        if not ss: return
        ws = _get_or_create_sheet(ss, "Error_Logs", [
            "Timestamp", "Source", "Error Message", "Context", "Severity"
        ])
        severity = "CRITICAL" if any(k in error.lower() for k in ["crash","fatal","exception"]) else "WARNING"
        ws.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            source, str(error)[:500], str(context)[:300], severity
        ])
    except Exception as e:
        pass  # Silent fail — don't crash the app over logging

# ── D. TOKEN USAGE ───────────────────────────────────────────
def log_token_usage(user_name: str, file_name: str, prompt_tokens: int, completion_tokens: int):
    """Log Groq API token usage per call."""
    try:
        ss = get_spreadsheet()
        if not ss: return
        ws = _get_or_create_sheet(ss, "Token_Usage", [
            "Timestamp", "Date", "User", "File", "Prompt Tokens",
            "Completion Tokens", "Total Tokens", "Est. Cost (USD)"
        ])
        total = prompt_tokens + completion_tokens
        # Llama-4-Scout pricing: ~$0.11/M input, ~$0.34/M output (approx)
        cost = round((prompt_tokens * 0.11 + completion_tokens * 0.34) / 1_000_000, 6)
        now = datetime.now()
        ws.append_row([
            now.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%Y-%m-%d"),
            user_name, file_name, prompt_tokens, completion_tokens, total, cost
        ])
    except Exception as e:
        pass

def get_token_summary() -> dict:
    """Return today's and total token usage summary."""
    try:
        ss = get_spreadsheet()
        if not ss: return {}
        ws = _get_or_create_sheet(ss, "Token_Usage", [
            "Timestamp", "Date", "User", "File", "Prompt Tokens",
            "Completion Tokens", "Total Tokens", "Est. Cost (USD)"
        ])
        records = ws.get_all_records()
        today = datetime.now().strftime("%Y-%m-%d")
        today_records = [r for r in records if str(r.get("Date","")) == today]

        return {
            "today_total": sum(int(r.get("Total Tokens", 0)) for r in today_records),
            "today_cost":  sum(float(r.get("Est. Cost (USD)", 0)) for r in today_records),
            "all_total":   sum(int(r.get("Total Tokens", 0)) for r in records),
            "all_cost":    sum(float(r.get("Est. Cost (USD)", 0)) for r in records),
            "today_calls": len(today_records),
        }
    except:
        return {}

def update_vendor_master(all_results: list):
    """Batch upsert unique vendors from a list of audit results."""
    try:
        seen_vendors = {}
        for res in all_results:
            d = res.get("_raw_data")
            if not d: continue
            gstin = d.get("vendor_gstin")
            if gstin:
                # Store most recent data for each unique GSTIN
                seen_vendors[gstin] = (d, d.get("compliance_audit", {}))
        
        for gstin, (d, audit) in seen_vendors.items():
            upsert_vendor(d, audit)
    except Exception as e:
        log_error("SheetsConnector.update_vendor_master", str(e))
