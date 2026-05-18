import requests
import os
import json
import time
import gspread
from google.oauth2.service_account import Credentials

# --- 1. GOOGLE SHEETS SETUP ---
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    
    # Target sheet check
    sheet = client.open("Mindful Sports Scraper Data").sheet1
    print("Successfully connected to Google Sheets!")
    
    # EXACT column structure matching your original Base44 fields
    headers_layout = ["Team", "Opponent", "Bet Type", "Line", "Best Odds", "Sportsbook", "Edge %", "Profit on $100 Stake"]
    sheet.clear()
    sheet.append_row(headers_layout)
    print("Sheet cleared and column headers synchronized.")

except Exception as e:
    print(f"Google Sheets Connection Error: {e}")
    sheet = None

# --- 2. CONFIGURATION SETUP ---
BASE44_URL = os.environ.get("BASE44_APP_URL")
BASE44_KEY = os.environ.get("BASE44_API_KEY")
API_KEY = os.environ.get("ODDS_API_KEY") 

REGIONS = "us"
MARKETS = "h2h,spreads"
TARGET_SPORTS = ["baseball_mlb", "soccer_usa_mls", "basketball_wnba", "basketball_nba"]

# --- 3. AMERICAN ODDS CONVERSION UTILITY ---
def convert_to_american(decimal_price):
    if not decimal_price or decimal_price <= 1.0:
        return 0, "N/A"
    if decimal_price >= 2.0:
        val = round((decimal_price - 1) * 100)
        return val, f"+{val}"
    else:
        val = round(100 / (decimal_price - 1))
        return -val, f"-{val}"

# --- 4. PROFIT ON METRIC CALCULATION ---
def calculate_profit_on_100(numeric_odds):
    if numeric_odds > 0:
        return f"${float(numeric_odds):.2f}"
    elif numeric_odds < 0:
        # FIXED: Corrected formula to properly evaluate standard minus odds payouts ($100 stake baseline)
        profit = (100 / abs(numeric_odds)) * 100
        return f"${profit:.2f}"
    return "$0.00"

def get_value_picks():
    if not API_KEY:
        print("Error: No Odds API Key found. Check GitHub Secrets.")
        return

    base44_headers = {"Authorization": f"Bearer {BASE44_KEY}", "Content-Type": "application/json"} if BASE44_KEY else {}
    
    # Master list to collect all batch data for Google Sheets
    all_sheet_rows = []

    for sport_key in TARGET_SPORTS:
        print(f"\nChecking active value lines for: {sport_key}...")
        nocache_ts = int(time.time())
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={API_KEY}&regions={REGIONS}&markets={MARKETS}&_ts={nocache_ts}"
        
        try:
            response = requests.get(url).json()
        except Exception as e:
            print(f"Failed to fetch data for {sport_key}: {e}")
            continue
        
        if not isinstance(response, list):
            continue

        # In-memory set to prevent duplicate rows for identical matchups during runtime
        seen_games = set()

        for game in response:
            home_team = game.get('home_team')
            away_team = game.get('away_team')
            bookmakers = game.get('bookmakers', [])
            
            # UNIQUE ID DETECTOR: Sorts teams alphabetically to flag identical matchups 
            matchup_key = tuple(sorted([home_team, away_team]))

            if len(bookmakers) > 1:
                try:
                    market_data = bookmakers[0]['markets'][0]
                    market_type = market_data['key']
                    bookie1 = bookmakers[0]['title']

                    for outcome in market_data.get('outcomes', []):
                        # FIXED: Instantly skip if this matchup key has already been logged on this run execution
                        if matchup_key in seen_games:
                            continue

                        betting_team = outcome.get('name')
                        
                        # FORCE-IGNORE THE SOCCER TIE OUTCOME ROW ENTIRELY
                        if not betting_team or betting_team.lower() == "draw":
                            continue
                            
                        opponent_team = away_team if betting_team == home_team else home_team
                        
                        # Split Bet Type and Line dynamically to map to individual columns
                        if market_type == 'h2h':
                            bet_type = "Moneyline"
                            line_val = "ML"
                        elif market_type == 'spreads':
                            bet_type = "Spread"
                            pts = outcome.get('point', 0)
                            line_val = f"+{pts}" if pts > 0 else str(pts)
                        else:
                            bet_type = "Pre-Match"
                            line_val = "N/A"

                        price1_decimal = outcome['price']
                        
                        # Find matching comparison book odds to calculate true variance edge
                        try:
                            comp_market = bookmakers[1]['markets'][0]
                            comp_outcomes = comp_market.get('outcomes', [])
                            price2_decimal = next(o['price'] for o in comp_outcomes if o['name'] == betting_team)
                        except (StopIteration, IndexError, KeyError):
                            price2_decimal = price1_decimal

                        # Exact Edge Percentage Calculation
                        implied_prob1 = 1 / price1_decimal
                        implied_prob2 = 1 / price2_decimal
                        edge_raw = abs(implied_prob1 - implied_prob2) * 100
                        edge_pct = round(edge_raw, 1)
                        
                        # Convert odds and get payout values
                        american_num, american_str = convert_to_american(price1_decimal)
                        profit_display = calculate_profit_on_100(american_num)
                        
                        # --- CRITICAL PRODUCTION DATA GUARD RAILS ---
                        if line_val == "N/A" or american_str == "N/A" or american_num == 0 or profit_display == "$0.00":
                            continue

                        # GUARDRAIL: Skip extreme, broken lines (e.g., the -667 favorite glitch)
                        if american_num < -400 or american_num > 500:
                            continue

                        if edge_raw > 1.0: 
                            print(f"    🚨 VALUE ALIGNMENT DETECTED: {betting_team} (Vs {opponent_team})")
                            
                            # Add matchup to the uniqueness verification map immediately upon detection
                            seen_games.add(matchup_key)

                            # Append row data to our local memory cache list
                            all_sheet_rows.append([
                                betting_team, 
                                opponent_team, 
                                bet_type, 
                                line_val, 
                                american_str, 
                                bookie1, 
                                edge_pct, 
                                profit_display
                            ])

                            # --- LIVE ROUTING TRANSMISSION ---
                            if BASE44_URL and BASE44_KEY:
                                game_payload = {
                                    "team": betting_team,
                                    "opponent": opponent_team,
                                    "bet_type": bet_type,
                                    "line": line_val,
                                    "best_odds": american_str,
                                    "sportsbook": bookie1,
                                    "edge_percentage": edge_pct,
                                    "profit_on_100_stake": profit_display
                                }
                                try:
                                    requests.post(BASE44_URL, json=game_payload, headers=base44_headers)
                                except:
                                    pass

                except (IndexError, KeyError):
                    continue

    # --- 5. SINGLE BATCH PUSH TO GOOGLE SHEETS ---
    if sheet and all_sheet_rows:
        try:
            print(f"\n📥 Batch uploading {len(all_sheet_rows)} clean value alerts to Google Sheets...")
            sheet.append_rows(all_sheet_rows)
            print("Spreadsheet synced successfully using 1 API token credit!")
        except Exception as sheet_err:
            print(f"Failed to batch write rows to Sheet: {sheet_err}")

    print(f"\n⚡ Run Complete. Spreadsheet synced cleanly with your original Base44 columns!")

if __name__ == "__main__":
    get_value_picks()
