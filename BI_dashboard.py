import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Tuple, Optional, List
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================
st.set_page_config(
    page_title="Election Analytics: NST District 2",
    layout="wide",
    initial_sidebar_state="expanded")

# ============================================================================
# CUSTOM CSS
# ============================================================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] { 
        font-family: 'Sarabun', sans-serif;
        font-size: 16px;
    }
    
    .main { 
        background-color: #0e1117;
        padding: 2rem;
    }
    
    /* Metric Cards */
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, #1e2530 0%, #161b22 100%);
        border: 2px solid #30363d;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        transition: transform 0.2s;
    }
    
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        border-color: #58a6ff;
    }
    
    div[data-testid="metric-container"] label {
        font-size: 14px !important;
        font-weight: 600 !important;
        color: #8b949e !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    div[data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-size: 28px !important;
        font-weight: 700 !important;
        color: #58a6ff !important;
    }
    
    /* Headers */
    h1 {
        color: #58a6ff !important;
        font-size: 2.5rem !important;
        font-weight: 700 !important;
        margin-bottom: 0.5rem !important;
    }
    
    h2 {
        color: #79c0ff !important;
        font-size: 1.8rem !important;
        font-weight: 600 !important;
        margin-top: 2rem !important;
        margin-bottom: 1rem !important;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #30363d;
    }
    
    h3 {
        color: #a5d6ff !important;
        font-size: 1.3rem !important;
        font-weight: 600 !important;
        margin-top: 1rem !important;
    }
    
    /* Charts */
    .stPlotlyChart { 
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
        background-color: #161b22;
        padding: 10px;
    }
    
    /* Dataframes */
    .dataframe {
        font-size: 14px !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding: 0 24px;
        background-color: #161b22;
        border-radius: 8px 8px 0 0;
        font-size: 16px;
        font-weight: 600;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #1f6feb;
    }
    
    /* Sidebar */
    .css-1d391kg, [data-testid="stSidebar"] {
        background-color: #0d1117;
    }
    
    /* Info boxes */
    .stAlert {
        border-radius: 8px;
        font-size: 15px;
    }
    
    /* Dividers */
    hr {
        margin: 2rem 0;
        border-color: #30363d;
    }
    </style>
    """, unsafe_allow_html=True)

# ============================================================================
# HELPER FUNCTIONS - DEFENSIVE COLUMN CHECKING
# ============================================================================

def safe_get_column(df: pd.DataFrame, col: str, default=0):
    """Safely get column value with default fallback"""
    return df[col] if col in df.columns else default

def check_required_columns(df: pd.DataFrame, required_cols: List[str], dataset_name: str) -> bool:
    """Check if required columns exist in dataframe"""
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        st.error(f"❌ {dataset_name}: Missing columns: {', '.join(missing)}")
        return False
    return True

def safe_sum(df: pd.DataFrame, col: str) -> float:
    """Safely sum column with error handling"""
    try:
        if col in df.columns:
            return df[col].sum()
    except Exception as e:
        st.warning(f"Error summing {col}: {e}")
    return 0

def safe_groupby_sum(df: pd.DataFrame, group_col: str, sum_col: str) -> pd.DataFrame:
    """Safely group and sum with error handling"""
    try:
        if group_col in df.columns and sum_col in df.columns:
            return df.groupby(group_col)[sum_col].sum().reset_index()
    except Exception as e:
        st.warning(f"Error grouping {group_col} by {sum_col}: {e}")
    return pd.DataFrame()

# ============================================================================
# DATA LOADING
# ============================================================================

@st.cache_data
def load_data() -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], 
                         Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """Load all election datasets with error handling"""
    
    datasets = {
        'constituency': 'output/final_csv/constituency.csv',
        'party_list': 'output/final_csv/party_list.csv',
        'early_constituency': 'output/final_csv/17_constituency.csv',
        'early_party_list': 'output/final_csv/17_party_list.csv'
    }
    
    loaded = {}
    
    for name, path in datasets.items():
        try:
            df = pd.read_csv(path)
            # Filter for District 2 only
            if 'เขตเลือกตั้งที่' in df.columns:
                df = df[df['เขตเลือกตั้งที่'] == 2]
            elif 'เขต' in df.columns:
                df = df[df['เขต'] == 2]
            loaded[name] = df
            st.sidebar.success(f"✅ {name}: {len(df)} rows")
        except FileNotFoundError:
            st.sidebar.error(f"❌ {name}: File not found")
            loaded[name] = None
        except Exception as e:
            st.sidebar.error(f"❌ {name}: {str(e)}")
            loaded[name] = None
    
    return (loaded['constituency'], loaded['party_list'], 
            loaded['early_constituency'], loaded['early_party_list'])

# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_ballot_consistency(df: pd.DataFrame) -> pd.DataFrame:
    """Check if ballot counts match turnout"""
    required = ['จำนวนผู้มาแสดงตน', 'จำนวนบัตรดี', 'จำนวนบัตรเสีย', 'จำนวนบัตรที่ไม่เลือกผู้สมัคร']
    
    if not all(col in df.columns for col in required):
        return pd.DataFrame()
    
    df = df.copy()
    df['ballot_sum'] = df['จำนวนบัตรดี'] + df['จำนวนบัตรเสีย'] + df['จำนวนบัตรที่ไม่เลือกผู้สมัคร']
    df['discrepancy'] = df['ballot_sum'] - df['จำนวนผู้มาแสดงตน']
    
    return df[df['discrepancy'] != 0]

def find_suspicious_stations(df: pd.DataFrame, threshold: float = 10.0) -> pd.DataFrame:
    """Find polling stations with unusually high invalid ballot rates"""
    required = ['จำนวนผู้มาแสดงตน', 'จำนวนบัตรเสีย']
    
    if not all(col in df.columns for col in required):
        return pd.DataFrame()
    
    df = df.copy()
    df['invalid_rate'] = (df['จำนวนบัตรเสีย'] / df['จำนวนผู้มาแสดงตน']) * 100
    
    return df[df['invalid_rate'] > threshold]

# ============================================================================
# VISUALIZATION FUNCTIONS
# ============================================================================

def plot_candidate_ranking(df: pd.DataFrame, title: str = "Candidate Votes"):
    """Plot horizontal bar chart for candidate votes"""
    if df.empty or 'ชื่อสกุล' not in df.columns or 'คะแนน' not in df.columns:
        st.warning("No candidate data available")
        return
    
    votes = safe_groupby_sum(df, 'ชื่อสกุล', 'คะแนน')
    if votes.empty:
        return
    
    votes = votes.sort_values('คะแนน', ascending=True)
    
    fig = px.bar(
        votes, 
        x='คะแนน', 
        y='ชื่อสกุล', 
        orientation='h',
        template="plotly_dark",
        color='คะแนน',
        color_continuous_scale='Blues',
        title=title,
        text='คะแนน'
    )
    fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
    fig.update_layout(
        height=max(400, len(votes) * 40),
        showlegend=False,
        font=dict(size=13),
        xaxis_title="Votes",
        yaxis_title=""
    )
    st.plotly_chart(fig, use_container_width=True)

def plot_party_ranking(df: pd.DataFrame, party_col: str, title: str = "Party Votes"):
    """Plot horizontal bar chart for party votes"""
    if df.empty or party_col not in df.columns or 'คะแนน' not in df.columns:
        st.warning("No party data available")
        return
    
    votes = safe_groupby_sum(df, party_col, 'คะแนน')
    if votes.empty:
        return
    
    votes = votes.sort_values('คะแนน', ascending=True)
    
    fig = px.bar(
        votes,
        x='คะแนน',
        y=party_col,
        orientation='h',
        template="plotly_dark",
        color='คะแนน',
        color_continuous_scale='Reds',
        title=title,
        text='คะแนน'
    )
    fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
    fig.update_layout(
        height=max(400, len(votes) * 40),
        showlegend=False,
        font=dict(size=13),
        xaxis_title="Votes",
        yaxis_title=""
    )
    st.plotly_chart(fig, use_container_width=True)

def plot_vote_share_pie(df: pd.DataFrame, group_col: str, title: str = "Vote Share"):
    """Plot pie chart for vote share"""
    if df.empty or group_col not in df.columns or 'คะแนน' not in df.columns:
        st.warning("No data available for pie chart")
        return
    
    votes = safe_groupby_sum(df, group_col, 'คะแนน')
    if votes.empty:
        return
    
    fig = px.pie(
        votes,
        names=group_col,
        values='คะแนน',
        template="plotly_dark",
        title=title,
        hole=0.4
    )
    fig.update_traces(
        textposition='inside',
        textinfo='percent+label',
        textfont_size=13
    )
    fig.update_layout(height=400, font=dict(size=13))
    st.plotly_chart(fig, use_container_width=True)

def plot_turnout_by_subdistrict(df: pd.DataFrame):
    """Plot turnout rate by subdistrict"""
    required = ['ตำบล', 'จำนวนผู้มีสิทธิเลือกตั้ง', 'จำนวนผู้มาแสดงตน']
    
    if not all(col in df.columns for col in required):
        st.warning("Missing columns for turnout analysis")
        return
    
    turnout = df.groupby('ตำบล').agg({
        'จำนวนผู้มีสิทธิเลือกตั้ง': 'sum',
        'จำนวนผู้มาแสดงตน': 'sum'
    }).reset_index()
    
    turnout['turnout_rate'] = (turnout['จำนวนผู้มาแสดงตน'] / turnout['จำนวนผู้มีสิทธิเลือกตั้ง']) * 100
    turnout = turnout.sort_values('turnout_rate', ascending=True)
    
    fig = px.bar(
        turnout,
        x='turnout_rate',
        y='ตำบล',
        orientation='h',
        template="plotly_dark",
        color='turnout_rate',
        color_continuous_scale='Greens',
        title="Turnout Rate by Subdistrict (%)",
        text='turnout_rate'
    )
    fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig.update_layout(
        height=max(400, len(turnout) * 40),
        showlegend=False,
        font=dict(size=13),
        xaxis_title="Turnout Rate (%)",
        yaxis_title=""
    )
    st.plotly_chart(fig, use_container_width=True)

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    st.title("📊 Election Analytics Dashboard")
    st.markdown("### 🗳️ Nakhon Si Thammarat District 2 (นครศรีธรรมราช เขต 2)")
    st.markdown("")
    
    # Load data
    with st.spinner("Loading election data..."):
        df_const, df_party, df_early_const, df_early_party = load_data()
    
    # Check if data loaded successfully
    if df_const is None or df_party is None:
        st.error("❌ Failed to load required datasets. Please check file paths.")
        return
    
    # ========================================================================
    # SIDEBAR FILTERS
    # ========================================================================
    st.sidebar.title("🎯 Filters")
    st.sidebar.markdown("")
    
    # Subdistrict filter
    subdistricts = []
    if 'ตำบล' in df_const.columns:
        subdistricts = sorted(df_const['ตำบล'].unique())
    
    selected_subdistricts = st.sidebar.multiselect(
        "📍 Select Subdistricts (ตำบล)",
        options=subdistricts,
        default=subdistricts,
        help="Filter data by subdistrict"
    )
    
    # Apply filters
    if selected_subdistricts:
        filtered_const = df_const[df_const['ตำบล'].isin(selected_subdistricts)]
        filtered_party = df_party[df_party['ตำบล'].isin(selected_subdistricts)]
    else:
        filtered_const = df_const
        filtered_party = df_party
    
    # Polling station filter
    polling_stations = []
    if 'หน่วยเลือกตั้งที่' in filtered_const.columns:
        polling_stations = sorted(filtered_const['หน่วยเลือกตั้งที่'].unique())
    
    selected_stations = st.sidebar.multiselect(
        "🏢 Select Polling Stations (หน่วยเลือกตั้ง)",
        options=polling_stations,
        default=[],
        help="Optional: Filter by specific polling stations"
    )
    
    if selected_stations:
        filtered_const = filtered_const[filtered_const['หน่วยเลือกตั้งที่'].isin(selected_stations)]
        filtered_party = filtered_party[filtered_party['หน่วยเลือกตั้งที่'].isin(selected_stations)]
    
    st.sidebar.markdown("")
    st.sidebar.info(f"� **{len(filtered_const)}** polling stations selected")
    
    # ========================================================================
    # SECTION 1: OVERVIEW KPI CARDS
    # ========================================================================
    st.markdown("")
    st.header("1️⃣ Overview")
    st.markdown("")
    
    # Calculate KPIs - Group by polling station first to avoid double counting
    if 'ตำบล' in filtered_const.columns and 'หน่วยเลือกตั้งที่' in filtered_const.columns:
        station_summary = filtered_const.groupby(['ตำบล', 'หน่วยเลือกตั้งที่']).agg({
            'จำนวนผู้มีสิทธิเลือกตั้ง': 'first',
            'จำนวนผู้มาแสดงตน': 'first',
            'จำนวนบัตรดี': 'first',
            'จำนวนบัตรเสีย': 'first',
            'จำนวนบัตรที่ใช้': 'first',
            'จำนวนบัตรที่ไม่เลือกผู้สมัคร': 'first'
        }).reset_index()
        
        total_eligible = safe_sum(station_summary, 'จำนวนผู้มีสิทธิเลือกตั้ง')
        total_turnout_regular = safe_sum(station_summary, 'จำนวนผู้มาแสดงตน')
        total_valid = safe_sum(station_summary, 'จำนวนบัตรดี')
        total_invalid = safe_sum(station_summary, 'จำนวนบัตรเสีย')
        total_ballots = safe_sum(station_summary, 'จำนวนบัตรที่ใช้')
        total_no_vote = safe_sum(station_summary, 'จำนวนบัตรที่ไม่เลือกผู้สมัคร')
    else:
        total_eligible = safe_sum(filtered_const, 'จำนวนผู้มีสิทธิเลือกตั้ง')
        total_turnout_regular = safe_sum(filtered_const, 'จำนวนผู้มาแสดงตน')
        total_valid = safe_sum(filtered_const, 'จำนวนบัตรดี')
        total_invalid = safe_sum(filtered_const, 'จำนวนบัตรเสีย')
        total_ballots = safe_sum(filtered_const, 'จำนวนบัตรที่ใช้')
        total_no_vote = safe_sum(filtered_const, 'จำนวนบัตรที่ไม่เลือกผู้สมัคร')
    
    # Early voting turnout - Group by ชุดที่ first
    total_turnout_early = 0
    early_valid = 0
    early_invalid = 0
    early_no_vote = 0
    
    if df_early_const is not None and not df_early_const.empty:
        if 'ชุดที่' in df_early_const.columns:
            early_summary = df_early_const.groupby('ชุดที่').agg({
                'บัตรดี': 'first',
                'บัตรเสีย': 'first',
                'บัตรที่ไม่เลือก': 'first'
            }).reset_index()
            
            early_valid = safe_sum(early_summary, 'บัตรดี')
            early_invalid = safe_sum(early_summary, 'บัตรเสีย')
            early_no_vote = safe_sum(early_summary, 'บัตรที่ไม่เลือก')
            total_turnout_early = early_valid + early_invalid + early_no_vote
        else:
            early_valid = safe_sum(df_early_const, 'บัตรดี')
            early_invalid = safe_sum(df_early_const, 'บัตรเสีย')
            early_no_vote = safe_sum(df_early_const, 'บัตรที่ไม่เลือก')
            total_turnout_early = early_valid + early_invalid + early_no_vote
    
    total_turnout = total_turnout_regular + total_turnout_early
    turnout_pct = (total_turnout / total_eligible * 100) if total_eligible > 0 else 0
    
    # Combined ballot counts (regular + early)
    total_valid_combined = total_valid + early_valid
    total_invalid_combined = total_invalid + early_invalid
    total_no_vote_combined = total_no_vote + early_no_vote
    
    # Winning candidate
    winning_candidate = "N/A"
    if 'ชื่อสกุล' in filtered_const.columns and 'คะแนน' in filtered_const.columns:
        cand_votes = safe_groupby_sum(filtered_const, 'ชื่อสกุล', 'คะแนน')
        if not cand_votes.empty:
            winning_candidate = cand_votes.loc[cand_votes['คะแนน'].idxmax(), 'ชื่อสกุล']
    
    # Winning party
    winning_party = "N/A"
    if 'พรรคการเมือง' in filtered_party.columns and 'คะแนน' in filtered_party.columns:
        party_votes = safe_groupby_sum(filtered_party, 'พรรคการเมือง', 'คะแนน')
        if not party_votes.empty:
            winning_party = party_votes.loc[party_votes['คะแนน'].idxmax(), 'พรรคการเมือง']
    
    # Display KPIs - Row 1
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("👥 Eligible Voters", f"{total_eligible:,.0f}")
    
    with col2:
        st.metric("✅ Total Turnout", f"{total_turnout:,.0f}")
    
    with col3:
        st.metric("📊 Turnout Rate", f"{turnout_pct:.2f}%")
    
    st.markdown("")
    
    # Display KPIs - Row 2
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📝 Valid Ballots", f"{total_valid_combined:,.0f}")
    
    with col2:
        invalid_pct = (total_invalid_combined / total_turnout * 100) if total_turnout > 0 else 0
        st.metric("❌ Invalid Ballots", f"{total_invalid_combined:,.0f}", f"{invalid_pct:.2f}%")
    
    with col3:
        st.metric("⚪ No Vote", f"{total_no_vote_combined:,.0f}")
    
    st.markdown("")
    
    # Display KPIs - Row 3
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("🏆 Winning Candidate", winning_candidate)
    
    with col2:
        st.metric("🎯 Top Party", winning_party)
    
    st.markdown("---")
    
    # ========================================================================
    # SECTION 2: PARTY ANALYSIS
    # ========================================================================
    st.header("2️⃣ Party Analysis")
    st.markdown("")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Party List Votes")
        plot_party_ranking(filtered_party, 'พรรคการเมือง', "Party List Votes")
    
    with col2:
        st.subheader("🥧 Party Vote Share")
        plot_vote_share_pie(filtered_party, 'พรรคการเมือง', "Party List Vote Share")
    
    st.markdown("---")
    
    # ========================================================================
    # SECTION 3: CANDIDATE ANALYSIS
    # ========================================================================
    st.header("3️⃣ Candidate Analysis")
    st.markdown("")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Constituency Votes")
        plot_candidate_ranking(filtered_const, "Candidate Votes (Constituency)")
    
    with col2:
        st.subheader("🏅 Top 5 Candidates")
        if 'ชื่อสกุล' in filtered_const.columns and 'คะแนน' in filtered_const.columns:
            cand_votes = safe_groupby_sum(filtered_const, 'ชื่อสกุล', 'คะแนน')
            if not cand_votes.empty:
                top5 = cand_votes.nlargest(5, 'คะแนน')
                
                # Add party info if available
                if 'พรรค' in filtered_const.columns:
                    party_map = filtered_const.groupby('ชื่อสกุล')['พรรค'].first()
                    top5 = top5.merge(party_map, left_on='ชื่อสกุล', right_index=True, how='left')
                
                st.dataframe(top5, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # ========================================================================
    # SECTION 4: EARLY VS REGULAR VOTING
    # ========================================================================
    st.header("4️⃣ Early vs Regular Voting")
    st.markdown("")
    
    if df_early_const is not None and df_early_party is not None:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Turnout Comparison")
            
            turnout_data = pd.DataFrame({
                'Type': ['Regular Voting', 'Early Voting'],
                'Turnout': [total_turnout_regular, total_turnout_early]
            })
            
            fig = px.bar(
                turnout_data,
                x='Type',
                y='Turnout',
                template="plotly_dark",
                color='Type',
                title="Turnout: Early vs Regular",
                text='Turnout'
            )
            fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("🥧 Vote Distribution")
            
            fig = px.pie(
                turnout_data,
                names='Type',
                values='Turnout',
                template="plotly_dark",
                hole=0.4,
                title="Vote Type Distribution"
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("")
        
        # Party comparison
        st.subheader("📊 Party Performance: Early vs Regular")
        st.markdown("")
        
        if 'พรรคการเมือง' in filtered_party.columns and 'พรรค' in df_early_party.columns:
            regular_party = safe_groupby_sum(filtered_party, 'พรรคการเมือง', 'คะแนน')
            early_party = safe_groupby_sum(df_early_party, 'พรรค', 'คะแนน')
            
            if not regular_party.empty and not early_party.empty:
                regular_party.columns = ['Party', 'Regular']
                early_party.columns = ['Party', 'Early']
                
                comparison = pd.merge(regular_party, early_party, on='Party', how='outer').fillna(0)
                comparison['Total'] = comparison['Regular'] + comparison['Early']
                comparison = comparison.sort_values('Total', ascending=False).head(10)
                
                fig = go.Figure(data=[
                    go.Bar(name='Regular Voting', x=comparison['Party'], y=comparison['Regular']),
                    go.Bar(name='Early Voting', x=comparison['Party'], y=comparison['Early'])
                ])
                fig.update_layout(
                    barmode='group',
                    template="plotly_dark",
                    title="Top 10 Parties: Early vs Regular Voting",
                    xaxis_title="Party",
                    yaxis_title="Votes",
                    height=500
                )
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("ℹ️ Early voting data not available")
    
    st.markdown("---")
    
    # ========================================================================
    # SECTION 5: TURNOUT ANALYSIS
    # ========================================================================
    st.header("5️⃣ Turnout Analysis")
    st.markdown("")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📍 Turnout by Subdistrict")
        plot_turnout_by_subdistrict(filtered_const)
    
    with col2:
        st.subheader("🏆 Top 10 Polling Stations")
        
        required = ['หน่วยเลือกตั้งที่', 'ตำบล', 'จำนวนผู้มาแสดงตน', 'จำนวนผู้มีสิทธิเลือกตั้ง']
        if all(col in filtered_const.columns for col in required):
            station_turnout = filtered_const.groupby(['หน่วยเลือกตั้งที่', 'ตำบล']).agg({
                'จำนวนผู้มีสิทธิเลือกตั้ง': 'first',
                'จำนวนผู้มาแสดงตน': 'first'
            }).reset_index()
            
            station_turnout['turnout_rate'] = (
                station_turnout['จำนวนผู้มาแสดงตน'] / 
                station_turnout['จำนวนผู้มีสิทธิเลือกตั้ง'] * 100
            )
            
            top10 = station_turnout.nlargest(10, 'turnout_rate')
            
            fig = px.bar(
                top10,
                x='turnout_rate',
                y='หน่วยเลือกตั้งที่',
                orientation='h',
                template="plotly_dark",
                color='turnout_rate',
                color_continuous_scale='Viridis',
                hover_data=['ตำบล'],
                title="Top 10 Stations by Turnout Rate"
            )
            fig.update_layout(height=500, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # ========================================================================
    # SECTION 6: BALLOT ANALYSIS
    # ========================================================================
    st.header("6️⃣ Ballot Analysis")
    st.markdown("")
    
    # Combine regular and early voting ballots
    total_ballots_combined = total_ballots + (early_valid + early_invalid + early_no_vote)
    total_valid_combined = total_valid + early_valid
    total_invalid_combined = total_invalid + early_invalid
    total_no_vote_combined = total_no_vote + early_no_vote
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📋 Total Ballots", f"{total_ballots_combined:,.0f}")
    
    with col2:
        invalid_rate = (total_invalid_combined / total_ballots_combined * 100) if total_ballots_combined > 0 else 0
        st.metric("❌ Invalid Ballots", f"{total_invalid_combined:,.0f}", f"{invalid_rate:.2f}%")
    
    with col3:
        no_vote_rate = (total_no_vote_combined / total_ballots_combined * 100) if total_ballots_combined > 0 else 0
        st.metric("⚪ No Vote", f"{total_no_vote_combined:,.0f}", f"{no_vote_rate:.2f}%")
    
    st.markdown("")
    
    # Ballot breakdown pie chart
    st.subheader("📊 Ballot Breakdown")
    
    ballot_data = pd.DataFrame({
        'Type': ['Valid', 'Invalid', 'No Vote'],
        'Count': [total_valid_combined, total_invalid_combined, total_no_vote_combined]
    })
    
    fig = px.pie(
        ballot_data,
        names='Type',
        values='Count',
        template="plotly_dark",
        color_discrete_sequence=['#2ecc71', '#e74c3c', '#95a5a6'],
        title="Ballot Distribution"
    )
    fig.update_traces(textposition='inside', textinfo='percent+label+value')
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # ========================================================================
    # SECTION 7: VALIDATION CHECKS
    # ========================================================================
    st.header("7️⃣ Validation & Quality Checks")
    st.markdown("")
    
    tab1, tab2, tab3 = st.tabs(["🔍 Ballot Consistency", "⚠️ Suspicious Stations", "📊 Data Quality"])
    
    with tab1:
        st.markdown("")
        st.subheader("Ballot Count Consistency Check")
        st.caption("Verifying that ballot counts match turnout numbers")
        st.markdown("")
        
        inconsistent = validate_ballot_consistency(filtered_const)
        
        if inconsistent.empty:
            st.success("✅ All polling stations have consistent ballot counts")
        else:
            st.error(f"❌ Found **{len(inconsistent)}** polling stations with inconsistent ballot counts")
            st.markdown("")
            
            display_cols = ['ตำบล', 'หน่วยเลือกตั้งที่', 'จำนวนผู้มาแสดงตน', 
                           'ballot_sum', 'discrepancy']
            available_cols = [col for col in display_cols if col in inconsistent.columns]
            
            st.dataframe(
                inconsistent[available_cols].sort_values('discrepancy', ascending=False),
                use_container_width=True,
                hide_index=True
            )
    
    with tab2:
        st.markdown("")
        st.subheader("Suspicious Polling Stations")
        st.caption("Stations with invalid ballot rate > 10%")
        st.markdown("")
        
        suspicious = find_suspicious_stations(filtered_const, threshold=10.0)
        
        if suspicious.empty:
            st.success("✅ No suspicious polling stations detected")
        else:
            st.warning(f"⚠️ Found **{len(suspicious)}** suspicious polling stations")
            st.markdown("")
            
            display_cols = ['ตำบล', 'หน่วยเลือกตั้งที่', 'จำนวนผู้มาแสดงตน', 
                           'จำนวนบัตรเสีย', 'invalid_rate']
            available_cols = [col for col in display_cols if col in suspicious.columns]
            
            st.dataframe(
                suspicious[available_cols].sort_values('invalid_rate', ascending=False),
                use_container_width=True,
                hide_index=True
            )
    
    with tab3:
        st.markdown("")
        st.subheader("Data Quality Summary")
        st.markdown("")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📍 Polling Stations", len(filtered_const))
        
        with col2:
            st.metric("🏘️ Subdistricts", filtered_const['ตำบล'].nunique() if 'ตำบล' in filtered_const.columns else 0)
        
        with col3:
            inconsistent_count = len(validate_ballot_consistency(filtered_const))
            st.metric("⚠️ Inconsistent", inconsistent_count)
        
        with col4:
            suspicious_count = len(find_suspicious_stations(filtered_const))
            st.metric("🚨 Suspicious", suspicious_count)
        
        st.markdown("")
        st.markdown("")
        
        # Data completeness check
        st.subheader("Column Completeness")
        st.markdown("")
        
        completeness = pd.DataFrame({
            'Column': filtered_const.columns,
            'Non-Null Count': [filtered_const[col].notna().sum() for col in filtered_const.columns],
            'Null Count': [filtered_const[col].isna().sum() for col in filtered_const.columns],
            'Completeness %': [(filtered_const[col].notna().sum() / len(filtered_const) * 100) 
                              for col in filtered_const.columns]
        })
        
        st.dataframe(
            completeness.sort_values('Completeness %'),
            use_container_width=True,
            hide_index=True
        )
    
    # ========================================================================
    # FOOTER
    # ========================================================================
    st.markdown("---")
    st.markdown("")
    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption("📊 **Election Analytics Dashboard** | Nakhon Si Thammarat District 2")
        st.caption("Data Source: Election Commission of Thailand")
    with col2:
        st.caption("Built with Streamlit")

# ============================================================================
# RUN APPLICATION
# ============================================================================
if __name__ == "__main__":
    main()
