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

# 🌟 LIVE MARKETS TARGET LIST
# The API requires concrete sport tags. We iterate through the main active leagues:
TARGET_SPORTS = [
    "basketball_nba",
    "baseball_mlb",
    "soccer_usa_mls",
    "basketball_wnba"
]

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
        print(f"\nChecking active live lines for: {sport_key}...")
        
        nocache_ts = int(time.time())
        # We target the actual valid sport directory route
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

        # Look for live in-play games by checking if the start time is past or current
        # If games are completely ahead in the calendar, we drop them out
        current_time_epoch = time.time()
        
        for game in response:
            if not isinstance(game, dict):
                continue
                
            commence_time_raw = game.get('commence_time', '')
            if not commence_time_raw:
                continue
                
            try:
                # Parse timestamp structure to verify if it's currently live or imminent
                clean_time = commence_time_raw.split('.')[0].replace('Z','')
                game_start_epoch = time.mktime(time.strptime(clean_time, '%Y-%m-%dT%H:%M:%S'))
                
                # Filter logic: Game must have started or starting within the hour to qualify as live-action
                if current_time_epoch < (game_start_epoch - 3600):
                    continue  # Skip far future upcoming matches
                    
            except Exception:
                pass # Fallback to check values regardless if parsing has drift

            home_team = game.get('home_team')
            away_team = game.get('away_team')
            bookmakers = game.get('bookmakers', [])
            
            if len(bookmakers) > 1:
                try:
                    bookie1 = bookmakers[0]['title']
                    price1 = bookmakers[0]['markets'][0]['outcomes'][0]['price']
                    price2 = bookmakers[1]['markets'][0]['outcomes'][0]['price']
                    diff = round(abs(price1 - price2), 2)
                    
                    edge_pct = f"{round((diff / price1) * 100, 1)}%"
                    
                    # Capture moving odds gaps
                    if diff > 0.02: 
                        print(f"   🚨 LIVE LINE ALIGNMENT DETECTED: {home_team} vs {away_team}")
                        
                        # --- 3. GOOGLE SHEETS BACKLOG ---
                        if sheet:
                            sheet.append_row([home_team, away_team, "Live Play", "N/A", price1, bookie1, edge_pct])

                        # --- 4. BASE44 TRANSMISSION ---
                        if BASE44_URL and BASE44_KEY:
                            game_payload = {
                                "team": home_team,
                                "opponent": away_team,
                                "bet_type": "Live Play",
                                "line": "N/A",
                                "best_odds": price1,
                                "sportsbook": bookie1,
                                "edge_percentage": edge_pct,
                                "last_updated": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                            }
                            
                            try:
                                b44_resp = requests.post(BASE44_URL, json=game_payload, headers=base44_headers)
                                if b44_resp.status_code in [200, 201]:
                                    success_count += 1
                                    print(f"    ✅ Row synced to Base44 dashboard.")
                            except Exception as b44_err:
                                print(f"    ❌ Sync connection dropped: {b44_err}")

                except (IndexError, KeyError):
                    continue

    print(f"\n⚡ Run Complete. Successfully pushed {success_count} real-time updates to Base44!")

if __name__ == "__main__":
    print("Starting Mindful Sports Scraper Live Production Build...")
    get_value_picks()
