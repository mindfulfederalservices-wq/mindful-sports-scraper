
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
    
    # Fresh headers
    headers_layout = ["Team", "Opponent", "Bet Type", "Line", "Best Odds", "Sportsbook", "Edge %"]
    sheet.clear()
    sheet.append_row(headers_layout)
    print("Sheet cleared and column headers initialized.")

except Exception as e:
    print(f"Google Sheets Connection Error: {e}")
    sheet = None

# --- 2. BASE44 & ODDS API SETUP ---
BASE44_URL = os.environ.get("BASE44_APP_URL")
BASE44_KEY = os.environ.get("BASE44_API_KEY")
API_KEY = os.environ.get("ODDS_API_KEY") 

REGIONS = "us"
MARKETS = "h2h,spreads"

# 🌟 LIVE & UPCOMING MARKETS TARGET LIST
TARGET_SPORTS = [
    "baseball_mlb",
    "soccer_usa_mls",
    "basketball_wnba",
    "basketball_nba"
]

# --- 3. ODDS CONVERSION UTILITY ---
def convert_to_american(decimal_price):
    """Converts raw decimal API odds into standard clean American odds string format."""
    if not decimal_price or decimal_price <= 1.0:
        return "N/A"
    if decimal_price >= 2.0:
        return f"+{round((decimal_price - 1) * 100)}"
    else:
        return f"-{round(100 / (decimal_price - 1))}"

def get_value_picks():
    if not API_KEY:
        print("Error: No Odds API Key found. Check your GitHub Secrets.")
        return

    base44_headers = {}
    if BASE44_KEY:
        base44_headers = {
            "Authorization": f"Bearer {BASE44_KEY}",
            "Content-Type": "application/json"
        }

    success_count = 0

    # Loop through our explicitly supported sports markets
    for sport_key in TARGET_SPORTS:
        print(f"\nChecking active value lines for: {sport_key}...")
        
        nocache_ts = int(time.time())
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={API_KEY}&regions={REGIONS}&markets={MARKETS}&_ts={nocache_ts}"
        
        try:
            response = requests.get(url).json()
        except Exception as e:
            print(f"Failed to fetch data for {sport_key}: {e}")
            continue
        
        # Check if the API returned an error message block for this specific sport
        if isinstance(response, dict):
            if "msg" in response:
                print(f" -> API Note ({sport_key}): {response['msg']}")
            else:
                print(f" -> API Error ({sport_key}): {response.get('message', 'Unknown Error')}")
            continue
                
        if not isinstance(response, list):
            print(f" -> Unexpected data type response for {sport_key}")
            continue

        # Process available games
        for game in response:
            if not isinstance(game, dict):
                continue
                
            home_team = game.get('home_team')
            away_team = game.get('away_team')
            bookmakers = game.get('bookmakers', [])
            
            if len(bookmakers) > 1:
                try:
                    bookie1 = bookmakers[0]['title']
                    price1_decimal = bookmakers[0]['markets'][0]['outcomes'][0]['price']
                    price2_decimal = bookmakers[1]['markets'][0]['outcomes'][0]['price']
                    
                    # Core Market Discrepancy (Pure Implied Probability Edge)
                    implied_prob1 = 1 / price1_decimal
                    implied_prob2 = 1 / price2_decimal
                    edge_raw = abs(implied_prob1 - implied_prob2) * 100
                    
                    # Format edge cleanly with one single percentage sign
                    edge_pct = f"{round(edge_raw, 1)}%"
                    
                    # Convert raw decimal odds into clear American Odds format for presentation
                    american_odds_display = convert_to_american(price1_decimal)
                    
                    # Capture meaningful gaps (Filter out noise)
                    if edge_raw > 1.0: 
                        print(f"   🚨 VALUE ALIGNMENT DETECTED: {home_team} vs {away_team}")
                        
                        # --- 4. GOOGLE SHEETS BACKLOG ---
                        if sheet:
                            sheet.append_row([home_team, away_team, "Pre-Match / Live", "N/A", american_odds_display, bookie1, edge_pct])

                        # --- 5. BASE44 TRANSMISSION (If utilizing raw webhook routing) ---
                        if BASE44_URL and BASE44_KEY:
                            game_payload = {
                                "team": home_team,
                                "opponent": away_team,
                                "bet_type": "Pre-Match / Live",
                                "line": "N/A",
                                "best_odds": american_odds_display,
                                "sportsbook": bookie1,
                                "edge_percentage": edge_pct,
                                "last_updated": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                            }
                            
                            try:
                                b44_resp = requests.post(BASE44_URL, json=game_payload, headers=base44_headers)
                                if b44_resp.status_code in [200, 201]:
                                    success_count += 1
                                    print(f"    ✅ Row synced to Base44 dashboard.")
                                else:
                                    print(f"    ❌ Base44 Response: Status {b44_resp.status_code}")
                            except Exception as b44_err:
                                print(f"    ❌ Sync connection dropped: {b44_err}")

                except (IndexError, KeyError):
                    continue

    print(f"\n⚡ Run Complete. Spreadsheet has been cleaned and synced with true values!")

if __name__ == "__main__":
    print("Starting Mindful Sports Scraper Live Production Build...")
    get_value_picks()
