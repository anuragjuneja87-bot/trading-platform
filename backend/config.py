"""
Configuration Management for Trading Platform
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration"""
    POLYGON_API_KEY = os.getenv('POLYGON_API_KEY', '')
    CACHE_DURATION = 30  # seconds
    PORT = 5001
    DEBUG = True
    HOST = '0.0.0.0'
    
    # API Rate limiting (future)
    RATE_LIMIT_ENABLED = False
    
    # Feature flags
    FEATURES = {
        'dashboard': True,
        'leveraged': True,
        'backtesting': False,  # Coming soon
        'portfolio': False,    # Coming soon
    }

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    CACHE_DURATION = 30

class ProductionConfig(Config):
    """Production configuration (future)"""
    DEBUG = False
    CACHE_DURATION = 60
    RATE_LIMIT_ENABLED = True

# Default to development
config = DevelopmentConfig()