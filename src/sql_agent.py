import os
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv
from pathlib import Path

# Import the context assembler from the same src/ directory
from context_assembler import assemble_context

# Load the Groq API Key from your .env file in the root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# 1. Define the Graph State
class AgentState(TypedDict):
    user_query: str
    context: str
    generated_sql: str
    error: str

# 2. Node: Context Builder
def build_context_node(state: AgentState):
    print("\n--- NODE 1: Building Context ---")
    # Call the exact function we tested
    context_payload = assemble_context(state["user_query"])
    return {"context": context_payload}

# 3. Node: SQL Generator
def generate_sql_node(state: AgentState):
    print("\n--- NODE 2: Generating SQL ---")
    # Initialize the LLM with temperature=0 for highly deterministic, factual output
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    
    # Strictly instruct the LLM to output ONLY the query
    prompt = PromptTemplate.from_template(
        "{context}\n\nReturn ONLY the raw SQLite query. Do not include any explanations or markdown formatting like ```sql."
    )
    
    chain = prompt | llm
    result = chain.invoke({"context": state["context"]})
    
    # Clean up the output just in case the LLM tries to be overly helpful
    raw_sql = result.content.strip().replace("```sql", "").replace("```", "").strip()
    print(f"Generated SQL:\n{raw_sql}")
    
    return {"generated_sql": raw_sql}

# 4. Compile the LangGraph Workflow
workflow = StateGraph(AgentState)

# Add our nodes to the graph
workflow.add_node("build_context", build_context_node)
workflow.add_node("generate_sql", generate_sql_node)

# Define the flow: Start -> Context -> SQL -> End
workflow.set_entry_point("build_context")
workflow.add_edge("build_context", "generate_sql")
workflow.add_edge("generate_sql", END)

# Compile the graph into an executable application
app = workflow.compile()

if __name__ == "__main__":
    # Test query
    test_query = "Who purchased a Laptop Pro and used the SAVE10 coupon?"
    print(f"Starting LangGraph execution for query: '{test_query}'")
    
    # Trigger the multi-agent graph
    final_state = app.invoke({"user_query": test_query})
    
    print("\n==========================================")
    print("           FINAL GRAPH OUTPUT             ")
    print("==========================================")
    print(f"User Query: {final_state['user_query']}")
    print(f"Final SQL : \n{final_state['generated_sql']}")
    print("==========================================")