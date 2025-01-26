import subprocess
import requests
import json
import time
from supabase import create_client, Client
from typing import TypedDict, List
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

# Retrieve Supabase URL and Key from environment variables
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")

supabase: Client = create_client(url, key)

class StockEntry(TypedDict):
   ticker: str
   created_at: datetime  
   updated_at: datetime
   name: str

# Manually set the headers at the PostgREST level
supabase.postgrest.auth(token=key)

response = supabase.table("stocks").select("*").execute()
response_data: List[StockEntry] = response.data

#organise into array of tickers

tickers = []
for stock in response_data:
    tickers.append(stock['ticker'])

short_list_tickers = tickers[1:3]
print(short_list_tickers)

# short_list_tickers = ["NVDA", "GOOGL"]

# def get_sec_tickers():
#     headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
#     response = requests.get(
#         "https://www.sec.gov/files/company_tickers.json",
#         headers=headers
#     )
#     if response.status_code != 200:
#         raise Exception(f"SEC API returned status code {response.status_code}")
#     return json.loads(response.text)

# for ticker in short_list_tickers:
#     print("Processing ticker:", ticker)
#     try:
#         sec_tickers = get_sec_tickers()
#         ticker_valid = any(company['ticker'] == ticker 
#                          for company in sec_tickers.values())
        
#         if not ticker_valid:
#             print(f"Warning: {ticker} not found")
#             continue
            
#         cmd = f'echo -e "a\\n" | poetry run python src/main.py --ticker {ticker}'
#         subprocess.run(cmd, shell=True, cwd='../')
#         time.sleep(1)  # Rate limiting
        
#     except Exception as e:
#         print(f"Error processing {ticker}: {str(e)}")
#         time.sleep(5)  # Longer delay on error
#         continue
