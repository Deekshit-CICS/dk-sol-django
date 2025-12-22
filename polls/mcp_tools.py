from django_mcp_server import MCPToolset

class CalculatorTools(MCPToolset):
    def add_number(self, a: init, b: int) -> int:
        """
        An MCP tool that adds two numbers together.
        """
        return a + b