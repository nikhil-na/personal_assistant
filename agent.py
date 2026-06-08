import operator


from typing import TypedDict, Literal
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.messages import AnyMessage
from typing_extensions import Annotated, Optional
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import StateGraph, START, END

# Define the state structure for the email agent
class EmailAgentState(TypedDict):
    intent: Optional[str]
    recipient_name: Optional[str] # Missing info to look up
    recipient_email: Optional[str] 
    email_draft: Optional[str]
    is_approved: Optional[str]

    messages: Annotated[list[AnyMessage], operator.add]

class IntentExtractor(TypedDict):
    intent: Literal["None", "read_email", "write_email"]
    recipient_name: Optional[str]
    recipient_email: Optional[str] 

# CREATING GRAPH OVERLAY
def create_agent_graph(tools: list):
    llm = ChatOllama(model="llama3.2", temperature=0.2)

    # NODES
    async def classifier_node(state: EmailAgentState):
        """Processes the user input and identifies what they want to do(search for emails or write an email)"""
        
        user_message = state["messages"][-1]
        structured_llm = llm.with_structured_output(IntentExtractor)

        system_prompt = SystemMessage(
            content=(
                "You are a precise routing and intent classification assistant for an email management system.\n"
                "Your sole task is to analyze the user's latest input and extract intent behind the user input.\n"
                "CRITICAL INTENT RULES:\n"
                "1. 'fetch_email_node' -> User wants to read, check, find, view, or look up emails from a specific person/address.\n"
                "2. 'contact_node'   -> User wants to write, send, compose, or draft a new email.\n"
                "3. 'unknown'       -> Greetings, casual chat, or unrelated requests.\n\n"
                "EXTRACTION RULES:\n"
                "- If a person's name is mentioned (e.g., 'John', 'Sarah'), extract it into 'recipient_name'. Do not guess an email for them.\n"
                "- If an explicit email address is provided (e.g., 'test@example.com'), extract it into 'recipient_email.\n"
                "- If no name or email is mentioned, leave those fields as null.\n"
            )
        )

        human_prompt = HumanMessage(
            content=(f"User instruction: {user_message}")
        )

        structured_response = await structured_llm.ainvoke([system_prompt, human_prompt])
        # print(structured_response)
        return {
            "intent": structured_response["intent"],
            "recipient_name": structured_response["recipient_name"],
            "recipient_email": structured_response["recipient_email"],

            # I DON'T KNOW IF THIS IS THE STANDARD PRACTICE. WHAT I DID WAS SIMPLY WROTE A SIMPLE HUMAN LANGUAGE MESSAGE AND APPENDED TO THE MESSAGE HISTORY WITH AIMESSAGE(). WHAT MIGHT BE DONE? AFTER WE GET THE INTENT, THEN SIMPLY MAKE A CONDITIONAL NODE HERE AND GOTO NODES AS PER REQUIRED. FOLLOW: https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph#step-1-map-out-your-workflow-as-discrete-steps:~:text=if%20classification%5B%27intent%27%5D 
            "messages": [AIMessage(content=(f"System: Verified action as{structured_response["intent"]}"))]
        }

    async def fetch_email_node(state: EmailAgentState):
        """Fetches all the emails from the provided email address or name"""

        # Mocking the emails we "found"
        mock_emails = (
            "Found 2 unread emails:\n\n"
            "1. From: Bob (bob@gmail.com)\n"
            "   Subject: Project Update\n"
            "   Body: Hey, just wanted to check if the design draft is ready for review?\n\n"
            "2. From: Bob (bob@gmail.com)\n"
            "   Subject: Lunch Tomorrow\n"
            "   Body: Are we still on for tacos at 1 PM?"
        )
        return {
            # Appends these mock emails cleanly into your AnyMessage history array
            "messages": [AIMessage(content=mock_emails)]}
    
    async def contact_node(state: EmailAgentState):
        """Resolves missing email addresses. Only runs ONCE."""
        if state["recipient_name"] and not state["recipient_email"]:
            # TODO: Search for email address based on the name
            return {"recipient_email": "pratyush@example.com"}
        return {}
    
    async def draft_node(state: EmailAgentState):
        """Drafts or rewrites the email."""

        user_message = state["messages"][-1]
        recipient_name = state.get("recipient_name", "unknown")
        
        system_prompt = SystemMessage(
            content=(
                "You are an expert AI email assistant. Draft a concise, professional email body "
                f"addressed to '{recipient_name}' based strictly on the user's instructions. "
                "Do not include subject lines, placeholders, or meta-commentary. Just return the email body text."
            )
        )
        human_prompt = HumanMessage(
            content=(f"User instruction: {user_message}")
        )

        response = await llm.ainvoke([system_prompt, human_prompt])

        print(response)
        generated_content_parsed= response.content.strip()

        return {
            "messages": [response],
            "email_draft": generated_content_parsed,
        }
    
    async def human_approval_node(state: EmailAgentState):
        """Asks for Human Approval before sending the email"""
        user_choice = input("Send it? (yes/no): ").strip().lower()
        return {"is_approved": user_choice}
    
    async def send_email_node(state: EmailAgentState):
        """Executes the final email tool call to send the drafted email"""
        print("\n[NODE] SEND_EMAIL_NODE EXECUTING! Heading to END...")
        return {}
    
    # FIRST CONDITIONAL NODE
    async def route_after_classifer(state: EmailAgentState) -> Literal["fetch_email_node", "contact_node"]:
        """Decides where to go based on the classifier's output."""
        if state["intent"] == "read_email":
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
    workflow.add_conditional_edges("classifier", route_after_classifer, ["fetch_email_node", "contact_node", END])
    workflow.add_edge("fetch_email_node", END)

    workflow.add_edge("contact_node", "draft_node")
    workflow.add_edge("draft_node", "human_approval")

    workflow.add_conditional_edges("human_approval", route_after_approval, ["draft_node", "send_email_node", END])
    workflow.add_edge("send_email_node", END)

    return workflow.compile()