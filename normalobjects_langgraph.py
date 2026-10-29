from typing import Literal, TypedDict
from datetime import date
from pathlib import Path


# Allowed values make workflow decisions easier to inspect and document.
ComplaintCategory = Literal[
    "delivery_delay",
    "missing_items",
    "invoice_discrepancy",
    "other",
]

ValidationStatus = Literal[
    "valid",
    "missing_information",
    "invalid",
]

Severity = Literal[
    "low",
    "medium",
    "high",
]

CaseStatus = Literal[
    "open",
    "waiting_for_customer",
    "escalated",
    "resolved",
    "rejected",
]


class ComplaintState(TypedDict):
    """Shared state passed between nodes in the complaint workflow.

    Each node reads the fields it needs and returns the fields it updates.
    Keeping evidence and routing decisions here makes each run traceable.
    """

    # Original customer input
    complaint: str

    # Information extracted from the complaint
    category: ComplaintCategory | None
    order_id: str | None

    # Validation results
    validation_status: ValidationStatus | None
    validation_issues: list[str]

    # Investigation results and the evidence behind them
    investigation_evidence: list[str]
    evidence_sufficient: bool | None
    severity: Severity | None
    issue_detected: bool | None

    # Proposed action and human review decision
    resolution: str | None
    human_review_required: bool

    # Workflow trace and final outcome
    workflow_path: list[str]
    status: CaseStatus
    final_message: str | None


def create_initial_state(complaint: str) -> ComplaintState:
    """Create a complete, predictable state for a new complaint."""

    return {
        "complaint": complaint,
        "category": None,
        "order_id": None,
        "validation_status": None,
        "validation_issues": [],
        "investigation_evidence": [],
        "evidence_sufficient": None,
        "severity": None,
        "resolution": None,
        "human_review_required": False,
        "workflow_path": [],
        "status": "open",
        "final_message": None,
        "issue_detected": None,
    }

from typing import Literal

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


# Load OPENAI_API_KEY from the project's .env file.
load_dotenv()


class IntakeResult(BaseModel):
    """Structured fields extracted from the customer's complaint."""

    category: Literal[
        "delivery_delay",
        "missing_items",
        "invoice_discrepancy",
        "other",
    ] = Field(description="The complaint category that best fits the message.")

    order_id: str | None = Field(
        default=None,
        description="Order ID explicitly mentioned in the complaint, if any.",
    )


# Structured output makes the model return fields that the workflow can use.
intake_model = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
).with_structured_output(IntakeResult)


def intake_node(state: ComplaintState) -> dict:
    """Extract the complaint category and any explicitly stated order ID."""

    result = intake_model.invoke(
        [
            (
                "system",
                """
                Extract information from a B2B customer complaint.

                Choose exactly one category:
                - delivery_delay
                - missing_items
                - invoice_discrepancy
                - other

                Extract an order ID only if it is explicitly present.
                Do not invent missing information. Use "other" when the
                complaint does not fit the listed business categories.
                """,
            ),
            ("human", state["complaint"]),
        ]
    )

    # Return only the fields this node updates.
    # The remaining state is preserved by LangGraph.
    return {
        "category": result.category,
        "order_id": result.order_id,
        "workflow_path": state["workflow_path"] + ["intake"],
    }

def validation_node(state: ComplaintState) -> dict:
    """Check that the complaint has the minimum information for investigation."""

    issues: list[str] = []
    complaint = state["complaint"].strip()
    category = state["category"]
    order_id = state["order_id"]

    # Reject empty input before attempting an investigation.
    if not complaint:
        validation_status: ValidationStatus = "invalid"
        issues.append("The complaint text is empty.")

    # Ask the customer for the missing order reference.
    elif not order_id:
        validation_status = "missing_information"
        issues.append("An order ID is required to investigate this complaint.")

    else:
        validation_status = "valid"

    # An uncategorized business issue may still be valid.
    # Flag it for human review instead of rejecting it automatically.
    human_review_required = (
        state["human_review_required"]
        or (
            category == "other"
            and validation_status != "invalid"
        )
    )

    if category == "other" and validation_status != "invalid":
        issues.append(
            "The complaint does not match a standard category; "
            "human review is recommended."
        )

    if validation_status == "invalid":
        status: CaseStatus = "rejected"
    elif validation_status == "missing_information":
        status = "waiting_for_customer"
    else:
        status = state["status"]

    return {
        "validation_status": validation_status,
        "validation_issues": issues,
        "human_review_required": human_review_required,
        "status": status,
        "workflow_path": state["workflow_path"] + ["validate"],
    }

# Small local dataset for the lab.
# In a real system, this data would come from an order-management system.
SAMPLE_ORDERS = {
    "ORD-1042": {
        "status": "delivered",
        "promised_delivery": "2026-10-24",
        "actual_delivery": "2026-10-28",
        "missing_items": [],
        "invoice_matches_order": True,
    },
    "ORD-2081": {
        "status": "shipped",
        "promised_delivery": "2026-10-30",
        "actual_delivery": None,
        "missing_items": [],
        "invoice_matches_order": True,
    },
}

# Example business rule used during investigation.
LATE_DELIVERY_POLICY = (
    "If an order arrives more than 2 calendar days after its promised "
    "delivery date, flag it for review."
)


def investigation_node(state: ComplaintState) -> dict:
    """Compare the complaint with the order record and relevant policy."""

    order_id = state["order_id"]
    category = state["category"]
    order = SAMPLE_ORDERS.get(order_id) if order_id else None

    if order is None:
        return {
            "investigation_evidence": [
                f"No order record was found for order ID {order_id!r}."
            ],
            "evidence_sufficient": False,
            "issue_detected": None,
            "severity": "medium",
            "workflow_path": state["workflow_path"] + ["investigate"],
        }

    evidence = [f"Order {order_id} status: {order['status']}."]
    issue_detected = False
    evidence_sufficient = True
    severity: Severity = "low"

    if category == "delivery_delay":
        evidence.extend([
            f"Promised delivery date: {order['promised_delivery']}.",
            f"Actual delivery date: {order['actual_delivery'] or 'not delivered yet'}.",
            f"Policy checked: {LATE_DELIVERY_POLICY}",
        ])

        if order["actual_delivery"] is None:
            # The order has not arrived, so the final delay is not yet known.
            evidence_sufficient = False
        else:
            promised = date.fromisoformat(order["promised_delivery"])
            actual = date.fromisoformat(order["actual_delivery"])
            delay_days = (actual - promised).days
            issue_detected = delay_days > 2
            evidence.append(f"Calculated delivery delay: {delay_days} day(s).")
            severity = "medium" if issue_detected else "low"

    elif category == "missing_items":
        missing_items = order["missing_items"]
        evidence.append(f"Items recorded as missing: {missing_items}.")
        issue_detected = bool(missing_items)
        severity = "medium" if issue_detected else "low"

    elif category == "invoice_discrepancy":
        invoice_matches = order["invoice_matches_order"]
        evidence.append(f"Invoice matches the order record: {invoice_matches}.")
        issue_detected = not invoice_matches
        severity = "medium" if issue_detected else "low"

    else:
        # We have an order record, but no category-specific rule to investigate.
        evidence_sufficient = False

    return {
        "investigation_evidence": evidence,
        "evidence_sufficient": evidence_sufficient,
        "issue_detected": issue_detected if evidence_sufficient else None,
        "severity": severity,
        "workflow_path": state["workflow_path"] + ["investigate"],
    }


def resolution_node(state: ComplaintState) -> dict:
    """Recommend an outcome based on the investigation evidence."""

    category = state["category"]
    evidence_sufficient = state["evidence_sufficient"]
    issue_detected = state["issue_detected"]

    # Missing or inconclusive evidence must not lead to an automatic decision.
    if not evidence_sufficient or issue_detected is None:
        resolution = (
            "The available records are insufficient to confirm the complaint. "
            "Review the case and gather any missing evidence."
        )
        human_review_required = True

    elif issue_detected:
        recommendations = {
            "delivery_delay": (
                "The delay is supported by the order dates. "
                "Review the case for an appropriate service recovery."
            ),
            "missing_items": (
                "Missing items are recorded. Verify the shipment and review "
                "whether a reshipment or refund is appropriate."
            ),
            "invoice_discrepancy": (
                "The invoice does not match the order record. "
                "Ask the finance team to review it."
            ),
        }

        resolution = recommendations.get(
            category or "other",
            "The reported issue is supported by the evidence. "
            "Review the case before taking action.",
        )
        human_review_required = True

    else:
        resolution = (
            "The available order record does not confirm the reported issue. "
            "No adjustment is recommended based on the current evidence."
        )
        human_review_required = False

    status: CaseStatus = (
        "escalated" if human_review_required else "resolved"
    )

    return {
        "resolution": resolution,
        "human_review_required": human_review_required,
        "status": status,
        "workflow_path": state["workflow_path"] + ["resolve"],
    }


def close_node(state: ComplaintState) -> dict:
    """Create a traceable summary without adding unsupported claims."""

    evidence_text = "\n".join(
        f"- {item}" for item in state["investigation_evidence"]
    ) or "- No investigation evidence was recorded."

    if state["status"] == "rejected":
        outcome = "Closed: the complaint did not pass validation."
    elif state["status"] == "waiting_for_customer":
        outcome = "Waiting for customer information."
    elif state["human_review_required"] or state["status"] == "escalated":
        outcome = "Draft — human review required."
    else:
        outcome = "Resolved based on the available records."

    validation_notes = "\n".join(
        f"- {issue}" for issue in state["validation_issues"]
    ) or "- None"

    final_message = (
        f"{outcome}\n"
        f"Case status: {state['status']}\n"
        f"Category: {state['category'] or 'not determined'}\n"
        f"Order ID: {state['order_id'] or 'not provided'}\n"
        f"Validation notes:\n{validation_notes}\n"
        f"Investigation evidence:\n{evidence_text}\n"
        f"Recommended resolution: "
        f"{state['resolution'] or 'No resolution recorded.'}"
    )

    return {
        "final_message": final_message,
        "workflow_path": state["workflow_path"] + ["close"],
    }


from langgraph.graph import END, START, StateGraph


def route_after_validation(
    state: ComplaintState,
) -> Literal["investigate", "close"]:
    """Investigate valid cases; close incomplete or invalid cases."""

    if state["validation_status"] == "valid":
        return "investigate"

    return "close"


# Assemble the workflow as an explicit state graph.
workflow = StateGraph(ComplaintState)

workflow.add_node("intake", intake_node)
workflow.add_node("validate", validation_node)
workflow.add_node("investigate", investigation_node)
workflow.add_node("resolve", resolution_node)
workflow.add_node("close", close_node)

workflow.add_edge(START, "intake")
workflow.add_edge("intake", "validate")

# The first conditional branch in the graph:
# valid cases proceed; all other cases close with their current status.
workflow.add_conditional_edges(
    "validate",
    route_after_validation,
    {
        "investigate": "investigate",
        "close": "close",
    },
)

workflow.add_edge("investigate", "resolve")
workflow.add_edge("resolve", "close")
workflow.add_edge("close", END)

app = workflow.compile()


def visualize_workflow(
    result: ComplaintState | None = None,
    save_path: str | None = None,
) -> str:
    """Render the compiled graph and optionally highlight an execution path."""

    diagram = app.get_graph().draw_mermaid()

    if result:
        visited_nodes = list(dict.fromkeys(result["workflow_path"]))

        # Highlight nodes that were visited in this run.
        for node in visited_nodes:
            diagram += (
                f"\nstyle {node} "
                "fill:#DCFCE7,stroke:#15803D,stroke-width:3px"
            )

        print("Executed path:", " -> ".join(result["workflow_path"]))
        print("Final status:", result["status"])

    print("\nLangGraph workflow diagram:\n")
    print(diagram)

    if save_path:
        Path(save_path).write_text(diagram, encoding="utf-8")
        print(f"\nDiagram saved to: {save_path}")

    return diagram


if __name__ == "__main__":
    sample_complaint = (
        "Order ORD-1042 arrived later than promised. "
        "Please investigate the delivery delay."
    )

    initial_state = create_initial_state(sample_complaint)
    result = app.invoke(initial_state)

    visualize_workflow(result)
    print()
    print(result["final_message"])
