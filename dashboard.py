import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
import os

matplotlib.rc('font', family='Tahoma')

st.set_page_config(
    page_title="ผลการเลือกตั้ง เขต 2 นครศรีธรรมราช",
    page_icon="🗳️",
    layout="wide"
)

st.title("🗳️ ผลการเลือกตั้ง เขต 2 นครศรีธรรมราช 2569")
st.caption("ข้อมูลจากการ OCR ใบรายงานผลการนับคะแนน")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
@st.cache_data
def load_data():
    df_con = pd.concat([
        pd.read_csv("output/final_csv/constituency.csv"),
        pd.read_csv("output/final_csv/17_constituency.csv"),
    ], ignore_index=True)
    cand_ref = pd.read_csv("reference/candidates_ref.csv")
    num_to_party = dict(zip(cand_ref["หมายเลข"], cand_ref["พรรค"]))
    df_con["พรรค"] = df_con["หมายเลข"].map(num_to_party)

    df_pl_main = pd.read_csv("output/final_csv/party_list.csv").rename(columns={"พรรคการเมือง": "พรรค"})
    df_pl_17   = pd.read_csv("output/cleaned/17_party_list.csv")
    for df in [df_pl_main, df_pl_17]:
        df["พรรค"] = df["พรรค"].str.replace("^พรรค", "", regex=True)
    df_pl = pd.concat([df_pl_main[["พรรค","คะแนน"]], df_pl_17[["พรรค","คะแนน"]]], ignore_index=True)

    return df_con, df_pl, cand_ref

df_con, df_pl, cand_ref = load_data()

PARTY_COLORS = {
    "ภูมิใจไทย":        "#1a6bb5",
    "ประชาธิปัตย์":     "#003f8a",
    "ประชาชน":          "#f97316",
    "รวมไทยสร้างชาติ":  "#dc2626",
    "เพื่อไทย":         "#e11d48",
    "กล้าธรรม":         "#7c3aed",
    "เศรษฐกิจ":         "#059669",
    "พลวัต":            "#d97706",
    "สังคมประชาธิปไตยไทย": "#6b7280",
    "ไทยก้าวใหม่":      "#0891b2",
}

# ---------------------------------------------------------------------------
# Sidebar filter
# ---------------------------------------------------------------------------
st.sidebar.header("🔍 Filter")
all_tambons = sorted(df_con["ตำบล"].dropna().unique())
selected_tambons = st.sidebar.multiselect("เลือกตำบล", all_tambons, default=all_tambons)

df_con_f = df_con[df_con["ตำบล"].isin(selected_tambons)]

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
total_eligible = df_con_f.groupby(["ตำบล","หน่วยเลือกตั้งที่"])["จำนวนผู้มีสิทธิเลือกตั้ง"].first().sum()
total_turnout  = df_con_f.groupby(["ตำบล","หน่วยเลือกตั้งที่"])["จำนวนผู้มาแสดงตน"].first().sum()
total_votes    = df_con_f["คะแนน"].sum()
winner         = df_con_f.groupby("ชื่อสกุล")["คะแนน"].sum().idxmax()

col1.metric("ผู้มีสิทธิเลือกตั้ง", f"{total_eligible:,.0f} คน")
col2.metric("ผู้มาใช้สิทธิ", f"{total_turnout:,.0f} คน",
            f"{total_turnout/total_eligible*100:.1f}%" if total_eligible > 0 else "")
col3.metric("คะแนนรวมทั้งหมด", f"{total_votes:,.0f}")
col4.metric("ผู้ชนะ", winner)

st.divider()

# ---------------------------------------------------------------------------
# Section 1: Constituency 2569
# ---------------------------------------------------------------------------
st.header("1️⃣ คะแนนรวม แบ่งเขต 2569")

con_total = df_con_f.groupby(["ชื่อสกุล","พรรค"])["คะแนน"].sum().reset_index()
con_total = con_total.sort_values("คะแนน", ascending=True)

fig, ax = plt.subplots(figsize=(10, 4))
colors = [PARTY_COLORS.get(p, "#94a3b8") for p in con_total["พรรค"]]
bars = ax.barh(con_total["ชื่อสกุล"], con_total["คะแนน"], color=colors)
for bar, val in zip(bars, con_total["คะแนน"]):
    ax.text(bar.get_width() + 100, bar.get_y() + bar.get_height()/2,
            f"{val:,}", va="center", fontsize=9)
ax.set_xlabel("คะแนน")
ax.set_title("คะแนนรวม แบ่งเขต 2569")
plt.tight_layout()
st.pyplot(fig)
plt.close()

with st.expander("ดูตาราง"):
    st.dataframe(con_total.sort_values("คะแนน", ascending=False).reset_index(drop=True))

st.divider()

# ---------------------------------------------------------------------------
# Section 2: Party List 2566 vs 2569
# ---------------------------------------------------------------------------
st.header("2️⃣ Party List 2566 vs 2569")

pl_2566 = pd.DataFrame({
    "พรรค":       ["ประชาธิปัตย์", "ประชาชน", "ภูมิใจไทย", "รวมไทยสร้างชาติ"],
    "คะแนน_2566": [7599, 28049, 1145, 37891]
})
pl_2569 = df_pl.groupby("พรรค")["คะแนน"].sum().reset_index()
pl_2569.columns = ["พรรค", "คะแนน_2569"]
compare = pl_2566.merge(pl_2569, on="พรรค")
compare["เปลี่ยนแปลง_%"] = ((compare["คะแนน_2569"] - compare["คะแนน_2566"]) / compare["คะแนน_2566"] * 100).round(1)
compare = compare.sort_values("คะแนน_2569", ascending=False)

x = range(len(compare))
fig, ax = plt.subplots(figsize=(10, 4))
ax.bar([i - 0.2 for i in x], compare["คะแนน_2566"], width=0.4, label="2566", color="#94a3b8")
ax.bar([i + 0.2 for i in x], compare["คะแนน_2569"], width=0.4, label="2569", color="#2563eb")
ax.set_xticks(list(x))
ax.set_xticklabels(compare["พรรค"], fontsize=11)
ax.set_ylabel("คะแนน")
ax.set_title("Party List 2566 vs 2569")
ax.legend()
for i, row in compare.reset_index(drop=True).iterrows():
    pct = row["เปลี่ยนแปลง_%"]
    sign = "+" if pct >= 0 else ""
    color = "green" if pct >= 0 else "red"
    ax.text(i, max(row["คะแนน_2566"], row["คะแนน_2569"]) + 500,
            f"{sign}{pct}%", ha="center", color=color, fontsize=9)
plt.tight_layout()
st.pyplot(fig)
plt.close()

with st.expander("ดูตาราง"):
    st.dataframe(compare.reset_index(drop=True))

st.divider()

# ---------------------------------------------------------------------------
# Section 3: Personal Vote
# ---------------------------------------------------------------------------
st.header("3️⃣ Personal Vote 2569")
st.caption("บวก = ผู้สมัครได้คะแนนมากกว่าพรรค | ลบ = พรรคได้มากกว่า")

con_by_party = df_con_f.groupby("พรรค")["คะแนน"].sum().reset_index()
con_by_party.columns = ["พรรค", "constituency"]
pl_by_party = df_pl.groupby("พรรค")["คะแนน"].sum().reset_index()
pl_by_party.columns = ["พรรค", "party_list"]
pv = con_by_party.merge(pl_by_party, on="พรรค").query("constituency > 0 and party_list > 0")
pv["personal_vote"] = pv["constituency"] - pv["party_list"]
pv = pv.sort_values("personal_vote", ascending=True)

fig, ax = plt.subplots(figsize=(10, 4))
colors = ["#16a34a" if v >= 0 else "#dc2626" for v in pv["personal_vote"]]
ax.barh(pv["พรรค"], pv["personal_vote"], color=colors)
ax.axvline(0, color="black", linewidth=0.8)
ax.set_xlabel("constituency - party_list")
ax.set_title("Personal Vote 2569")
plt.tight_layout()
st.pyplot(fig)
plt.close()

with st.expander("ดูตาราง"):
    st.dataframe(pv[["พรรค","constituency","party_list","personal_vote"]].reset_index(drop=True))

st.divider()

# ---------------------------------------------------------------------------
# Section 4: Voter Turnout
# ---------------------------------------------------------------------------
st.header("4️⃣ Voter Turnout แยกตำบล")

turnout = df_con_f.groupby("ตำบล").agg(
    ผู้มีสิทธิ=("จำนวนผู้มีสิทธิเลือกตั้ง","sum"),
    ผู้มาใช้สิทธิ=("จำนวนผู้มาแสดงตน","sum"),
).reset_index().dropna()
turnout["turnout_%"] = (turnout["ผู้มาใช้สิทธิ"] / turnout["ผู้มีสิทธิ"] * 100).round(1)
turnout = turnout.sort_values("turnout_%", ascending=True)
avg = turnout["turnout_%"].mean()

fig, ax = plt.subplots(figsize=(10, max(4, len(turnout) * 0.4)))
colors = ["#16a34a" if v >= avg else "#f97316" for v in turnout["turnout_%"]]
ax.barh(turnout["ตำบล"], turnout["turnout_%"], color=colors)
ax.axvline(avg, color="navy", linestyle="--", label=f"เฉลี่ย {avg:.1f}%")
ax.set_xlabel("Turnout (%)")
ax.set_title("Voter Turnout แยกตำบล 2569")
ax.legend()
plt.tight_layout()
st.pyplot(fig)
plt.close()

with st.expander("ดูตาราง"):
    st.dataframe(turnout.sort_values("turnout_%", ascending=False).reset_index(drop=True))
