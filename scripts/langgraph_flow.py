from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import operator
import re
import warnings
from pathlib import Path
from typing import Annotated, Any, Literal

warnings.filterwarnings("ignore")

try:
    with contextlib.redirect_stderr(io.StringIO()):
        from langgraph.graph import END, StateGraph
except ModuleNotFoundError as exc:  # pragma: no cover - exercised only without dependencies.
    raise SystemExit(
        "LangGraph is not installed. Run: python3 -m pip install -r requirements.txt"
    ) from exc

try:
    from typing import TypedDict
except ImportError:  # pragma: no cover - Python < 3.8 fallback.
    from typing_extensions import TypedDict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_OUTPUT_PATH = PROJECT_ROOT / "outputs/langgraph_examples.md"

RouteName = Literal[
    "preparedness_guidance",
    "local_resource_lookup",
    "household_task",
    "clarification",
]


class AgentState(TypedDict):
    """Shared graph state passed between LangGraph nodes."""

    user_question: str
    selected_route: str
    route_reason: str
    extracted_entities: dict[str, Any]
    missing_inputs: list[str]
    tool_result: dict[str, Any]
    final_answer: str
    executed_nodes: Annotated[list[str], operator.add]
    observations: Annotated[list[dict[str, Any]], operator.add]


PREPAREDNESS_KNOWLEDGE_BASE = [
    {
        "chunk_id": "emergency_kit_chunk_001",
        "title": "Emergency Supply Kit",
        "section": "Medication and essentials",
        "keywords": {"kit", "go-bag", "bag", "medication", "medicine", "prescription", "water", "food"},
        "content": (
            "Keep a go-bag with water, shelf-stable food, flashlights, batteries, "
            "copies of key documents, chargers, hygiene items, and several days "
            "of critical prescription medication when possible."
        ),
    },
    {
        "chunk_id": "evacuation_plan_chunk_002",
        "title": "Evacuation Plan",
        "section": "Routes and meeting places",
        "keywords": {"evacuation", "evacuate", "route", "meeting", "family", "plan", "leave"},
        "content": (
            "A household evacuation plan should define two meeting places, two travel "
            "routes, an out-of-area communication contact, and the items to take when "
            "leaving quickly."
        ),
    },
    {
        "chunk_id": "pets_service_animals_chunk_003",
        "title": "Pets and Service Animals",
        "section": "Evacuation with animals",
        "keywords": {"pet", "pets", "animal", "animals", "service", "evacuation", "shelter"},
        "content": (
            "Prepare carriers, leashes, food, water, medication, vaccination records, "
            "and identification for pets and service animals before evacuation."
        ),
    },
    {
        "chunk_id": "wireless_alerts_chunk_004",
        "title": "Emergency Alerts",
        "section": "Wireless Emergency Alerts",
        "keywords": {"wea", "alert", "alerts", "warning", "phone", "app", "notification"},
        "content": (
            "Wireless Emergency Alerts are sent to compatible phones in targeted areas. "
            "A separate app is not required, but the phone must be compatible, powered on, "
            "and connected to a participating wireless network."
        ),
    },
]


LOCAL_RESOURCE_DIRECTORY = {
    "springfield_oh": {
        "display_name": "Springfield, OH",
        "last_updated_utc": "2026-08-09T10:00:00Z",
        "resources": {
            "shelter": {
                "name": "Springfield Community Center",
                "status": "open",
                "address": "101 Civic Plaza, Springfield, OH",
                "capacity_available": 84,
                "pet_policy": "Pets accepted in the adjacent support area.",
                "last_verified_utc": "2026-08-09T09:30:00Z",
            },
            "hotline": {
                "name": "Springfield Emergency Assistance Line",
                "status": "active",
                "phone": "555-0101",
                "hours": "24 hours during activation",
                "last_verified_utc": "2026-08-09T09:15:00Z",
            },
            "distribution_point": {
                "name": "Westside Library Parking Lot",
                "status": "open",
                "address": "44 West Main Street, Springfield, OH",
                "available_supplies": ["bottled water", "charging station", "basic hygiene kits"],
                "hours": "12:00-18:00 local time",
                "last_verified_utc": "2026-08-09T09:20:00Z",
            },
        },
    },
    "riverside_ca": {
        "display_name": "Riverside, CA",
        "last_updated_utc": "2026-08-09T10:00:00Z",
        "resources": {
            "shelter": {
                "name": "East Valley High School Gym",
                "status": "open",
                "address": "2400 Valley Road, Riverside, CA",
                "capacity_available": 42,
                "pet_policy": "Service animals only inside the main gym.",
                "last_verified_utc": "2026-08-09T08:40:00Z",
            },
            "alert": {
                "name": "Wildfire smoke advisory",
                "status": "active",
                "severity": "high",
                "instructions": "Stay indoors when possible and follow official evacuation notices.",
                "effective_until": "2026-08-10T03:00:00Z",
                "last_verified_utc": "2026-08-09T09:05:00Z",
            },
            "hotline": {
                "name": "Riverside Emergency Assistance Line",
                "status": "active",
                "phone": "555-0299",
                "hours": "24 hours during emergency activation",
                "last_verified_utc": "2026-08-09T08:50:00Z",
            },
        },
    },
}


TASK_TEMPLATES = {
    "kit_review": {
        "title": "Review household emergency kit",
        "default_steps": [
            "Check water, food, batteries, chargers, and medication.",
            "Replace expired supplies.",
            "Put the updated kit in an easy-to-reach location.",
        ],
    },
    "smoke_detector_check": {
        "title": "Check smoke and carbon monoxide detectors",
        "default_steps": [
            "Test each detector.",
            "Replace weak batteries.",
            "Record the check date for the household.",
        ],
    },
    "contact_list_update": {
        "title": "Update emergency contact list",
        "default_steps": [
            "Confirm phone numbers for household members.",
            "Add an out-of-area emergency contact.",
            "Print or save an offline copy.",
        ],
    },
    "general_preparedness_task": {
        "title": "Complete preparedness task",
        "default_steps": [
            "Write down the goal.",
            "Assign an owner.",
            "Review completion during the next household check-in.",
        ],
    },
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def contains_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def classify_route(question: str) -> tuple[RouteName, str]:
    normalized = normalize_text(question)

    task_terms = {"task", "todo", "to-do", "remind", "create", "schedule", "assign", "checklist"}
    local_terms = {
        "open",
        "currently",
        "current",
        "tonight",
        "near me",
        "capacity",
        "hotline",
        "phone number",
        "shelter",
        "distribution",
        "water",
        "charging",
        "resource",
        "advisory",
    }
    guidance_terms = {
        "prepare",
        "kit",
        "go-bag",
        "evacuation",
        "evacuate",
        "pets",
        "pet",
        "plan",
        "wea",
        "wireless emergency alert",
        "what should",
        "how should",
    }

    if contains_any(normalized, task_terms):
        return "household_task", "The user wants the assistant to create a structured task."
    if contains_any(normalized, local_terms):
        return "local_resource_lookup", "The user asks for local or time-sensitive operational data."
    if contains_any(normalized, guidance_terms):
        return "preparedness_guidance", "The user asks for stable preparedness guidance."
    return "clarification", "The request is too broad or ambiguous for a safe tool call."


def extract_location_code(question: str) -> str | None:
    normalized = normalize_text(question)
    if "springfield_oh" in normalized or "springfield" in normalized:
        return "springfield_oh"
    if "riverside_ca" in normalized or "riverside" in normalized:
        return "riverside_ca"
    return None


def extract_resource_type(question: str) -> str | None:
    normalized = normalize_text(question)
    if any(term in normalized for term in ("shelter", "cot", "place to stay", "capacity")):
        return "shelter"
    if any(term in normalized for term in ("hotline", "call", "phone number", "assistance line")):
        return "hotline"
    if any(term in normalized for term in ("current alert", "active alert", "advisory", "warning")):
        return "alert"
    if any(term in normalized for term in ("water", "charging", "distribution", "supplies")):
        return "distribution_point"
    return None


def extract_task_type(question: str) -> str:
    normalized = normalize_text(question)
    if any(term in normalized for term in ("kit", "go-bag", "supplies")):
        return "kit_review"
    if any(term in normalized for term in ("smoke", "carbon monoxide", "detector")):
        return "smoke_detector_check"
    if any(term in normalized for term in ("contact", "phone list", "communication")):
        return "contact_list_update"
    return "general_preparedness_task"


def extract_due_date_label(question: str) -> str:
    normalized = normalize_text(question)
    if "today" in normalized:
        return "today"
    if "tomorrow" in normalized:
        return "tomorrow"
    for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
        if day in normalized:
            return f"next_{day}"
    if "this week" in normalized:
        return "this_week"
    return "not_specified"


def extract_owner(question: str) -> str:
    match = re.search(r"\bfor ([A-Z][a-z]+)\b", question)
    if match:
        return match.group(1)
    if any(term in normalize_text(question) for term in ("me", "my", "i ")):
        return "household_lead"
    return "unassigned"


def extract_entities(question: str) -> dict[str, Any]:
    return {
        "location_code": extract_location_code(question),
        "resource_type": extract_resource_type(question),
        "task_type": extract_task_type(question),
        "due_date": extract_due_date_label(question),
        "owner": extract_owner(question),
    }


def search_preparedness_knowledge_base(question: str) -> dict[str, Any]:
    query_terms = set(re.findall(r"[a-z0-9-]+", normalize_text(question)))
    best_doc = max(
        PREPAREDNESS_KNOWLEDGE_BASE,
        key=lambda doc: len(query_terms & doc["keywords"]),
    )
    return {
        "chunk_id": best_doc["chunk_id"],
        "title": best_doc["title"],
        "section": best_doc["section"],
        "score": len(query_terms & best_doc["keywords"]),
        "content": best_doc["content"],
    }


def lookup_local_resource(location_code: str, resource_type: str) -> dict[str, Any]:
    location = LOCAL_RESOURCE_DIRECTORY.get(location_code)
    if location is None:
        return {
            "success": False,
            "error": f"Unsupported location_code: {location_code}",
            "supported_locations": sorted(LOCAL_RESOURCE_DIRECTORY),
        }

    resource = location["resources"].get(resource_type)
    if resource is None:
        return {
            "success": True,
            "location_code": location_code,
            "location_name": location["display_name"],
            "resource_type": resource_type,
            "dataset_last_updated_utc": location["last_updated_utc"],
            "resource": None,
            "message": "No active resource of this type is listed in the mock directory.",
        }

    return {
        "success": True,
        "location_code": location_code,
        "location_name": location["display_name"],
        "resource_type": resource_type,
        "dataset_last_updated_utc": location["last_updated_utc"],
        "resource": resource,
    }


def create_household_task(task_type: str, owner: str, due_date: str) -> dict[str, Any]:
    template = TASK_TEMPLATES.get(task_type, TASK_TEMPLATES["general_preparedness_task"])
    seed = f"{task_type}:{owner}:{due_date}".encode("utf-8")
    task_id = "task_" + hashlib.sha1(seed).hexdigest()[:10]
    return {
        "task_id": task_id,
        "status": "created",
        "task_type": task_type,
        "title": template["title"],
        "owner": owner,
        "due_date": due_date,
        "next_steps": template["default_steps"],
    }


def classify_request(state: AgentState) -> dict[str, Any]:
    route, reason = classify_route(state["user_question"])
    entities = extract_entities(state["user_question"])

    missing_inputs = []
    if route == "local_resource_lookup":
        if entities["location_code"] is None:
            missing_inputs.append("location_code")
        if entities["resource_type"] is None:
            missing_inputs.append("resource_type")
        if missing_inputs:
            route = "clarification"
            reason = "The request needs local resource data but required input is missing."

    return {
        "selected_route": route,
        "route_reason": reason,
        "extracted_entities": entities,
        "missing_inputs": missing_inputs,
        "executed_nodes": ["classify_request"],
        "observations": [
            {
                "node": "classify_request",
                "route": route,
                "reason": reason,
                "missing_inputs": missing_inputs,
            }
        ],
    }


def run_preparedness_guidance(state: AgentState) -> dict[str, Any]:
    result = search_preparedness_knowledge_base(state["user_question"])
    return {
        "tool_result": result,
        "executed_nodes": ["run_preparedness_guidance"],
        "observations": [
            {
                "node": "run_preparedness_guidance",
                "tool": "search_preparedness_knowledge_base",
                "result": result,
            }
        ],
    }


def run_local_resource_lookup(state: AgentState) -> dict[str, Any]:
    entities = state["extracted_entities"]
    result = lookup_local_resource(
        location_code=entities["location_code"],
        resource_type=entities["resource_type"],
    )
    return {
        "tool_result": result,
        "executed_nodes": ["run_local_resource_lookup"],
        "observations": [
            {
                "node": "run_local_resource_lookup",
                "tool": "lookup_local_resource",
                "result": result,
            }
        ],
    }


def run_household_task(state: AgentState) -> dict[str, Any]:
    entities = state["extracted_entities"]
    result = create_household_task(
        task_type=entities["task_type"],
        owner=entities["owner"],
        due_date=entities["due_date"],
    )
    return {
        "tool_result": result,
        "executed_nodes": ["run_household_task"],
        "observations": [
            {
                "node": "run_household_task",
                "tool": "create_household_task",
                "result": result,
            }
        ],
    }


def ask_clarification(state: AgentState) -> dict[str, Any]:
    if state["missing_inputs"]:
        missing = ", ".join(state["missing_inputs"])
        answer = (
            f"I need one more detail before acting: {missing}. "
            "Please include a supported location such as springfield_oh or riverside_ca, "
            "and specify shelter, hotline, alert, or distribution point if relevant."
        )
    else:
        answer = (
            "Could you clarify the goal? I can answer preparedness guidance questions, "
            "look up local emergency resources, or create a household preparedness task."
        )

    result = {"message": answer, "missing_inputs": state["missing_inputs"]}
    return {
        "tool_result": result,
        "final_answer": answer,
        "executed_nodes": ["ask_clarification"],
        "observations": [
            {
                "node": "ask_clarification",
                "tool": None,
                "result": result,
            }
        ],
    }


def build_answer(state: AgentState) -> dict[str, Any]:
    route = state["selected_route"]
    result = state["tool_result"]

    if route == "preparedness_guidance":
        answer = (
            f"According to {result['title']} / {result['section']} "
            f"({result['chunk_id']}): {result['content']}"
        )
    elif route == "local_resource_lookup":
        answer = build_local_resource_answer(result)
    elif route == "household_task":
        answer = (
            f"Created task {result['task_id']}: {result['title']}. "
            f"Owner: {result['owner']}. Due date: {result['due_date']}. "
            f"First step: {result['next_steps'][0]}"
        )
    else:
        answer = state["final_answer"]

    return {
        "final_answer": answer,
        "executed_nodes": ["build_answer"],
        "observations": [
            {
                "node": "build_answer",
                "result": {"final_answer": answer},
            }
        ],
    }


def build_local_resource_answer(result: dict[str, Any]) -> str:
    if not result["success"]:
        return f"I could not complete the local lookup: {result['error']}"

    if result["resource"] is None:
        return (
            f"I checked the mock local resource directory for {result['location_name']}, "
            f"but no active {result['resource_type']} record is listed. "
            f"Dataset updated: {result['dataset_last_updated_utc']}."
        )

    resource = result["resource"]
    if result["resource_type"] == "shelter":
        return (
            f"{resource['name']} is currently {resource['status']} at {resource['address']}. "
            f"Available capacity: {resource['capacity_available']}. "
            f"Pet policy: {resource['pet_policy']} Last verified: {resource['last_verified_utc']}."
        )
    if result["resource_type"] == "hotline":
        return (
            f"The current hotline is {resource['name']} at {resource['phone']}. "
            f"Status: {resource['status']}. Hours: {resource['hours']}. "
            f"Last verified: {resource['last_verified_utc']}."
        )
    if result["resource_type"] == "alert":
        return (
            f"Current alert for {result['location_name']}: {resource['name']} "
            f"({resource['severity']} severity). Instructions: {resource['instructions']} "
            f"Effective until: {resource['effective_until']}."
        )
    return (
        f"{resource['name']} is {resource['status']} at {resource['address']}. "
        f"Available supplies: {', '.join(resource['available_supplies'])}. Hours: {resource['hours']}."
    )


def route_after_classification(state: AgentState) -> str:
    return state["selected_route"]


def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("classify_request", classify_request)
    workflow.add_node("run_preparedness_guidance", run_preparedness_guidance)
    workflow.add_node("run_local_resource_lookup", run_local_resource_lookup)
    workflow.add_node("run_household_task", run_household_task)
    workflow.add_node("ask_clarification", ask_clarification)
    workflow.add_node("build_answer", build_answer)

    workflow.set_entry_point("classify_request")
    workflow.add_conditional_edges(
        "classify_request",
        route_after_classification,
        {
            "preparedness_guidance": "run_preparedness_guidance",
            "local_resource_lookup": "run_local_resource_lookup",
            "household_task": "run_household_task",
            "clarification": "ask_clarification",
        },
    )
    workflow.add_edge("run_preparedness_guidance", "build_answer")
    workflow.add_edge("run_local_resource_lookup", "build_answer")
    workflow.add_edge("run_household_task", "build_answer")
    workflow.add_edge("ask_clarification", END)
    workflow.add_edge("build_answer", END)

    return workflow.compile()


def initial_state(question: str) -> AgentState:
    return {
        "user_question": question,
        "selected_route": "",
        "route_reason": "",
        "extracted_entities": {},
        "missing_inputs": [],
        "tool_result": {},
        "final_answer": "",
        "executed_nodes": [],
        "observations": [],
    }


APP = build_graph()


def run_agent(question: str) -> AgentState:
    return APP.invoke(initial_state(question))


def final_state_for_report(state: AgentState) -> dict[str, Any]:
    return {
        "user_question": state["user_question"],
        "selected_route": state["selected_route"],
        "route_reason": state["route_reason"],
        "extracted_entities": state["extracted_entities"],
        "missing_inputs": state["missing_inputs"],
        "tool_result": state["tool_result"],
        "executed_nodes": state["executed_nodes"],
        "final_answer": state["final_answer"],
    }


def write_examples(output_path: Path = EXAMPLES_OUTPUT_PATH) -> None:
    questions = [
        "What should I put in my emergency kit for prescription medication?",
        "Which shelter is open in springfield_oh tonight?",
        "Create a task for me to check smoke detectors by Friday.",
    ]

    lines = [
        "# LangGraph Workflow Examples",
        "",
        "Framework: LangGraph",
        "",
        "Graph path:",
        "",
        "```text",
        "classify_request -> conditional edge -> route node -> build_answer -> END",
        "```",
        "",
    ]

    for index, question in enumerate(questions, start=1):
        state = run_agent(question)
        lines.extend(
            [
                f"## Example {index}",
                "",
                f"Input question: {question}",
                "",
                f"Selected route: `{state['selected_route']}`",
                "",
                "Executed nodes:",
                "",
                " -> ".join(state["executed_nodes"]),
                "",
                "Final state:",
                "",
                "```json",
                json.dumps(final_state_for_report(state), ensure_ascii=False, indent=2),
                "```",
                "",
                f"Final answer: {state['final_answer']}",
                "",
                "Observations:",
                "",
                "```json",
                json.dumps(state["observations"], ensure_ascii=False, indent=2),
                "```",
                "",
                "---",
                "",
            ]
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the LangGraph emergency assistant workflow.")
    parser.add_argument("--question", help="Question or goal to run through the graph.")
    parser.add_argument("--write-examples", action="store_true", help="Write outputs/langgraph_examples.md.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.write_examples or not args.question:
        write_examples()
        print(f"Wrote examples to {EXAMPLES_OUTPUT_PATH.relative_to(PROJECT_ROOT)}")

    if args.question:
        state = run_agent(args.question)
        print(json.dumps(final_state_for_report(state), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
