from flask import Flask, render_template, request, jsonify, session
import openai
import pandas as pd
import numpy as np
import os

app = Flask(__name__)
app.secret_key = "sentinel_secret_key"

# ============================================================
# CONFIGURATION
# ============================================================
API_KEY = "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"
CSV_PATH = "final_sentinel_v2.csv"
MODEL   = "meta-llama/llama-4-maverick"
# ============================================================

# --- Load and compute stats ONCE when server starts ---
def load_data(path):
    try:
        df = pd.read_csv(path, dtype=str, low_memory=False)
        print(f"✅ Loaded: {df.shape[0]} rows, {df.shape[1]} columns")
        return df
    except FileNotFoundError:
        print(f"❌ File not found: {path}")
        exit()


def compute_stats(df):
    stats = {}
    stats['total_records'] = len(df)
    stats['columns'] = list(df.columns)

    if 'BORO_NM' in df.columns:
        stats['crimes_by_borough'] = (
            df['BORO_NM'].astype(str).str.strip().str.upper()
            .value_counts().to_dict()
        )
    if 'LAW_CAT_CD' in df.columns:
        stats['crimes_by_category'] = (
            df['LAW_CAT_CD'].astype(str).str.strip().str.upper()
            .value_counts().to_dict()
        )
    if 'OFNS_DESC' in df.columns:
        stats['top_10_offenses'] = (
            df['OFNS_DESC'].astype(str).str.strip().str.upper()
            .value_counts().head(10).to_dict()
        )
    if 'SUSP_AGE_GROUP' in df.columns:
        stats['suspect_age_distribution'] = (
            df['SUSP_AGE_GROUP'].astype(str).value_counts().to_dict()
        )
    if 'SUSP_RACE' in df.columns:
        stats['suspect_race_distribution'] = (
            df['SUSP_RACE'].astype(str).value_counts().to_dict()
        )
    if 'SUSP_SEX' in df.columns:
        stats['suspect_sex_distribution'] = (
            df['SUSP_SEX'].astype(str).value_counts().to_dict()
        )
    if 'VIC_AGE_GROUP' in df.columns:
        stats['victim_age_distribution'] = (
            df['VIC_AGE_GROUP'].astype(str).value_counts().to_dict()
        )
    if 'VIC_RACE' in df.columns:
        stats['victim_race_distribution'] = (
            df['VIC_RACE'].astype(str).value_counts().to_dict()
        )
    if 'VIC_SEX' in df.columns:
        stats['victim_sex_distribution'] = (
            df['VIC_SEX'].astype(str).value_counts().to_dict()
        )
    if 'TIME_OF_DAY' in df.columns:
        stats['crimes_by_time_of_day'] = (
            df['TIME_OF_DAY'].astype(str).value_counts().to_dict()
        )
    if 'TIME_OF_DAY' in df.columns and 'LAW_CAT_CD' in df.columns:
        felony_mask = (
            df['LAW_CAT_CD'].astype(str).str.strip().str.upper() == 'FELONY'
        )
        stats['felonies_by_time_of_day'] = (
            df[felony_mask]['TIME_OF_DAY'].astype(str)
            .value_counts().to_dict()
        )
    if 'PREM_TYP_DESC' in df.columns:
        stats['top_10_premises'] = (
            df['PREM_TYP_DESC'].astype(str).str.strip().str.upper()
            .value_counts().head(10).to_dict()
        )
    if 'PATROL_BORO' in df.columns:
        stats['crimes_by_patrol_boro'] = (
            df['PATROL_BORO'].astype(str).str.strip().str.upper()
            .value_counts().to_dict()
        )

    if 'CMPLNT_FR_DT' in df.columns:
        df['CMPLNT_FR_DT'] = pd.to_datetime(df['CMPLNT_FR_DT'], errors='coerce')
        stats['crimes_by_day_of_week'] = (
            df['CMPLNT_FR_DT'].dt.day_name()
            .value_counts().to_dict()
    )
        
    if 'RESPONSE_TIME_HRS' in df.columns:
        rt = pd.to_numeric(df['RESPONSE_TIME_HRS'], errors='coerce')
        rt = rt[rt >= 0].dropna()
        if len(rt) > 0:
            stats['response_time_stats'] = {
                'mean_hours'  : round(rt.mean(), 2),
                'median_hours': round(rt.median(), 2),
                'max_hours'   : round(rt.max(), 2)
            }
    if 'CRIME_SEVERITY_SCORE' in df.columns and 'BORO_NM' in df.columns:
        df['CRIME_SEVERITY_SCORE'] = pd.to_numeric(
            df['CRIME_SEVERITY_SCORE'], errors='coerce'
        )
        stats['avg_severity_by_borough'] = (
            df.groupby('BORO_NM')['CRIME_SEVERITY_SCORE']
            .mean().round(2).dropna().to_dict()
        )
    if 'SUSPECT_INFO_KNOWN' in df.columns:
        df['SUSPECT_INFO_KNOWN'] = pd.to_numeric(
            df['SUSPECT_INFO_KNOWN'], errors='coerce'
        )
        stats['suspect_info_known'] = {
            'known'  : int(df['SUSPECT_INFO_KNOWN'].sum()),
            'unknown': int((df['SUSPECT_INFO_KNOWN'] == 0).sum())
        }
    return stats


def build_system_prompt(stats):
    return f"""
You are a data analyst assistant for the NYPD Sentinel Pilot 2025 crime dataset.
You have been given pre-computed statistics from a cleaned crime complaints CSV file.
Use ONLY the statistics provided below to answer user questions.
Be specific, cite numbers, and give clear insights.
If a question cannot be answered from the available stats, say so honestly.

=== DATASET OVERVIEW ===
Total Records: {stats.get('total_records', 'N/A')}
Columns: {', '.join(stats.get('columns', []))}

=== CRIMES BY BOROUGH ===
{stats.get('crimes_by_borough', 'Not available')}

=== CRIMES BY LEGAL CATEGORY ===
{stats.get('crimes_by_category', 'Not available')}

=== TOP 10 OFFENSE TYPES ===
{stats.get('top_10_offenses', 'Not available')}

=== CRIMES BY TIME OF DAY ===
{stats.get('crimes_by_time_of_day', 'Not available')}

=== FELONIES BY TIME OF DAY ===
{stats.get('felonies_by_time_of_day', 'Not available')}

=== TOP 10 PREMISES ===
{stats.get('top_10_premises', 'Not available')}

=== CRIMES BY PATROL BOROUGH ===
{stats.get('crimes_by_patrol_boro', 'Not available')}

=== SUSPECT AGE ===
{stats.get('suspect_age_distribution', 'Not available')}

=== CRIMES BY DAY OF WEEK ===
{stats.get('crimes_by_day_of_week', 'Not available')}

=== SUSPECT RACE ===
{stats.get('suspect_race_distribution', 'Not available')}

=== SUSPECT SEX ===
{stats.get('suspect_sex_distribution', 'Not available')}

=== VICTIM AGE ===
{stats.get('victim_age_distribution', 'Not available')}

=== VICTIM RACE ===
{stats.get('victim_race_distribution', 'Not available')}

=== VICTIM SEX ===
{stats.get('victim_sex_distribution', 'Not available')}

=== RESPONSE TIME STATS ===
{stats.get('response_time_stats', 'Not available')}

=== AVG SEVERITY BY BOROUGH (1=Violation 2=Misdemeanor 3=Felony) ===
{stats.get('avg_severity_by_borough', 'Not available')}

=== SUSPECT INFO KNOWN vs UNKNOWN ===
{stats.get('suspect_info_known', 'Not available')}

=== REMAINING NULL COUNTS ===
{stats.get('null_counts', 'None')}
""".strip()


# --- Compute everything once at startup ---
print("⏳ Loading data and computing stats...")
df            = load_data(CSV_PATH)
stats         = compute_stats(df)
SYSTEM_PROMPT = build_system_prompt(stats)
client        = openai.OpenAI(
    api_key  = API_KEY,
    base_url = "https://openrouter.ai/api/v1"
)
print("✅ Ready!\n")


# ============================================================
# FLASK ROUTES
# ============================================================

@app.route("/")
def index():
    session['history'] = []          # fresh history on page load
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message", "").strip()
    if not user_message:
        return jsonify({"reply": "Please type a question."})

    # Load history from session
    history = session.get('history', [])

    # Add user message
    history.append({"role": "user", "content": user_message})

    # Call OpenRouter
    try:
        response = client.chat.completions.create(
            model      = MODEL,
            max_tokens = 1024,
            messages   = [
                {"role": "system", "content": SYSTEM_PROMPT},
                *history
            ]
        )
        reply = response.choices[0].message.content

    except Exception as e:
        reply = f"Error: {str(e)}"

    # Save assistant reply to history
    history.append({"role": "assistant", "content": reply})
    session['history'] = history

    return jsonify({"reply": reply})


if __name__ == "__main__":
    app.run(debug=True)