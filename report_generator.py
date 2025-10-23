# TO GENERATE A REPORT IN JSON OUTPUT FROM IAC

#===== Importing Libraries & Env Variables======

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END

from templates import AIReport, GraphState
from prompts import report_generator_prompt
from graph_functions import get_file, generate_report_issues, populate_metadata, save_results

from dotenv import load_dotenv
import sys
from functools import partial

load_dotenv()

#===== Defining Agent to be used ======

# --- LLM ---

# Ollama - Mistral:7b-instruct for report generation.

# llm = ChatOllama(
#     model="mistral:7b-instruct",
#     temperature=0.1
# )

# Gemini - Non local alternative

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
).with_structured_output(AIReport)

# --- Prompt ---

prompt = report_generator_prompt

# ===== Graph Creation =====

graph = StateGraph(GraphState)

# --- Graph Nodes ---
graph.add_node("get_file", get_file)
graph.add_node("generate_report_issues", partial(generate_report_issues, llm=llm, prompt_template=prompt))
graph.add_node("populate_metadata", populate_metadata)
graph.add_node("save_results", save_results)

# --- Graph Edges ---
graph.add_edge(START, "get_file")
graph.add_edge("get_file", "generate_report_issues")
graph.add_edge("generate_report_issues", "populate_metadata")
graph.add_edge("populate_metadata", "save_results")
graph.add_edge("save_results", END)

# ===== Compilation & Inference =====

workflow = graph.compile()

if(len(sys.argv) != 2):
    print("""Incorrect number of arguments
    Usage: python main.py <file-path>""")

path = sys.argv[1]
initial_state = {"file_path": path}
final_state = workflow.invoke(initial_state)