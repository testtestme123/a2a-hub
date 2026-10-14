#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, sys, urllib.request, urllib.error

DEFAULT_HUB = "https://a2a.jiademin2688.top"

def register_with_card(hub_url, name, description, url, skills_raw):
    skills = []
    for s in skills_raw:
        parts = s.split(":", 2)
        if len(parts) < 2: continue
        skill = {"id": parts[0], "name": parts[1]}
        if len(parts) >= 3: skill["description"] = parts[2]
        skills.append(skill)
    if not skills: skills = [{"id": "default", "name": "General", "description": "Default skill"}]
    payload = {"agent_card": {"name": name, "description": description, "url": url, "skills": skills}}
    return _post(hub_url, payload)

def register_with_card_url(hub_url, card_url):
    return _post(hub_url, {"agent_card_url": card_url})

def _post(hub_url, payload):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(hub_url.rstrip("/") + "/api/agents", data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            agent_id = result.get("id")
            print("[OK] Registration successful!")
            print(f"   Agent ID: {agent_id}")
            print(f"   Name: {result.get(chr(97)+chr(103)+chr(101)+chr(110)+chr(116)+chr(95)+chr(99)+chr(97)+chr(114)+chr(100), {}).get(chr(110)+chr(97)+chr(109)+chr(101))}")
            print(f"   Status: {result.get(chr(115)+chr(116)+chr(97)+chr(116)+chr(117)+chr(115))}")
            print(f"\\n   Details: {hub_url.rstrip(chr(47))}/api/agents/{agent_id}")
            return 0
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"[FAIL] HTTP {e.code}: {body}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        return 1

def main():
    parser = argparse.ArgumentParser(description="A2A Hub Registration Script")
    parser.add_argument("--hub", default=DEFAULT_HUB, help="A2A Hub URL")
    parser.add_argument("--url", help="Agent A2A endpoint URL")
    parser.add_argument("--name", help="Agent name")
    parser.add_argument("--description", default="", help="Agent description")
    parser.add_argument("--skill", action="append", default=[], help="Skill: id:name[:description]")
    parser.add_argument("--card-url", help="Agent Card URL for auto-fetch")
    args = parser.parse_args()
    if args.card_url:
        return register_with_card_url(args.hub, args.card_url)
    if not args.url or not args.name:
        parser.error("--url and --name required (or use --card-url)")
    return register_with_card(args.hub, args.name, args.description, args.url, args.skill)

if __name__ == "__main__":
    sys.exit(main())
