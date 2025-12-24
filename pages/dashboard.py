import streamlit as st
from openai import OpenAI
from datetime import datetime


api_key = st.secrets["OPENAI_API_KEY"]

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Dashboard", layout="wide")

client = OpenAI(api_key=api_key)

LEAGUES = [
    "NFL",
    "NBA",
    "WNBA",
    "IPL",
    "NHL",
    "Tennis",
    "Formula 1",
    "MLB"
]


def is_league_in_season(league: str) -> bool:
    month = datetime.utcnow().month

    season_months = {
        "NFL": [9, 10, 11, 12, 1, 2],
        "NBA": [10, 11, 12, 1, 2, 3, 4, 5, 6],
        "WNBA": [5, 6, 7, 8, 9, 10],
        "IPL": [3, 4, 5],
        "NHL": [10, 11, 12, 1, 2, 3, 4, 5, 6],
        "Tennis": list(range(1, 13)),
        "Formula 1": [3, 4, 5, 6, 7, 8, 9, 10, 11],
        "MLB": [3, 4, 5, 6, 7, 8, 9, 10]
    }

    return month in season_months.get(league, [])


ACTIVE_LEAGUES = [l for l in LEAGUES if is_league_in_season(l)]


# ---------------- UI ----------------
st.title("🏆 Sports Intelligence Dashboard")
st.caption("Powered entirely by ChatGPT + live web search")

refresh = st.button("🔄 Refresh Data")

# ---------------- PROMPT ----------------
def build_prompt(active_leagues):
    return f"""
You are a sports intelligence assistant.

For EACH of the following leagues:
{", ".join(active_leagues)}

Return the response STRICTLY in this format:

### LEAGUE: <League Name>
- In Season: Yes
- Season Start Date: (Official season start date, include year)
- Season End Date: (Official season end date or expected end, include year)
- Current Standings: (Top 5 teams ranked by the CURRENT SEASON standings as of today)
- Ticket Demand: Low/Medium/High + short reason based on current season interest
- Trophies Won: (Total number of LEAGUE TITLES won historically by the TOP 3 teams in this league; list team name + title count)
- Injury News: (Only major injuries affecting current season games; else say None)
- Upcoming Big Match: (Next high-profile scheduled game in the current season)
- Most Hyped Team/Player Right Now + reason (based on current season performance or news)

Rules:
- Use live web search
- All information must reflect the CURRENT SEASON only
- If season dates or standings are not officially available today, say "Not Available"
- Be concise
- Do NOT invent facts
"""



# ---------------- GPT CALL ----------------
def fetch_dashboard():
    response = client.responses.create(
        model="gpt-4.1",
        tools=[{"type": "web_search"}],
        input=build_prompt(ACTIVE_LEAGUES)
    )
    return response.output_text

# ---------------- PARSER ----------------
def split_by_league(text):
    sections = text.split("### LEAGUE:")
    data = {}

    for section in sections[1:]:
        lines = section.strip().split("\n")
        league = lines[0].strip()
        content = "\n".join(lines[1:])
        data[league] = content

    return data

# ---------------- DATA LOAD ----------------
if refresh or "dashboard_data" not in st.session_state:
    with st.spinner("Fetching live sports data..."):
        st.session_state["dashboard_data"] = fetch_dashboard()

league_sections = split_by_league(st.session_state["dashboard_data"])

# ---------------- DASHBOARD LAYOUT ----------------
cols = st.columns(2)
col_index = 0

for league, content in league_sections.items():
    with cols[col_index]:
        st.subheader(f"🏅 {league}")

        in_season = "Yes" if "In Season: Yes" in content else "No"
        demand = (
            "High" if "High" in content
            else "Medium" if "Medium" in content
            else "Low"
        )

        m1, m2 = st.columns(2)
        m1.metric("In Season", in_season)
        m2.metric("Ticket Demand", demand)

        with st.expander("View Full Details"):
            st.markdown(content)

    col_index = (col_index + 1) % 2
