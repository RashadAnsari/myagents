import logging
import os
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
    agent_store = None
    try:
        disable_project_memory = os.environ.get("DISABLE_PROJECT_MEMORY", "").lower() in ("1", "true", "yes")
        agent_store = AgentMemoryStore(default_database_path())
        project_service = ProjectMemoryService(agent_store)
        user_service = UserMemoryService(agent_store)
        mcp = create_server(project_service, user_service, disable_project_memory=disable_project_memory)
    except Exception as exc:
        logger.exception("initialization failed: %s", exc)
        sys.exit(1)
    try:
        mcp.run()
    except Exception as exc:
        logger.exception("server error: %s", exc)
        sys.exit(1)
    finally:
        agent_store.close()


if __name__ == "__main__":
    main()
