"""Export actual FastAPI OpenAPI for frontend type generation; no DB/network."""
import json
from pathlib import Path
from backend.main import create_app

if __name__=="__main__":
    path=Path(__file__).resolve().parents[1]/"tmp/openapi-v2.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(create_app().openapi(),ensure_ascii=False,indent=2),encoding="utf-8")
    print(path)
