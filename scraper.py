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
    
    # Connect directly to your Mindful Sports Scraper spreadsheet
    sheet = client.open("Mindful Sports Scraper Data").sheet1
    print("Successfully connected to Google Sheets!")
    
    # Set the precise column layout to match your dashboard
    headers_layout = ["Team (vs. Opponent)", "Bet Type (Line)", "Best Odds", "Sportsbook", "Edge %", "Profit on $100 Stake"]
    sheet.clear()
    sheet.append_row(headers_layout)
    print("Sheet cleared and clean layout headers initialized.")

except Exception as e:
    print(f"Google Sheets Connection Error: {e}")
    sheet = None

# --- 2. ENDPOINT CONFIGURATION ---
BASE44_URL = os.environ.get("BASE44_APP_URL")
BASE44_KEY = os.environ.get("BASE44_API_KEY")
API_KEY = os.environ.get("ODDS_API_KEY") 

REGIONS = "us"
MARKETS = "h2h,spreads"
TARGET_SPORTS = ["baseball_mlb", "soccer_usa_mls", "basketball_wnba", "basketball_nba"]

# --- 3. ODDS CONVERSION UTILITY ---
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
        profit = (100 / abs(numeric_odds)) * 100
        return f"${profit:.2f}"
    return "$0.00"

# --- 5. CORE ENGINE SCANNER ---
def get_value_picks():
    if not API_KEY:
        print("Error: No Odds API Key found. Check GitHub Secrets.")
        return

    base44_headers = {"Authorization": f"Bearer {BASE44_KEY}", "Content-Type": "application/json"} if BASE44_KEY else {}

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

        for game in response:
            home_team = game.get('home_team')
            away_team = game.get('away_team')
            bookmakers = game.get('bookmakers', [])
            
            if len(bookmakers) > 1:
                try:
                    market_data = bookmakers[0]['markets'][0]
                    market_type = market_data['key']
                    
                    # Clean Labels for Market Type
                    if market_type == 'h2h':
                        line_display = "moneyline"
                    elif market_type == 'spreads':
                        line_val = market_data['outcomes'][0].get('point', 0)
                        line_display = f"spread ({'+' if line_val > 0 else ''}{line_val})"
                    else:
                        line_display = "pre-match"

                    bookie1 = bookmakers[0]['title']
                    price1_decimal = market_data['outcomes'][0]['price']
                    price2_decimal = bookmakers[1]['markets'][0]['outcomes'][0]['price']
                    
                    # Math Processing (Pure float sent to prevent double %% glitch)
                    implied_prob1 = 1 / price1_decimal
                    implied_prob2 = 1 / price2_decimal
                    edge_raw = abs(implied_prob1 - implied_prob2) * 100
                    edge_pct = round(edge_raw, 1) 
                    
                    # Convert to true American numeric/string structures
                    american_num, american_str = convert_to_american(price1_decimal)
                    profit_display = calculate_profit_on_100(american_num)
                    
                    # Structural string styling to match original dashboard vision
                    team_matchup_display = f"{home_team} (vs. {away_team})"
                    
                    if edge_raw > 1.0: 
                        print(f"   🚨 VALUE ALIGNMENT DETECTED: {team_matchup_display}")
                        
                        # --- WRITE ROW TO GOOGLE SHEET ---
                        if sheet:
                            sheet.append_row([
                                team_matchup_display, 
                                line_display, 
                                american_str, 
                                bookie1, 
                                edge_pct, 
                                profit_display
                            ])

                        # --- LIVE ROUTING TO BASE44 ENGINE ---
                        if BASE44_URL and BASE44_KEY:
                            game_payload = {
                                "team_vs_opponent": team_matchup_display,
                                "bet_type_line": line_display,
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

    print(f"\n⚡ Run Complete. Spreadsheet data updated cleanly!")

if __name__ == "__main__":
    get_value_picks()
