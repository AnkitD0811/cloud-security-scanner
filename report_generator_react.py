# TO GENERATE A REPORT IN JSON OUTPUT FROM IAC
# ReAct Agent Variant With Tools

# ===== Importing Libraries & Env Variables======

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END

from templates import AIReport, ReActGraphState
from graph_functions import prepare_graph_state, llm_call, tool_call, should_continue, write_report, save_final_results
from tools import checkov_tool

from dotenv import load_dotenv
import sys
from functools import partial

load_dotenv()

# ===== Defining Tool List =====

tool_list = {
    "checkov_tool" : checkov_tool
}

# ===== Defining Agents to be Used =====

# --- Reasoning LLM ---

# Ollama - Mistral:7b-instruct for report generation.

# llm = ChatOllama(
#     model="mistral:7b-instruct",
#     temperature=0.1
# )

# Gemini - Non local alternative

reason_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
).bind_tools([checkov_tool])

# --- Writer LLM ---

writer_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
).with_structured_output(AIReport)

# ===== Graph Creation =====

agent = StateGraph(ReActGraphState)

# --- Graph Nodes ---

agent.add_node("prepare_graph_state", prepare_graph_state)
agent.add_node("llm_call", partial(llm_call, reason_llm = reason_llm))
agent.add_node("tool_call", partial(tool_call, tool_list = tool_list))
agent.add_node("write_report", partial(write_report, writer_llm = writer_llm))
agent.add_node("save_final_results", save_final_results)

# --- Graph Edges ---

agent.add_edge(START, "prepare_graph_state")
agent.add_edge("prepare_graph_state", "llm_call")
agent.add_conditional_edges("llm_call", 
    should_continue, 
    {
        "tool_call": "tool_call",
        "write_report": "write_report"
    })
agent.add_edge("tool_call", "llm_call")
agent.add_edge("write_report", "save_final_results")
agent.add_edge("save_final_results", END)

# --- Agent compilation ---

react_agent = agent.compile()

if(len(sys.argv) != 2):
    print("""Incorrect number of arguments
    Usage: python main.py <file-path>""")

path = sys.argv[1]
initial_state = {"input_file_path": path, "output_dir": ""}
final_state = react_agent.invoke(initial_state)