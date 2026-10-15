"""CrewAI integration for A2A Hub.

Expose agents discovered on A2A Hub as CrewAI Tools.

Install:
    pip install crewai crewai-tools

Usage:
    from a2a_hub_tool import A2ASearchTool, A2ASendMessageTool
    from crewai import Agent, Task, Crew

    researcher = Agent(
        role="Agent Researcher",
        goal="Find useful AI agents on A2A Hub",
        backstory="You discover remote agents via the public A2A registry.",
        tools=[A2ASearchTool()],
    )
    crew = Crew(agents=[researcher], tasks=[...])
"""

import json
import os
import urllib.request
import urllib.parse

from crewai.tools import BaseTool

HUB_URL = os.environ.get("A2A_HUB_URL", "https://a2a.jiademin2688.top")


class A2ASearchTool(BaseTool):
    """Search for AI agents on the A2A Hub public registry."""

    name: str = "a2a_search_agents"
    description: str = (
        "Search for AI agents on the A2A Hub public registry by keyword. "
        "Input: a keyword such as 'translate', 'weather', 'strategy'. "
        "Returns a JSON list of matching agents with id, name, description, skills and url."
    )

    def _run(self, query: str) -> str:
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


class A2ASendMessageTool(BaseTool):
    """Send a message to an AI agent via the A2A protocol (JSON-RPC message/send)."""

    name: str = "a2a_send_message"
    description: str = (
        "Send a text message to a remote AI agent via the A2A protocol. "
        "Input: JSON object with keys 'agent_url' (the A2A endpoint from search results) "
        "and 'message' (the text to send). Returns the agent's reply."
    )

    def _run(self, args_json: str) -> str:
        try:
            args = json.loads(args_json)
        except json.JSONDecodeError:
            return "Invalid input: expected a JSON object with 'agent_url' and 'message' keys."
        agent_url = args.get("agent_url", "")
        message = args.get("message", "")
        if not agent_url or not message:
            return "Both 'agent_url' and 'message' are required."

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": message}],
                    "messageId": "crew-1",
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
    print(A2ASearchTool()._run("translate"))
