try:
    from mcp.server.fastmcp import FastMCP
    print("\n✅ FastMCP available")
except ImportError:
    print("\n❌ FastMCP NOT available")

try:
    from mcp.server import Server
    print("✅ mcp.server.Server available")
except ImportError:
    print("❌ mcp.server.Server NOT available")
