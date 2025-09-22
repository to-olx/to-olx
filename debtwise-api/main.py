"""
Entry point for running the application with uvicorn.
"""

import uvicorn

from app.core.config import settings


def main():
    """Run the application using uvicorn."""
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
