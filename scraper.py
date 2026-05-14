import requests
import os

# The bot will look for your key in the "Secret Safe" we set up next
API_KEY = os.environ.get("ODDS_API_KEY") 
SPORT = "upcoming" 
REGIONS = "us"
MARKETS = "h2h,spreads"

def get_value_picks():
    if not API_KEY:
        print("Error: No API Key found. Check your GitHub Secrets.")
        return

    # 1. Get the Odds
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds/?apiKey={API_KEY}&regions={REGIONS}&markets={MARKETS}"
    response = requests.get(url).json()
    
    # Check if we got a valid response
    if isinstance(response, dict) and "msg" in response:
        print(f"API Error: {response['msg']}")
        return

    for game in response:
        home_team = game.get('home_team')
        away_team = game.get('away_team')
        
        # 2. SIMPLE LOGIC: Look for "Value"
        bookmakers = game.get('bookmakers', [])
        if len(bookmakers) > 1:
            # We look at the first market for the first two bookies to find a gap
            try:
                price1 = bookmakers[0]['markets'][0]['outcomes'][0]['price']
                price2 = bookmakers[1]['markets'][0]['outcomes'][0]['price']
                diff = abs(price1 - price2)
                
                if diff > 0.15: # If there is a 15-cent gap in odds
                    print(f"🚨 VALUE ALERT: {home_team} vs {away_team}")
                    print(f"Gap found: {diff} - Check both books for the best price!")
            except (IndexError, KeyError):
                continue

if __name__ == "__main__":
    print("Starting Mindful Sports Scraper...")
    get_value_picks()
