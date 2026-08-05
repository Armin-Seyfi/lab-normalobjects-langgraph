# Chaos agent: tools, lore, less questionable judgments

> **How you'll submit this lab**
>
> This repo is your lab. Fork it, do the work described below in your fork, then open a pull
> request back into this repository. An AI reviewer will check your PR against `rubric.md` and
> leave feedback directly on the PR. See `README.md` for the full workflow.

## Learning Goal

You will build or evaluate one NormalObjects - Strict Complaint Processor (LangGraph) path and prove the answer is grounded in inspectable evidence.

## Working Context

This lab focuses on the chain between source material, tool behavior, and final answer.
You keep the system small enough to trace one query, one retrieval or tool step, and one final output.
The proof should show grounding, not just a successful response.

## Proof of Learning

Submit one `lab_proof.md` with the code or workflow, one query, retrieved or tool evidence, final output, and one failure or limitation.

## Pseudocode

```text
INPUT: source documents, tool result, or user query
DECIDE: retrieval, tool, agent, or guardrail path
BUILD: prepare source -> run path -> capture output
VERIFY: inspect evidence that supports the answer
EXPLAIN: identify one grounding risk or failure mode
```

## Prompt Discipline

Use AI for review, debugging, or critique. Do not ask it to produce the final artifact or final answer.

```text
Role: Retrieval or agent reviewer
Task: Review my plan for grounding and verification.
Inputs: source material, query, tool path, and proof evidence.
Constraints: Do not produce the final answer. Identify weak grounding and missing traces.
Output format: three grounding risks, two trace checks, and one simplification.
Verification: Name the evidence that ties the answer to the source.
```

## Build

## Step-by-Step Instructions

### Step 1: Setup and State Definition

Do: Set up LangGraph and define the state structure.

Do:
1. Create a new file: `normalobjects_langgraph.py`
2. Install required packages
3. Define the state TypedDict

---

### Step 2: Define Workflow Nodes

Do: Create node functions for each step in the workflow.

Do:
1. Create intake node (parse complaint)
2. Create validation node (check against rules)
3. Create investigation node (gather information)
4. Create resolution node (apply fix)
5. Create closure node (confirm completion)
```python
def intake_node(state: ComplaintState) -> ComplaintState:
    """Step 1: Intake - Parse and categorize the complaint"""
    print("\n[INTAKE] Processing complaint...")

    complaint = state["complaint"]

    # Categorize complaint using LLM
    categorization_prompt = f"""Categorize this Downside Up complaint into one of these categories:
- portal: Issues with portal timing, location, or behavior
- monster: Issues with creature behavior (demogorgons, etc.)
- psychic: Issues with psychic abilities or limitations
- environmental: Issues with electricity, weather, or physical environment
- other: Anything else

Complaint: {complaint}

Respond with ONLY the category name (portal, monster, psychic, environmental, or other)."""

    response = llm.invoke([HumanMessage(content=categorization_prompt)])
    category = response.content.strip().lower()

    # Update state
    new_state = {
        **state,
        "category": category,
        "workflow_path": state.get("workflow_path", []) + ["intake"],
        "status": "intake"
    }

    print(f"[INTAKE] Categorized as: {category}")
    return new_state

```

---

### Step 3: Build the Graph

Do: Connect nodes with edges to create the workflow graph.

Do:
1. Create StateGraph
2. Add all nodes
3. Define edges (linear and conditional)
4. Compile the graph
```python
# Create the graph, INCOMPLETE EXAMPLE - YOU MUST CONNECT AS YOU WISH
workflow = StateGraph(ComplaintState)

# Add nodes
workflow.add_node("intake", intake_node)

# Define edges
workflow.set_entry_point("intake")  # Start here

# Intake always goes to validate
workflow.add_edge("intake", "validate")

# Linear flow: investigate → resolve → close
workflow.add_edge("investigate", "resolve")
workflow.add_edge("resolve", "close")

# Close goes to end
workflow.add_edge("close", END)

# Compile the graph
app = workflow.compile()
```

---

### Step 4: Test the Workflow

Do: Test the structured workflow with sample complaints.
```python

test_complaints = [
    "The Downside Up portal opens at different times each day. How do I predict when?",
    "Demogorgons sometimes work together and sometimes fight. What's their deal?",
    "El can move things with her mind but can't lift heavy rocks. Why?",
    "Why do creatures and power lines react so strangely together?",
    "This is not a valid complaint about something random"  # Should be rejected
]

print("\nTesting workflow with sample complaints...\n")

```

---

### Step 5: Visualize Workflow Execution

Do: Create a function to visualize the workflow path or monitor the workflow path via logging.

---

### Step 6: Compare with LangChain Approach

Do: Document differences between structured and creative approaches.

---

## Submission Guidelines


## Extension Activities (Optional)

1. **Add parallel processing:** Investigate multiple categories simultaneously
2. **Add retry logic:** Retry failed steps with error handling
3. **Add human approval:** Include human-in-the-loop for certain resolutions
4. **Add persistence:** Save workflow state to database
5. **Create web interface:** Build UI to submit and track complaints

---

## Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [State Management Tutorial](https://langchain-ai.github.io/langgraph/tutorials/state/)
- [Conditional Edges Guide](https://langchain-ai.github.io/langgraph/how-tos/add-conditional-edges/)

---

## Troubleshooting

**Issue:** Workflow stops at a node
- **Solution:** Check node return values match state structure, verify edges are properly defined

**Issue:** Conditional routing doesn't work
- **Solution:** Ensure routing function returns valid node names, check conditional edge mapping

**Issue:** State not updating between nodes
- **Solution:** Make sure nodes return updated state dictionaries, check state structure matches TypedDict

**Issue:** Workflow goes to wrong node
- **Solution:** Verify edge definitions, check conditional routing logic, review entry point

## Verify

The reviewer can trace one answer back to retrieved content, tool output, or guardrail evidence.

## Explain

Where could the system produce a plausible but unsupported answer?

## Submission Sanity Check

Before you submit:
- Keep only files for this lab.
- Name files clearly.
- Remove secrets, API keys, tokens, and unrelated data.
- Make `lab_proof.md` the entry point for the reviewer.

## Optional Stretch

- Add one targeted improvement: better chunking, reranking, a guardrail, a trace view, or a failure-case test.
- Create a small demo UI with vibecoding only if it helps inspect sources and answers. Deploy only if it can run safely without exposed secrets.
