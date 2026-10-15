from db import Base, engine
from models import session, message, user, project, template  # noqa: F401 - registers tables
from mcp_client.models import MCPServer  # noqa: F401 - registers MCP table

if __name__ == "__main__":
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Done ✅")
