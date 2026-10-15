"""a2a_hub — A2A Hub Agent Discovery SDK

Default public registry: https://a2a.jiademin2688.top

Usage:
    from a2a_hub import A2AHubClient

    client = A2AHubClient()
    agents = client.search_agents("translate")
    card = client.get_agent_card(agents[0]["id"])
"""

from .client import A2AHubClient

__version__ = "0.1.0"
__all__ = ["A2AHubClient"]
