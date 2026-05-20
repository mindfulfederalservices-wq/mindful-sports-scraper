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
    
    workbook = client.open("Mindful Sports Scraper Data")
    sheet = workbook.sheet1
    print("Successfully connected to Google Sheets (Active Dashboard)!")
    
    try:
        history_sheet = workbook.worksheet("Past_Results")
        print("Connected to existing Past_Results tab.")
    except gspread.exceptions.WorksheetNotFound:
        history_headers = ["Team", "Opponent", "Bet Type", "Line", "Best Odds", "Sportsbook", "Edge %", "Profit on $100 Stake", "Status", "Final Score"]
        history_sheet = workbook.add_worksheet(title="Past_Results", rows="1000", cols="10")
        history_sheet.append_row(history_headers)
        print("Created new Past_Results tab with tracking headers.")
    
    headers_layout = ["Team", "Opponent", "Bet Type", "Line", "Best Odds", "Sportsbook", "Edge %", "Profit on $100 Stake"]
    sheet.clear()
    sheet.append_row(headers_layout)
    print("Sheet cleared and column headers synchronized.")

except Exception as e:
    print(f"Google Sheets Connection Error: {e}")
    sheet = None
    history_sheet = None

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
    try:
        odds = int(numeric_odds)
        if odds == 0:
            return 0.00
        if odds > 0:
            return round(float(odds), 2)
        else:
            profit = (100 / abs(odds)) * 100
            return round(profit, 2)
    except Exception:
        return 0.00

# --- 4. SOLVED VALUE FILTER LOOP ---
def get_value_picks():
    if not API_KEY:
        print("Error: No Odds API Key found. Check GitHub Secrets.")
        return

    base44_headers = {"Authorization": f"Bearer {BASE44_KEY}", "Content-Type": "application/json"} if BASE44_KEY else {}
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

        # FIX: Reset 'seen' map per individual league type loop execution block
        seen_games_this_sport = set()

        for game in response:
            home_team = game.get('home_team')
            away_team = game.get('away_team')
            bookmakers = game.get('bookmakers', [])
            matchup_key = tuple(sorted([home_team, away_team]))

            if len(bookmakers) > 1:
                try:
                    market_data = bookmakers[0]['markets'][0]
                    market_type = market_data['key']
                    bookie1 = bookmakers[0]['title']

                    for outcome in market_data.get('outcomes', []):
                        if matchup_key in seen_games_this_sport:
                            continue

                        betting_team = outcome.get('name')
                        if not betting_team or betting_team.lower() == "draw":
                            continue
                            
                        opponent_team = away_team if betting_team == home_team else home_team
                        
                        if market_type == 'h2h':
                            bet_type = "Moneyline"
                            line_val = "ML"
                        elif market_type == 'spreads':
                            bet_type = "Spread"
                            pts = outcome.get('point', 0)
                            line_val = f"+{pts}" if pts > 0 else str(pts)
                        else:
                            continue

                        price1_decimal = outcome['price']
                        
                        try:
                            comp_market = bookmakers[1]['markets'][0]
                            comp_outcomes = comp_market.get('outcomes', [])
                            price2_decimal = next(o['price'] for o in comp_outcomes if o['name'] == betting_team)
                        except (StopIteration, IndexError, KeyError):
                            price2_decimal = price1_decimal

                        implied_prob1 = 1 / price1_decimal
                        implied_prob2 = 1 / price2_decimal
                        edge_raw = abs(implied_prob1 - implied_prob2) * 100
                        edge_pct = round(edge_raw, 1)
                        
                        american_num, american_str = convert_to_american(price1_decimal)
                        profit_display = calculate_profit_on_100(american_num)
                        
                        if line_val == "N/A" or american_str == "N/A" or american_num == 0 or profit_display == 0.00:
                            continue

                        if american_num < -400 or american_num > 500:
                            continue

                        # Strict minimum edge barrier check
                        if edge_raw > 1.0: 
                            print(f"    🚨 VALUE ALIGNMENT DETECTED: {betting_team} (Vs {opponent_team})")
                            seen_games_this_sport.add(matchup_key)

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

    if sheet and all_sheet_rows:
        try:
            print(f"\n📥 Batch uploading {len(all_sheet_rows)} isolated alerts to Google Sheets...")
            sheet.append_rows(all_sheet_rows)
            print("Spreadsheet synced successfully using 1 API token credit!")
            
            if history_sheet:
                history_rows = []
                for row in all_sheet_rows:
                    history_rows.append(row + ["PENDING", "N/A"])
                history_sheet.append_rows(history_rows)
                print("Pending plays logged safely into Past_Results archive.")
                
        except Exception as sheet_err:
            print(f"Failed to batch write rows to Sheet: {sheet_err}")

    print(f"\n⚡ Run Complete. Spreadsheet synced cleanly with your original Base44 columns!")

# --- 5. ROBUST RESILIENT RESULTS GRADER (NBA ADDED) ---
def grade_past_results():
    if not history_sheet:
        print("History sheet not accessible. Skipping grading.")
        return

    print("\n🔄 Running Free ESPN Score Check Pipeline...")
    
    sport_urls = {
        "baseball_mlb": "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard",
        "soccer_usa_mls": "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard",
        "basketball_wnba": "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard",
        "basketball_nba": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    }

    live_winners = {}
    for sport, endpoint_url in sport_urls.items():
        try:
            res = requests.get(endpoint_url).json()
            for event in res.get('events', []):
                # Target complete games cleanly
                if event['status']['type']['name'] in ["STATUS_FINAL", "STATUS_POSTPONED"]:
                    competitors = event['competitions'][0]['competitors']
                    score_string = " - ".join([f"{t['team']['displayName']}: {t.get('score')}" for t in competitors])
                    
                    for team in competitors:
                        t_name = team['team']['displayName']
                        is_winner = team.get('winner', False)
                        
                        # Store structural layout mapping for safe lookup
                        live_winners[t_name] = {"winner": is_winner, "score": score_string}
                        
                        # Catch alternate names or short names (e.g. "Red Bulls" vs "New York Red Bulls")
                        short_name = team['team'].get('shortDisplayName', '')
                        if short_name:
                            live_winners[short_name] = {"winner": is_winner, "score": score_string}
        except Exception as e:
            print(f"Skipping network read for {sport} score lines: {e}")

    try:
        all_history = history_sheet.get_all_values()
    except Exception as e:
        print(f"Error accessing history sheet records: {e}")
        return

    if len(all_history) <= 1:
        print("No matches in archive to grade.")
        return

    # Scan and match cells
    for idx, row in enumerate(all_history[1:], start=2):
        if len(row) >= 9 and "PENDING" in row[8]:
            picked_team = row[0]
            matched = False
            
            # Substring key validation routine
            for key in live_winners:
                if key.lower() in picked_team.lower() or picked_team.lower() in key.lower():
                    final_score = live_winners[key]["score"]
                    status_label = "🟢 WIN" if live_winners[key]["winner"] else "🔴 LOSS"
                    
                    try:
                        history_sheet.update_cell(idx, 9, status_label)
                        history_sheet.update_cell(idx, 10, final_score)
                        print(f"Settled {picked_team}: {status_label}")
                    except Exception as cell_err:
                        print(f"Failed to update row {idx}: {cell_err}")
                    matched = True
                    break
            
            if not matched:
                print(f"Match for {picked_team} is still live or hasn't updated to STATUS_FINAL yet.")

if __name__ == "__main__":
    get_value_picks()
    grade_past_results()
