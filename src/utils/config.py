"""Configuration management for saving and loading previous choices"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional


class Config:
    def __init__(self):
        self.config_dir = Path.home() / ".ai-hedge-fund"
        self.config_file = self.config_dir / "config.json"
        self.config_dir.mkdir(exist_ok=True)
        
    def save_selection(self, analysts: List[str], model_name: str, model_provider: str, use_ollama: bool = False):
        """Save the current selection for next time"""
        config_data = {
            "analysts": analysts,
            "model_name": model_name,
            "model_provider": model_provider,
            "use_ollama": use_ollama
        }
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save configuration: {e}")
    
    def load_selection(self) -> Optional[Dict]:
        """Load the previous selection"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load configuration: {e}")
        return None
    
    def has_previous_selection(self) -> bool:
        """Check if there's a previous selection available"""
        return self.config_file.exists()
    
    def get_previous_analysts(self) -> List[str]:
        """Get the previously selected analysts"""
        config = self.load_selection()
        return config.get("analysts", []) if config else []
    
    def get_previous_model(self) -> Dict[str, str]:
        """Get the previously selected model"""
        config = self.load_selection()
        if config:
            return {
                "name": config.get("model_name", ""),
                "provider": config.get("model_provider", "")
            }
        return {"name": "", "provider": ""}
    
    def get_previous_ollama_flag(self) -> bool:
        """Get the previous ollama flag"""
        config = self.load_selection()
        return config.get("use_ollama", False) if config else False
    
    def get_config_summary(self) -> str:
        """Get a summary of the previous configuration"""
        config = self.load_selection()
        if not config:
            return "No previous configuration found"
        
        analysts = config.get("analysts", [])
        model_name = config.get("model_name", "Unknown")
        model_provider = config.get("model_provider", "Unknown")
        use_ollama = config.get("use_ollama", False)
        
        analyst_names = [analyst.replace('_', ' ').title() for analyst in analysts]
        model_type = "Ollama" if use_ollama else model_provider
        
        return f"{len(analysts)} analysts ({', '.join(analyst_names[:3])}{'...' if len(analysts) > 3 else ''}), {model_type} model: {model_name}"


# Global config instance
_config = Config()

def get_config() -> Config:
    """Get the global configuration instance"""
    return _config
