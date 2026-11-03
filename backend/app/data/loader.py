import pandas as pd
import json
import os
from typing import Dict, Any


class DataLoader:
    def __init__(self, data_dir: str = "../data"):
        self.data_dir = data_dir
    
    def load_csv(self, filename: str) -> pd.DataFrame:
        filepath = os.path.join(self.data_dir, filename)
        return pd.read_csv(filepath)
    
    def load_json(self, filename: str) -> Dict[Any, Any]:
        filepath = os.path.join(self.data_dir, filename)
        with open(filepath, 'r') as f:
            return json.load(f)
    
    def load_all(self) -> Dict[str, Any]:
        return {
            'actuals': self.load_csv('actuals.csv'),
            'budget': self.load_csv('budget.csv'),
            'forecast': self.load_csv('forecast.csv'),
            'financial_drivers': self.load_csv('financial_drivers.csv'),
            'cash_flow': self.load_csv('cash_flow.csv'),
            'scenarios': self.load_json('scenarios.json')
        }
