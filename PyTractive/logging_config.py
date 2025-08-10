"""
Logging configuration for PyTractive.
"""

import logging
import logging.config
from pathlib import Path


def setup_logging(level: int = logging.INFO, log_file: str = None) -> None:
    """
    Setup comprehensive logging configuration.
    
    Args:
        level: Logging level (e.g., logging.INFO, logging.DEBUG)
        log_file: Optional log file path
    """
    # Create logs directory if needed
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Logging configuration
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'detailed': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'simple': {
                'format': '%(levelname)s - %(message)s'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': level,
                'formatter': 'detailed',
                'stream': 'ext://sys.stdout'
            }
        },
        'loggers': {
            'PyTractive': {
                'level': level,
                'handlers': ['console'],
                'propagate': False
            },
            'requests': {
                'level': logging.WARNING,
                'handlers': ['console'],
                'propagate': False
            },
            'urllib3': {
                'level': logging.WARNING,
                'handlers': ['console'],
                'propagate': False
            }
        },
        'root': {
            'level': logging.WARNING,
            'handlers': ['console']
        }
    }
    
    # Add file handler if log file specified
    if log_file:
        config['handlers']['file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': level,
            'formatter': 'detailed',
            'filename': log_file,
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5
        }
        
        # Add file handler to loggers
        config['loggers']['PyTractive']['handlers'].append('file')
        config['root']['handlers'].append('file')
    
    logging.config.dictConfig(config)
