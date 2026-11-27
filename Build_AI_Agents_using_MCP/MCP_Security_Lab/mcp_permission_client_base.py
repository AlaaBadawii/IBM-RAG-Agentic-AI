import json
from contextlib import AsyncExitStack
from datetime import datetime
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import AnyUrl


class MCPPermissionClient:
    """Base MCP client with permission checking and sudit logging."""

    def __init__(
        self, server_script: str, permission_file: str = "data/permissions.json"
    ):
        self.server_script = server_script
        self.permission_file = Path(permission_file)
        self.permission_file.parent.mkdir(exist_ok=True)
        self.audit_log_file = self.permission_file.parent / "audit.log"
        self.session = None
        self.exit_stack = AsyncExitStack()
        self._connected = False
        self.permissions = self.load_permissions()

    async def connect(self):
        """Connect to the MCP server."""
        if self._connected:
            return

        server_parmas = StdioServerParameters(
            command="python", args=[self.server_script], env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_parmas)
        )

        read, write = stdio_transport

        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read, write)
        )

        await self.session.initialize()
        self._connected = True

    def load_permissions(self):
        """Load permissions from the JSON file."""
        if self.permission_file.exists():
            return json.loads(self.permission_file.read_text())

        return {
            "read_file": "allow",
            "write_file": "ask",
            "delete_file": "deny",
            "execute_command": "deny",
        }

    def save_permissions(self):
        """Save permissions to the JSON file."""
        self.permission_file.write_text(json.dumps(self.permissions, indent=4))

    def check_permission(self, tool_name: str, args: dict) -> str:
        """Check the permission for a given operation."""
        arg_key = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
        if arg_key in self.permissions:
            return self.permissions[arg_key]

        return self.permissions.get(tool_name, "ask")

    def log_audit(self, operation: str, decision: str, reason: str = ""):
        """Log an operation to the audit log."""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] {operation} - Decision: {decision}"
        if reason:
            log_entry += f" - Reason: {reason}"
        log_entry += "\n"
        with open(self.audit_log_file, "a") as f:
            f.write(log_entry)

    async def request_elicitation(self, schema: dict, description: str) -> dict:
        """
        Request structured user input via elicitation.
        This is a conceptual implementation. In production,
        this would trigger a UI dialog and wait for user response.

        Args:
            schema: JSON schema for the required input
            description: Human-readable description of what's needed

        Returns:
            Dictionary with user's input
        """
        print(f"\nElicitation requestes: {description}")
        print(f"Schema: {json.dumps(schema, indent=2)}")
        print("(Conceptual - automatic approval demo)")

        return {}

    async def list_tools(self):
        """List all available tools from the server."""
        await self.connect()
        assert self.session is not None
        result = await self.session.list_tools()

        return result.tools

    async def call_tool_with_permission(
        self, tool_name: str, args: dict | None = None, approved: bool = False
    ):
        """Call a tool after checking its permissions."""
        await self.connect()

        if args is None:
            args = {}

        permission = self.check_permission(tool_name, args)

        if permission == "deny":
            self.log_audit(f"TOOL: {tool_name}", "DENIED", "Policy: deny")
            return [
                type("obj", (), {"text": f"Permission denied for toll {tool_name}"})
            ]

        if permission == "ask" and not approved:
            # Log that approval was requested
            self.log_audit(f"TOOL: {tool_name}", "ASK", "Awaiting approval")

            # Return approval request message
            approval_msg = f"""Permission required for tool: {tool_name}
Arguments: {json.dumps(args, indent=2)}

This tool requires approval before execution.
Please approve this operation in the GUI to proceed."""
            return [type("obj", (), {"text": approval_msg})]

        # Execute the tool
        self.log_audit(f"TOOL: {tool_name}", "ALLOWED", f"Policy: {permission}")
        assert self.session is not None
        result = await self.session.call_tool(tool_name, arguments=args)
        return result.content

    async def list_resources(self):
        """List all avialable resources from the server."""
        await self.connect()
        assert self.session is not None
        result = await self.session.list_resources()
        return result.resources

    async def read_resource(self, uri: str):
        """Read a resource by uri."""
        await self.connect()
        assert self.session is not None
        result = await self.session.read_resource(uri=AnyUrl(uri))
        return result.contents

    async def list_prompts(self):
        """List all available prompts from the server."""
        await self.connect()
        assert self.session is not None
        result = await self.session.list_prompts()
        return result.prompts

    async def get_prompt(self, prompt_name: str, arguments: dict | None = None):
        """Get a rendered prompt template."""
        await self.connect()
        assert self.session is not None
        if arguments is None:
            arguments = {}
        result = await self.session.get_prompt(name=prompt_name, arguments=arguments)
        return result.messages


    async def cleanup(self):
        """Clean up recources."""
        await self.exit_stack.aclose()

    