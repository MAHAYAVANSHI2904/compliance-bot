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
    
    # Use empty space to center vertically
    st.markdown("<div style='margin-top: 15vh;'></div>", unsafe_allow_html=True)
    
    # Center horizontally
    _, col, _ = st.columns([1, 1.2, 1])
    
    with col:
        st.markdown("""
        <div style='text-align:center; margin-bottom: 32px;'>
            <div style='width:64px;height:64px;border-radius:18px;background:linear-gradient(135deg, #4f6ef7, #818cf8); display:flex;align-items:center;justify-content:center; font-size:32px;margin:0 auto 24px; box-shadow: 0 10px 25px -5px rgba(79, 110, 247, 0.3);'>⚡</div>
            <div style='font-size:28px;font-weight:800;color:#ffffff; margin-bottom:8px;letter-spacing:-0.5px;'>Invoice Compliance Hub</div>
            <div style='font-size:15px;color:#9ca3af;'>Enterprise Authentication</div>
        </div>
        """, unsafe_allow_html=True)
        
        user_name = st.text_input("Your name", placeholder="Enter your full name", label_visibility="collapsed")
        
        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
        
        if st.button("Authenticate & Enter System →", use_container_width=True, type="primary", key="login_btn"):
            if user_name.strip():
                st.session_state.logged_in = True
                st.session_state.user_name = user_name.strip()
                st.session_state.session_start = datetime.utcnow()
                SheetsConnector.log_login(user_name.strip())
                st.rerun()
            else:
                st.error("Please enter your name to continue.")

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
    if 'session_start' not in st.session_state:
        st.session_state.session_start = datetime.utcnow()

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
                st.markdown("##### Consolidated Invoice Dataset")
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
                        deadline_dt = now
                    else:
                        if now.month == 12:
                            deadline_dt = now.replace(year=now.year + 1, month=1, day=7)
                        else:
                            deadline_dt = now.replace(month=now.month + 1, day=7)
                    
                    deadline_str = deadline_dt.strftime("%#d %B") # e.g. "7 May"
                    st.info(f"📅 **{deadline_str} deadline**: ₹{total_tds:,.0f} TDS payable to govt based on current session.")
                    
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
                        "Default TDS Section": gs_data.get("Default TDS Section") or (audit.get("tds_details", [{}])[0].get("section") if audit.get("tds_details") else "N/A"),
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
                st.download_button(label=":material/download: Download Journal Entries (CSV)", data=csv, file_name="journal_entries.csv", mime="text/csv")
                
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
                            
                        UIEngine.render_smart_search(audit, tds_info, d)

        UIEngine.render_google_footer()

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
                clear_session_invoices(st.session_state.session_start)
                st.session_state.processed_results = []
                st.session_state.vendor_totals = {}
                st.session_state.chat_history  = []
                st.rerun()

        if uploaded_files:
            col1, col2 = st.columns(2)
            proceed = col1.button(":material/rocket_launch: PROCEED", use_container_width=True, type="primary")
            stop    = col2.button(":material/stop_circle: STOP ANALYSIS", use_container_width=True)

            if stop:
                clear_session_invoices(st.session_state.session_start)
                st.session_state.processed_results = []
                st.session_state.vendor_totals = {}
                st.session_state.chat_history  = []
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
                            aggregate_194c = get_194c_aggregate(gstin, fy=curr_fy) + session_aggregate
                            
                            for v in vendor_master:
                                if str(v.get("GSTIN")).strip().upper() == str(gstin).strip().upper():
                                    if str(v.get("206AB Risk", "")).strip().upper() == "HIGH":
                                        manual_206ab_flag = True
                                    break
    
                            audit = ComplianceEngine.perform_compliance_audit(data, manual_206ab_flag, aggregate_194c)
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

        UIEngine.render_google_footer()

if __name__ == "__main__":
    main()
