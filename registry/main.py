"""A2A Hub 注册中心服务
遵循 Google A2A 标准：Agent Card、注册中心 REST API、A2A JSON-RPC 协议端点
"""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
import datetime
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, Response

DB_PATH = "/data/registry.db"
PLATFORM_URL = "https://a2a.jiademin2688.top"

app = FastAPI(title="A2A Hub Registry", version="1.0.0")


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                card TEXT NOT NULL,
                status TEXT DEFAULT 'unknown',
                created_at REAL NOT NULL
            )
            """
        )


init_db()


def platform_card() -> dict:
    return {
        "name": "A2A Hub",
        "description": "A2A 发布注册平台：遵循 Google A2A 协议的 Agent 注册与发现中心，支持 Agent 注册、技能搜索、健康检查与 A2A 协议消息互通。",
        "url": f"{PLATFORM_URL}/a2a/jsonrpc",
        "provider": {"organization": "A2A Hub", "url": PLATFORM_URL},
        "version": "1.0.0",
        "protocolVersion": "0.3.0",
        "documentationUrl": f"{PLATFORM_URL}/",
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": True,
        },
        "defaultInputModes": ["text", "application/json"],
        "defaultOutputModes": ["text", "application/json"],
        "skills": [
            {
                "id": "agent.register",
                "name": "Agent 注册",
                "description": "注册新 Agent：提交 agent_card 对象或 agent_card_url 自动拉取校验",
                "tags": ["registry", "publish"],
            },
            {
                "id": "agent.search",
                "name": "Agent 搜索发现",
                "description": "按关键词或技能标签搜索已注册 Agent",
                "tags": ["registry", "discovery"],
            },
            {
                "id": "agent.check",
                "name": "健康检查",
                "description": "探测已注册 Agent 的在线状态",
                "tags": ["registry", "health"],
            },
        ],
    }


# ---------------- Agent Card 标准路径 ----------------
@app.get("/.well-known/agent-card.json")
async def agent_card():
    return platform_card()


@app.get("/.well-known/agent.json")
async def agent_card_alias():
    return platform_card()


# ---------------- 注册中心 REST API ----------------
REQUIRED_FIELDS = ["name", "description", "url", "skills"]


async def validate_and_get_card(payload: dict) -> dict:
    if "agent_card" in payload:
        card = payload["agent_card"]
        if not isinstance(card, dict):
            raise HTTPException(400, "agent_card 必须是对象")
    elif "agent_card_url" in payload:
        url = payload["agent_card_url"]
        try:
            async with httpx.AsyncClient(timeout=15, verify=False) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                card = resp.json()
        except Exception as exc:
            raise HTTPException(400, f"拉取 agent_card_url 失败: {exc}")
    else:
        raise HTTPException(400, "必须提供 agent_card 或 agent_card_url")

    missing = [f for f in REQUIRED_FIELDS if not card.get(f)]
    if missing:
        raise HTTPException(400, f"agent_card 缺少必填字段: {', '.join(missing)}")
    if not isinstance(card.get("skills"), list) or len(card["skills"]) == 0:
        raise HTTPException(400, "skills 必须是非空数组")
    return card


@app.post("/api/agents", status_code=201)
async def register_agent(payload: dict):
    card = await validate_and_get_card(payload)
    agent_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO agents (id, card, status, created_at) VALUES (?, ?, ?, ?)",
            (agent_id, json.dumps(card, ensure_ascii=False), "unknown", time.time()),
        )
    return {"id": agent_id, "agent_card": card, "status": "registered"}


@app.get("/api/agents")
async def list_agents(search: str = "", skill: str = ""):
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM agents ORDER BY created_at DESC").fetchall()
    agents = []
    for row in rows:
        card = json.loads(row["card"])
        if search:
            text = json.dumps(card, ensure_ascii=False).lower()
            if search.lower() not in text:
                continue
        if skill:
            skill_ids = [s.get("id", "") for s in card.get("skills", [])]
            skill_names = [s.get("name", "") for s in card.get("skills", [])]
            if skill not in skill_ids and skill not in skill_names:
                continue
        agents.append(
            {
                "id": row["id"],
                "name": card.get("name"),
                "description": card.get("description"),
                "url": card.get("url"),
                "skills": card.get("skills"),
                "status": row["status"],
                "created_at": row["created_at"],
            }
        )
    return {"agents": agents, "total": len(agents)}


@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Agent 不存在")
    card = json.loads(row["card"])
    return {
        "id": row["id"],
        "name": card.get("name"),
        "description": card.get("description"),
        "url": card.get("url"),
        "skills": card.get("skills"),
        "status": row["status"],
        "created_at": row["created_at"],
    }


@app.get("/api/agents/{agent_id}/card")
async def get_agent_card(agent_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT card FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Agent 不存在")
    return json.loads(row["card"])


@app.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: str):
    with get_db() as conn:
        cur = conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "Agent 不存在")
    return {"status": "deleted", "id": agent_id}


@app.post("/api/agents/{agent_id}/check")
async def check_agent(agent_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT card FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Agent 不存在")
    card = json.loads(row["card"])
    base_url = card.get("url", "").rstrip("/")
    parsed = base_url.split("/")[:3]
    card_url = "/".join(parsed) + "/.well-known/agent-card.json"
    status = "offline"
    try:
        async with httpx.AsyncClient(timeout=10, verify=False) as client:
            resp = await client.get(card_url)
            if resp.status_code == 200:
                status = "online"
    except Exception:
        status = "offline"
    with get_db() as conn:
        conn.execute("UPDATE agents SET status = ? WHERE id = ?", (status, agent_id))
    return {"id": agent_id, "status": status, "checked_url": card_url}


# ---------------- A2A 协议端点（JSON-RPC 2.0） ----------------
TASKS: dict[str, dict] = {}


def rpc_ok(req_id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def rpc_err(req_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def extract_text(message: dict) -> str:
    parts = message.get("parts", [])
    texts = []
    for p in parts:
        if isinstance(p, dict):
            if p.get("kind") == "text" and p.get("text"):
                texts.append(p["text"])
            elif "text" in p and p["text"]:
                texts.append(p["text"])
    return " ".join(texts).strip()


def build_task(task_id: str, context_id: str, user_text: str) -> dict:
    reply = (
        f"A2A Hub 已收到您的消息：{user_text}。"
        "我是 A2A 发布注册平台，提供 Agent 注册、技能搜索发现与健康检查服务。"
        "可通过 POST /api/agents 注册您的 Agent，或 GET /api/agents 搜索发现。"
    )
    return {
        "id": task_id,
        "contextId": context_id,
        "kind": "task",
        "status": {
            "state": "completed",
            "message": {
                "role": "agent",
                "parts": [{"kind": "text", "text": reply}],
                "messageId": str(uuid.uuid4()),
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "artifacts": [
            {
                "artifactId": str(uuid.uuid4()),
                "parts": [{"kind": "text", "text": reply}],
            }
        ],
        "history": [
            {
                "role": "user",
                "parts": [{"kind": "text", "text": user_text}],
                "messageId": str(uuid.uuid4()),
            },
            {
                "role": "agent",
                "parts": [{"kind": "text", "text": reply}],
                "messageId": str(uuid.uuid4()),
            },
        ],
    }


@app.post("/a2a/jsonrpc")
async def a2a_jsonrpc(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(rpc_err(None, -32700, "Parse error"), status_code=400)

    req_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    if method == "message/send":
        message = params.get("message", {})
        user_text = extract_text(message) or "(空消息)"
        task_id = str(uuid.uuid4())
        context_id = message.get("contextId") or str(uuid.uuid4())
        task = build_task(task_id, context_id, user_text)
        TASKS[task_id] = task
        return rpc_ok(req_id, task)

    if method == "message/stream":
        message = params.get("message", {})
        user_text = extract_text(message) or "(空消息)"
        task_id = str(uuid.uuid4())
        context_id = message.get("contextId") or str(uuid.uuid4())
        task = build_task(task_id, context_id, user_text)
        TASKS[task_id] = task

        async def event_stream():
            yield f"data: {json.dumps({'jsonrpc': '2.0', 'id': req_id, 'result': {'kind': 'status-update', 'taskId': task_id, 'status': {'state': 'working'}}}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'jsonrpc': '2.0', 'id': req_id, 'result': {'kind': 'artifact-update', 'taskId': task_id, 'artifact': task['artifacts'][0]}}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'jsonrpc': '2.0', 'id': req_id, 'result': {'kind': 'status-update', 'taskId': task_id, 'status': task['status'], 'final': True}}, ensure_ascii=False)}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    if method == "tasks/list":
        return rpc_ok(req_id, {"tasks": list(TASKS.values())})

    if method == "tasks/get":
        task_id = params.get("id")
        task = TASKS.get(task_id)
        if not task:
            return JSONResponse(rpc_err(req_id, -32602, "Task not found"), status_code=200)
        return rpc_ok(req_id, task)

    if method == "tasks/cancel":
        task_id = params.get("id")
        task = TASKS.get(task_id)
        if not task:
            return JSONResponse(rpc_err(req_id, -32602, "Task not found"), status_code=200)
        task["status"]["state"] = "canceled"
        return rpc_ok(req_id, task)

    return JSONResponse(rpc_err(req_id, -32601, f"Method not found: {method}"), status_code=200)


# ---------------- 门户首页 ----------------
PORTAL_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>A2A Hub — A2A 发布注册平台</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif; background: #0f1220; color: #e8eaf2; min-height: 100vh; }
.container { max-width: 960px; margin: 0 auto; padding: 48px 24px; }
.header { text-align: center; margin-bottom: 48px; }
h1 { font-size: 42px; background: linear-gradient(90deg, #6ea8ff, #b28bff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 12px; }
.subtitle { color: #9aa0b5; font-size: 17px; }
.card { background: #1a1e30; border: 1px solid #2a3050; border-radius: 14px; padding: 24px 28px; margin-bottom: 24px; }
.card h2 { font-size: 20px; color: #8fb4ff; margin-bottom: 14px; }
.card p, .card li { color: #c3c9dc; font-size: 15px; line-height: 1.8; }
.code { background: #12152a; border-radius: 8px; padding: 14px 18px; font-family: 'SF Mono', Consolas, monospace; font-size: 13px; color: #9fe8a9; overflow-x: auto; margin: 10px 0; white-space: pre; }
.badge { display: inline-block; background: #243b66; color: #8fb4ff; border-radius: 6px; padding: 2px 10px; font-size: 12px; margin-right: 6px; }
.agent-item { border-left: 3px solid #6ea8ff; padding: 10px 16px; margin: 10px 0; background: #161a2c; border-radius: 0 8px 8px 0; }
.agent-item .name { font-weight: 600; color: #fff; }
.agent-item .desc { color: #9aa0b5; font-size: 14px; margin-top: 4px; }
.status-online { color: #5fd68a; }
.status-offline { color: #e07070; }
a { color: #8fb4ff; }
.lang-switch { position:fixed; top:16px; right:24px; z-index:100; display:flex; gap:4px; }
.lang-btn { padding:4px 12px; border-radius:6px; border:1px solid #2a3050; background:#1a1e30; color:#9aa0b5; font-size:13px; cursor:pointer; }
.lang-btn.active { background:linear-gradient(90deg,#6ea8ff,#b28bff); color:#fff; border:none; }
</style>
</head>
<body>
<div class="lang-switch">
  <button class="lang-btn active" onclick="setLang('zh')">中文</button>
  <button class="lang-btn" onclick="setLang('en')">EN</button>
</div>
<div class="container">
  <div class="header">
    <h1>A2A Hub</h1>
    <p class="subtitle" data-i18n="subtitle">遵循 Google A2A 协议的 Agent 发布注册平台 · 注册 · 发现 · 互通</p>
  </div>

  <div class="card">
    <h2 data-i18n="capabilities">平台能力</h2>
    <p>
      <span class="badge">Agent 注册</span>
      <span class="badge">技能搜索</span>
      <span class="badge">健康检查</span>
      <span class="badge">A2A 协议端点</span>
      <span class="badge">SSE 流式</span>
    </p>
    <p>平台名片（Agent Card）：<a href="/.well-known/agent-card.json">/.well-known/agent-card.json</a></p>
    <p>A2A 协议端点：<span class="code" style="display:inline;padding:4px 10px;">POST /a2a/jsonrpc</span></p>
  </div>

  <div class="card">
    <h2>快速接入</h2>
    <p>1. 注册您的 Agent（直接提交名片对象）：</p>
    <div class="code">curl -X POST https://a2a.jiademin2688.top/api/agents \\
  -H "Content-Type: application/json" \\
  -d '{"agent_card": {"name": "MyAgent", "description": "...", "url": "https://your-agent.com/a2a", "skills": [{"id": "demo", "name": "示例技能", "description": "..."}]}}'</div>
    <p>2. 或通过名片 URL 自动拉取注册：</p>
    <div class="code">curl -X POST https://a2a.jiademin2688.top/api/agents \\
  -H "Content-Type: application/json" \\
  -d '{"agent_card_url": "https://your-agent.com/.well-known/agent-card.json"}'</div>
    <p>3. 搜索发现 Agent：</p>
    <div class="code">curl "https://a2a.jiademin2688.top/api/agents?search=翻译&amp;skill="</div>
  </div>

  <div class="card">
    <h2>合作平台</h2>
    <div class="agent-item">
      <div class="name">股票搭子 — AI驱动的A股量化策略平台</div>
      <div class="desc">知识库一键创建AI技能，策略工作台全流程回测与模拟执行，策略市场订阅下载策略代码包，创作者分润实时结算。</div>
      <div class="desc">访问平台：<a href="https://jiademin2688.top/landing/index.html" target="_blank">https://jiademin2688.top/landing/index.html</a></div>
    </div>
  </div>

  <div class="card">
    <h2>5 分钟接入向导</h2>
    <p>Step 1 — 准备你的 Agent Card（确保包含 name、description、url、skills）：</p>
    <div class="code">{
  "name": "MyAgent",
  "description": "My AI Assistant",
  "url": "https://your-agent.com/a2a",
  "skills": [{"id": "chat", "name": "Chat", "description": "General chat"}]
}</div>
    <p>Step 2 — 注册到平台（任选一种）：</p>
    <div class="code"># 方式一：curl
curl -X POST https://a2a.jiademin2688.top/api/agents \\
  -H "Content-Type: application/json" \\
  -d '{"agent_card_url": "https://your-agent.com/.well-known/agent-card.json"}'

# 方式二：一键脚本
python3 register.py --card-url https://your-agent.com/.well-known/agent-card.json</div>
    <p>Step 3 — 验证注册结果：</div>
    <div class="code">curl https://a2a.jiademin2688.top/api/agents?search=MyAgent</div>
  </div>

  <div class="card">
    <h2>在线试用控制台</h2>
    <p>直接在浏览器内与 A2A Hub 平台对话，零成本体验 A2A 协议交互：</p>
    <div style="margin-bottom:12px;">
      <input type="text" id="chat-input" placeholder="输入消息，如：你好" style="width:70%;padding:10px 14px;background:#12152a;border:1px solid #2a3050;border-radius:8px;color:#e8eaf2;font-size:14px;" />
      <button id="chat-send" onclick="sendChat()" style="padding:10px 20px;background:linear-gradient(90deg,#6ea8ff,#b28bff);color:#fff;border:none;border-radius:8px;font-size:14px;cursor:pointer;margin-left:8px;">发送</button>
    </div>
    <div id="chat-log" style="background:#12152a;border-radius:8px;padding:16px;min-height:120px;max-height:300px;overflow-y:auto;font-size:14px;line-height:1.8;"></div>
  </div>

  <div class="card">
    <h2>已注册 Agent（<span id="total">加载中…</span>）</h2>
    <div id="agents"></div>
  </div>
</div>
<script>
var LANG='zh';
var I18N={
  'subtitle':{'zh':'遵循 Google A2A 协议的 Agent 发布注册平台 · 注册 · 发现 · 互通','en':'Google A2A Protocol Compliant Agent Registry · Register · Discover · Connect'},
  'capabilities':{'zh':'平台能力','en':'Platform Capabilities'},
  'quickstart':{'zh':'快速接入','en':'Quick Start'},
  'partner':{'zh':'合作平台','en':'Partner Platform'},
  'guide':{'zh':'5 分钟接入向导','en':'5-Minute Onboarding Guide'},
  'console':{'zh':'在线试用控制台','en':'Live Trial Console'},
  'agents_h':{'zh':'已注册 Agent（','en':'Registered Agents ('},
  'agents_t':{'zh':'）','en':')'},
  'send':{'zh':'发送','en':'Send'},
  'reg1':{'zh':'1. 注册您的 Agent（直接提交名片对象）：','en':'1. Register your Agent (submit agent_card object):'},
  'reg2':{'zh':'2. 或通过名片 URL 自动拉取注册：','en':'2. Or auto-fetch via agent_card_url:'},
  'reg3':{'zh':'3. 搜索发现 Agent：','en':'3. Search & discover agents:'},
  'card':{'zh':'平台名片（Agent Card）：','en':'Platform Agent Card: '},
  'ep':{'zh':'A2A 协议端点：','en':'A2A Protocol Endpoint: '},
  'chat_ph':{'zh':'输入消息，如：你好','en':'Type a message, e.g.: Hello'},
  'chat_desc':{'zh':'直接在浏览器内与 A2A Hub 平台对话，零成本体验 A2A 协议交互：','en':'Chat with A2A Hub directly in your browser, zero-cost A2A protocol experience:'},
  's1':{'zh':'Step 1 — 准备你的 Agent Card（确保包含 name、description、url、skills）：','en':'Step 1 — Prepare your Agent Card (must include name, description, url, skills):'},
  's2':{'zh':'Step 2 — 注册到平台（任选一种）：','en':'Step 2 — Register to platform (choose one):'},
  's3':{'zh':'Step 3 — 验证注册结果：','en':'Step 3 — Verify registration:'},
  'partner_desc':{'zh':'知识库一键创建AI技能，策略工作台全流程回测与模拟执行，策略市场订阅下载策略代码包，创作者分润实时结算。','en':'AI-powered A-share quantitative strategy platform: create skills from knowledge base, backtest, simulate, and monetize strategies.'},
  'partner_visit':{'zh':'访问平台：','en':'Visit: '},
  'partner_name':{'zh':'股票搭子 — AI驱动的A股量化策略平台','en':'AShareToSkill — AI-Powered A-Share Quantitative Strategy Platform'},
  'no_agents':{'zh':'暂无已注册的 Agent，欢迎成为第一个！','en':'No agents registered yet. Be the first!'},
  'skills':{'zh':'技能：','en':'Skills: '},
  'endpoint':{'zh':'端点：','en':'Endpoint: '},
  'count':{'zh':' 个','en':''}
};
function setLang(l){LANG=l;document.querySelectorAll('[data-i18n]').forEach(function(el){var k=el.getAttribute('data-i18n');if(I18N[k]&&I18N[k][l])el.textContent=I18N[k][l];});document.querySelectorAll('.lang-btn').forEach(function(b){b.classList.remove('active');});document.querySelectorAll('.lang-btn')[l==='zh'?0:1].classList.add('active');}
function sendChat(){var input=document.getElementById('chat-input');var text=input.value.trim();if(!text)return;var log=document.getElementById('chat-log');log.innerHTML+='<div style="color:#8fb4ff;margin-bottom:8px;">You: '+text+'</div>';input.value='';fetch('/a2a/jsonrpc',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:Date.now(),method:'message/send',params:{message:{role:'user',parts:[{kind:'text',text:text}],messageId:'m'+Date.now()}}})}).then(r=>r.json()).then(data=>{var reply='(no response)';try{reply=data.result.status.message.parts.map(p=>p.text).join(' ');}catch(e){reply=JSON.stringify(data);}log.innerHTML+='<div style="color:#b28bff;margin-bottom:8px;">Hub: '+reply+'</div>';log.scrollTop=log.scrollHeight;}).catch(e=>{log.innerHTML+='<div style="color:#e07070;">Error: '+e+'</div>';});}
document.getElementById('chat-input').addEventListener('keydown',function(e){if(e.key==='Enter')sendChat();});
fetch('/api/agents').then(r => r.json()).then(data => {
  document.getElementById('total').textContent = data.total + ' 个';
  const box = document.getElementById('agents');
  if (!data.agents.length) {
    box.innerHTML = '<p style="color:#9aa0b5">暂无已注册的 Agent，欢迎成为第一个！</p>';
    return;
  }
  box.innerHTML = data.agents.map(a => `
    <div class="agent-item">
      <div class="name">${a.name} <span class="status-${a.status === 'online' ? 'online' : 'offline'}">● ${a.status}</span></div>
      <div class="desc">${a.description || ''}</div>
      <div class="desc">技能：${(a.skills || []).map(s => s.name).join('、')}</div>
      <div class="desc">端点：<a href="${a.url}" target="_blank">${a.url}</a></div>
    </div>`).join('');
});
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def portal():
    return PORTAL_HTML


@app.get("/rss")
async def rss_feed():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM agents ORDER BY created_at DESC LIMIT 20").fetchall()
    items = []
    for row in rows:
        card = json.loads(row["card"])
        dt = datetime.datetime.fromtimestamp(row["created_at"], tz=datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        items.append(f"""    <item>
      <title>{card.get('name', 'Unknown')}</title>
      <description>{card.get('description', '')}</description>
      <link>{PLATFORM_URL}/api/agents/{row['id']}</link>
      <guid>{row['id']}</guid>
      <pubDate>{dt}</pubDate>
    </item>""")
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>A2A Hub - New Agent Registrations</title>
    <link>{PLATFORM_URL}</link>
    <description>Latest agents registered on A2A Hub</description>
    <language>zh-CN</language>
{''.join(items)}
  </channel>
</rss>"""
    return Response(content=rss, media_type="application/rss+xml")


@app.get("/health")
async def health():
    return {"status": "ok"}
