from dataclasses import dataclass
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("DATA_DIR", str(ROOT / "data")))
    db_path: Path = Path(os.getenv("DB_PATH", str(ROOT / "runtime" / "desk.db")))
    payswift_base_url: str = os.getenv("PAYSWIFT_BASE_URL", "http://localhost:8081")
    auto_pay_limit: int = int(os.getenv("AUTO_PAY_LIMIT", "200"))
    max_retries: int = int(os.getenv("MAX_WORKFLOW_RETRIES", "2"))

settings = Settings()
