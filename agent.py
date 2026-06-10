import operator
import re

from typing import TypedDict, Literal
from langchain_core.messages import AnyMessage
from typing_extensions import Annotated, Optional
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langgraph.checkpoint.memory import MemorySaver

# Define the state structure for the email agent
class EmailAgentState(TypedDict):
    intent: Optional[str]
    recipient_name: Optional[str]
    recipient_email: Optional[str] 
    email_draft: Optional[str]
    is_approved: Optional[str]

    messages: Annotated[list[AnyMessage], operator.add]

class IntentExtractor(TypedDict):
    intent: Literal["None", "read_email", "write_email"]
    recipient_name: Optional[str]
    recipient_email: Optional[str] 

# CREATING GRAPH OVERLAY
def create_agent_graph(tools: list, use_checkpointer: bool = True):
    llm = ChatOllama(model="llama3.2", temperature=0.2)

    #Map tools by name so our nodes can find and execute them easily
    tools_by_names = {t.name: t for t in tools}

    # NODES
    async def classifier_node(state: EmailAgentState):
        """Processes the user input and identifies what they want to do(search for emails or write an email)"""
        
        user_message = state["messages"][-1]
        structured_llm = llm.with_structured_output(IntentExtractor)

        system_prompt = SystemMessage(
            content=(
                "You are a precise routing and intent classification assistant for an email management system.\n"
                "Analyze the user's latest input and extract the core intent, recipient name, and explicit email.\n\n"
                "INTENT RULES:\n"
                "- 'read_email'  -> User wants to read, check, find, view, or look up emails.\n"
                "- 'write_email' -> User wants to write, send, compose, or draft a new email.\n"
                "- 'None'        -> Greetings, casual chat, or unrelated requests.\n\n"
                "CRITICAL EXTRACTION RULES:\n"
                "1. Extract a person's name (like 'nikhil') into 'recipient_name'.\n"
                "2. For 'recipient_email': ONLY extract a value if the user explicitly typed an email address containing an '@' symbol in their message. BE VERY STRICT ABOUT THIS. If they did not type a full email address, you MUST set 'recipient_email' to null.\n"
                "3. DO NOT invent, guess, or placeholder any email address. Never output an email address that wasn't literally provided by the user."
            )
        )

        human_prompt = HumanMessage(
            content=(f"User instruction: {user_message}")
        )

        structured_response = await structured_llm.ainvoke([system_prompt, human_prompt])

        print(structured_response)

        raw_email = structured_response.get("recipient_email")
        cleaned_email = raw_email if (raw_email and "@" in raw_email) else None

        print(f"email: {cleaned_email}")
        print(structured_response["recipient_name"])

        return {
            "intent": structured_response["intent"],
            "recipient_name": structured_response["recipient_name"],
            "recipient_email": cleaned_email,

            # I DON'T KNOW IF THIS IS THE STANDARD PRACTICE. WHAT I DID WAS SIMPLY WROTE A SIMPLE HUMAN LANGUAGE MESSAGE AND APPENDED TO THE MESSAGE HISTORY WITH AIMESSAGE(). WHAT MIGHT BE DONE? AFTER WE GET THE INTENT, THEN SIMPLY MAKE A CONDITIONAL NODE HERE AND GOTO NODES AS PER REQUIRED. FOLLOW: https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph#step-1-map-out-your-workflow-as-discrete-steps:~:text=if%20classification%5B%27intent%27%5D 

            # "messages": []
        }

    async def fetch_email_node(state: EmailAgentState):
        """Fetches all the emails from the provided name via IMAP tool."""

        fetch_tool = tools_by_names.get("fetch_emails")
        name = state["recipient_name"]
        email = state["recipient_email"]
        if fetch_tool:
            result = await fetch_tool.ainvoke({"name": name, "email": email})
            return {
                "messages": [AIMessage(content=result)]
            }
        return {"error": "no fetch email node tool found"}

    async def contact_node(state: EmailAgentState):
        """Resolves missing email addresses and requests one if lookup fails."""
        if not (state["recipient_email"]):
            search_tool = tools_by_names.get("search_gmail_contacts")

            recipient_name = state.get("recipient_name")
            if not recipient_name:
                return {}

            lookup_result = await search_tool.ainvoke({"name": recipient_name})

            if isinstance(lookup_result, dict) and lookup_result.get("email"):
                found_email = lookup_result["email"]
                print("===from contact node===")
                print(f"DEBUG: found email = {found_email}")
                print(f"DEBUG: returning = {{'recipient_email': {found_email}}}")
                return {"recipient_email": found_email}

            # No email found — interrupt and ask the user
            # LangGraph will pause here and resume with the user's reply as the return value
            else:
                user_provided_email = interrupt(
                    f"I couldn't find an email address for {recipient_name}. "
                    f"Please provide their email address:"
                )
                add_email_tool = tools_by_names.get("add_email_database")
                await add_email_tool.ainvoke({"name": recipient_name, "email": user_provided_email})

            return {"recipient_email": user_provided_email}
        return {}

    async def draft_node(state: EmailAgentState):
        """Drafts or rewrites the email."""
        print(f"DEBUG draft_node state: recipient_email={state.get('recipient_email')}, recipient_name={state.get('recipient_name')}")


        user_message = state["messages"]
        recipient_name = state.get("recipient_name", "unknown")
        
        system_prompt = SystemMessage(
            content=(
                "You are an expert AI email assistant. Draft a concise, professional email body "
                f"addressed to '{recipient_name}' based strictly on the user's instructions. "
                "Do not include subject lines, placeholders, or meta-commentary. Just return the email body text."
                "The name of the sender should be Nikhil Aryal."
            )
        )
        human_prompt = HumanMessage(
            content=(f"User instruction: {user_message}")
        )

        response = await llm.ainvoke([system_prompt, human_prompt])
        generated_content_parsed= response.content.strip()

        return {
            "messages": [response],
            "email_draft": generated_content_parsed,
        }
    
    async def human_approval_node(state: EmailAgentState):
        """Asks for Human Approval before sending the email"""

        user_choice = interrupt(
            f"Here is your draft: {state["email_draft"]}.\n\n Send it? (yes/no): "
        )
        return {"is_approved": user_choice.strip().lower()}
    
    async def send_email_node(state: EmailAgentState):
        """Executes the final email tool call to send the drafted email"""
        print("\n[NODE] SEND_EMAIL_NODE EXECUTING! Heading to END...")
        send_email_tool = tools_by_names.get("send_email")

        recipient_email = state["recipient_email"]
        recipient_name = state["recipient_name"]
        email_body = state["email_draft"]

        await send_email_tool.ainvoke({"recipient": recipient_email, "body": email_body})
        
        return {}

    
    # FIRST CONDITIONAL NODE
    async def route_after_classifer(state: EmailAgentState) -> Literal["fetch_email_node", "contact_node"]:
        """Decides where to go based on the classifier's output."""
        if state["intent"] == "read_email":
            return "fetch_email_node"
        elif state["intent"] == "write_email":
            return "contact_node"
        return END

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

    if use_checkpointer:
        return workflow.compile(checkpointer=MemorySaver())
    else:
        return workflow.compile()  # langgraph dev provides its own

agent = create_agent_graph(tools=[], use_checkpointer=False)