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

# 2. Initialize the Slack Bolt App with your credentials
slack_app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

@slack_app.event("app_mention")
def handle_mentions(event, say):
    # 1. Extract the raw text from the Slack event
    raw_text = event.get('text', '')
    
    # 2. Strip out the bot's @mention string (e.g., "<@U123456> ")
    if ">" in raw_text:
        clean_text = raw_text.split(">", 1)[1].strip()
    else:
        clean_text = raw_text

    # Let the user know the bot is thinking
    say(f"_Analyzing database for:_ '{clean_text}' ⏳")

    try:
        # 3. Pass the clean text into your LangGraph brain
        result = langgraph_app.invoke({"user_query": clean_text})
        
        # 4. Extract the data from the final state
        sql_used = result.get('generated_sql', 'No SQL generated')
        results = result.get('query_results')
        columns = result.get('column_names')
        error = result.get('execution_error')

        # 5. Format the final Slack message
        if error:
            response_msg = f"❌ *Query Failed*\n*Error:* {error}"
        elif results:
            # Format the output as a clean text block
            formatted_results = f"**Columns:** {', '.join(columns)}\n" if columns else ""
            for row in results:
                formatted_results += f"• {row}\n"
            
            response_msg = f"✅ *Success!*\n*Executed SQL:*\n```sql\n{sql_used}\n```\n*Results:*\n{formatted_results}"
        else:
            response_msg = f"✅ *Success!*\n*Executed SQL:*\n```sql\n{sql_used}\n```\n*Results:* No data found for that query."

        # 6. Send the final compiled output back to the Slack channel
        say(response_msg)

    except Exception as e:
        say(f"⚠️ *System Error:* {str(e)}")

# 3. Initialize FastAPI and the Slack adapter
app = FastAPI()
handler = SlackRequestHandler(slack_app)

# 4. Create the webhook endpoint Slack will talk to
@app.post("/slack/events")
async def slack_events(req: Request):
    return await handler.handle(req)

# 5. A simple health check to ensure our server is alive
@app.get("/")
def health_check():
    return {"status": "ok", "message": "NL2SQL Bot is running!"}