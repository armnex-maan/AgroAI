"""Run the API in dev mode: bootstrap SQLite schema, then uvicorn on 0.0.0.0:8000
(0.0.0.0 so ESP32 boards on the LAN can reach it)."""
import devenv

devenv.apply()

import uvicorn  # noqa: E402
from scripts.dev_bootstrap import main as bootstrap  # noqa: E402

if __name__ == "__main__":
    bootstrap()
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
