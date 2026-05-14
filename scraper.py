import requests
import os
import json
import gspread
from google.oauth2.service_account import Credentials

# --- 1. GOOGLE SHEETS SETUP ---
# This part uses the secret you saved in GitHub to log into your Sheet
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    # Get the big block of text from GitHub Secrets
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    
    # Open your sheet by name (Make sure this matches exactly!)
    sheet = client.open("Mindful_Sports_Data").sheet1
    print("Successfully connected to Google Sheets!")
except Exception as e:
    print(f"Google Sheets Connection Error: {e}")
    sheet = None

# --- 2. ODDS API SETUP ---
API_KEY = os.environ.get("ODDS_API_KEY") 
SPORT = "upcoming" 
REGIONS = "us"
MARKETS = "h2h,spreads"

def get_value_picks():
    if not API_KEY:
        print("Error: No API Key found. Check your GitHub Secrets.")
        return

    # Fetch the Odds
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds/?apiKey={API_KEY}&regions={REGIONS}&markets={MARKETS}"
    response = requests.get(url).json()
    
    if isinstance(response, dict) and "msg" in response:
        print(f"API Error: {response['msg']}")
        return

    for game in response:
        home_team = game.get('home_team')
        away_team = game.get('away_team')
        bookmakers = game.get('bookmakers', [])
        
        if len(bookmakers) > 1:
            try:
                # Logic to find the price gap
                price1 = bookmakers[0]['markets'][0]['outcomes'][0]['price']
                price2 = bookmakers[1]['markets'][0]['outcomes'][0]['price']
                diff = abs(price1 - price2)
                
                if diff > 0.15: 
                    print(f"🚨 VALUE ALERT: {home_team} vs {away_team}")
                    
                    # --- 3. SEND TO SHEET ---
                    if sheet:
                        sheet.append_row([home_team, away_team, price1, price2, diff])
                        print(f"Data sent to sheet for {home_team}!")
                    else:
                        print("Sheet not connected, skipping upload.")

            except (IndexError, KeyError):
                continue

if __name__ == "__main__":
    print("Starting Mindful Sports Scraper...")
    get_value_picks()
