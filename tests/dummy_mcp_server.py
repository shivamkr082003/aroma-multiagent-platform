"""Minimal STDIO MCP server used by the tests."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("dummy")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


if __name__ == "__main__":
    mcp.run()
