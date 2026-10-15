"""A2A Hub client — discover agents on the default public registry.

Default registry: https://a2a.jiademin2688.top
"""

import json
import urllib.request
import urllib.parse
import urllib.error

DEFAULT_HUB_URL = "https://a2a.jiademin2688.top"


class A2AHubClient:
    """Client for the A2A Hub public agent registry.

    Args:
        hub_url: Registry base URL. Defaults to the public A2A Hub instance.
        timeout: Request timeout in seconds.
    """

    def __init__(self, hub_url: str = DEFAULT_HUB_URL, timeout: int = 30):
        self.hub_url = hub_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str) -> dict:
        url = self.hub_url + path
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code} from {url}: {e.read().decode('utf-8', errors='replace')}") from e

    def _post(self, path: str, payload: dict) -> dict:
        url = self.hub_url + path
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code} from {url}: {e.read().decode('utf-8', errors='replace')}") from e

    # ---------------- Discovery API ----------------

    def list_agents(self) -> list:
        """List all registered agents."""
        return self._get("/api/agents").get("agents", [])

    def search_agents(self, search: str = "", skill: str = "") -> list:
        """Search agents by keyword and/or skill.

        Args:
            search: Free-text keyword matched against the whole agent card.
            skill: Skill id or name to filter by.
        """
        params = {}
        if search:
            params["search"] = search
        if skill:
            params["skill"] = skill
        qs = ("?" + urllib.parse.urlencode(params)) if params else ""
        return self._get("/api/agents" + qs).get("agents", [])

    def get_agent(self, agent_id: str) -> dict:
        """Get agent details by id."""
        return self._get(f"/api/agents/{agent_id}")

    def get_agent_card(self, agent_id: str) -> dict:
        """Get the full Agent Card of a registered agent."""
        return self._get(f"/api/agents/{agent_id}/card")

    def check_agent(self, agent_id: str) -> dict:
        """Trigger a health check for an agent (probes its agent-card endpoint)."""
        return self._post(f"/api/agents/{agent_id}/check", {})

    # ---------------- Registry API ----------------

    def register_agent_card(self, agent_card: dict) -> dict:
        """Register an agent by submitting its agent_card object."""
        return self._post("/api/agents", {"agent_card": agent_card})

    def register_agent_card_url(self, card_url: str) -> dict:
        """Register an agent by its agent-card URL (auto-fetched by the hub)."""
        return self._post("/api/agents", {"agent_card_url": card_url})

    # ---------------- Platform card ----------------

    def platform_card(self) -> dict:
        """Get the Agent Card of the hub itself."""
        return self._get("/.well-known/agent-card.json")
