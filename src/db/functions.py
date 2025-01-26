from datetime import datetime
import random

def store_backtest_record(supabase, record):
    """Store a single backtest record"""
    try:
        response = supabase.table('backtest_records').upsert(record).execute()
        return True
    except Exception as e:
        print(f"Error storing backtest record: {e}")
        return False

def store_analyst_signals(supabase, date, ticker, signals):
    """Store analyst signals"""
    for analyst, signal_data in signals.items():
        record = {
            'date': date,
            'ticker': ticker,
            'analyst': analyst,
            'signal': signal_data.get('signal', 'unknown'),
            'confidence': signal_data.get('confidence', 0)
        }
        try:
            supabase.table('analyst_signals').upsert(record).execute()
        except Exception as e:
            print(f"Error storing analyst signal: {e}")

def get_stored_data(supabase, ticker, start_date, end_date):
    """Retrieve stored backtest records and analyst signals for a date range"""
    backtest_data = supabase.table('backtest_records')\
        .select('*')\
        .gte('date', start_date)\
        .lte('date', end_date)\
        .eq('ticker', ticker)\
        .execute()
    
    analyst_signals = supabase.table('analyst_signals')\
        .select('*')\
        .gte('date', start_date)\
        .lte('date', end_date)\
        .eq('ticker', ticker)\
        .execute()
    
    return backtest_data.data, analyst_signals.data

def check_existing_data(supabase, date, ticker):
    """Check if data exists for given date and ticker"""
    response = supabase.table('backtest_records').select('*')\
        .eq('date', date)\
        .eq('ticker', ticker)\
        .execute()
    return len(response.data) > 0

def verify_tables(supabase):
    """Verify database tables exist and are accessible"""
    random_number_string = str(random.randint(1, 9000))
    test_record = {
        'date': '2025-01-01',
        'ticker': random_number_string,
        'action': random_number_string,
        'quantity': 0,
        'price': 0,
        'shares_owned': 0,
        'position_value': 0,
        'bullish_count': 0,
        'bearish_count': 0,
        'neutral_count': 0,
        'total_value': 0,
        'return_pct': 0,
        'cash_balance': 0,
        'total_position_value': 0
    }
    try:
        response = supabase.table('backtest_records').upsert(test_record).execute()
        print("Database tables verified")
        return True
    except Exception as e:
        print(f"Database table verification failed: {e}")
        return False

def reconstruct_portfolio_state(stored_data, initial_capital):
    """Reconstruct portfolio state from stored data"""
    if not stored_data:
        return None
    
    latest_record = max(stored_data, key=lambda x: x['date'])
    return {
        "cash": latest_record['cash_balance'],
        "positions": {latest_record['ticker']: latest_record['shares_owned']},
        "realized_gains": {latest_record['ticker']: 0},  # Cannot reconstruct
        "cost_basis": {latest_record['ticker']: latest_record['shares_owned'] * latest_record['price'] if latest_record['shares_owned'] > 0 else 0}
    }