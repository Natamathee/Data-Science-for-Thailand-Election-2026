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
# POLITICAL INSIGHTS FUNCTIONS
# ============================================================================

def analyze_split_ticket_voting(const_df: pd.DataFrame, party_df: pd.DataFrame) -> pd.DataFrame:
    """Analyze split-ticket voting behavior by comparing constituency vs party-list votes"""
    if const_df.empty or party_df.empty:
        return pd.DataFrame()
    
    # Get party votes from constituency
    const_party = const_df.groupby('พรรค')['คะแนน'].sum().reset_index()
    const_party.columns = ['Party', 'Constituency_Votes']
    
    # Get party-list votes
    party_votes = party_df.groupby('พรรคการเมือง')['คะแนน'].sum().reset_index()
    party_votes.columns = ['Party', 'PartyList_Votes']
    
    # Merge and calculate difference
    comparison = pd.merge(const_party, party_votes, on='Party', how='outer').fillna(0)
    comparison['Difference'] = comparison['PartyList_Votes'] - comparison['Constituency_Votes']
    comparison['Split_Pct'] = (comparison['Difference'] / comparison['Constituency_Votes'] * 100).replace([float('inf'), -float('inf')], 0)
    
    return comparison.sort_values('Difference', ascending=False)

def find_stronghold_subdistricts(df: pd.DataFrame, min_votes: int = 100) -> pd.DataFrame:
    """Find subdistricts where parties have strong support"""
    if df.empty or 'ตำบล' not in df.columns:
        return pd.DataFrame()
    
    # Get top party per subdistrict
    subdistrict_party = df.groupby(['ตำบล', 'พรรค'])['คะแนน'].sum().reset_index()
    
    # Get total votes per subdistrict
    total_per_subdistrict = subdistrict_party.groupby('ตำบล')['คะแนน'].sum().reset_index()
    total_per_subdistrict.columns = ['ตำบล', 'Total_Votes']
    
    # Merge and calculate percentage
    subdistrict_party = pd.merge(subdistrict_party, total_per_subdistrict, on='ตำบล')
    subdistrict_party['Vote_Share'] = (subdistrict_party['คะแนน'] / subdistrict_party['Total_Votes'] * 100)
    
    # Get top party per subdistrict
    idx = subdistrict_party.groupby('ตำบล')['คะแนน'].idxmax()
    strongholds = subdistrict_party.loc[idx]
    
    # Filter by minimum votes and sort
    strongholds = strongholds[strongholds['คะแนน'] >= min_votes].sort_values('Vote_Share', ascending=False)
    
    return strongholds[['ตำบล', 'พรรค', 'คะแนน', 'Vote_Share']]

def analyze_candidate_strength(df: pd.DataFrame) -> pd.DataFrame:
    """Analyze candidate personal vote strength vs party performance"""
    if df.empty:
        return pd.DataFrame()
    
    # Get candidate votes
    cand_votes = df.groupby(['ชื่อสกุล', 'พรรค'])['คะแนน'].sum().reset_index()
    
    # Get party total votes
    party_total = df.groupby('พรรค')['คะแนน'].sum().reset_index()
    party_total.columns = ['พรรค', 'Party_Total']
    
    # Merge and calculate personal vote strength
    cand_analysis = pd.merge(cand_votes, party_total, on='พรรค')
    cand_analysis['Personal_Strength'] = (cand_analysis['คะแนน'] / cand_analysis['Party_Total'] * 100)
    
    return cand_analysis.sort_values('คะแนน', ascending=False)

def find_competitive_areas(df: pd.DataFrame, margin_threshold: float = 5.0) -> pd.DataFrame:
    """Find subdistricts with close competition (small margin between top 2)"""
    if df.empty or 'ตำบล' not in df.columns:
        return pd.DataFrame()
    
    # Get votes by subdistrict and candidate
    subdistrict_cand = df.groupby(['ตำบล', 'ชื่อสกุล', 'พรรค'])['คะแนน'].sum().reset_index()
    
    competitive = []
    
    for subdistrict in subdistrict_cand['ตำบล'].unique():
        sub_data = subdistrict_cand[subdistrict_cand['ตำบล'] == subdistrict].sort_values('คะแนน', ascending=False)
        
        if len(sub_data) >= 2:
            top1 = sub_data.iloc[0]
            top2 = sub_data.iloc[1]
            total_votes = sub_data['คะแนน'].sum()
            
            if total_votes > 0:
                margin = ((top1['คะแนน'] - top2['คะแนน']) / total_votes * 100)
                
                if margin <= margin_threshold:
                    competitive.append({
                        'ตำบล': subdistrict,
                        'Winner': top1['ชื่อสกุล'],
                        'Winner_Party': top1['พรรค'],
                        'Winner_Votes': top1['คะแนน'],
                        'Runner_Up': top2['ชื่อสกุล'],
                        'Runner_Up_Party': top2['พรรค'],
                        'Runner_Up_Votes': top2['คะแนน'],
                        'Margin_Pct': margin
                    })
    
    return pd.DataFrame(competitive).sort_values('Margin_Pct') if competitive else pd.DataFrame()

def analyze_turnout_anomalies(df: pd.DataFrame, std_threshold: float = 2.0) -> pd.DataFrame:
    """Find polling stations with unusual turnout rates"""
    if df.empty:
        return pd.DataFrame()
    
    required = ['ตำบล', 'หน่วยเลือกตั้งที่', 'จำนวนผู้มีสิทธิเลือกตั้ง', 'จำนวนผู้มาแสดงตน']
    if not all(col in df.columns for col in required):
        return pd.DataFrame()
    
    # Group by station
    station_data = df.groupby(['ตำบล', 'หน่วยเลือกตั้งที่']).agg({
        'จำนวนผู้มีสิทธิเลือกตั้ง': 'first',
        'จำนวนผู้มาแสดงตน': 'first'
    }).reset_index()
    
    station_data['turnout_rate'] = (station_data['จำนวนผู้มาแสดงตน'] / station_data['จำนวนผู้มีสิทธิเลือกตั้ง'] * 100)
    
    # Calculate mean and std
    mean_turnout = station_data['turnout_rate'].mean()
    std_turnout = station_data['turnout_rate'].std()
    
    # Find anomalies
    station_data['z_score'] = (station_data['turnout_rate'] - mean_turnout) / std_turnout
    anomalies = station_data[abs(station_data['z_score']) > std_threshold]
    
    return anomalies.sort_values('z_score', ascending=False)

def compare_early_vs_regular(const_df: pd.DataFrame, early_const_df: pd.DataFrame) -> dict:
    """Compare voting patterns between early and regular voting"""
    insights = {}
    
    if const_df.empty or early_const_df.empty:
        return insights
    
    # Regular voting - group by candidate
    regular_cand = const_df.groupby(['ชื่อสกุล', 'พรรค'])['คะแนน'].sum().reset_index()
    regular_total = regular_cand['คะแนน'].sum()
    regular_cand['Regular_Pct'] = (regular_cand['คะแนน'] / regular_total * 100) if regular_total > 0 else 0
    
    # Early voting - group by ชุดที่ first, then candidate
    if 'ชุดที่' in early_const_df.columns:
        early_grouped = early_const_df.groupby(['ชุดที่', 'ชื่อสกุล', 'พรรค'])['คะแนน'].sum().reset_index()
        early_cand = early_grouped.groupby(['ชื่อสกุล', 'พรรค'])['คะแนน'].sum().reset_index()
    else:
        early_cand = early_const_df.groupby(['ชื่อสกุล', 'พรรค'])['คะแนน'].sum().reset_index()
    
    early_total = early_cand['คะแนน'].sum()
    early_cand['Early_Pct'] = (early_cand['คะแนน'] / early_total * 100) if early_total > 0 else 0
    
    # Merge and compare
    comparison = pd.merge(
        regular_cand[['ชื่อสกุล', 'พรรค', 'Regular_Pct']], 
        early_cand[['ชื่อสกุล', 'พรรค', 'Early_Pct']], 
        on=['ชื่อสกุล', 'พรรค'], 
        how='outer'
    ).fillna(0)
    
    comparison['Difference'] = comparison['Early_Pct'] - comparison['Regular_Pct']
    
    insights['comparison'] = comparison.sort_values('Difference', ascending=False)
    insights['biggest_gainer'] = comparison.loc[comparison['Difference'].idxmax()] if not comparison.empty else None
    insights['biggest_loser'] = comparison.loc[comparison['Difference'].idxmin()] if not comparison.empty else None
    
    return insights

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
    winning_candidate_party = ""
    if 'ชื่อสกุล' in filtered_const.columns and 'คะแนน' in filtered_const.columns:
        cand_votes = safe_groupby_sum(filtered_const, 'ชื่อสกุล', 'คะแนน')
        if not cand_votes.empty:
            winning_candidate = cand_votes.loc[cand_votes['คะแนน'].idxmax(), 'ชื่อสกุล']
            # Get the party of the winning candidate
            if 'พรรค' in filtered_const.columns:
                winner_data = filtered_const[filtered_const['ชื่อสกุล'] == winning_candidate]
                if not winner_data.empty:
                    winning_candidate_party = winner_data['พรรค'].iloc[0]
                    winning_candidate = f"{winning_candidate} ({winning_candidate_party})"
    
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
            
            # Group early party by ชุดที่ first to avoid double counting
            if 'ชุดที่' in df_early_party.columns:
                early_party_grouped = df_early_party.groupby(['ชุดที่', 'พรรค'])['คะแนน'].sum().reset_index()
                early_party = early_party_grouped.groupby('พรรค')['คะแนน'].sum().reset_index()
            else:
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
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📋 Total Ballots", f"{total_ballots_combined:,.0f}")
    
    with col2:
        valid_rate = (total_valid_combined / total_ballots_combined * 100) if total_ballots_combined > 0 else 0
        st.metric("✅ Valid Ballots", f"{total_valid_combined:,.0f}", f"{valid_rate:.2f}%")
    
    with col3:
        invalid_rate = (total_invalid_combined / total_ballots_combined * 100) if total_ballots_combined > 0 else 0
        st.metric("❌ Invalid Ballots", f"{total_invalid_combined:,.0f}", f"{invalid_rate:.2f}%")
    
    with col4:
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
    # SECTION 7: POLITICAL INSIGHTS
    # ========================================================================
    st.header("7️⃣ Political Insights & Analysis")
    st.markdown("")
    
    insight_tab1, insight_tab2, insight_tab3, insight_tab4 = st.tabs([
        "🎯 Key Findings", 
        "🔄 Split-Ticket Analysis", 
        "📍 Geographic Patterns",
        "⚡ Competitive Analysis"
    ])
    
    with insight_tab1:
        st.markdown("")
        st.subheader("📊 Key Political Insights")
        st.markdown("")
        
        # Winning trends
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🏆 Winning Party Trends")
            
            # Constituency winner
            if 'ชื่อสกุล' in filtered_const.columns and 'พรรค' in filtered_const.columns:
                cand_votes = safe_groupby_sum(filtered_const, 'ชื่อสกุล', 'คะแนน')
                if not cand_votes.empty:
                    winner_idx = cand_votes['คะแนน'].idxmax()
                    winner_name = cand_votes.loc[winner_idx, 'ชื่อสกุล']
                    winner_votes = cand_votes.loc[winner_idx, 'คะแนน']
                    
                    # Get winner's party
                    winner_party = filtered_const[filtered_const['ชื่อสกุล'] == winner_name]['พรรค'].iloc[0]
                    
                    total_const_votes = cand_votes['คะแนน'].sum()
                    winner_pct = (winner_votes / total_const_votes * 100) if total_const_votes > 0 else 0
                    
                    st.success(f"**Constituency Winner:** {winner_name} ({winner_party})")
                    st.metric("Vote Share", f"{winner_pct:.1f}%", f"{winner_votes:,.0f} votes")
            
            # Party-list winner
            if 'พรรคการเมือง' in filtered_party.columns:
                party_votes = safe_groupby_sum(filtered_party, 'พรรคการเมือง', 'คะแนน')
                if not party_votes.empty:
                    party_winner_idx = party_votes['คะแนน'].idxmax()
                    party_winner = party_votes.loc[party_winner_idx, 'พรรคการเมือง']
                    party_winner_votes = party_votes.loc[party_winner_idx, 'คะแนน']
                    
                    total_party_votes = party_votes['คะแนน'].sum()
                    party_winner_pct = (party_winner_votes / total_party_votes * 100) if total_party_votes > 0 else 0
                    
                    st.info(f"**Party-List Winner:** {party_winner}")
                    st.metric("Vote Share", f"{party_winner_pct:.1f}%", f"{party_winner_votes:,.0f} votes")
        
        with col2:
            st.markdown("### 📈 Candidate Personal Strength")
            
            cand_strength = analyze_candidate_strength(filtered_const)
            if not cand_strength.empty:
                top3 = cand_strength.head(3)
                
                for idx, row in top3.iterrows():
                    with st.container():
                        st.markdown(f"**{row['ชื่อสกุล']}** ({row['พรรค']})")
                        st.progress(min(row['Personal_Strength'] / 100, 1.0))
                        st.caption(f"{row['คะแนน']:,.0f} votes • {row['Personal_Strength']:.1f}% of party total")
                        st.markdown("")
        
        st.markdown("")
        
        # Early vs Regular insights
        if df_early_const is not None and not df_early_const.empty:
            st.markdown("### 🗳️ Early vs Regular Voting Patterns")
            
            early_insights = compare_early_vs_regular(filtered_const, df_early_const)
            
            if early_insights and 'biggest_gainer' in early_insights and early_insights['biggest_gainer'] is not None:
                col1, col2 = st.columns(2)
                
                with col1:
                    gainer = early_insights['biggest_gainer']
                    st.success(f"**Strongest in Early Voting:** {gainer['ชื่อสกุล']} ({gainer['พรรค']})")
                    st.metric("Early Vote Advantage", f"+{gainer['Difference']:.1f}%")
                
                with col2:
                    loser = early_insights['biggest_loser']
                    st.warning(f"**Weaker in Early Voting:** {loser['ชื่อสกุล']} ({loser['พรรค']})")
                    st.metric("Early Vote Disadvantage", f"{loser['Difference']:.1f}%")
    
    with insight_tab2:
        st.markdown("")
        st.subheader("🔄 Split-Ticket Voting Analysis")
        st.caption("Comparing constituency votes vs party-list votes by party")
        st.markdown("")
        
        split_analysis = analyze_split_ticket_voting(filtered_const, filtered_party)
        
        if not split_analysis.empty:
            # Summary cards
            col1, col2, col3 = st.columns(3)
            
            with col1:
                max_gain = split_analysis.loc[split_analysis['Difference'].idxmax()]
                st.success(f"**Most Party-List Gain**")
                st.metric(max_gain['Party'], f"+{max_gain['Difference']:,.0f} votes")
                st.caption(f"{max_gain['Split_Pct']:.1f}% increase")
            
            with col2:
                max_loss = split_analysis.loc[split_analysis['Difference'].idxmin()]
                st.error(f"**Most Party-List Loss**")
                st.metric(max_loss['Party'], f"{max_loss['Difference']:,.0f} votes")
                st.caption(f"{max_loss['Split_Pct']:.1f}% decrease")
            
            with col3:
                avg_split = split_analysis['Difference'].abs().mean()
                st.info(f"**Average Split**")
                st.metric("Mean Difference", f"{avg_split:,.0f} votes")
            
            st.markdown("")
            st.markdown("### 📊 Detailed Split-Ticket Comparison")
            
            # Visualization
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                name='Constituency',
                x=split_analysis['Party'],
                y=split_analysis['Constituency_Votes'],
                marker_color='lightblue'
            ))
            
            fig.add_trace(go.Bar(
                name='Party-List',
                x=split_analysis['Party'],
                y=split_analysis['PartyList_Votes'],
                marker_color='lightcoral'
            ))
            
            fig.update_layout(
                barmode='group',
                template='plotly_dark',
                height=500,
                xaxis_title="Party",
                yaxis_title="Votes"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("")
            st.markdown("### 📋 Split-Ticket Data Table")
            st.dataframe(
                split_analysis,
                use_container_width=True,
                hide_index=True
            )
    
    with insight_tab3:
        st.markdown("")
        st.subheader("📍 Geographic Voting Patterns")
        st.markdown("")
        
        # Add tabs for Constituency and Party-List
        geo_tab1, geo_tab2 = st.tabs(["🗳️ Constituency", "📋 Party-List"])
        
        with geo_tab1:
            st.markdown("")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 🏰 Candidate Strongholds")
                st.caption("Subdistricts with dominant candidate support")
                st.markdown("")
                
                strongholds = find_stronghold_subdistricts(filtered_const, min_votes=50)
                
                if not strongholds.empty:
                    top_strongholds = strongholds.head(10)
                    
                    for idx, row in top_strongholds.iterrows():
                        with st.container():
                            col_a, col_b = st.columns([3, 1])
                            with col_a:
                                st.markdown(f"**{row['ตำบล']}** → {row['พรรค']}")
                            with col_b:
                                st.markdown(f"**{row['Vote_Share']:.1f}%**")
                            st.progress(row['Vote_Share'] / 100)
                            st.markdown("")
                else:
                    st.info("No significant strongholds detected")
            
            with col2:
                st.markdown("### ⚡ Competitive Areas")
                st.caption("Close races with margins < 5%")
                st.markdown("")
                
                competitive = find_competitive_areas(filtered_const, margin_threshold=5.0)
                
                if not competitive.empty:
                    for idx, row in competitive.iterrows():
                        with st.container():
                            st.warning(f"**{row['ตำบล']}** - Margin: {row['Margin_Pct']:.2f}%")
                            st.markdown(f"🥇 {row['Winner']} ({row['Winner_Party']}): {row['Winner_Votes']:,.0f}")
                            st.markdown(f"🥈 {row['Runner_Up']} ({row['Runner_Up_Party']}): {row['Runner_Up_Votes']:,.0f}")
                            st.markdown("")
                else:
                    st.success("No highly competitive areas detected")
        
        with geo_tab2:
            st.markdown("")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 🏰 Party-List Strongholds")
                st.caption("Subdistricts with dominant party-list support")
                st.markdown("")
                
                # Analyze party-list strongholds
                if 'ตำบล' in filtered_party.columns and 'พรรคการเมือง' in filtered_party.columns:
                    subdistrict_party = filtered_party.groupby(['ตำบล', 'พรรคการเมือง'])['คะแนน'].sum().reset_index()
                    
                    # Get total votes per subdistrict
                    total_per_subdistrict = subdistrict_party.groupby('ตำบล')['คะแนน'].sum().reset_index()
                    total_per_subdistrict.columns = ['ตำบล', 'Total_Votes']
                    
                    # Merge and calculate percentage
                    subdistrict_party = pd.merge(subdistrict_party, total_per_subdistrict, on='ตำบล')
                    subdistrict_party['Vote_Share'] = (subdistrict_party['คะแนน'] / subdistrict_party['Total_Votes'] * 100)
                    
                    # Get top party per subdistrict
                    idx = subdistrict_party.groupby('ตำบล')['คะแนน'].idxmax()
                    party_strongholds = subdistrict_party.loc[idx]
                    
                    # Filter and sort
                    party_strongholds = party_strongholds[party_strongholds['คะแนน'] >= 50].sort_values('Vote_Share', ascending=False)
                    
                    if not party_strongholds.empty:
                        top_party_strongholds = party_strongholds.head(10)
                        
                        for idx, row in top_party_strongholds.iterrows():
                            with st.container():
                                col_a, col_b = st.columns([3, 1])
                                with col_a:
                                    st.markdown(f"**{row['ตำบล']}** → {row['พรรคการเมือง']}")
                                with col_b:
                                    st.markdown(f"**{row['Vote_Share']:.1f}%**")
                                st.progress(row['Vote_Share'] / 100)
                                st.markdown("")
                    else:
                        st.info("No significant party-list strongholds detected")
                else:
                    st.warning("Party-list data not available")
            
            with col2:
                st.markdown("### 🔄 Party-List Competition")
                st.caption("Subdistricts with close party-list races")
                st.markdown("")
                
                # Find competitive party-list areas
                if 'ตำบล' in filtered_party.columns and 'พรรคการเมือง' in filtered_party.columns:
                    competitive_party = []
                    
                    for subdistrict in filtered_party['ตำบล'].unique():
                        sub_data = filtered_party[filtered_party['ตำบล'] == subdistrict]
                        party_votes = sub_data.groupby('พรรคการเมือง')['คะแนน'].sum().sort_values(ascending=False)
                        
                        if len(party_votes) >= 2:
                            top1_party = party_votes.index[0]
                            top2_party = party_votes.index[1]
                            top1_votes = party_votes.iloc[0]
                            top2_votes = party_votes.iloc[1]
                            total_votes = party_votes.sum()
                            
                            if total_votes > 0:
                                margin = ((top1_votes - top2_votes) / total_votes * 100)
                                
                                if margin <= 5.0:
                                    competitive_party.append({
                                        'ตำบล': subdistrict,
                                        'Winner': top1_party,
                                        'Winner_Votes': top1_votes,
                                        'Runner_Up': top2_party,
                                        'Runner_Up_Votes': top2_votes,
                                        'Margin_Pct': margin
                                    })
                    
                    if competitive_party:
                        competitive_party_df = pd.DataFrame(competitive_party).sort_values('Margin_Pct')
                        
                        for idx, row in competitive_party_df.iterrows():
                            with st.container():
                                st.warning(f"**{row['ตำบล']}** - Margin: {row['Margin_Pct']:.2f}%")
                                st.markdown(f"🥇 {row['Winner']}: {row['Winner_Votes']:,.0f}")
                                st.markdown(f"🥈 {row['Runner_Up']}: {row['Runner_Up_Votes']:,.0f}")
                                st.markdown("")
                    else:
                        st.success("No highly competitive party-list areas detected")
                else:
                    st.warning("Party-list data not available")
        
        st.markdown("")
        st.markdown("### 🗺️ Turnout Anomalies by Location")
        st.caption("Applies to regular voting only")
        
        turnout_anomalies = analyze_turnout_anomalies(filtered_const, std_threshold=2.0)
        
        if not turnout_anomalies.empty:
            st.warning(f"Found **{len(turnout_anomalies)}** polling stations with unusual turnout")
            
            display_cols = ['ตำบล', 'หน่วยเลือกตั้งที่', 'turnout_rate', 'z_score']
            st.dataframe(
                turnout_anomalies[display_cols].sort_values('z_score', ascending=False),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.success("No significant turnout anomalies detected")
    
    with insight_tab4:
        st.markdown("")
        st.subheader("⚡ Competitive Analysis")
        st.markdown("")
        
        # Add tabs for Constituency and Party-List
        comp_tab1, comp_tab2 = st.tabs(["🗳️ Constituency Race", "📋 Party-List Race"])
        
        with comp_tab1:
            st.markdown("")
            
            # Margin analysis
            if 'ชื่อสกุล' in filtered_const.columns:
                cand_votes = safe_groupby_sum(filtered_const, 'ชื่อสกุล', 'คะแนน')
                
                if not cand_votes.empty and len(cand_votes) >= 2:
                    cand_votes = cand_votes.sort_values('คะแนน', ascending=False)
                    
                    winner = cand_votes.iloc[0]
                    runner_up = cand_votes.iloc[1]
                    
                    margin = winner['คะแนน'] - runner_up['คะแนน']
                    total_votes = cand_votes['คะแนน'].sum()
                    margin_pct = (margin / total_votes * 100) if total_votes > 0 else 0
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("🥇 Winner", winner['ชื่อสกุล'])
                        st.metric("Votes", f"{winner['คะแนน']:,.0f}")
                    
                    with col2:
                        st.metric("🥈 Runner-Up", runner_up['ชื่อสกุล'])
                        st.metric("Votes", f"{runner_up['คะแนน']:,.0f}")
                    
                    with col3:
                        st.metric("📊 Victory Margin", f"{margin:,.0f} votes")
                        st.metric("Margin %", f"{margin_pct:.2f}%")
                    
                    st.markdown("")
                    
                    # Competitiveness assessment
                    if margin_pct < 3:
                        st.error("🔥 **Highly Competitive Race** - Margin < 3%")
                    elif margin_pct < 10:
                        st.warning("⚡ **Competitive Race** - Margin < 10%")
                    else:
                        st.success("✅ **Clear Victory** - Margin > 10%")
                    
                    st.markdown("")
                    st.markdown("### 📊 Candidate Vote Distribution")
                    
                    # Top 5 candidates comparison
                    top5 = cand_votes.head(5)
                    
                    fig = go.Figure(data=[
                        go.Bar(
                            x=top5['ชื่อสกุล'],
                            y=top5['คะแนน'],
                            text=top5['คะแนน'],
                            texttemplate='%{text:,.0f}',
                            textposition='outside',
                            marker_color=['gold', 'silver', '#CD7F32', 'lightblue', 'lightgray'][:len(top5)]
                        )
                    ])
                    
                    fig.update_layout(
                        template='plotly_dark',
                        height=400,
                        xaxis_title="Candidate",
                        yaxis_title="Votes",
                        showlegend=False
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
        
        with comp_tab2:
            st.markdown("")
            
            # Party-list margin analysis
            if 'พรรคการเมือง' in filtered_party.columns:
                party_votes = safe_groupby_sum(filtered_party, 'พรรคการเมือง', 'คะแนน')
                
                if not party_votes.empty and len(party_votes) >= 2:
                    party_votes = party_votes.sort_values('คะแนน', ascending=False)
                    
                    winner_party = party_votes.iloc[0]
                    runner_up_party = party_votes.iloc[1]
                    
                    margin_party = winner_party['คะแนน'] - runner_up_party['คะแนน']
                    total_party_votes = party_votes['คะแนน'].sum()
                    margin_party_pct = (margin_party / total_party_votes * 100) if total_party_votes > 0 else 0
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("🥇 Winner", winner_party['พรรคการเมือง'])
                        st.metric("Votes", f"{winner_party['คะแนน']:,.0f}")
                    
                    with col2:
                        st.metric("🥈 Runner-Up", runner_up_party['พรรคการเมือง'])
                        st.metric("Votes", f"{runner_up_party['คะแนน']:,.0f}")
                    
                    with col3:
                        st.metric("📊 Victory Margin", f"{margin_party:,.0f} votes")
                        st.metric("Margin %", f"{margin_party_pct:.2f}%")
                    
                    st.markdown("")
                    
                    # Competitiveness assessment
                    if margin_party_pct < 3:
                        st.error("🔥 **Highly Competitive Race** - Margin < 3%")
                    elif margin_party_pct < 10:
                        st.warning("⚡ **Competitive Race** - Margin < 10%")
                    else:
                        st.success("✅ **Clear Victory** - Margin > 10%")
                    
                    st.markdown("")
                    st.markdown("### 📊 Party Vote Distribution")
                    
                    # Top 5 parties comparison
                    top5_party = party_votes.head(5)
                    
                    fig = go.Figure(data=[
                        go.Bar(
                            x=top5_party['พรรคการเมือง'],
                            y=top5_party['คะแนน'],
                            text=top5_party['คะแนน'],
                            texttemplate='%{text:,.0f}',
                            textposition='outside',
                            marker_color=['gold', 'silver', '#CD7F32', 'lightcoral', 'lightpink'][:len(top5_party)]
                        )
                    ])
                    
                    fig.update_layout(
                        template='plotly_dark',
                        height=400,
                        xaxis_title="Party",
                        yaxis_title="Votes",
                        showlegend=False
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.markdown("")
                    st.markdown("### 📈 Vote Share Comparison")
                    
                    # Calculate vote shares
                    party_votes['Vote_Share'] = (party_votes['คะแนน'] / total_party_votes * 100)
                    
                    # Show top 10 parties with vote share
                    top10_party = party_votes.head(10)
                    
                    fig2 = px.bar(
                        top10_party,
                        x='พรรคการเมือง',
                        y='Vote_Share',
                        text='Vote_Share',
                        template='plotly_dark',
                        color='Vote_Share',
                        color_continuous_scale='Reds'
                    )
                    
                    fig2.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                    fig2.update_layout(
                        height=400,
                        xaxis_title="Party",
                        yaxis_title="Vote Share (%)",
                        showlegend=False
                    )
                    
                    st.plotly_chart(fig2, use_container_width=True)
            else:
                st.warning("Party-list data not available")
    
    st.markdown("---")
    
    # ========================================================================
    # SECTION 8: VALIDATION CHECKS
    # ========================================================================
    st.header("8️⃣ Validation & Quality Checks")
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
