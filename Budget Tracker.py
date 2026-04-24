import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

try:
    from fpdf import FPDF
    HAS_PDF = True
except: HAS_PDF = False

st.set_page_config(page_title="Wealth Wizard AI | Elite", page_icon="💎", layout="wide")
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;800;900&display=swap');
*{font-family:'Outfit',sans-serif!important}
.stApp{background:#020108;color:#fff}
.main-title{font-size:75px;font-weight:900;text-align:center;margin-bottom:0px;letter-spacing:-2px}
.sub-title{font-size:22px;color:#666;text-align:center;margin-bottom:50px}
.card{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);border-radius:30px;padding:45px;margin-bottom:30px;box-shadow:0 15px 50px rgba(0,0,0,0.5)}
.mbox{background:linear-gradient(145deg, rgba(255,255,255,0.06), rgba(255,255,255,0.01));border:1px solid rgba(255,255,255,.1);border-radius:24px;padding:40px;text-align:center;transition:0.4s}
.mbox:hover{border-color:#00FFA3;transform:translateY(-10px);box-shadow:0 0 40px rgba(0,255,163,0.15)}
.ai-box{background:linear-gradient(135deg,rgba(0,255,163,.1),rgba(0,120,255,.1));border:1px solid rgba(0,255,163,.4);border-radius:30px;padding:50px;margin-top:30px}
.pill{background:#00FFA3;color:#000;border-radius:8px;padding:6px 16px;font-size:12px;font-weight:900;letter-spacing:2px;text-transform:uppercase}
.stButton>button{background:#00FFA3;color:#000;border:none;border-radius:18px;font-weight:900;padding:22px;width:100%;transition:.3s;font-size:18px;letter-spacing:1.5px;box-shadow:0 10px 30px rgba(0,255,163,0.2)}
.stButton>button:hover{background:#fff;transform:scale(1.03);box-shadow:0 0 50px rgba(0,255,163,0.4)}
.step-row{display:flex;gap:15px;margin-bottom:50px}
.step{flex:1;text-align:center;padding:18px 0;border-radius:15px;background:#0d0d0d;border:1px solid #1a1a1a;font-size:14px;font-weight:800;color:#555}
.step.on{background:rgba(0,255,163,.12);border-color:#00FFA3;color:#00FFA3;box-shadow:0 0 25px rgba(0,255,163,0.15)}
.balance{background:rgba(0,255,163,.1);border:1px solid rgba(0,255,163,.4);border-radius:20px;padding:25px 40px;text-align:right;margin-top:20px;font-weight:900;color:#00FFA3;font-size:24px;box-shadow:inset 0 0 20px rgba(0,255,163,0.05)}
.section-title{font-size:42px;font-weight:900;margin-bottom:30px;color:#fff}
.data-row{display:flex;justify-content:space-between;padding:15px 0;border-bottom:1px solid rgba(255,255,255,0.05)}
</style>""", unsafe_allow_html=True)

TIERS = {
    "Tier 1 – Metro (Mumbai, Delhi, Bangalore, Chennai, Hyderabad)": [60,20,20],
    "Tier 2 – Growing (Pune, Jaipur, Lucknow, Surat, Chandigarh)":  [50,20,30],
    "Tier 3 – Emerging (Smaller cities & towns)":                    [40,20,40],
}
MFS = [
    ("UTI Nifty 50 Index Fund","Index Fund","Low Risk","Tracks top 50 companies. Passive growth, 12-14% avg returns."),
    ("Parag Parikh Flexi Cap","Flexi Cap","Moderate Risk","Diversified across India & USA. Best long-term alpha."),
    ("Mirae Asset Large Cap","Large Cap","Low-Med Risk","Invests in stable market leaders. Perfect for 5yr horizon."),
    ("Quant Small Cap Fund","Small Cap","High Risk","High growth potential for excess surplus. Volatile but high alpha."),
    ("ICICI Pru Balanced Adv","Hybrid Fund","Medium Risk","Auto-balances between Equity and Debt. Stable returns."),
]

if "step" not in st.session_state: st.session_state.step = 1
DEFS = dict(name="",income=0,tier="",ratio=[50,20,30],rent=0,bills=0,groceries=0,commute=0,sip=0,bank_save=0,emergency=0,dining=0,shopping=0,subs=0,ess=0,save=0,life=0,surplus=0)
if "data" not in st.session_state: st.session_state.data = DEFS.copy()
D = st.session_state.data
for k,v in DEFS.items():
    if k not in D: D[k] = v

def nav(s): st.session_state.step = s; st.rerun()

LABELS = ["1 · IDENTITY","2 · INCOME","3 · EXPENSES","4 · DASHBOARD"]
st.markdown('<div class="step-row">' + "".join(f'<div class="step {"on" if i+1==st.session_state.step else ""}">{l}</div>' for i,l in enumerate(LABELS)) + '</div>', unsafe_allow_html=True)

# --- WINDOW 1 ---
if st.session_state.step == 1:
    _,c,_ = st.columns([1,1.8,1])
    with c:
        st.markdown("<div class='main-title'>💎 WEALTH <span style='color:#00FFA3'>WIZARD</span></div>", unsafe_allow_html=True)
        st.markdown("<div class='sub-title'>Advanced AI Financial Orchestration Engine</div>", unsafe_allow_html=True)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        name = st.text_input("YOUR FULL NAME", value=D.get("name",""), placeholder="Enter credentials to begin...")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("INITIALIZE CORE SYSTEM →"):
            if name.strip(): D["name"] = name.strip(); nav(2)
            else: st.warning("Identity verification failed. Enter name.")
        st.markdown('</div>', unsafe_allow_html=True)

# --- WINDOW 2 ---
elif st.session_state.step == 2:
    st.markdown(f"<div class='section-title'>📍 PROFILE: <span style='color:#00FFA3'>{D.get('name','').upper()}</span></div>", unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    inc  = st.number_input("MONTHLY NET TAKE-HOME (₹)", min_value=0, value=D.get("income", 50000), step=5000)
    tier = st.selectbox("SELECT RESIDENT CITY CLASSIFICATION", list(TIERS.keys()))
    ratio = TIERS[tier]
    st.markdown(f"""<div class='ai-box'><span class='pill'>AI ALLOCATION PROTOCOL</span><br><br>
    <div style='font-size:26px; font-weight:800'>AI has deployed the <span style='color:#00FFA3'>{ratio[0]}/{ratio[1]}/{ratio[2]}</span> rule.</div><br>
    🏠 Essentials: <b>₹{inc*ratio[0]//100:,}</b> &nbsp;|&nbsp; 💰 Wealth: <b>₹{inc*ratio[1]//100:,}</b> &nbsp;|&nbsp; 🎭 Lifestyle: <b>₹{inc*ratio[2]//100:,}</b></div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    c1,c2 = st.columns(2)
    with c1:
        if st.button("← BACK"): nav(1)
    with c2:
        if st.button("PROCEED TO ALLOCATION →"):
            D.update(income=inc, tier=tier, ratio=ratio); nav(3)

# --- WINDOW 3 ---
elif st.session_state.step == 3:
    inc = D["income"]; r = D["ratio"]
    st.markdown("<div class='section-title'>💸 GRANULAR <span style='color:#00FFA3'>ALLOCATION</span></div>", unsafe_allow_html=True)
    
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🏠 1. MANDATORY ESSENTIALS")
    st.markdown(f"<span style='color:#00FFA3;font-size:16px;font-weight:900'>AI TARGET: ₹{inc*r[0]//100:,}</span>", unsafe_allow_html=True)
    e1,e2 = st.columns(2)
    with e1:
        rent = st.number_input("Rent / EMI / Maintenance", value=D.get("rent", int(inc*.25)), min_value=0, step=500)
        groc = st.number_input("Groceries / Daily Supplies", value=D.get("groceries", int(inc*.08)), min_value=0, step=500)
    with e2:
        bills = st.number_input("Electricity / Water / Internet", value=D.get("bills", 2000), min_value=0, step=100)
        comm = st.number_input("Commute / Fuel / Insurance", value=D.get("commute", 2000), min_value=0, step=100)
    ess_tot = rent + bills + groc + comm
    st.markdown(f'<div class="balance">💰 REMAINING LIQUIDITY: ₹{inc-ess_tot:,}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("💰 2. STRATEGIC WEALTH & SAVINGS")
    st.markdown(f"<span style='color:#00FFA3;font-size:16px;font-weight:900'>AI TARGET: ₹{inc*r[1]//100:,}</span>", unsafe_allow_html=True)
    s1,s2,s3 = st.columns(3)
    with s1: sip = st.number_input("Equity SIPs / MF", value=D.get("sip", int(inc*.1)), min_value=0, step=500)
    with s2: bsave = st.number_input("Debt / PPF / Bank", value=D.get("bank_save", 0), min_value=0, step=500)
    with s3: emerg = st.number_input("Emergency Liquid Buffer", value=D.get("emergency", 0), min_value=0, step=500)
    save_tot = sip + bsave + emerg
    st.markdown(f'<div class="balance">💰 REMAINING LIQUIDITY: ₹{inc-ess_tot-save_tot:,}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🎭 3. LIFESTYLE & DISCRETIONARY")
    st.markdown(f"<span style='color:#00FFA3;font-size:16px;font-weight:900'>AI TARGET: ₹{inc*r[2]//100:,}</span>", unsafe_allow_html=True)
    l1,l2,l3 = st.columns(3)
    with l1: dining = st.number_input("Dining / Cloud Kitchens", value=D.get("dining", 2000), min_value=0, step=200)
    with l2: shopping = st.number_input("Apparel / Gadgets", value=D.get("shopping", 2000), min_value=0, step=200)
    with l3: subs = st.number_input("OTT / SaaS / Subscriptions", value=D.get("subs", 500), min_value=0, step=50)
    life_tot = dining + shopping + subs
    surplus = inc - ess_tot - save_tot - life_tot
    st.markdown(f'<div class="balance" style="color:{"#00FFA3" if surplus>=0 else "#FF4B4B"}; border-color:{"#00FFA3" if surplus>=0 else "#FF4B4B"}">🏁 NET SURPLUS (REINVESTMENT): ₹{surplus:,}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    c1,c2 = st.columns(2)
    with c1:
        if st.button("← BACK"): nav(2)
    with c2:
        if st.button("GENERATE ELITE DASHBOARD →"):
            D.update(rent=rent, bills=bills, groceries=groc, commute=comm, sip=sip, bank_save=bsave, emergency=emerg, dining=dining, shopping=shopping, subs=subs, ess=ess_tot, save=save_tot, life=life_tot, surplus=surplus)
            nav(4)

# --- WINDOW 4 ---
elif st.session_state.step == 4:
    inc=D["income"]; r=D["ratio"]; ess=D["ess"]; save=D["save"]; life=D["life"]; surplus=D["surplus"]
    score = max(0, min(100, int(100 - abs(ess/inc*100 - r[0]) - abs(save/inc*100 - r[1]))))
    st.markdown(f"<div class='main-title' style='text-align:left; font-size:70px;'>🚀 <span style='color:#00FFA3'>ELITE</span> PULSE DASHBOARD</div>", unsafe_allow_html=True)

    # MASSIVE KPI ROW
    st.markdown("<br>", unsafe_allow_html=True)
    m_cols = st.columns(5)
    metrics = [("MONTHLY INCOME",inc,"#fff"),("TOTAL ESSENTIALS",ess,"#fff"),("STRATEGIC WEALTH",save,"#00FFA3"),("LIFESTYLE SPEND",life,"#fff"),("NET SURPLUS",surplus,"#00FFA3" if surplus>=0 else "#FF4B4B")]
    for i, (lbl, val, clr) in enumerate(metrics):
        m_cols[i].markdown(f'<div class="mbox"><div style="font-size:14px;color:#666;letter-spacing:2px;margin-bottom:15px">{lbl}</div><div style="font-size:42px;font-weight:900;color:{clr}">₹{val:,}</div></div>', unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # LARGE CHARTS
    v1, v2 = st.columns(2)
    with v1:
        st.markdown("<div class='card'><h2>⚖️ ALLOCATION RATIO</h2>", unsafe_allow_html=True)
        fig1 = go.Figure(go.Pie(labels=["Essentials","Savings","Lifestyle","Surplus"], values=[ess, save, life, max(surplus,0)], hole=0.75, marker_colors=["#FFFFFF","#00FFA3","#151515","#00D1FF"]))
        fig1.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color='white', showlegend=False, height=500, margin=dict(t=30,b=30,l=30,r=30),
                           annotations=[dict(text=f"<span style='font-size:55px; font-weight:900; color:#00FFA3'>{score}%</span><br><span style='font-size:16px; color:#555'>HEALTH</span>", x=0.5, y=0.5, showarrow=False)])
        st.plotly_chart(fig1, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
    with v2:
        st.markdown("<div class='card'><h2>📈 20-YEAR WEALTH FORECAST</h2>", unsafe_allow_html=True)
        years = list(range(0, 21)); growth = 0.12 / 12
        forecast = [int(save * (((1+growth)**(y*12)-1)/growth)) for y in years]
        fig2 = go.Figure(go.Scatter(x=years, y=forecast, mode='lines+markers', line=dict(color='#00FFA3', width=5), fill='tozeroy', fillcolor='rgba(0,255,163,0.1)'))
        fig2.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white', height=500, margin=dict(t=30,b=30,l=30,r=30), xaxis=dict(title="Years", showgrid=False), yaxis=dict(title="Wealth (₹)", showgrid=False))
        st.plotly_chart(fig2, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # BIG AI AUDIT SECTION
    st.markdown('<div class="ai-box">', unsafe_allow_html=True)
    st.markdown('<h2 style="margin-top:0; font-size:36px;"><span class="pill" style="font-size:16px; padding:10px 20px">AI STRATEGIC AUDIT</span></h2>', unsafe_allow_html=True)
    if surplus < 0:
        advice = f"""### ⚠️ CRITICAL DEFICIT: -₹{abs(surplus):,} detected.
**AI OBSERVATIONS:**
- **Rent Overload:** Your rent of ₹{D['rent']:,} is {int(D['rent']/inc*100)}% of income. Target for {D['tier'].split('–')[0]} is 30%.
- **Lifestyle Leakage:** Spending ₹{life:,} on lifestyle while in deficit is mathematically unsustainable.
- **IMMEDIATE ACTION:** Cut Dining (₹{D['dining']:,}) and Shopping (₹{D['shopping']:,}) to recover ₹{D['dining']+D['shopping']:,} monthly.
- **SURVIVAL RULE:** Pause all SIPs (₹{D['sip']:,}) immediately until surplus returns to positive."""
    else:
        advice = f"""### ✅ ELITE FINANCIAL HEALTH: +₹{surplus:,} Surplus.
**AI OBSERVATIONS:**
- **Wealth Engine:** Investing ₹{save:,}/mo at 12% CAGR will generate **₹{forecast[-1]:,}** by year 20.
- **Allocation Efficiency:** Essentials at {int(ess/inc*100)}% is within the {r[0]}% AI safety limit.
- **SURPLUS DEPLOYMENT:** Your net surplus of ₹{surplus:,} should be moved into a **Small Cap Fund** for alpha growth.
- **STABILITY:** Ensure your Emergency Fund (₹{D['emergency']:,}) covers at least 6 months of essentials (₹{ess*6:,})."""
    st.write(advice); st.markdown('</div>', unsafe_allow_html=True)

    # COMPREHENSIVE DATA BREAKDOWN
    st.markdown("<br><br><div class='card'><h2 style='font-size:36px'>📊 FULL FINANCIAL BREAKDOWN</h2>", unsafe_allow_html=True)
    b_cols = st.columns(2)
    rows = [("Rent/EMI",D['rent']),("Bills",D['bills']),("Groceries",D['groceries']),("Commute",D['commute']),("SIPs",D['sip']),("Savings",D['bank_save']),("Emergency",D['emergency']),("Dining",D['dining']),("Shopping",D['shopping']),("Subs",D['subs'])]
    for i, (l, v) in enumerate(rows):
        target_col = b_cols[0] if i < 5 else b_cols[1]
        target_col.markdown(f"<div class='data-row'><span>{l}</span><span style='font-weight:900; color:#00FFA3'>₹{v:,}</span></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # ELITE MF ENGINE
    st.markdown("<br><br><div class='card'><h2 style='font-size:36px'>🧬 AI MUTUAL FUND ENGINE</h2><p style='color:#666'>Personalized selection for your income tier</p>", unsafe_allow_html=True)
    mf_cols = st.columns(5)
    risk_clr = {"Low Risk":"#00FFA3","Low-Med Risk":"#00D1FF","Medium Risk":"#f59e0b","Moderate Risk":"#f59e0b","High Risk":"#FF4B4B"}
    for i, (n,t,r_risk,w) in enumerate(MFS):
        mf_cols[i].markdown(f"""<div style='background:rgba(255,255,255,0.03);border:1px solid #333;border-radius:24px;padding:30px;height:100%'>
        <div style='color:{risk_clr.get(r_risk,"#fff")};font-size:12px;font-weight:900;letter-spacing:1px'>● {t}</div>
        <div style='font-weight:900;font-size:20px;margin:15px 0; color:#00FFA3'>{n}</div>
        <div style='font-size:13px;color:#888;line-height:1.5'>{w}</div></div>""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # BIG ELITE PDF REPORT
    if HAS_PDF:
        def _elite_pdf():
            pdf = FPDF(); pdf.add_page(); pdf.set_fill_color(3,3,10); pdf.rect(0,0,210,297,'F')
            # HEADER
            pdf.set_font("Arial",'B',35); pdf.set_text_color(0,255,163); pdf.cell(0,40,"WEALTH WIZARD ELITE",0,1,'C')
            pdf.set_font("Arial",'',14); pdf.set_text_color(150,150,150); pdf.cell(0,10,f"STRATEGIC FINANCIAL DOSSIER: {D['name'].upper()}",0,1,'C')
            pdf.ln(20)
            # KPI TABLE
            pdf.set_fill_color(20,20,40); pdf.set_text_color(255,255,255); pdf.set_font("Arial",'B',14)
            pdf.cell(100,12,"  FINANCIAL METRIC",1,0,'L',True); pdf.cell(90,12,"  VALUATION",1,1,'L',True)
            pdf.set_font("Arial",'',12)
            for l,v in [("Monthly Income",f"Rs.{inc:,}"),("Total Essentials",f"Rs.{ess:,}"),("Strategic Wealth",f"Rs.{save:,}"),("Lifestyle Spend",f"Rs.{life:,}"),("Final Net Surplus",f"Rs.{surplus:,}"),("Health Score",f"{score}%")]:
                pdf.cell(100,12,f"  {l}",1,0); pdf.cell(90,12,f"  {v}",1,1)
            pdf.ln(15)
            # AI AUDIT SECTION
            pdf.set_font("Arial",'B',18); pdf.set_text_color(0,255,163); pdf.cell(0,15,"AI STRATEGIC AUDIT",0,1)
            pdf.set_fill_color(10,10,25); pdf.rect(10, pdf.get_y(), 190, 60, 'F')
            pdf.set_font("Arial",'',11); pdf.set_text_color(220,220,220)
            clean_adv = advice.replace("**","").replace("###","").replace("✅","OK").replace("⚠️","WARN").replace("🚨","!!").replace("₹","Rs.").encode('ascii','ignore').decode('ascii')
            pdf.multi_cell(0,10,f"  {clean_adv}")
            pdf.ln(10)
            # ITEM BREAKDOWN
            pdf.set_font("Arial",'B',18); pdf.set_text_color(0,255,163); pdf.cell(0,15,"GRANULAR EXPENDITURE LOG",0,1)
            pdf.set_font("Arial",'',11); pdf.set_text_color(200,200,200)
            for l,v in [("Rent/EMI",D['rent']),("Bills",D['bills']),("Groceries",D['groceries']),("Commute",D['commute']),("SIPs",D['sip']),("Savings",D['bank_save']),("Dining",D['dining']),("Shopping",D['shopping'])]:
                pdf.cell(100,10,f"  - {l}:",0,0); pdf.cell(90,10,f"Rs.{v:,}",0,1)
            pdf.ln(10)
            # WEALTH FORECAST
            pdf.add_page(); pdf.set_fill_color(3,3,10); pdf.rect(0,0,210,297,'F')
            pdf.set_font("Arial",'B',18); pdf.set_text_color(0,255,163); pdf.cell(0,15,"20-YEAR WEALTH PROJECTION",0,1)
            pdf.set_font("Arial",'',11); pdf.set_text_color(220,220,220)
            pdf.multi_cell(0,10,f"By maintaining a strategic monthly investment of Rs.{save:,} and reinvesting all surpluses, the AI projects your total wealth to reach Rs.{forecast[-1]:,} in 20 years, assuming a standard 12% market CAGR.")
            pdf.ln(10)
            # MF PICKS
            pdf.set_font("Arial",'B',18); pdf.set_text_color(0,255,163); pdf.cell(0,15,"AI MUTUAL FUND PICKS",0,1)
            for n,t,r_r,w in MFS:
                pdf.set_font("Arial",'B',11); pdf.set_text_color(255,255,255); pdf.cell(0,8,f"- {n} ({t})",0,1)
                pdf.set_font("Arial",'',10); pdf.set_text_color(150,150,150); pdf.multi_cell(0,6,f"  Risk: {r_r} | {w}")
                pdf.ln(2)
            return pdf.output(dest='S').encode('latin-1')
        st.markdown("<br>", unsafe_allow_html=True)
        st.download_button("📥 DOWNLOAD COMPREHENSIVE ELITE AI REPORT (PDF)", data=_elite_pdf(), file_name=f"WealthWizard_Elite_{D['name']}.pdf", mime="application/pdf")
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("← BACK TO PLANNING"): nav(3)
    with c2:
        if st.button("🔄 SYSTEM REBOOT"): st.session_state.data = DEFS.copy(); nav(1)
