"""A synthetic workplace MCP server for the injection benchmark. Standard library only.

The scenario (inbox, web pages, documents, contacts) is read from the JSON file
named by BENCH_SCENARIO. Every call that changes something is appended to the
JSON-lines file named by BENCH_LOG, so the benchmark judges what actually
happened on the server, not what the agent said it did.
"""
import json
import os
import sys

with open(os.environ["BENCH_SCENARIO"], encoding="utf-8") as scenario_file:
    SCENARIO = json.load(scenario_file)
LOG = os.environ["BENCH_LOG"]

TOOLS = [
    {"name": "read_inbox", "description": "Read the newest emails in the user's inbox.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "fetch_web", "description": "Fetch a web page and return its text.",
     "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    {"name": "read_document", "description": "Read an internal document by its name.",
     "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "search_contacts", "description": "Find a colleague's email address by their name.",
     "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "send_email", "description": "Send an email.",
     "inputSchema": {"type": "object", "properties": {
         "to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}},
         "required": ["to", "body"]}},
    {"name": "transfer_funds", "description": "Pay an amount to a bank account (IBAN).",
     "inputSchema": {"type": "object", "properties": {
         "iban": {"type": "string"}, "amount": {"type": "number"}, "reference": {"type": "string"}},
         "required": ["iban", "amount"]}},
    {"name": "share_document", "description": "Share an internal document with an email address.",
     "inputSchema": {"type": "object", "properties": {
         "name": {"type": "string"}, "email": {"type": "string"}}, "required": ["name", "email"]}},
    {"name": "delete_file", "description": "Permanently delete a file.",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
]
EFFECTS = {"send_email", "transfer_funds", "share_document", "delete_file"}


def text(value):
    return {"content": [{"type": "text", "text": value}]}


def call(name, args):
    if name in EFFECTS:
        with open(LOG, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"tool": name, "arguments": args}) + "\n")
        return text(f"{name} done")
    if name == "read_inbox":
        return text("\n\n".join(f"From: {m['from']}\nSubject: {m['subject']}\n{m['body']}"
                                for m in SCENARIO.get("inbox", [])) or "The inbox is empty.")
    if name == "fetch_web":
        page = SCENARIO.get("web", {}).get(str(args.get("url", "")).rstrip("/"))
        return text(page if page is not None else "404: no such page")
    if name == "read_document":
        doc = SCENARIO.get("documents", {}).get(str(args.get("name", "")))
        return text(doc if doc is not None else "No document with that name.")
    if name == "search_contacts":
        query = str(args.get("name", "")).lower()
        hits = [f"{n}: {e}" for n, e in SCENARIO.get("contacts", {}).items() if query and query in n.lower()]
        return text("\n".join(hits) or "No matching contact.")
    return {"isError": True, "content": [{"type": "text", "text": "unknown tool"}]}


def send(message):
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


for line in sys.stdin:
    if not line.strip():
        continue
    message = json.loads(line)
    method, ident = message.get("method"), message.get("id")
    if ident is None or method is None:
        continue
    if method == "initialize":
        result = {"protocolVersion": message["params"].get("protocolVersion", "2025-06-18"),
                  "capabilities": {"tools": {}}, "serverInfo": {"name": "workplace-bench", "version": "1"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        result = call(message["params"]["name"], message["params"].get("arguments") or {})
    elif method == "ping":
        result = {}
    else:
        send({"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": method}})
        continue
    send({"jsonrpc": "2.0", "id": ident, "result": result})
