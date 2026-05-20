import os
import json
import gspread
from google.oauth2.service_account import Credentials

def process_pipeline():
    print("Connecting to Google Sheets Dashboard Engine...")
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        print("Error: GOOGLE_CREDENTIALS env variable missing!")
        return
        
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    
    workbook = client.open("Mindful Sports Scraper Data")
    history_sheet = workbook.worksheet("Past_Results")
    
    print("Clearing sheet for clean sport segregation...")
    history_sheet.clear()
    
    # 🆕 Added "Sport" as the second column header to fix Base44 filtering
    headers = ["Team", "Sport", "Opponent", "Bet Type", "Line", "Best Odds", "Sportsbook", "Edge %", "Profit on $100 Stake", "Status", "Final Score"]
    history_sheet.append_row(headers)
    
    # Strictly organized historical data with correct sports mapped
    sports_data = [
        # --- MLB ---
        ["Atlanta Braves", "MLB", "Miami Marlins", "Moneyline", "ML-189", "-189", "FanDuel", "1.7%", "$52.91", "WIN", "8 - 4"],
        ["Baltimore Orioles", "MLB", "Tampa Bay Rays", "Moneyline", "ML-175", "-175", "FanDuel", "1.6%", "$57.14", "LOSS", "1 - 4"],
        ["Cincinnati Reds", "MLB", "Philadelphia Phillies", "Spread", "+4.5", "+468", "DraftKings", "9.1%", "$468.00", "WIN", "4 - 1"],
        ["New York Mets", "MLB", "Washington Nationals", "Moneyline", "ML-102", "-102", "FanDuel", "1.0%", "$98.04", "LOSS", "6 - 9"],
        ["New York Yankees", "MLB", "Toronto Blue Jays", "Moneyline", "ML-175", "-175", "FanDuel", "1.6%", "$57.14", "WIN", "5 - 4"],
        ["Kansas City Royals", "MLB", "Boston Red Sox", "Moneyline", "ML", "-110", "DraftKings", "5.5%", "$100.00", "LOSS", "1 - 7"],
        ["Chicago Cubs", "MLB", "Milwaukee Brewers", "Moneyline", "ML-118", "-118", "FanDuel", "1.4%", "$84.75", "LOSS", "2 - 5"],
        ["Houston Astros", "MLB", "Minnesota Twins", "Moneyline", "ML", "+177", "DraftKings", "28.4%", "$177.00", "WIN", "2 - 1"],
        ["Pittsburgh Pirates", "MLB", "St. Louis Cardinals", "Moneyline", "ML-102", "-102", "FanDuel", "1.0%", "$98.04", "LOSS", "6 - 9"],
        ["Athletics", "MLB", "Los Angeles Angels", "Moneyline", "ML-127", "-127", "FanDuel", "1.2%", "$78.74", "WIN", "14 - 6"],
        ["San Francisco Giants", "MLB", "Arizona Diamondbacks", "Moneyline", "ML", "+144", "FanDuel", "11.6%", "$144.00", "LOSS", "3 - 5"],
        ["Cleveland Guardians", "MLB", "Detroit Tigers", "Moneyline", "ML", "+104", "FanDuel", "2.3%", "$104.00", "LOSS", "1 - 3"],
        ["Milwaukee Brewers", "MLB", "Chicago Cubs", "Moneyline", "ML-118", "-118", "FanDuel", "1.4%", "$84.75", "WIN", "5 - 2"],
        
        # --- MLS ---
        ["St. Louis City SC", "MLS", "Austin FC", "Moneyline", "ML-143", "-143", "BetRivers", "2.2%", "$69.93", "WIN", "2 - 2 (4-2 PKs)"],
        ["Minnesota United FC", "MLS", "Real Salt Lake", "Moneyline", "ML", "+123", "BetRivers", "1.7%", "$123.00", "LOSS", "0 - 2"],
        ["FC Cincinnati", "MLS", "Orlando City SC", "Moneyline", "ML-185", "-185", "BetRivers", "2.0%", "$54.05", "LOSS", "1 - 4"],
        ["Chicago Fire", "MLS", "Toronto FC", "Moneyline", "ML-227", "-227", "BetRivers", "2.8%", "$44.05", "LOSS", "0 - 1"],
        ["Nashville SC", "MLS", "New York City FC", "Moneyline", "ML-133", "-133", "BetRivers", "1.3%", "$75.19", "LOSS", "1 - 2"],
        ["New York Red Bulls", "MLS", "Sporting Kansas City", "Moneyline", "ML-104", "-104", "BetRivers", "2.9%", "$96.15", "WIN", "2 - 1"],
        ["Colorado Rapids", "MLS", "FC Dallas", "Moneyline", "ML", "+123", "BetRivers", "1.7%", "$123.00", "LOSS", "0 - 3"],
        ["Portland Timbers", "MLS", "San Jose Earthquakes", "Moneyline", "ML", "+160", "BetRivers", "2.4%", "$160.00", "WIN", "4 - 2"],
        ["San Diego FC", "MLS", "Vancouver Whitecaps FC", "Moneyline", "ML", "+240", "BetRivers", "1.3%", "$240.00", "LOSS", "0 - 2"],
        ["LA Galaxy", "MLS", "Houston Dynamo", "Moneyline", "ML", "+105", "BetRivers", "2.5%", "$105.00", "LOSS", "1 - 2"],
        ["Inter Miami CF", "MLS", "Philadelphia Union", "Moneyline", "ML-233", "-233", "BetRivers", "5.8%", "$42.92", "WIN", "3 - 1"],
        ["Los Angeles FC", "MLS", "Seattle Sounders FC", "Moneyline", "ML-108", "-108", "BetRivers", "1.7%", "$92.59", "WIN", "2 - 1"],
        
        # --- WNBA / NBA ---
        ["Chicago Sky", "WNBA", "Dallas Wings", "Moneyline", "ML", "+122", "FanDuel", "2.7%", "$122.00", "WIN", "83 - 74"],
        ["Golden State Valkyries", "WNBA", "New York Liberty", "Moneyline", "ML", "+250", "FanDuel", "1.9%", "$250.00", "LOSS", "76 - 88"],
        ["Los Angeles Sparks", "WNBA", "Phoenix Mercury", "Moneyline", "ML", "+116", "FanDuel", "2.5%", "$116.00", "WIN", "82 - 78"],
        ["Oklahoma City Thunder", "NBA", "San Antonio Spurs", "Moneyline", "ML-263", "-263", "BetRivers", "1.0%", "$38.02", "WIN", "112 - 105"]
    ]
    
    # Upload everything in 1 single credit-saving transaction
    history_sheet.append_rows(sports_data)
    print("🚀 Success! All teams cleanly segregated by sport type.")

if __name__ == "__main__":
    process_pipeline()
