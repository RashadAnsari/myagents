import sys
import traceback

from .db import ProjectMemoryStore
from .memory_service import ProjectMemoryService, UserMemoryService
from .paths import default_database_path
from .server import create_server


def main() -> None:
    store = None
    try:
        store = ProjectMemoryStore(default_database_path())
        project_service = ProjectMemoryService(store)
        user_service = UserMemoryService(store)
        mcp = create_server(project_service, user_service)
    except Exception as exc:
        print(f"project-memory: initialization failed: {exc}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
    try:
        mcp.run()
    except Exception as exc:
        print(f"project-memory: server error: {exc}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
    finally:
        store.close()


if __name__ == "__main__":
    main()
