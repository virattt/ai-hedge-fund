# src/performance/metrics.py

def calculate_sharpe_ratio(returns, risk_free_rate=0.0):
    """
    Calculate the Sharpe ratio of an investment.
    
    Args:
        returns: List or array of returns
        risk_free_rate: The risk-free rate of return
        
    Returns:
        The Sharpe ratio
    """
    import numpy as np
    
    # Calculate the average return
    mean_return = np.mean(returns)
    
    # Calculate the standard deviation of returns
    std_dev = np.std(returns)
    
    # Calculate and return the Sharpe ratio
    if std_dev == 0:
        return 0
    return (mean_return - risk_free_rate) / std_dev

def calculate_max_drawdown(returns):
    """
    Calculate the maximum drawdown of an investment.
    
    Args:
        returns: List or array of returns
        
    Returns:
        The maximum drawdown as a positive percentage
    """
    import numpy as np
    
    # Convert returns to cumulative returns
    cum_returns = np.cumprod(1 + np.array(returns))
    
    # Calculate the running maximum
    running_max = np.maximum.accumulate(cum_returns)
    
    # Calculate the drawdown
    drawdown = (running_max - cum_returns) / running_max
    
    # Return the maximum drawdown
    return np.max(drawdown)

if __name__ == "__main__":
    # Example usage
    test_returns = [0.01, 0.02, 0.03, 0.01, -0.01, 0.02, -0.03]
    
    print(f"Sharpe Ratio: {calculate_sharpe_ratio(test_returns)}")
    print(f"Maximum Drawdown: {calculate_max_drawdown(test_returns)}")
    print("Performance metrics module test complete")