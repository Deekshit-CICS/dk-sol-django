from mcp_server import ModelQueryToolset
from polls.mcp_tools import CalculatorTools

server = ModelQueryToolset()
server.register_toolset(CalculatorTools())
server.run()