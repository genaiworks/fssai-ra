import hashlib
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

CONTRACT_DIR = os.path.join(_ROOT, "contract")

from fssaira import Agent  # noqa: E402


def sign(key: str, data: str) -> str:
    return hashlib.sha256((key + data).encode()).hexdigest()


def privileged_agent(pipeline, agent_id: str = "broad-1") -> Agent:
    """A deliberately over-provisioned agent, used to isolate a single control
    (egress / high-impact approval) rather than have least-privilege mask it."""
    ops = {"read_case", "prepare_recommendation", "approve_award",
           "broaden_access", "delete_evidence", "notify_external"}
    return Agent(agent_id, allowed_tools=set(ops), permitted_operations=set(ops),
                 data_scope={"all"}, tool_registry=pipeline.registry)
