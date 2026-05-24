import logging
import sys

from .db import AgentMemoryStore
from .memory_service import ProjectMemoryService, UserMemoryService
from .paths import default_database_path
from .server import create_server

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)

logger = logging.getLogger(__name__)


def main() -> None:
    store = None
    try:
        store = AgentMemoryStore(default_database_path())
        project_service = ProjectMemoryService(store)
        user_service = UserMemoryService(store)
        mcp = create_server(project_service, user_service)
    except Exception as exc:
        logger.exception("initialization failed: %s", exc)
        sys.exit(1)
    try:
        mcp.run()
    except Exception as exc:
        logger.exception("server error: %s", exc)
        sys.exit(1)
    finally:
        store.close()


if __name__ == "__main__":
    main()
