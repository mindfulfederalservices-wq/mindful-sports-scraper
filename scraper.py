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
    
    # Matches your sheet name perfectly
    sheet = client.open("Mindful Sports Scraper Data").sheet1
    print("Successfully connected to Google Sheets!")
    
    # Initialize column headers and wipe old data
    headers_layout = ["Team", "Opponent", "Bet Type", "Line", "Best Odds", "Sportsbook", "Edge %"]
    sheet.clear()
    sheet.append_row(headers_layout)
    print("Sheet cleared and column headers initialized.")

except Exception as e:
    print(f"Google Sheets Connection Error: {e}")
    sheet = None

# --- 2. BASE44 & ODDS API REAL-TIME SETUP ---
BASE44_URL = os.environ.get("BASE44_APP_URL")
BASE44_KEY = os.environ.get("BASE44_API_KEY")
API_KEY = os.environ.get("ODDS_API_KEY") 

REGIONS = "us"
MARKETS = "h2h,spreads"

def get_value_picks():
    if not API_KEY:
        print("Error: No Odds API Key found. Check your GitHub Secrets.")
        return

    # 🌟 FIXED: Using the special 'all' keyword endpoint to pull ALL active live in-play sports games
    nocache_ts = int(time.time())
    url = f"https://api.the-odds-api.com/v4/sports/all/odds/?apiKey={API_KEY}&regions={REGIONS}&markets={MARKETS}&_ts={nocache_ts}"
    
    try:
        response = requests.get(url).json()
    except Exception as e:
        print(f"Failed to fetch real-time odds data: {e}")
        return
    
    # Verify that the API response is valid
    if isinstance(response, dict):
        if "msg" in response:
            print(f"API Notification: {response['msg']}")
            return
        else:
            print(f"API Error Response: {response}")
            return
            
    if not isinstance(response, list):
        print(f"API Error: Expected a list of games, but received: {type(response)}")
        return

    # Filter down to ONLY active live games
    live_games = [game for game in response if isinstance(game, dict) and game.get('commence_time') and (time.time() > time.mktime(time.strptime(game.get('commence_time').split('.')[0].replace('Z',''), '%Y-%m-%dT%H:%M:%S')) - 10800)] # buffer for live status

    if len(live_games) == 0:
        print("No active live-action games found in play right now. Waiting for the next live window!")
        return

    # Prepare authorization headers for Base44 app stream
    base44_headers = {}
    if BASE44_KEY:
        base44_headers = {
            "Authorization": f"Bearer {BASE44_KEY}",
            "Content-Type": "application/json"
        }

    success_count = 0

    for game in live_games:
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
                
                # Check for live line discrepancies
                if diff > 0.03: 
                    print(f"🚨 REAL REAL-TIME ALERT: {home_team} vs {away_team}")
                    
                    # --- 3. SEND TO GOOGLE SHEETS BACKLOG ---
                    if sheet:
                        sheet.append_row([
                            home_team,    
                            away_team,    
                            "Live Moneyline", 
                            "N/A",        
                            price1,       
                            bookie1,      
                            edge_pct      
                        ])
                        print(f"Data pushed to Sheets for {home_team}!")

                    # --- 4. STREAM TO BASE44 ROW-BY-ROW ---
                    if BASE44_URL and BASE44_KEY:
                        game_payload = {
                            "team": home_team,
                            "opponent": away_team,
                            "bet_type": "Live Moneyline",
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
                                print(f"✅ Real-time row pushed cleanly to Base44 dashboard.")
                            else:
                                print(f"⚠️ Base44 rejected transmission with status: {b44_resp.status_code}")
                        except Exception as b44_err:
                            print(f"Failed to stream record to Base44 pipeline: {b44_err}")

            except (IndexError, KeyError):
                continue

    print(f"\n⚡ Run Complete. Successfully pushed {success_count} real-time updates to Base44!")

if __name__ == "__main__":
    print("Starting Mindful Sports Scraper Live Production Build...")
    get_value_picks()
