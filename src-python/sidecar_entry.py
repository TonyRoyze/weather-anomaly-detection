import os

import uvicorn

from main import app


def main() -> None:
    host = os.getenv("ANOMALIZE_HOST", "127.0.0.1")
    port = int(os.getenv("ANOMALIZE_PORT", "8000"))
    log_level = os.getenv("ANOMALIZE_LOG_LEVEL", "warning")

    uvicorn.run(app, host=host, port=port, log_level=log_level)


if __name__ == "__main__":
    main()

