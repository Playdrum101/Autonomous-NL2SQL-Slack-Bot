import os
from fastapi import FastAPI, Request
from slack_bolt import App
from slack_bolt.adapter.fastapi import SlackRequestHandler
from dotenv import load_dotenv
from pathlib import Path
from src.sql_agent import app as langgraph_app

# 1. Load environment variables
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# 2. Initialize the Slack Bolt App
slack_app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# ---------------------------------------------------------
# EVENT HANDLER: User tags the bot
# ---------------------------------------------------------
@slack_app.event("app_mention")
def handle_mentions(event, say):
    raw_text = event.get('text', '')
    if ">" in raw_text:
        clean_text = raw_text.split(">", 1)[1].strip()
    else:
        clean_text = raw_text

    # Create a unique Thread ID using the Slack message timestamp
    thread_id = event.get('ts')
    config = {"configurable": {"thread_id": thread_id}}

    say(f"_Analyzing database for:_ '{clean_text}' ⏳")

    try:
        # Invoke the graph with the thread configuration
        result = langgraph_app.invoke({"user_query": clean_text}, config=config)
        
        # Check the current status of the graph
        current_state = langgraph_app.get_state(config)
        
        # If the graph is paused right before 'execute_sql', ask for human approval
        if "execute_sql" in current_state.next:
            sql_used = result.get('generated_sql', 'No SQL generated')
            
            # SLACK BLOCK KIT: The UI for Approval
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "⚠️ *Approval Required*\nThe AI drafted the following SQL query. Please review it before execution:"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"```sql\n{sql_used}\n```"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Approve ✅"},
                            "style": "primary",
                            "action_id": "approve_sql",
                            "value": thread_id  # Pass the thread ID so the button knows which memory to wake up
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Deny ❌"},
                            "style": "danger",
                            "action_id": "deny_sql",
                            "value": thread_id
                        }
                    ]
                }
            ]
            say(blocks=blocks, text="SQL requires approval")
            
        else:
            # If it didn't pause, it likely failed the Security Gate or self-healing limits
            error = result.get('execution_error', 'Unknown Error')
            say(f"❌ *Query Failed/Blocked*\n*Error:* {error}")

    except Exception as e:
        say(f"⚠️ *System Error:* {str(e)}")


# ---------------------------------------------------------
# ACTION HANDLER: User clicks "Approve ✅"
# ---------------------------------------------------------
@slack_app.action("approve_sql")
def approve_sql(ack, body, say):
    ack() # Instantly tell Slack we received the button click
    
    # Retrieve the exact thread ID from the button's hidden value
    thread_id = body['actions'][0]['value']
    config = {"configurable": {"thread_id": thread_id}}
    
    say("_Executing query..._ 🏃‍♂️")
    
    try:
        # Resume the graph by passing None as the input
        result = langgraph_app.invoke(None, config=config)
        
        sql_used = result.get('generated_sql', '')
        results = result.get('query_results')
        columns = result.get('column_names')
        error = result.get('execution_error')

        if error:
            response_msg = f"❌ *Execution Failed*\n*Error:* {error}"
        elif results:
            formatted_results = f"**Columns:** {', '.join(columns)}\n" if columns else ""
            for row in results:
                # Formatting the tuple output cleanly
                clean_row = ", ".join([str(item) for item in row])
                formatted_results += f"• {clean_row}\n"
            
            response_msg = f"✅ *Success!*\n*Executed SQL:*\n```sql\n{sql_used}\n```\n*Results:*\n{formatted_results}"
        else:
            response_msg = f"✅ *Success!*\n*Executed SQL:*\n```sql\n{sql_used}\n```\n*Results:* No data found."

        say(response_msg)
        
    except Exception as e:
        say(f"⚠️ *Execution Error:* {str(e)}")


# ---------------------------------------------------------
# ACTION HANDLER: User clicks "Deny ❌"
# ---------------------------------------------------------
@slack_app.action("deny_sql")
def deny_sql(ack, body, say):
    ack()
    say("🛑 *Execution Denied by User.* The query was safely discarded.")


# 3. Initialize FastAPI and the Slack adapter
app = FastAPI()
handler = SlackRequestHandler(slack_app)

@app.post("/slack/events")
async def slack_events(req: Request):
    return await handler.handle(req)

@app.get("/")
def health_check():
    return {"status": "ok", "message": "NL2SQL Bot is running!"}