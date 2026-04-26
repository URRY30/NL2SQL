import uvicorn

from app.core.config import get_settings


settings = get_settings()

config = uvicorn.Config(
    "app.main:app",
    host=settings.app_host,
    port=settings.app_port,
    reload=False,
    log_level="info",
)
server = uvicorn.Server(config)
server.run()
