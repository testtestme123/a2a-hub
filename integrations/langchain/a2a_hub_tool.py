"""LangChain integration for A2A Hub.

Expose agents discovered on A2A Hub as LangChain Tools.

Install:
    pip install langchain langchain-community

Usage:
    from a2a_hub_tool import make_a2a_search_tool, make_a2a_call_tool

    tools = [
        make_a2a_search_tool(),
        make_a2a_call_tool(),
    ]
    # Use with any LangChain agent that accepts tools.
"""

import json
import os
import urllib.request

from langchain.tools import tool

HUB_URL = os.environ.get("A2A_HUB_URL", "https://a2a.jiademin2688.top")


def _hub_get(path: str) -> dict:
    req = urllib.request.Request(HUB_URL + path, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _hub_jsonrpc(method: str, text: str) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": text}],
                "messageId": "lc-1",
            }
        },
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        HUB_URL + "/a2a/jsonrpc",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def make_a2a_search_tool():
    """Create a LangChain Tool that searches agents on A2A Hub."""

    @tool("a2a_search_agents")
    def a2a_search_agents(query: str) -> str:
        """Search for AI agents on the A2A Hub public registry by keyword.

        Args:
            query: Keyword to search for, e.g. 'translate', 'weather', 'strategy'.

        Returns:
            JSON string with matching agents (id, name, description, skills, url).
        """
        import urllib.parse

        qs = urllib.parse.urlencode({"search": query})
        result = _hub_get(f"/api/agents?{qs}")
        agents = [
            {
                "id": a["id"],
                "name": a.get("name"),
                "description": a.get("description"),
                "skills": [s.get("name") for s in (a.get("skills") or [])],
                "url": a.get("url"),
            }
            for a in result.get("agents", [])
        ]
        return json.dumps(agents, ensure_ascii=False)

    return a2a_search_agents


def make_a2a_call_tool():
    """Create a LangChain Tool that sends a message to an agent via A2A protocol."""

    @tool("a2a_send_message")
    def a2a_send_message(agent_url: str, message: str) -> str:
        """Send a message to an AI agent via the A2A protocol (JSON-RPC message/send).

        Args:
            agent_url: The A2A endpoint URL of the target agent (from a2a_search_agents).
            message: The text message to send.

        Returns:
            The agent's reply text, or the raw JSON-RPC result.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": message}],
                    "messageId": "lc-1",
                }
            },
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            agent_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        try:
            parts = result["result"]["status"]["message"]["parts"]
            return " ".join(p.get("text", "") for p in parts if p.get("text"))
        except (KeyError, TypeError):
            return json.dumps(result, ensure_ascii=False)

    return a2a_send_message


if __name__ == "__main__":
    search = make_a2a_search_tool()
    print(search.invoke({"query": "translate"}))
