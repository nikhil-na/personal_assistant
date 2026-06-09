import os
import uuid
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama
from dotenv import load_dotenv
from agent import create_agent_graph
from langchain_core.messages import HumanMessage
from langgraph.types import Command

async def assistant():

    load_dotenv()

    server_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../server/mock_server.py"))

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


    # generate once when the terminal starts
    session_id = str(uuid.uuid4())
    run_config = {"configurable": {"thread_id": str(session_id)}}

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

        # First invocation
        response = await app.ainvoke(initial_state, config=run_config)

        # Handle interrupts in a loop (there could be multiple)
        while response.get("__interrupt__"):
            interrupt_payload = response["__interrupt__"][0]
            
            # Show the question to the user
            user_reply = input(f"Assistant: {interrupt_payload.value}\nYou: ").strip()

            # Resume the graph with the user's answer
            response = await app.ainvoke(
                Command(resume=user_reply),
                config=run_config  # same thread_id so it picks up where it left off
            )

        print(f"Assistant: {response}")



