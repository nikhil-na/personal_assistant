import os
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama
from dotenv import load_dotenv
from agent import create_agent_graph
from langchain_core.messages import HumanMessage

async def assistant():

    load_dotenv()

    server_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../server/mock_server.py"))

    llm = ChatOllama(model="llama3.2", temperature=0.8)

    config = {
        "PersonalAssistant": {
            "transport": "stdio",
            "command": "uv",
            "args": [
                "run",
                server_path
            ]
        }
    }

    client = MultiServerMCPClient(config)
    tools = await client.get_tools()

    app = create_agent_graph(tools)

    while True:
        user_input = input("User: ").strip()
        if user_input.lower() in ["exit", "quit"]:
            print("Exiting assistant.")
            break
        
        # Set up a clean, blank initial state memory for this specific turn
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "intent": None,
            "recipient_name": None,
            "recipient_email": None,
            "email_draft": None,
            "is_approved": None
        }

        response = await app.ainvoke(initial_state)

        print(response)



