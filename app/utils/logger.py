"""
Logging utility cho toàn bộ ứng dụng
Sử dụng structured logging với JSON format
"""

import logging
import sys
from pathlib import Path
from pythonjsonlogger import jsonlogger
from colorlog import ColoredFormatter
from app.core.config import settings


class Logger:
    """Custom logger với JSON format và colored console output"""
    
    _loggers = {}
    
    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """
        Lấy hoặc tạo logger mới
        
        Args:
            name: Tên của logger (thường là __name__ của module)
            
        Returns:
            logging.Logger instance
        """
        if name in Logger._loggers:
            return Logger._loggers[name]
        
        logger = logging.getLogger(name)
        logger.setLevel(settings.log_level)
        
        # Xóa handlers cũ nếu có
        logger.handlers.clear()
        
        # Console handler với màu sắc
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(settings.log_level)
        
        # Colored formatter cho console
        console_format = (
            "%(log_color)s%(levelname)-8s%(reset)s "
            "%(cyan)s%(name)s%(reset)s "
            "%(message)s"
        )
        console_formatter = ColoredFormatter(
            console_format,
            log_colors={
                'DEBUG': 'white',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # File handler với JSON format
        log_file = Path(settings.log_file_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(settings.log_level)
        
        # JSON formatter cho file
        json_format = '%(asctime)s %(name)s %(levelname)s %(message)s'
        json_formatter = jsonlogger.JsonFormatter(json_format)
        file_handler.setFormatter(json_formatter)
        logger.addHandler(file_handler)
        
        # Prevent propagation to root logger
        logger.propagate = False
        
        Logger._loggers[name] = logger
        return logger


# Convenience function
def get_logger(name: str) -> logging.Logger:
    """Shortcut để lấy logger"""
    return Logger.get_logger(name)