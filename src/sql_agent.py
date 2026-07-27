import os
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv
from pathlib import Path
from typing import TypedDict, Optional, Any
import sqlite3
import sqlparse
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
    query_results: Optional[Any]
    column_names: Optional[list[str]]
    execution_error: Optional[str]
    retry_count: int

# 2. Node: Context Builder
def build_context_node(state: AgentState):
    print("\n--- NODE 1: Building Context ---")
    # Call the exact function we tested
    context_payload = assemble_context(state["user_query"])
    return {"context": context_payload}

# 3. Node: SQL Generator
def generate_sql_node(state: AgentState):
    print("\n--- NODE 2: Generating SQL ---")
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    
    # Check if we are in a self-healing loop
    error_msg = state.get("execution_error")
    retry_count = state.get("retry_count", 0)
    
    # Base instructions
    prompt_str = "{context}\n\nReturn ONLY the raw SQLite query. Do not include any explanations or markdown formatting like ```sql."
    
    # If self-healing, inject the error into the prompt!
    if error_msg:
        print(f"[SELF-HEALING] Attempt {retry_count + 1} - Fixing error: {error_msg}")
        prompt_str += f"\n\nWARNING: Your previous SQL failed with this SQLite Error:\n{error_msg}\nFix the query and try again."
        
    prompt = PromptTemplate.from_template(prompt_str)
    chain = prompt | llm
    result = chain.invoke({"context": state["context"]})
    
    raw_sql = result.content.strip().replace("```sql", "").replace("```", "").strip()
    print(f"Generated SQL:\n{raw_sql}")
    
    return {
        "generated_sql": raw_sql, 
        "retry_count": retry_count + 1 # Increment the retry counter
    }

def security_gate_node(state: AgentState):
    """Node 2.5: Parses the SQL to ensure it is purely read-only (SELECT) and enforces limits."""
    print("\n--- NODE 2.5: Security Gate ---")
    raw_sql = state.get("generated_sql", "")
    
    if not raw_sql:
        return {"execution_error": "No SQL provided to security gate."}

    # Parse the SQL to understand its structure
    parsed = sqlparse.parse(raw_sql)
    if not parsed:
        return {"execution_error": "Unparsable SQL generated."}
        
    stmt = parsed[0]
    stmt_type = stmt.get_type().upper()
    
    # 1. STRICT BLOCK: Allow only SELECT statements
    if stmt_type != "SELECT":
        error_msg = f"SECURITY ALERT: Blocked a {stmt_type} statement. Only SELECT queries are permitted."
        print(f"[BLOCKED] {error_msg}")
        return {
            "generated_sql": None, # Wipe the query so it cannot be executed
            "execution_error": error_msg
        }
        
    # 2. ENFORCE LIMIT: Prevent massive data dumps that could crash Slack
    if "LIMIT" not in raw_sql.upper():
        raw_sql += " LIMIT 100"
        print("[MODIFIED] Automatically appended 'LIMIT 100' to query.")
        
    print("[PASSED] Query is a valid SELECT statement.")
    return {"generated_sql": raw_sql}


def execute_sql(state: AgentState) -> dict:
    """Node 3: Executes the SQL query and catches SQLite errors."""
    print("---NODE 3: EXECUTING SQL---")
    
    query = state.get("generated_sql")
    
    if not query:
        return {"execution_error": "No SQL query provided to the executor."}
        
    # Dynamically resolve the absolute path to ecommerce.db
    base_dir = Path(__file__).resolve().parent.parent
    db_path = base_dir / "data" / "ecommerce.db"
    
    try:
        # Connect to the database and execute
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        # Extract column names to provide context for the final output
        column_names = [description[0] for description in cursor.description] if cursor.description else []
        
        conn.close()
        
        return {
            "query_results": results,
            "column_names": column_names,
            "execution_error": None # Clear any previous errors
        }
        
    except sqlite3.Error as e:
        print(f"---EXECUTION FAILED: {str(e)}---")
        # Catch SQL syntax errors or hallucinated tables/columns
        return {
            "query_results": None,
            "column_names": None,
            "execution_error": f"SQLite Error: {str(e)}"
        }

def route_after_execution(state: AgentState):
    """Router: Decides whether to finish or send the error back to the Drafter."""
    error = state.get("execution_error")
    retry_count = state.get("retry_count", 0)
    
    # If there is an error AND we haven't hit our retry limit (e.g., max 3 tries)
    # Note: We also check if 'generated_sql' exists so we don't retry malicious DROP commands.
    if error and state.get("generated_sql") and retry_count < 3:
        print(f"\n--- ROUTING: Error detected. Routing back to Drafter (Attempt {retry_count}/3) ---")
        return "generate_sql"
    
    if error and retry_count >= 3:
        print("\n--- ROUTING: Max retries reached. Failing gracefully. ---")
        
    return END
    
# 4. Compile the LangGraph Workflow
workflow = StateGraph(AgentState)

# Add our nodes to the graph
workflow.add_node("build_context", build_context_node)
workflow.add_node("generate_sql", generate_sql_node)
workflow.add_node("security_gate", security_gate_node)
workflow.add_node("execute_sql", execute_sql)
# Define the flow: Start -> Context -> SQL -> End
workflow.set_entry_point("build_context")
workflow.add_edge("build_context", "generate_sql")
workflow.add_edge("generate_sql", "security_gate")     # Route to Security
workflow.add_edge("security_gate", "execute_sql")      # Route to Executor
# Replace the old END edge with our new conditional router
workflow.add_conditional_edges(
    "execute_sql",
    route_after_execution,
    {
        "generate_sql": "generate_sql", # Route backward to heal
        END: END                        # Route forward to finish
    }
)

# Compile the graph into an executable application
app = workflow.compile()

if __name__ == "__main__":
    # Test query
    test_query = "What is the phone_number of the user who bought a Laptop Pro?"
    print(f"Starting LangGraph execution for query: '{test_query}'")
    
    # Trigger the multi-agent graph
    final_state = app.invoke({"user_query": test_query})
    
    print("\n==========================================")
    print("           FINAL GRAPH OUTPUT             ")
    print("==========================================")
    print(f"User Query: {final_state['user_query']}")
    print(f"Final SQL : \n{final_state['generated_sql']}")
    print("==========================================")
    print(f"Column Names    : {final_state.get('column_names')}")
    print(f"Query Results   : {final_state.get('query_results')}")
    print(f"Execution Error : {final_state.get('execution_error')}")
    print("==========================================")