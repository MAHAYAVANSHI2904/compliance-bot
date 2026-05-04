import streamlit as st
import pandas as pd
import ComplianceEngine
from ComplianceEngine import get_194c_aggregate, clear_session_invoices
import SheetsConnector
import UIEngine
from datetime import datetime

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Invoice Compliance Hub",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject global CSS from UIEngine
UIEngine.inject_css()

def login_page():
    UIEngine.inject_css()
    
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@300;400;500&display=swap');

    @keyframes fadeInSlideUp {
        from { opacity: 0; transform: translateY(15px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes pulse-glow {
        0% { opacity: 0.5; }
        50% { opacity: 1; }
        100% { opacity: 0.5; }
    }

    .login-shell {
        width: 100%; max-width: 420px;
        margin: 0 auto; padding: 10vh 20px 0;
        font-family: 'Geist', sans-serif;
    }
    .login-top-bar {
        display: flex; align-items: center;
        justify-content: space-between; margin-bottom: 64px;
        animation: fadeInSlideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    .login-logo { display: flex; align-items: center; gap: 9px; }
    .login-logo-mark {
        width: 28px; height: 28px; border-radius: 8px;
        background: #1a1c22; border: 1px solid rgba(255,255,255,0.08);
        display: flex; align-items: center; justify-content: center;
        transition: transform 0.3s ease;
    }
    .login-logo:hover .login-logo-mark { transform: scale(1.05); }
    .login-logo-name {
        font-size: 13px; font-weight: 500;
        color: rgba(255,255,255,0.5); letter-spacing: -0.2px;
    }
    
    .login-status { display: flex; align-items: center; gap: 6px; }
    .login-status-dot {
        width: 5px; height: 5px; border-radius: 50%; background: #4ade80;
        animation: pulse-glow 2s infinite;
    }
    .login-status-text { font-size: 11px; color: rgba(255,255,255,0.2); letter-spacing: 0.3px; font-weight: 400;}
    
    .login-h1 {
        font-family: 'Instrument Serif', serif !important;
        font-size: 38px !important; font-weight: 400 !important;
        color: #f4f5f7 !important; line-height: 1.1 !important;
        letter-spacing: -0.5px; margin-bottom: 10px;
        animation: fadeInSlideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.1s both;
    }
    .login-h1 em { font-style: italic; color: rgba(255,255,255,0.35); }
    
    .login-desc {
        font-size: 13px; color: rgba(255,255,255,0.28);
        line-height: 1.7; font-weight: 300;
        margin-bottom: 36px; max-width: 300px;
        animation: fadeInSlideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.2s both;
    }
    
    .login-footer-row {
        display: flex; align-items: center; gap: 16px; margin-top: 28px;
        animation: fadeInSlideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.5s both;
    }
    .login-f-tag {
        font-size: 10px; color: rgba(255,255,255,0.15);
        letter-spacing: 0.8px; text-transform: uppercase;
    }
    .login-f-sep { width: 1px; height: 10px; background: rgba(255,255,255,0.08); }

    div[data-testid="stTextInput"], div[data-testid="stButton"], div[data-testid="stAlert"] {
        max-width: 420px;
        margin: 0 auto;
    }

    div[data-testid="stTextInput"] {
        animation: fadeInSlideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.3s both;
    }

    /* Override Streamlit input */
    .login-shell .stTextInput input {
        background: rgba(255,255,255,0.03) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 8px !important;
        padding: 13px 16px !important;
        font-size: 14px !important;
        color: #e8eaf0 !important;
        font-family: 'Geist', sans-serif !important;
        font-weight: 300 !important;
        transition: all 0.3s ease !important;
    }
    .login-shell .stTextInput input:hover {
        border-color: rgba(255,255,255,0.15) !important;
    }
    .login-shell .stTextInput input:focus {
        border-color: rgba(255,255,255,0.25) !important;
        box-shadow: none !important;
        background: rgba(255,255,255,0.05) !important;
    }
    .login-shell .stTextInput input::placeholder { color: rgba(255,255,255,0.16) !important; }

    div[data-testid="stButton"] {
        animation: fadeInSlideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.4s both;
    }

    /* Override Streamlit button matching the dark screenshot */
    .login-shell .stButton > button {
        background: #0a0a0a !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: 8px !important;
        padding: 13px 16px !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        color: #ffffff !important;
        font-family: 'Geist', sans-serif !important;
        letter-spacing: 0.1px !important;
        transition: all 0.3s ease !important;
        width: 100% !important;
        justify-content: center !important;
    }
    .login-shell .stButton > button:hover { 
        background: rgba(255,255,255,0.05) !important;
        border-color: rgba(255,255,255,0.3) !important;
    }
    </style>

    <div class="login-shell">
      <div class="login-top-bar">
        <div class="login-logo">
          <div class="login-logo-mark">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.5)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
          </div>
          <span class="login-logo-name">Compliance Hub</span>
        </div>
        <div class="login-status">
          <div class="login-status-dot"></div>
          <span class="login-status-text">All systems normal</span>
        </div>
      </div>

      <h1 class="login-h1">Good to see<br>you <em>again.</em></h1>
      <p class="login-desc">Invoice intelligence for FY 2025–26. GST, TDS, and forensic audit — all in one place.</p>
    """, unsafe_allow_html=True)

    user_name = st.text_input("name", placeholder="Your full name", label_visibility="collapsed")
    st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)

    if st.button("Enter workspace", use_container_width=True):
        if user_name.strip():
            st.session_state.logged_in = True
            st.session_state.user_name = user_name.strip()
            st.session_state.session_start = datetime.now()
            SheetsConnector.log_login(user_name.strip())
            st.rerun()
        else:
            st.error("Please enter your name.")

    st.markdown("""
      <div class="login-footer-row">
        <span class="login-f-tag">Finance Act 2024</span>
        <div class="login-f-sep"></div>
        <span class="login-f-tag">AY 2026–27</span>
        <div class="login-f-sep"></div>
        <span class="login-f-tag">Encrypted</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        login_page()
        return

    api_key = st.secrets.get("GROQ_API_KEY", "")

    if 'vendor_totals' not in st.session_state:
        st.session_state.vendor_totals = {}
    if 'session_tokens' not in st.session_state:
        st.session_state.session_tokens = {"prompt": 0, "completion": 0}
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'processed_results' not in st.session_state:
        st.session_state.processed_results = []
        if st.session_state.logged_in:
            try:
                import json
                from sqlalchemy import text
                engine = ComplianceEngine.get_db_engine()
                now = datetime.now()
                fy_str = f"{now.year-1}-{str(now.year)[2:]}" if now.month <= 3 else f"{now.year}-{str(now.year+1)[2:]}"
                with engine.connect() as conn:
                    rows = conn.execute(text("SELECT raw_json FROM processed_invoices WHERE user_id = :user_id AND fy = :fy AND raw_json IS NOT NULL"), 
                                        {"user_id": st.session_state.user_name, "fy": fy_str}).fetchall()
                for row in rows:
                    d = json.loads(row[0])
                    audit = d.get("compliance_audit", {})
                    tds_info = audit.get("tds_details", [{}])[0] if audit.get("tds_details") else {}
                    base_v  = float(d.get("base_value", 0.0) or 0.0)
                    cgst_v  = float(d.get("cgst_amount", 0.0) or 0.0)
                    sgst_v  = float(d.get("sgst_amount", 0.0) or 0.0)
                    igst_v  = float(d.get("igst_amount", 0.0) or 0.0)
                    tds_v   = float(tds_info.get("amount") or 0.0)
                    is_rcm  = (audit.get("rcm_alert") or d.get("rcm_applicable") == "yes")
                    if is_rcm:
                        net_v = base_v - tds_v
                    else:
                        net_v = (base_v + cgst_v + sgst_v + igst_v) - tds_v
                    
                    st.session_state.processed_results.append({
                        "Sr. No.":           len(st.session_state.processed_results) + 1,
                        "Vendor":            d.get("vendor", "N/A"),
                        "Vendor GSTIN":      d.get("vendor_gstin", "N/A"),
                        "Invoice #":         d.get("invoice_number", "N/A"),
                        "Invoice Date":      d.get("invoice_date", "N/A"),
                        "Nature":            d.get("invoice_nature", "N/A"),
                        "Base Value":        base_v,
                        "CGST":              cgst_v,
                        "SGST":              sgst_v,
                        "IGST":              igst_v,
                        "RCM":               "YES" if is_rcm else "NO",
                        "TDS Section (Old)": tds_info.get("old_section", "N/A"),
                        "New Section (393)": tds_info.get("new_section", "N/A"),
                        "TDS %":             tds_info.get("rate", "0%"),
                        "TDS Deduction":     tds_v,
                        "Net Payable":       net_v,
                        "Status":            audit.get("gst_summary", ""),
                        "ITC Status":        "CLAIMABLE" if audit.get("itc_eligible") else "BLOCKED",
                        "_raw_data":         d
                    })
                conn.close()
            except Exception as e:
                print(f"Error loading session: {e}")
                
    if 'session_start' not in st.session_state:
        st.session_state.session_start = datetime.now()

    # Page routing via UIEngine
    active_page = UIEngine.render_sidebar(st.session_state.user_name)

    # KPI row always at top
    UIEngine.render_kpi_row()

    all_results = st.session_state.get('processed_results', [])

    # ══════════════════════════════════════════════════════════════
    # PAGE: DASHBOARD
    # ══════════════════════════════════════════════════════════════
    if active_page == "Dashboard":
        UIEngine.render_page_header("Dashboard", "CENTRAL INTELLIGENCE")
        if not all_results:
            st.info("No invoices processed yet. Head over to the **Scan Invoice** page to get started.")
        else:
            # Use tabs to organize the dashboard views
            tabs = st.tabs([
                ":material/bar_chart: Overview", 
                ":material/policy: Forensic Scans", 
                ":material/receipt: TDS Summary", 
                ":material/account_balance: GST Summary", 
                ":material/storefront: Vendor Data", 
                ":material/import_contacts: Journal Entry", 
                ":material/search: Research"
            ])
            
            with tabs[0]: # Overview
                total_tds = sum(float(r.get("TDS Deduction", 0) or 0) for r in all_results)
                irn_count = sum(1 for r in all_results if any("IRN" in str(f).upper() for f in r.get("_raw_data", {}).get("compliance_audit", {}).get("flags", [])))
                
                v_master = SheetsConnector.get_vendor_master()
                risk_gstins = [str(v.get("GSTIN")).strip().upper() for v in v_master if str(v.get("206AB Risk", "")).strip().upper() == "HIGH"]
                risk_count = sum(1 for r in all_results if str(r.get("Vendor GSTIN", "")).strip().upper() in risk_gstins)
                
                now = datetime.now()
                if now.day <= 7:
                    deadline_dt = now.replace(day=7)
                else:
                    deadline_dt = now.replace(year=now.year + 1, month=1, day=7) if now.month == 12 else now.replace(month=now.month + 1, day=7)
                deadline_str = deadline_dt.strftime("%d %B")
                
                st.markdown("##### 🚨 Top Action Items")
                c1, c2, c3 = st.columns(3)
                
                if total_tds > 0:
                    c1.error(f"**₹{total_tds:,.0f} TDS due {deadline_str}**")
                else:
                    c1.success("**No TDS Due**")
                    
                if irn_count > 0:
                    c2.warning(f"**{irn_count} invoices need IRN**")
                else:
                    c2.success("**0 invoices need IRN**")
                    
                if risk_count > 0:
                    c3.error(f"**{risk_count} vendor(s) 206AB risk**")
                else:
                    c3.success("**0 vendors 206AB risk**")
                
                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander("📊 Consolidated Invoice Dataset", expanded=False):
                    df = pd.DataFrame(all_results)
                    clean_df = df.drop(columns=["_raw_data"], errors="ignore")
                    st.dataframe(clean_df, use_container_width=True, hide_index=True)
                    csv = clean_df.to_csv(index=False).encode('utf-8')
                    st.download_button(label="📥 Download Overview (CSV)", data=csv, file_name="invoice_overview.csv", mime="text/csv")
                
            with tabs[1]: # Forensic Scans
                for r in all_results:
                    d = r["_raw_data"]
                    audit = d.get("compliance_audit", {})
                    tds_info = audit.get("tds_details", [{}])[0] if audit.get("tds_details") else {}
                    score, emoji, css_cls = ComplianceEngine.get_compliance_score(audit, d)
                    checklist = ComplianceEngine.get_action_checklist(d, audit, tds_info, r)
                    UIEngine.render_scan_result_card(r, score, emoji, css_cls, checklist)
                    
                    with st.expander("✏️ Correct Extraction Errors & Recalculate"):
                        with st.form(key=f"edit_form_{r['Invoice #']}_{r['Vendor']}"):
                            c1, c2, c3 = st.columns(3)
                            new_base = c1.number_input("Base Value (₹)", value=float(d.get("base_value", 0)), step=100.0)
                            new_nature = c2.text_input("Invoice Nature", value=d.get("invoice_nature", ""))
                            new_gstin = c3.text_input("Vendor GSTIN", value=d.get("vendor_gstin", ""))
                            
                            if st.form_submit_button("Save & Recalculate Compliance", type="primary"):
                                d["base_value"] = new_base
                                d["invoice_nature"] = new_nature
                                d["vendor_gstin"] = new_gstin
                                

                                audit = ComplianceEngine.perform_compliance_audit(
                                    d, 
                                    manual_206ab_verification_flag=False, 
                                    vendor_history_total=0.0, 
                                    user_id=st.session_state.user_name
                                )
                                d["compliance_audit"] = audit
                                tds_info = audit.get("tds_details", [{}])[0] if audit.get("tds_details") else {}
                                
                                base_v  = float(d.get("base_value", 0.0) or 0.0)
                                cgst_v  = float(d.get("cgst_amount", 0.0) or 0.0)
                                sgst_v  = float(d.get("sgst_amount", 0.0) or 0.0)
                                igst_v  = float(d.get("igst_amount", 0.0) or 0.0)
                                tds_v   = float(tds_info.get("amount") or 0.0)
                                is_rcm  = (audit.get("rcm_alert") or d.get("rcm_applicable") == "yes")
                                
                                net_v = (base_v - tds_v) if is_rcm else ((base_v + cgst_v + sgst_v + igst_v) - tds_v)

                                r["Base Value"] = base_v
                                r["Nature"] = new_nature
                                r["Vendor GSTIN"] = new_gstin
                                r["RCM"] = "YES" if is_rcm else "NO"
                                r["TDS Section (Old)"] = tds_info.get("old_section", "N/A")
                                r["New Section (393)"] = tds_info.get("new_section", "N/A")
                                r["TDS %"] = tds_info.get("rate", "0%")
                                r["TDS Deduction"] = tds_v
                                r["Net Payable"] = net_v
                                r["Status"] = audit.get("gst_summary", "")
                                r["ITC Status"] = "CLAIMABLE" if audit.get("itc_eligible") else "BLOCKED"
                                
                                import json
                                from sqlalchemy import text
                                try:
                                    engine = ComplianceEngine.get_db_engine()
                                    with engine.begin() as conn:
                                        conn.execute(text("UPDATE processed_invoices SET raw_json = :rj WHERE user_id = :u AND vendor_gstin = :v AND invoice_number = :inv"), 
                                                  {"rj": json.dumps(r), "u": st.session_state.user_name, "v": r['Vendor GSTIN'], "inv": r['Invoice #']})
                                except Exception as e:
                                    pass
                                
                                st.rerun()
            with tabs[2]: # TDS Summary
                tds_summary = []
                for r in all_results:
                    audit = r["_raw_data"].get("compliance_audit", {})
                    for tds in audit.get("tds_details", []):
                        if tds.get("amount", 0) > 0:
                            tds_summary.append({
                                "Vendor": r["Vendor"],
                                "Invoice #": r["Invoice #"],
                                "Section": tds.get("old_section", tds["section"]),
                                "Rate": tds.get("rate", "N/A"),
                                "Base Value": r["Base Value"],
                                "TDS Amount": float(tds["amount"]),
                                "Note": tds.get("note", ""),
                            })
                if tds_summary:
                    tds_df = pd.DataFrame(tds_summary)
                    st.metric("Total TDS Payable", f"₹{tds_df['TDS Amount'].sum():,.2f}")
                    st.dataframe(tds_df, use_container_width=True, hide_index=True)
                    csv = tds_df.to_csv(index=False).encode('utf-8')
                    st.download_button(label="📥 Download TDS Summary (CSV)", data=csv, file_name="tds_summary.csv", mime="text/csv")
                else:
                    st.info("No TDS deductions applicable.")
                
                # TDS Deadline Banner (Dynamic Date)
                total_tds = sum(float(r.get("TDS Deduction", 0) or 0) for r in st.session_state.get("processed_results", []))
                if total_tds > 0:
                    now = datetime.now()
                    # If today is <= 7th, deadline is 7th of this month. Otherwise, 7th of next month.
                    if now.day <= 7:
                        deadline_dt = now.replace(day=7)
                    else:
                        if now.month == 12:
                            deadline_dt = now.replace(year=now.year + 1, month=1, day=7)
                        else:
                            deadline_dt = now.replace(month=now.month + 1, day=7)
                    
                    deadline_str = deadline_dt.strftime("%d %B") # e.g. "07 May"
                    st.info(f"📅 **{deadline_str} deadline**: ₹{total_tds:,.0f} deducted, not yet deposited — due {deadline_str}.")
                    
            with tabs[3]: # GST Summary
                gst_detail = []
                total_gst_val = 0.0
                total_base_val = 0.0
                total_claimable = 0.0
                total_blocked = 0.0
                
                for r in all_results:
                    d = r["_raw_data"]
                    audit = d.get("compliance_audit", {})
                    gst_val = r["CGST"] + r["SGST"] + r["IGST"]
                    total_gst_val += gst_val
                    total_base_val += r["Base Value"]
                    
                    itc_status = r["ITC Status"]
                    if itc_status == "CLAIMABLE":
                        total_claimable += gst_val
                    else:
                        total_blocked += gst_val
                        
                    gst_detail.append({
                        "Vendor": r["Vendor"],
                        "Vendor GSTIN": r.get("Vendor GSTIN", "N/A"),
                        "Invoice Date": r.get("Invoice Date", "N/A"),
                        "Invoice #": r["Invoice #"],
                        "HSN/SAC": d.get("hsn_sac", "N/A"),
                        "Supply Type": audit.get("supply_type", "N/A"),
                        "Base Value": r["Base Value"],
                        "CGST": r["CGST"],
                        "SGST": r["SGST"],
                        "IGST": r["IGST"],
                        "Total GST": gst_val,
                        "ITC Status": itc_status,
                        "RCM": r["RCM"],
                        "Flags": " | ".join(audit.get("flags", [])) or "Compliant",
                    })
                if gst_detail:
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Base Value", f"₹{total_base_val:,.2f}")
                    col2.metric("Total GST Input", f"₹{total_gst_val:,.2f}")
                    col3.metric("Claimable ITC", f"₹{total_claimable:,.2f}")
                    col4.metric("Blocked ITC", f"₹{total_blocked:,.2f}")
                    
                    gst_df = pd.DataFrame(gst_detail)
                    st.dataframe(gst_df, use_container_width=True, hide_index=True)
                    csv = gst_df.to_csv(index=False).encode('utf-8')
                    st.download_button(label=":material/download: Download GST Summary (CSV)", data=csv, file_name="gst_summary.csv", mime="text/csv")
                else:
                    st.info("No GST details available.")
                
                if gst_detail:
                    st.markdown("---")
                    st.markdown("##### 🔍 GSTR-2B ITC Reconciliation")
                    st.info("Upload your GSTR-2B CSV to verify if vendors have filed their returns. ITC is at risk if invoices are missing.")
                    gstr2b_file = st.file_uploader("Upload GSTR-2B (CSV)", type="csv")
                    if gstr2b_file:
                        try:
                            gstr2b_df = pd.read_csv(gstr2b_file)
                            gstr2b_df.columns = [c.lower().strip() for c in gstr2b_df.columns]
                            gstin_col = next((c for c in gstr2b_df.columns if "gstin" in c), None)
                            inv_col = next((c for c in gstr2b_df.columns if "invoice" in c or "document details" in c or "inv no" in c or "number" in c), None)
                            
                            if gstin_col and inv_col:
                                gstr2b_df['gstin_clean'] = gstr2b_df[gstin_col].astype(str).str.strip().str.upper()
                                gstr2b_df['inv_clean'] = gstr2b_df[inv_col].astype(str).str.strip().str.upper()
                                
                                engine = ComplianceEngine.get_db_engine()
                                gstr2b_df[['gstin_clean', 'inv_clean']].to_sql('temp_gstr2b', engine, if_exists='replace', index=False)
                                
                                query = """
                                    SELECT g.vendor_gstin, g.invoice_number, g.total_gst, 
                                           CASE WHEN t.inv_clean IS NOT NULL THEN 'Filed' ELSE 'Not Filed (ITC at Risk)' END as filing_status
                                    FROM gst_ledger g
                                    LEFT JOIN temp_gstr2b t ON g.vendor_gstin = t.gstin_clean AND g.invoice_number = t.inv_clean
                                    WHERE g.total_gst > 0
                                """
                                recon_df = pd.read_sql(query, engine)
                                
                                risk_count = len(recon_df[recon_df['filing_status'] != 'Filed'])
                                risk_amt = recon_df[recon_df['filing_status'] != 'Filed']['total_gst'].sum()
                                
                                if risk_count > 0:
                                    st.warning(f"⚠️ {risk_count} invoice(s) from your ledger not found in GSTR-2B. ITC of ₹{risk_amt:,.2f} is at risk.")
                                else:
                                    st.success("✅ All ledger invoices successfully matched with GSTR-2B!")
                                    
                                st.dataframe(recon_df, use_container_width=True, hide_index=True)
                            else:
                                st.error("Could not find GSTIN or Invoice Number columns in the uploaded CSV.")
                        except Exception as e:
                            st.error(f"Error processing GSTR-2B: {e}")
                
            with tabs[4]: # Vendor Data
                all_vendors = SheetsConnector.get_vendor_master()
                gs_vendor_map = {str(v.get("GSTIN", "")).strip().upper(): v for v in all_vendors if v.get("GSTIN")}
                
                vendor_data_list = []
                seen_vendors = set()
                
                for r in all_results:
                    d = r["_raw_data"]
                    v_name = r.get("Vendor", "N/A")
                    gstin = str(r.get("Vendor GSTIN", "N/A")).strip().upper()
                    
                    key = gstin if gstin != "N/A" and gstin else v_name.upper()
                    if key in seen_vendors:
                        continue
                    seen_vendors.add(key)
                    
                    gs_data = gs_vendor_map.get(gstin, {})
                    pan_info = ComplianceEngine._extract_pan_info(gstin)
                    state_code = ComplianceEngine._get_state_from_gstin(gstin)
                    
                    vendor_data_list.append({
                        "Vendor Name": v_name,
                        "GSTIN": gstin,
                        "PAN": pan_info.get("pan", "N/A"),
                        "State Code": state_code,
                        "Address": gs_data.get("Address") or d.get("vendor_address", "N/A"),
                        "Email": gs_data.get("Email") or d.get("vendor_email", "N/A"),
                        "Phone": gs_data.get("Phone") or d.get("vendor_phone", "N/A"),
                        "Bank Name": gs_data.get("Bank Name") or d.get("bank_name", "N/A"),
                        "Account Number": gs_data.get("Account Number") or d.get("account_number", "N/A"),
                        "IFSC Code": gs_data.get("IFSC Code") or d.get("ifsc_code", "N/A"),
                        "Branch": gs_data.get("Branch") or d.get("bank_branch", "N/A"),
                        "MSME Registered": gs_data.get("MSME Registered") or d.get("msme_registered", "N/A"),
                        "Udyam Number": gs_data.get("Udyam Number") or d.get("udyam_number", "N/A"),
                        "Nature of Supply": gs_data.get("Nature of Supply") or d.get("invoice_nature", "N/A"),
                        "Default TDS Section": gs_data.get("Default TDS Section") or (d.get("compliance_audit", {}).get("tds_details", [{}])[0].get("section") if d.get("compliance_audit", {}).get("tds_details") else "N/A"),
                        "Total Invoices": gs_data.get("Total Invoices", "N/A"),
                        "Total Base Value": gs_data.get("Total Base Value", "N/A"),
                        "206AB Risk": gs_data.get("206AB Risk", "LOW"),
                        "Outstanding Flags": gs_data.get("Outstanding Flags", "None"),
                    })
                
                if vendor_data_list:
                    v_df = pd.DataFrame(vendor_data_list)
                    st.dataframe(v_df, use_container_width=True, hide_index=True)
                    csv = v_df.to_csv(index=False).encode('utf-8')
                    st.download_button(label=":material/download: Download Vendor Data (CSV)", data=csv, file_name="vendor_data.csv", mime="text/csv")
                else:
                    st.info("No vendor data available.")
                    
            with tabs[5]: # Journal Entry
                je_data = []
                for r in all_results:
                    je_data.append({"Date": r["Invoice Date"], "Account": f"Expense ({r['Vendor']})", "Debit": r["Base Value"], "Credit": 0})
                    gst_total = r.get("CGST", 0) + r.get("SGST", 0) + r.get("IGST", 0)
                    if gst_total > 0:
                        je_data.append({"Date": r["Invoice Date"], "Account": "GST ITC (Input)", "Debit": gst_total, "Credit": 0})
                    
                    if r["TDS Deduction"] > 0:
                        je_data.append({"Date": r["Invoice Date"], "Account": "TDS Payable", "Debit": 0, "Credit": r["TDS Deduction"]})
                    
                    if r["RCM"] == "YES":
                        if gst_total > 0:
                            je_data.append({"Date": r["Invoice Date"], "Account": "GST Payable (RCM)", "Debit": 0, "Credit": gst_total})
                        je_data.append({"Date": r["Invoice Date"], "Account": f"Vendor ({r['Vendor']})", "Debit": 0, "Credit": r["Base Value"] - r["TDS Deduction"]})
                    else:
                        je_data.append({"Date": r["Invoice Date"], "Account": f"Vendor ({r['Vendor']})", "Debit": 0, "Credit": r["Net Payable"]})
                je_df = pd.DataFrame(je_data)
                st.dataframe(je_df, use_container_width=True, hide_index=True)
                csv = je_df.to_csv(index=False).encode('utf-8')
                
                tally_xml = ["<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA><REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME></REQUESTDESC><REQUESTDATA>"]
                for r in all_results:
                    date_str = str(r['Invoice Date']).replace('-', '').replace('/', '').replace(' ', '')
                    if not date_str.isdigit():
                        date_str = datetime.now().strftime("%Y%m%d")
                    tally_xml.append(f'<TALLYMESSAGE xmlns:UDF="TallyUDF"><VOUCHER VCHTYPE="Journal" ACTION="Create" OBJVIEW="Accounting Voucher View">')
                    tally_xml.append(f'<DATE>{date_str}</DATE><NARRATION>Invoice {r["Invoice #"]} from {r["Vendor"]}</NARRATION><PARTYLEDGERNAME>{r["Vendor"]}</PARTYLEDGERNAME><VOUCHERTYPENAME>Journal</VOUCHERTYPENAME>')
                    tally_xml.append(f'<ALLLEDGERENTRIES.LIST><LEDGERNAME>Expense ({r["Vendor"]})</LEDGERNAME><ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE><AMOUNT>-{r["Base Value"]}</AMOUNT></ALLLEDGERENTRIES.LIST>')
                    gst_total = r.get("CGST", 0) + r.get("SGST", 0) + r.get("IGST", 0)
                    if gst_total > 0:
                        tally_xml.append(f'<ALLLEDGERENTRIES.LIST><LEDGERNAME>GST ITC (Input)</LEDGERNAME><ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE><AMOUNT>-{gst_total}</AMOUNT></ALLLEDGERENTRIES.LIST>')
                    if r["TDS Deduction"] > 0:
                        tally_xml.append(f'<ALLLEDGERENTRIES.LIST><LEDGERNAME>TDS Payable</LEDGERNAME><ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE><AMOUNT>{r["TDS Deduction"]}</AMOUNT></ALLLEDGERENTRIES.LIST>')
                    if r["RCM"] == "YES":
                        if gst_total > 0:
                            tally_xml.append(f'<ALLLEDGERENTRIES.LIST><LEDGERNAME>GST Payable (RCM)</LEDGERNAME><ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE><AMOUNT>{gst_total}</AMOUNT></ALLLEDGERENTRIES.LIST>')
                        tally_xml.append(f'<ALLLEDGERENTRIES.LIST><LEDGERNAME>Vendor ({r["Vendor"]})</LEDGERNAME><ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE><AMOUNT>{r["Base Value"] - r["TDS Deduction"]}</AMOUNT></ALLLEDGERENTRIES.LIST>')
                    else:
                        tally_xml.append(f'<ALLLEDGERENTRIES.LIST><LEDGERNAME>Vendor ({r["Vendor"]})</LEDGERNAME><ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE><AMOUNT>{r["Net Payable"]}</AMOUNT></ALLLEDGERENTRIES.LIST>')
                    tally_xml.append('</VOUCHER></TALLYMESSAGE>')
                tally_xml.append("</REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>")
                tally_xml_str = "\\n".join(tally_xml).encode('utf-8')
                
                col1, col2 = st.columns(2)
                col1.download_button(label=":material/table: Download Journal Entries (Excel/CSV format)", data=csv, file_name="journal_entries.csv", mime="text/csv", use_container_width=True)
                col2.download_button(label=":material/code: Download Tally XML (<TALLYMESSAGE>)", data=tally_xml_str, file_name="tally_journal.xml", mime="application/xml", use_container_width=True)
                
            with tabs[6]: # Research
                for r in all_results:
                    d = r["_raw_data"]
                    audit = d.get("compliance_audit", {})
                    tds_info = audit.get("tds_details", [{}])[0] if audit.get("tds_details") else {}
                    with st.expander(f":material/search: {r['Vendor']} - {r['Invoice #']} (Score: {ComplianceEngine.get_compliance_score(audit, d)[0]}/100)", expanded=True):
                        findings = ComplianceEngine.compliance_reasoning_engine(d, audit, tds_info)
                        if not findings:
                            st.success(":material/check_circle: Fully Compliant. No compliance warnings or issues detected.")
                        else:
                            UIEngine.render_findings(findings)
                        
                        # Add a raw data preview for more intelligence
                        with st.popover("View Extracted JSON Intelligence"):
                            UIEngine.render_json_intelligence(d)
                            




    # ══════════════════════════════════════════════════════════════
    # PAGE: SCAN INVOICE
    # ══════════════════════════════════════════════════════════════
    elif active_page == "Scan Invoice":
        UIEngine.render_page_header(":material/document_scanner: Scan Invoice", "DATA EXTRACTION")

        if not api_key:
            st.error("FATAL: SYSTEM API KEY NOT FOUND IN SECRETS.")
            return

        uploaded_files = st.file_uploader(
            "Drop your invoices",
            type=["pdf", "png", "jpg", "jpeg"],
            accept_multiple_files=True
        )

        if st.session_state.processed_results:
            st.markdown("---")
            st.markdown("##### :material/folder_open: Currently in Dashboard Memory")
            for r in st.session_state.processed_results:
                st.markdown(f"- **{r['Vendor']}** (Invoice #: {r['Invoice #']} | ₹{r['Base Value']:,.2f})")
            
            if st.button(":material/delete: Clear Dashboard & Start Fresh", use_container_width=True):
                clear_session_invoices(st.session_state.session_start, st.session_state.user_name)
                st.session_state.processed_results = []
                st.session_state.vendor_totals = {}
                st.session_state.chat_history  = []
                st.session_state.pop('vendor_master_cache', None)
                st.rerun()

        if uploaded_files:
            col1, col2 = st.columns(2)
            proceed = col1.button(":material/rocket_launch: PROCEED", use_container_width=True, type="primary")
            stop    = col2.button(":material/stop_circle: STOP ANALYSIS", use_container_width=True)

            if stop:
                clear_session_invoices(st.session_state.session_start, st.session_state.user_name)
                st.session_state.processed_results = []
                st.session_state.vendor_totals = {}
                st.session_state.chat_history  = []
                st.session_state.pop('vendor_master_cache', None)
                st.rerun()

            if proceed:
                # Removed wiping logic to allow incremental scanning!
                # We append to processed_results instead of overwriting it.
                
                with st.status("EXECUTING FORENSIC AUDIT...", expanded=True) as status:
                    # Cache vendor master once per scan session to save quota
                    st.session_state.vendor_master_cache = SheetsConnector.get_vendor_master()
                    
                    for idx, file in enumerate(uploaded_files):
                        st.write(f":material/search: Analyzing: **{file.name}**...")
                        file_bytes = file.read()

                        data, msg, token_info = ComplianceEngine.extract_with_groq(file_bytes, file.name, api_key)
                        
                        if token_info:
                            SheetsConnector.log_token_usage(
                                st.session_state.user_name, file.name,
                                token_info.get("prompt", 0), token_info.get("completion", 0)
                            )
                            st.session_state.session_tokens["prompt"]     += token_info.get("prompt", 0)
                            st.session_state.session_tokens["completion"] += token_info.get("completion", 0)

                        if data:
                            gstin = data.get("vendor_gstin", "N/A")
                            vendor_master = st.session_state.vendor_master_cache
                            manual_206ab_flag = False  # Default to normal rate
                            
                            # Dynamic FY for aggregate query
                            now = datetime.now()
                            curr_fy = f"{now.year-1}-{str(now.year)[2:]}" if now.month <= 3 else f"{now.year}-{str(now.year+1)[2:]}"
                            
                            # 194C Aggregate from SQLite + Session
                            session_aggregate = sum(r["Base Value"] for r in st.session_state.processed_results if r["Vendor GSTIN"] == gstin and str(r.get("TDS Section (Old)", "")).startswith("194C"))
                            aggregate_194c = get_194c_aggregate(gstin, fy=curr_fy, user_id=st.session_state.user_name) + session_aggregate
                            
                            for v in vendor_master:
                                if str(v.get("GSTIN")).strip().upper() == str(gstin).strip().upper():
                                    if str(v.get("206AB Risk", "")).strip().upper() == "HIGH":
                                        manual_206ab_flag = True
                                    break
    
                            audit = ComplianceEngine.perform_compliance_audit(data, manual_206ab_flag, aggregate_194c, st.session_state.user_name)
                            data["compliance_audit"] = audit
                            tds_info = audit.get("tds_details", [{}])[0] if audit.get("tds_details") else {}
    
                            base_v  = float(data.get("base_value", 0.0) or 0.0)
                            cgst_v  = float(data.get("cgst_amount", 0.0) or 0.0)
                            sgst_v  = float(data.get("sgst_amount", 0.0) or 0.0)
                            igst_v  = float(data.get("igst_amount", 0.0) or 0.0)
                            tds_v   = float(tds_info.get("amount") or 0.0)
                            
                            is_rcm  = (audit.get("rcm_alert") or data.get("rcm_applicable") == "yes")
                            if is_rcm:
                                net_v = base_v - tds_v
                            else:
                                net_v = (base_v + cgst_v + sgst_v + igst_v) - tds_v
    
                            res = {
                                "Sr. No.":           idx + len(st.session_state.processed_results) + 1,
                                "Vendor":            data.get("vendor", "N/A"),
                                "Vendor GSTIN":      data.get("vendor_gstin", "N/A"),
                                "Invoice #":         data.get("invoice_number", "N/A"),
                                "Invoice Date":      data.get("invoice_date", "N/A"),
                                "Nature":            data.get("invoice_nature", "N/A"),
                                "Base Value":        base_v,
                                "CGST":              cgst_v,
                                "SGST":              sgst_v,
                                "IGST":              igst_v,
                                "Supply Type":       audit.get("supply_type", "N/A"),
                                "ITC Status":        "CLAIMABLE" if audit.get("itc_eligible") else "BLOCKED",
                                "RCM":               "YES" if (audit.get("rcm_alert") or data.get("rcm_applicable") == "yes") else "NO",
                                "TDS Section (Old)": tds_info.get("old_section") or tds_info.get("section") or "N/A",
                                "New Section (393)": tds_info.get("new_section", "N/A"),
                                "TDS %":             tds_info.get("base_rate") or tds_info.get("rate") or "0%",
                                "TDS Deduction":     tds_v,
                                "Net Payable":       net_v,
                                "_raw_data":         data
                            }
                            st.session_state.processed_results.append(res)
                            
                            # Update Vendor Master Intelligence in Google Sheets
                            try:
                                SheetsConnector.upsert_vendor(data, audit)
                            except:
                                pass
    
                            st.success(f"✅ Processed successfully: {file.name}")
                        else:
                            st.error(f"Error processing {file.name}: {msg}")
                            
                st.info("Scan complete! Head over to the Dashboard to view the results.")



    # ══════════════════════════════════════════════════════════════
    # PAGE: RESEARCH
    # ══════════════════════════════════════════════════════════════
    elif active_page == "Research":
        UIEngine.render_page_header(":material/search: Research Hub", "GLOBAL INTELLIGENCE")
        
        st.markdown("##### Forensic Search & Tax Intelligence")
        st.info("Use this hub to research specific tax sections, GST rules, or perform global forensic lookups.")
        
        st.markdown("---")
        st.markdown("##### ⚡ Quick Research Links")
        cols = st.columns(3)
        with cols[0]:
            st.markdown("###### TDS Sections")
            if st.button("Sec 194C (Contracts)", use_container_width=True):
                st.markdown("[Open Search](https://www.google.com/search?q=Section+194C+income+tax+India)", unsafe_allow_html=True)
            if st.button("Sec 194J (Professional)", use_container_width=True):
                st.markdown("[Open Search](https://www.google.com/search?q=Section+194J+income+tax+India)", unsafe_allow_html=True)
        with cols[1]:
            st.markdown("###### GST Rules")
            if st.button("ITC Rule 37", use_container_width=True):
                st.markdown("[Open Search](https://www.google.com/search?q=GST+Rule+37+reversal)", unsafe_allow_html=True)
            if st.button("Section 16(4) Deadlines", use_container_width=True):
                st.markdown("[Open Search](https://www.google.com/search?q=GST+Section+16(4)+deadline)", unsafe_allow_html=True)
        with cols[2]:
            st.markdown("###### Vendor Checks")
            if st.button("GSTIN Search", use_container_width=True):
                st.markdown("[Open Search](https://www.google.com/search?q=verify+GSTIN+number+online)", unsafe_allow_html=True)
            if st.button("PAN Verification", use_container_width=True):
                st.markdown("[Open Search](https://www.google.com/search?q=verify+PAN+card+details+income+tax)", unsafe_allow_html=True)

        if all_results:
            st.markdown("---")
            st.markdown("##### 🔍 Contextual Intelligence (from Active Session)")
            for r in all_results:
                with st.expander(f"{r['Vendor']} - {r['Invoice #']}"):
                    d = r["_raw_data"]
                    audit = d.get("compliance_audit", {})
                    tds_info = audit.get("tds_details", [{}])[0] if audit.get("tds_details") else {}
                    
                    findings = ComplianceEngine.compliance_reasoning_engine(d, audit, tds_info)
                    if not findings:
                        st.success(":material/check_circle: Fully Compliant. No compliance warnings or issues detected.")
                    else:
                        UIEngine.render_findings(findings)
                    
                    # Add a raw data preview for more intelligence
                    with st.popover("View Extracted JSON Intelligence"):
                        UIEngine.render_json_intelligence(d)



    


if __name__ == "__main__":
    main()
