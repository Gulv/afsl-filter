import html
import os
import re
import requests
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Page config & password gate
# ---------------------------------------------------------------------------

st.set_page_config(page_title="AFSL Condition Filter", layout="wide",
                   initial_sidebar_state="collapsed")

# Password protection
def check_password():
    """Show a login form and return True if the password is correct."""
    if st.session_state.get("authenticated"):
        return True

    st.markdown("## AFSL Condition Filter")
    st.markdown("Please enter the password to access this application.")
    password = st.text_input("Password", type="password", key="password_input")
    if st.button("Login", type="primary"):
        # Password is stored in Streamlit secrets (st.secrets) or falls back to default
        correct_pw = st.secrets.get("password", "afsl2026")
        if password == correct_pw:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False

if not check_password():
    st.stop()

st.markdown("""
<style>
    /* Tighter padding */
    .block-container { padding-top: 1.5rem; padding-bottom: 0.5rem; }

    /* Filter box styling */
    .filter-box {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 6px;
        padding: 10px 12px;
        height: 100%;
    }
    .filter-box h4 {
        margin: 0 0 8px 0;
        font-size: 14px;
        color: #1a5276;
        border-bottom: 2px solid #1a5276;
        padding-bottom: 4px;
    }

    /* Smaller checkboxes */
    .stCheckbox { margin-bottom: -10px; }
    .stCheckbox label p { font-size: 13px !important; }

    /* Sub-type box */
    .sub-box {
        background: #eef6ee;
        border: 1px solid #b7dab7;
        border-radius: 4px;
        padding: 6px 8px;
        margin-top: 4px;
    }
    .sub-box h5 {
        margin: 0 0 4px 0;
        font-size: 12px;
        color: #1a6b1a;
    }

    /* Separator */
    .filter-sep {
        border-top: 1px solid #ccc;
        margin: 6px 0;
    }
    .restrict-label {
        font-size: 12px;
        font-weight: bold;
        color: #856404;
        margin-bottom: 2px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Filter definitions
# ---------------------------------------------------------------------------

ACTIVITIES = {
    "Provide financial product advice": "provide financial product advice",
    "Deal in a financial product": "deal in a financial product",
    "Make a market": "make a market",
    "Provide custodial or depository services": "custodial or depository",
    "Operate registered MIS": r"operate.*managed investment scheme",
    "Operate CCIV": "operate the business and conduct the affairs of a",
    "Underwriting": "underwriting",
    "Superannuation trustee service": "superannuation trustee service",
    "Traditional trustee company services": "traditional trustee company services",
    "Claims handling and settling": "claims handling and settling",
}

DEAL_SUBTYPES = {
    "Issue/apply/acquire/vary/dispose (principal)": "issuing, applying for, acquiring, varying or disposing",
    "Apply/acquire/vary/dispose on behalf of another": "on behalf of another person",
    "Arrange for another person": "arranging for another person",
}

ADVICE_SUBTYPES = {
    "General advice only": "general financial product advice",
    "Personal advice": "personal financial product advice",
}

PRODUCT_TYPES = {
    "Derivatives": "derivatives",
    "Foreign exchange contracts": "foreign exchange contracts",
    "Securities": "securities",
    "General insurance products": "general insurance products",
    "Life products - investment": "investment life insurance products",
    "Life products - risk": "life risk insurance products",
    "Managed investment schemes": "managed investment scheme",
    "Superannuation": "superannuation",
    "Deposit and payment products": "deposit and payment products",
    "Basic deposit products": "basic deposit products",
    "Govt debentures/stocks/bonds": "debentures, stocks or bonds issued or proposed to be issued by a government",
    "Standard margin lending": "standard margin lending facility",
    "RSA products": "retirement savings accounts",
    "Consumer credit insurance": "consumer credit insurance",
    "Non-cash payment products": "non-cash payment products",
}

CLIENT_TYPES = {
    "Retail clients": "retail",
    "Wholesale clients": "wholesale",
}

RESTRICTION_FILTERS = {
    "Has 'limited to'": "limited to",
    "Has 'hedging'": "hedging",
    "Has 'restricted to'": "restricted to",
    "Has 'other than'": "other than",
}

HIGHLIGHT_PATTERNS = [
    (r"(limited to)", "background-color:#fff3cd;color:#856404;font-weight:bold;padding:1px 3px;border-radius:3px"),
    (r"(hedging)", "background-color:#d4edda;color:#155724;font-weight:bold;padding:1px 3px;border-radius:3px"),
    (r"(restricted to)", "background-color:#f8d7da;color:#721c24;font-weight:bold;padding:1px 3px;border-radius:3px"),
    (r"(other than)", "background-color:#f8d7da;color:#721c24;font-weight:bold;padding:1px 3px;border-radius:3px"),
]

ACTIVITY_KEYWORDS = [
    "provide financial product advice",
    "provide general financial product advice",
    "deal in a financial product",
    "make a market",
    "custodial or depository",
    "operate",
    "underwriting",
    "superannuation trustee",
    "traditional trustee",
    "claims handling",
]

# ---------------------------------------------------------------------------
# Data loading & filtering
# ---------------------------------------------------------------------------

CKAN_API_URL = "https://data.gov.au/data/api/3/action/datastore_search"
RESOURCE_ID = "d98a113d-6b50-40e6-b65f-2612efc877f4"


@st.cache_data(ttl=3600)
def load_data_from_api():
    """Fetch all AFSL records from the data.gov.au CKAN DataStore API."""
    all_records = []
    offset = 0
    limit = 1000
    while True:
        resp = requests.get(CKAN_API_URL, params={
            "resource_id": RESOURCE_ID,
            "limit": limit,
            "offset": offset,
        }, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        records = data["result"]["records"]
        if not records:
            break
        all_records.extend(records)
        offset += limit
    df = pd.DataFrame(all_records)
    if "_id" in df.columns:
        df = df.drop(columns=["_id"])
    return df


@st.cache_data
def load_data_from_csv(csv_file):
    return pd.read_csv(csv_file, encoding="utf-8-sig")


def filter_dataframe(df, activities, deal_subtypes, advice_subtypes,
                     products, clients, restrictions,
                     exclusive_products=False, exclusive_advice=False,
                     no_restrictions=False):
    mask = pd.Series(True, index=df.index)
    cond_col = df["AFS_LIC_CONDITION"].fillna("")

    for term in activities:
        if ".*" in term:
            mask &= cond_col.str.contains(term, case=False, regex=True, na=False)
        else:
            mask &= cond_col.str.contains(term, case=False, regex=False, na=False)

    # Deal subtypes: OR logic (any selected subtype matches)
    if deal_subtypes:
        sub_mask = pd.Series(False, index=df.index)
        for term in deal_subtypes:
            sub_mask |= cond_col.str.contains(term, case=False, regex=False, na=False)
        mask &= sub_mask

    # Advice subtypes: OR logic
    # Unqualified "provide financial product advice" covers both general and personal
    if advice_subtypes:
        sub_mask = pd.Series(False, index=df.index)
        for term in advice_subtypes:
            sub_mask |= cond_col.str.contains(term, case=False, regex=False, na=False)
        # Also match unqualified "provide financial product advice" (no general/personal qualifier)
        has_broad = cond_col.str.contains("provide financial product advice", case=False, regex=False, na=False)
        has_general = cond_col.str.contains("general financial product advice", case=False, regex=False, na=False)
        has_personal = cond_col.str.contains("personal financial product advice", case=False, regex=False, na=False)
        unqualified = has_broad & ~has_general & ~has_personal
        sub_mask |= unqualified
        mask &= sub_mask

    # Product types: OR logic (any selected product matches)
    if products:
        sub_mask = pd.Series(False, index=df.index)
        for term in products:
            sub_mask |= cond_col.str.contains(term, case=False, regex=False, na=False)
        mask &= sub_mask

    for term_list in [clients, restrictions]:
        for term in term_list:
            mask &= cond_col.str.contains(term, case=False, regex=False, na=False)

    # Exclusive: reject if any non-selected product type is also present
    if exclusive_products and products:
        excluded = [t for t in PRODUCT_TYPES.values() if t not in products]
        for term in excluded:
            mask &= ~cond_col.str.contains(term, case=False, regex=False, na=False)

    # Exclusive advice: reject if any non-selected advice subtype is also present
    if exclusive_advice and advice_subtypes:
        excluded = [t for t in ADVICE_SUBTYPES.values() if t not in advice_subtypes]
        for term in excluded:
            mask &= ~cond_col.str.contains(term, case=False, regex=False, na=False)

    # No restrictions: exclude licences containing any restriction keyword
    if no_restrictions:
        for term in RESTRICTION_FILTERS.values():
            mask &= ~cond_col.str.contains(term, case=False, regex=False, na=False)

    return df[mask]


def format_condition_html(condition_text):
    parts = condition_text.split("~")
    lines = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        display = html.escape(part)
        for pattern, style in HIGHLIGHT_PATTERNS:
            display = re.sub(pattern, rf'<span style="{style}">\1</span>',
                             display, flags=re.IGNORECASE)
        p = part.lower()
        if p.startswith("this licence"):
            lines.append(f'<div style="margin-bottom:6px;">{display}</div>')
        elif any(p.startswith(kw) for kw in ACTIVITY_KEYWORDS):
            lines.append(f'<div style="margin-top:14px;margin-bottom:4px;font-weight:bold;color:#1a6b1a;font-size:15px;">{display}</div>')
        elif p.startswith("to retail") or p.startswith("to wholesale"):
            lines.append(f'<div style="margin-top:10px;font-weight:bold;color:#1a5276;">{display}</div>')
        elif p.startswith("and") or p.startswith("or "):
            lines.append(f'<div style="margin-left:60px;color:#555;">{display}</div>')
        else:
            lines.append(f'<div style="margin-left:30px;">{display}</div>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

CSV_FALLBACK = "afs_lic_202603.csv"

st.markdown("## AFSL Condition Filter")

# Data source selection
with st.expander("Data Source"):
    source = st.radio("Load data from:", [
        "ASIC API (data.gov.au — latest)",
        "Local CSV file (bundled)",
        "Upload CSV",
    ], key="data_source", horizontal=True)

    uploaded = None
    if source == "Upload CSV":
        uploaded = st.file_uploader("Upload a CSV file", type=["csv"], key="csv_upload")

# Load data based on selection
if source == "ASIC API (data.gov.au — latest)":
    try:
        with st.spinner("Fetching latest data from ASIC (data.gov.au)..."):
            df = load_data_from_api()
        st.success(f"Loaded **{len(df):,}** licences from ASIC API (live data)")
    except Exception as e:
        st.warning(f"API fetch failed: {e}. Falling back to local CSV.")
        df = load_data_from_csv(CSV_FALLBACK)
elif source == "Upload CSV" and uploaded is not None:
    df = load_data_from_csv(uploaded)
else:
    try:
        df = load_data_from_csv(CSV_FALLBACK)
    except FileNotFoundError:
        st.error(f"CSV file '{CSV_FALLBACK}' not found and API unavailable.")
        st.stop()

# ---------------------------------------------------------------------------
# Filter panels — 4 columns across the top, matching the desktop layout
# ---------------------------------------------------------------------------

col1, col2, col3, col4 = st.columns([3, 3, 3, 2])

# --- Column 1: Activity Type ---
with col1:
    st.markdown('<div class="filter-box"><h4>Activity Type</h4></div>',
                unsafe_allow_html=True)
    selected_activities = []
    for label, term in ACTIVITIES.items():
        if st.checkbox(label, key=f"act_{label}"):
            selected_activities.append(term)

# --- Column 2: Sub-type (dynamic) ---
with col2:
    st.markdown('<div class="filter-box"><h4>Sub-type</h4></div>',
                unsafe_allow_html=True)

    deal_selected = ACTIVITIES["Deal in a financial product"] in selected_activities
    advice_selected = ACTIVITIES["Provide financial product advice"] in selected_activities

    selected_deal_subs = []
    selected_advice_subs = []

    if deal_selected:
        st.markdown('<div class="sub-box"><h5>Dealing Method</h5></div>',
                    unsafe_allow_html=True)
        for label, term in DEAL_SUBTYPES.items():
            if st.checkbox(label, key=f"deal_{label}"):
                selected_deal_subs.append(term)

    if advice_selected:
        st.markdown('<div class="sub-box"><h5>Advice Type</h5></div>',
                    unsafe_allow_html=True)
        for label, term in ADVICE_SUBTYPES.items():
            if st.checkbox(label, key=f"adv_{label}"):
                selected_advice_subs.append(term)
        exclusive_advice = st.checkbox("Exclusive (no other advice type)", key="exclusive_adv")
    else:
        exclusive_advice = False

    if not deal_selected and not advice_selected:
        st.caption("Select 'Deal' or 'Advice' in Activity Type to see sub-options.")

# --- Column 3: Product Type ---
with col3:
    st.markdown('<div class="filter-box"><h4>Product Type</h4></div>',
                unsafe_allow_html=True)
    selected_products = []
    for label, term in PRODUCT_TYPES.items():
        if st.checkbox(label, key=f"prod_{label}"):
            selected_products.append(term)
    st.markdown('<div class="filter-sep"></div>', unsafe_allow_html=True)
    exclusive_products = st.checkbox("Exclusive (no other products)", key="exclusive_prod")

# --- Column 4: Client Type & Restrictions ---
with col4:
    st.markdown('<div class="filter-box"><h4>Client Type &amp; Restrictions</h4></div>',
                unsafe_allow_html=True)
    selected_clients = []
    for label, term in CLIENT_TYPES.items():
        if st.checkbox(label, key=f"cl_{label}"):
            selected_clients.append(term)

    st.markdown('<div class="filter-sep"></div>', unsafe_allow_html=True)
    st.markdown('<div class="restrict-label">Restrictions:</div>',
                unsafe_allow_html=True)
    selected_restrictions = []
    for label, term in RESTRICTION_FILTERS.items():
        if st.checkbox(label, key=f"res_{label}"):
            selected_restrictions.append(term)
    st.markdown('<div class="filter-sep"></div>', unsafe_allow_html=True)
    no_restrictions = st.checkbox("No restrictions", key="no_restrictions")

# ---------------------------------------------------------------------------
# Buttons & status bar
# ---------------------------------------------------------------------------

st.markdown("---")
btn_col1, btn_col2, btn_col3, status_col = st.columns([1, 1, 1, 5])

with btn_col1:
    search_clicked = st.button("Search", type="primary")
with btn_col2:
    reset_clicked = st.button("Reset")

# Handle reset — clear all checkboxes by resetting session state
if reset_clicked:
    for key in list(st.session_state.keys()):
        if key.startswith(("act_", "deal_", "adv_", "prod_", "cl_", "res_")) or key in ("exclusive_prod", "exclusive_adv", "no_restrictions"):
            st.session_state[key] = False
    st.session_state["searched"] = False
    st.rerun()

# Gather all filters
has_filters = any([selected_activities, selected_deal_subs, selected_advice_subs,
                   selected_products, selected_clients, selected_restrictions,
                   exclusive_products, exclusive_advice, no_restrictions])

# Run search automatically when any filter is ticked (live filtering)
if has_filters:
    results = filter_dataframe(df, selected_activities, selected_deal_subs,
                               selected_advice_subs, selected_products,
                               selected_clients, selected_restrictions,
                               exclusive_products=exclusive_products,
                               exclusive_advice=exclusive_advice,
                               no_restrictions=no_restrictions)

    with status_col:
        st.markdown(f"**Found {len(results):,} of {len(df):,} licences**")

    # --- Results table ---
    display_cols = [
        "AFS_LIC_NUM", "AFS_LIC_NAME", "AFS_LIC_ABN_ACN",
        "AFS_LIC_START_DT", "AFS_LIC_PRE_FSR",
        "AFS_LIC_ADD_LOCAL", "AFS_LIC_ADD_STATE", "AFS_LIC_ADD_PCODE",
    ]
    col_rename = {
        "AFS_LIC_NUM": "AFSL #",
        "AFS_LIC_NAME": "Licensee Name",
        "AFS_LIC_ABN_ACN": "ABN / ACN",
        "AFS_LIC_START_DT": "Start Date",
        "AFS_LIC_PRE_FSR": "Pre-FSR",
        "AFS_LIC_ADD_LOCAL": "Locality",
        "AFS_LIC_ADD_STATE": "State",
        "AFS_LIC_ADD_PCODE": "Postcode",
    }

    display_df = results[display_cols].rename(columns=col_rename).reset_index(drop=True)
    display_df.index = display_df.index + 1

    st.dataframe(display_df, height=400)

    # Export button
    with btn_col3:
        csv_data = results[display_cols + ["AFS_LIC_CONDITION"]].to_csv(index=False)
        st.download_button("Export CSV", csv_data,
                           file_name="afsl_filtered.csv", mime="text/csv",
                           )

    # --- Condition detail viewer ---
    st.markdown("---")
    st.markdown("### Licence Conditions")
    if len(results) > 0:
        options = [f"{r['AFS_LIC_NUM']} — {r['AFS_LIC_NAME']}"
                   for _, r in results.head(500).iterrows()]
        selected = st.selectbox("Select a licence to view conditions:", options)
        if selected:
            lic_num = selected.split(" — ")[0].strip()
            row = results[results["AFS_LIC_NUM"].astype(str) == lic_num].iloc[0]
            cond = row.get("AFS_LIC_CONDITION", "")
            if cond:
                st.markdown(
                    f'<div style="background:#fafafa;border:1px solid #ddd;'
                    f'border-radius:8px;padding:20px;font-size:14px;'
                    f'line-height:1.7;max-height:500px;overflow-y:auto;'
                    f'font-family:Segoe UI,system-ui,sans-serif;">'
                    f'{format_condition_html(cond)}</div>',
                    unsafe_allow_html=True,
                )
else:
    with status_col:
        st.markdown(f"Loaded **{len(df):,}** licences — select filters above to search.")
