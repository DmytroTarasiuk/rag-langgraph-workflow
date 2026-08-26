# LangGraph Workflow Examples

Framework: LangGraph

Graph path:

```text
classify_request -> conditional edge -> route node -> build_answer -> END
```

## Example 1

Input question: What should I put in my emergency kit for prescription medication?

Selected route: `preparedness_guidance`

Executed nodes:

classify_request -> run_preparedness_guidance -> build_answer

Final state:

```json
{
  "user_question": "What should I put in my emergency kit for prescription medication?",
  "selected_route": "preparedness_guidance",
  "route_reason": "The user asks for stable preparedness guidance.",
  "extracted_entities": {
    "location_code": null,
    "resource_type": null,
    "task_type": "kit_review",
    "due_date": "not_specified",
    "owner": "household_lead"
  },
  "missing_inputs": [],
  "tool_result": {
    "chunk_id": "emergency_kit_chunk_001",
    "title": "Emergency Supply Kit",
    "section": "Medication and essentials",
    "score": 3,
    "content": "Keep a go-bag with water, shelf-stable food, flashlights, batteries, copies of key documents, chargers, hygiene items, and several days of critical prescription medication when possible."
  },
  "executed_nodes": [
    "classify_request",
    "run_preparedness_guidance",
    "build_answer"
  ],
  "final_answer": "According to Emergency Supply Kit / Medication and essentials (emergency_kit_chunk_001): Keep a go-bag with water, shelf-stable food, flashlights, batteries, copies of key documents, chargers, hygiene items, and several days of critical prescription medication when possible."
}
```

Final answer: According to Emergency Supply Kit / Medication and essentials (emergency_kit_chunk_001): Keep a go-bag with water, shelf-stable food, flashlights, batteries, copies of key documents, chargers, hygiene items, and several days of critical prescription medication when possible.

Observations:

```json
[
  {
    "node": "classify_request",
    "route": "preparedness_guidance",
    "reason": "The user asks for stable preparedness guidance.",
    "missing_inputs": []
  },
  {
    "node": "run_preparedness_guidance",
    "tool": "search_preparedness_knowledge_base",
    "result": {
      "chunk_id": "emergency_kit_chunk_001",
      "title": "Emergency Supply Kit",
      "section": "Medication and essentials",
      "score": 3,
      "content": "Keep a go-bag with water, shelf-stable food, flashlights, batteries, copies of key documents, chargers, hygiene items, and several days of critical prescription medication when possible."
    }
  },
  {
    "node": "build_answer",
    "result": {
      "final_answer": "According to Emergency Supply Kit / Medication and essentials (emergency_kit_chunk_001): Keep a go-bag with water, shelf-stable food, flashlights, batteries, copies of key documents, chargers, hygiene items, and several days of critical prescription medication when possible."
    }
  }
]
```

---

## Example 2

Input question: Which shelter is open in springfield_oh tonight?

Selected route: `local_resource_lookup`

Executed nodes:

classify_request -> run_local_resource_lookup -> build_answer

Final state:

```json
{
  "user_question": "Which shelter is open in springfield_oh tonight?",
  "selected_route": "local_resource_lookup",
  "route_reason": "The user asks for local or time-sensitive operational data.",
  "extracted_entities": {
    "location_code": "springfield_oh",
    "resource_type": "shelter",
    "task_type": "general_preparedness_task",
    "due_date": "not_specified",
    "owner": "unassigned"
  },
  "missing_inputs": [],
  "tool_result": {
    "success": true,
    "location_code": "springfield_oh",
    "location_name": "Springfield, OH",
    "resource_type": "shelter",
    "dataset_last_updated_utc": "2026-08-09T10:00:00Z",
    "resource": {
      "name": "Springfield Community Center",
      "status": "open",
      "address": "101 Civic Plaza, Springfield, OH",
      "capacity_available": 84,
      "pet_policy": "Pets accepted in the adjacent support area.",
      "last_verified_utc": "2026-08-09T09:30:00Z"
    }
  },
  "executed_nodes": [
    "classify_request",
    "run_local_resource_lookup",
    "build_answer"
  ],
  "final_answer": "Springfield Community Center is currently open at 101 Civic Plaza, Springfield, OH. Available capacity: 84. Pet policy: Pets accepted in the adjacent support area. Last verified: 2026-08-09T09:30:00Z."
}
```

Final answer: Springfield Community Center is currently open at 101 Civic Plaza, Springfield, OH. Available capacity: 84. Pet policy: Pets accepted in the adjacent support area. Last verified: 2026-08-09T09:30:00Z.

Observations:

```json
[
  {
    "node": "classify_request",
    "route": "local_resource_lookup",
    "reason": "The user asks for local or time-sensitive operational data.",
    "missing_inputs": []
  },
  {
    "node": "run_local_resource_lookup",
    "tool": "lookup_local_resource",
    "result": {
      "success": true,
      "location_code": "springfield_oh",
      "location_name": "Springfield, OH",
      "resource_type": "shelter",
      "dataset_last_updated_utc": "2026-08-09T10:00:00Z",
      "resource": {
        "name": "Springfield Community Center",
        "status": "open",
        "address": "101 Civic Plaza, Springfield, OH",
        "capacity_available": 84,
        "pet_policy": "Pets accepted in the adjacent support area.",
        "last_verified_utc": "2026-08-09T09:30:00Z"
      }
    }
  },
  {
    "node": "build_answer",
    "result": {
      "final_answer": "Springfield Community Center is currently open at 101 Civic Plaza, Springfield, OH. Available capacity: 84. Pet policy: Pets accepted in the adjacent support area. Last verified: 2026-08-09T09:30:00Z."
    }
  }
]
```

---

## Example 3

Input question: Create a task for me to check smoke detectors by Friday.

Selected route: `household_task`

Executed nodes:

classify_request -> run_household_task -> build_answer

Final state:

```json
{
  "user_question": "Create a task for me to check smoke detectors by Friday.",
  "selected_route": "household_task",
  "route_reason": "The user wants the assistant to create a structured task.",
  "extracted_entities": {
    "location_code": null,
    "resource_type": null,
    "task_type": "smoke_detector_check",
    "due_date": "next_friday",
    "owner": "household_lead"
  },
  "missing_inputs": [],
  "tool_result": {
    "task_id": "task_fc88cdc556",
    "status": "created",
    "task_type": "smoke_detector_check",
    "title": "Check smoke and carbon monoxide detectors",
    "owner": "household_lead",
    "due_date": "next_friday",
    "next_steps": [
      "Test each detector.",
      "Replace weak batteries.",
      "Record the check date for the household."
    ]
  },
  "executed_nodes": [
    "classify_request",
    "run_household_task",
    "build_answer"
  ],
  "final_answer": "Created task task_fc88cdc556: Check smoke and carbon monoxide detectors. Owner: household_lead. Due date: next_friday. First step: Test each detector."
}
```

Final answer: Created task task_fc88cdc556: Check smoke and carbon monoxide detectors. Owner: household_lead. Due date: next_friday. First step: Test each detector.

Observations:

```json
[
  {
    "node": "classify_request",
    "route": "household_task",
    "reason": "The user wants the assistant to create a structured task.",
    "missing_inputs": []
  },
  {
    "node": "run_household_task",
    "tool": "create_household_task",
    "result": {
      "task_id": "task_fc88cdc556",
      "status": "created",
      "task_type": "smoke_detector_check",
      "title": "Check smoke and carbon monoxide detectors",
      "owner": "household_lead",
      "due_date": "next_friday",
      "next_steps": [
        "Test each detector.",
        "Replace weak batteries.",
        "Record the check date for the household."
      ]
    }
  },
  {
    "node": "build_answer",
    "result": {
      "final_answer": "Created task task_fc88cdc556: Check smoke and carbon monoxide detectors. Owner: household_lead. Due date: next_friday. First step: Test each detector."
    }
  }
]
```

---
