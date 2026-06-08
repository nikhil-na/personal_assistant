import operator


from typing import TypedDict, Literal
from langchain_core.messages import AnyMessage
from typing_extensions import Annotated, Optional
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import StateGraph, START, END

# Define the state structure for the email agent
class EmailAgentState(TypedDict):
    intent: Optional[str] # E.g., "write_email", "read_email"
    recipient_name: Optional[str] # Missing info to look up
    recipient_email: Optional[str] 
    email_draft: Optional[str]
    is_approved: Optional[str]

    messages: Annotated[list[AnyMessage], operator.add]

# CREATING GRAPH OVERLAY
def create_agent_graph(tools: list):
    llm = ChatOllama(model="llama3.2", temperature=0.2)


    # NODES
    async def classifier_node(state: EmailAgentState):
        """Processes the user input and identifies what they want to do(search for emails or write an email)"""
        return {"intent": "write_email", "recipient_name": "Pratyush Khanal"}
    
    async def fetch_email_node(state: EmailAgentState):
        """Fetches all the emails from the provided email address or name"""
        print("Inbox: Found 2 unread emails.")
        return {}
    
    async def contact_node(state: EmailAgentState):
        """Resolves missing email addresses. Only runs ONCE."""
        if state["recipient_name"] and not state["recipient_email"]:
            # TODO: Search for email address based on the name
            return {"recipient_email": "pratyush@example.com"}
        return {}
    
    async def draft_node(state: EmailAgentState):
        """Drafts or rewrites the email."""
        return {"email_draft": "Hey, I won't be available to do that concept."}
    
    async def human_approval_node(state: EmailAgentState):
        """Asks for Human Approval before sending the email"""

        ##### PRINTING FOR UNDERSTANDING. DELETE LATER
        print(f"Generated Draft Content:\n\" {state.get("email_draft")} \"")


        user_choice = input("Send it? (yes/no): ").strip().lower()
        return {"is_approved": user_choice}
    
    async def send_email_node(state: EmailAgentState):
        """Executes the final email tool call to send the drafted email"""
        print("\n[NODE] SEND_EMAIL_NODE EXECUTING! Heading to END...")
        return {}
    
    # FIRST CONDITIONAL NODE
    async def route_after_classifer(state: EmailAgentState) -> Literal["fetch_email_node", "contact_node"]:
        """Decides where to go based on the classifier's output."""
        if state["intent"] == "read_emails":
            print("this was selected")
            return "fetch_email_node"
        return "contact_node"

    # SECOND CONDITIONAL NODE
    async def route_after_approval(state: EmailAgentState) -> Literal["send_email_node", "draft_node"]:
        """Decides if the LLM needs to run a tool, ask a human, or stop."""
        if state["is_approved"]== "yes":
            return "send_email_node"
        else:
            return "draft_node"


    # GRAPH CREATION
    workflow = StateGraph(EmailAgentState)
    # Add nodes with appropriate error handling
    workflow.add_node("classifier", classifier_node)
    workflow.add_node("fetch_email_node", fetch_email_node)
    workflow.add_node("contact_node", contact_node)
    workflow.add_node("draft_node", draft_node)
    workflow.add_node("human_approval", human_approval_node)
    workflow.add_node("send_email_node", send_email_node)

    workflow.add_edge(START, "classifier")
    workflow.add_conditional_edges("classifier", route_after_classifer, ["fetch_email_node", "contact_node"])
    workflow.add_edge("fetch_email_node", END)

    workflow.add_edge("contact_node", "draft_node")
    workflow.add_edge("draft_node", "human_approval")

    workflow.add_conditional_edges("human_approval", route_after_approval, ["send_email_node", "draft_node"])
    workflow.add_edge("send_email_node", END)

    return workflow.compile()