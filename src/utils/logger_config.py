import os
import time
import re
import logging
from colorama import Fore, Style

# 状态图标
SUCCESS_ICON = "✓"
ERROR_ICON = "✗"
WAIT_ICON = "⟳"

# 全局 logger 实例
_global_logger = None

class ColorFormatter(logging.Formatter):
    def format(self, record):
        message = super().format(record)
        # 使用正则表达式去除颜色控制字符
        message_without_color = re.sub(r'\x1b\[[0-9;]*m', '', message)
        return message_without_color

def setup_logger(name='stock_agent', log_level=logging.INFO):
    """
    设置全局日志记录器
    
    Args:
        name: 日志记录器名称
        log_level: 日志级别
        
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    global _global_logger
    
    # 如果全局 logger 已经初始化，直接返回
    if _global_logger is not None:
        return _global_logger
    
    # 创建 logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # 移除所有现有的处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 创建日志目录
    log_dir = os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 设置文件处理器
    log_file = os.path.join(log_dir, f'{name}_{time.strftime("%Y%m%d_%H%M")}.log')
    print(f"Creating log file at: {log_file}")
    
    try:
        file_handler = logging.FileHandler(log_file, encoding='utf-8', mode='a')
        file_handler.setLevel(log_level)
        print("Successfully created file handler")
    except Exception as e:
        print(f"Error creating file handler: {str(e)}")
        return None
    
    # 设置控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    # 设置日志格式
    blank_formatter = ColorFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    color_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(blank_formatter)
    console_handler.setFormatter(color_formatter)
    
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # 立即测试日志记录
    logger.info("Logger initialization completed")
    logger.info(f"{name} logging system started")
    
    
    # 保存为全局 logger
    _global_logger = logger

    return logger

def get_logger():
    """
    获取全局日志记录器，如果未初始化则先初始化
    
    Returns:
        logging.Logger: 全局日志记录器
    """
    global _global_logger
    if _global_logger is None:
        return setup_logger()
    return _global_logger

# # 初始化全局 logger
# logger = setup_logger()