"""AutoGen integration for A2A Hub.

Expose agents discovered on A2A Hub as AutoGen function tools.

Install:
    pip install pyautogen

Usage:
    import autogen
    from a2a_hub_tool import a2a_search_agents, a2a_send_message

    config_list = [{"model": "gpt-4o-mini", "api_key": "..."}]
    assistant = autogen.AssistantAgent(
        name="assistant",
        llm_config={
            "config_list": config_list,
            "functions": [
                {
                    "name": "a2a_search_agents",
                    "description": "Search AI agents on the A2A Hub public registry by keyword",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string", "description": "Keyword, e.g. translate, weather"}},
                        "required": ["query"],
                    },
                },
            ],
        },
    )
    user_proxy = autogen.UserProxyAgent(
        name="user_proxy",
        code_execution_config=False,
        function_map={"a2a_search_agents": a2a_search_agents},
    )
"""

import json
import os
import urllib.request
import urllib.parse

HUB_URL = os.environ.get("A2A_HUB_URL", "https://a2a.jiademin2688.top")


def a2a_search_agents(query: str) -> str:
    """Search for AI agents on the A2A Hub public registry by keyword.

    Args:
        query: Keyword to search for, e.g. 'translate', 'weather', 'strategy'.

    Returns:
        JSON string with matching agents (id, name, description, skills, url).
    """
    qs = urllib.parse.urlencode({"search": query})
    req = urllib.request.Request(
        HUB_URL + f"/api/agents?{qs}",
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
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


def a2a_send_message(agent_url: str, message: str) -> str:
    """Send a text message to a remote AI agent via the A2A protocol.

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
                "messageId": "autogen-1",
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


if __name__ == "__main__":
    print(a2a_search_agents("translate"))
