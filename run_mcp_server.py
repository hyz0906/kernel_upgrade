from src.mcp_server.server import main

if __name__ == "__main__":
    print("Starting MCP Server...")
    # FastMCP.run() typically uses sys.argv to determine mode (stdio/sse)
    # Default is usually stdio if no args.
    # To run as SSE (standalone http), one might need specific args or method.
    # But for now, we just expose the entry point.
    main()
