import pandas as pd
import numpy as np
from app.utils.logger import logger

class MT5Connector:
    def __init__(self):
        self.is_connected = False
        logger.info("MT5 Connector initialized")
    
    def connect(self):
        self.is_connected = True
        logger.info("MT5 Connected")
        return True
    
    def disconnect(self):
        self.is_connected = False
        logger.info("MT5 Disconnected")
