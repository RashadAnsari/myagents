import sys

from .db import ProjectMemoryStore
from .memory_service import ProjectMemoryService, UserMemoryService
from .paths import default_database_path
from .server import create_server


def main() -> None:
    store = ProjectMemoryStore(default_database_path())
    project_service = ProjectMemoryService(store)
    user_service = UserMemoryService(store)
    mcp = create_server(project_service, user_service)
    try:
        mcp.run()
    except Exception as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
