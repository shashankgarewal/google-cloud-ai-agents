from datetime import datetime
from zoneinfo import ZoneInfo
import yaml
from pathlib import Path

# Path to YAML file storing agent state
BASE_DIR = Path(__file__).resolve().parent.parent
INFO_PATH = BASE_DIR / "artifact" / "info.yaml"

INFO_PATH.parent.mkdir(parents=True, exist_ok=True)
INFO_PATH.touch(exist_ok=True)

def build_grounding() -> str:
    """Generate and store system grounding context"""
    
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    date_str = now.strftime('%A, %Y-%m-%d')
    
    grounding_context = f"""
You are part of the Farmer Assistant suite.
Today's Date: {date_str} (India)
"""
    # 
    
    # overwrite existing data
    data = {"system_grounding": grounding_context}
    with open(INFO_PATH, "w") as f:
        yaml.dump(data, f)
    
    return grounding_context


def store_info(key: str, value, mode: str = "w"):
    """Store/update a key in YAML artifact"""
    
    data = {}
    if INFO_PATH.exists():
        with open(INFO_PATH, "r") as f:
            data = yaml.safe_load(f) or {}
    
    data[key] = value
    
    with open(INFO_PATH, "w") as f:
        yaml.dump(data, f)


def load_info() -> dict:
    """Load stored YAML data"""
    
    if not INFO_PATH.exists():
        return {}
    
    with open(INFO_PATH, "r") as f:
        return yaml.safe_load(f) or {}