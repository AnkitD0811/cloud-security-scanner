from langgraph.graph import END
from langchain_core.messages import ToolMessage
from langchain.messages import SystemMessage, HumanMessage
from typing import Literal

from templates import ReActGraphState, SecurityReport
from prompts import react_thinker_prompt_human, react_thinker_prompt_system, react_writer_prompt

from datetime import datetime
import json
import os

# ===== Simple Graph Node Functions =====

def get_file(state: dict) -> dict:
    """
    This node takes the file path and gets the IaC code.
    """

    print("Fetching code...")
    path = state["input_file_path"]

    try:
        with open(path, "r", encoding="utf-8") as f:
            iac_code = f.read()
    except FileNotFoundError:
        print(f"Error: File not found at {path}")
        iac_code = ""
    except Exception as e:
        print(f"Error reading file: {e}")
        iac_code = ""

    return {"iac_template": iac_code}


def generate_report_issues(state: dict, llm, prompt_template) -> dict:
    """
    This node calls the LLM to check and document all the issues in an IaC Template
    """

    if(state["iac_template"] == ""):
        return {"iac_issues" : []}

    print("Analyzing IaC Template...")
    iac_template = state["iac_template"]
    chain = prompt_template | llm
    ai_report = chain.invoke({"iac_template": iac_template})
    print("Report Scanned")
    return {"iac_issues": ai_report}
    

def populate_metadata(state: dict) -> dict:
    """
    This node populates the other fields of the SecuirtyReport Class
    """ 
    print("Generating Report Metadata...")
    # Extract issues from AI output
    issues = state.get("iac_issues", [])
    issues = issues.issues

    # Generate report name (FileName + Timestamp)
    file_name = state.get("input_file_path", "unknown_file").split("/")[-1]
    file_name = file_name.replace(".", "_")
    timestamp = datetime.now()
    name = f"{file_name}_{timestamp.strftime('%m-%d-%Y_%H:%M:%S')}"
    output_dir = "./outputs/" + name + "/" if state["output_dir"] == "" else state["output_dir"]

    # Compute summary
    summary = {
        "count": len(issues),
        "low": sum(1 for i in issues if i.severity == "Low"),
        "medium": sum(1 for i in issues if i.severity == "Medium"),
        "high": sum(1 for i in issues if i.severity == "High"),
    }

    # Populate state
    # state["name"] = name
    # state["summary"] = summary
    # state["timestamp"] = timestamp
    # state["file"] = state.get("file_path", "unknown_file")

    final_report = SecurityReport(
        name=name,
        summary=summary,
        timestamp=timestamp,
        file=state.get("input_file_path", "unknown_file"),
        issues=issues
    )
    
    print("Metadata Populated")

    return {"report": final_report, "output_dir": output_dir}


def save_results(state: dict):

    print("Generated Report:\n")
    report = json.dumps(state["report"].model_dump(), indent=2, default=str)
    print(report)

    output_file_path = state["output_dir"] + f"{state["report"].name}.json"
    os.makedirs(state["output_dir"], exist_ok=True)
    with open(output_file_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nReport saved to: {output_file_path}")

# ===== ReAct Agent Node Functions =====

def prepare_graph_state(state: ReActGraphState) -> dict:
    """
    Makes the following changes to the state:
    1. Prepares the messages list with an initial SystemMessage & HumanMessage.
    2. Prepares the output file directory.
    3. Creates the output files directory if not there already.
    4. Generates Output File Name.
    5. Loads the IaC template as a string
    """

    # Generate Output File Name(FileName + Timestamp)
    file_name = state.get("input_file_path", "unknown_file").split("/")[-1]
    file_name = file_name.replace(".", "_")
    timestamp = datetime.now()
    final_name = f"{file_name}_{timestamp.strftime('%m-%d-%Y_%H:%M:%S')}"
    output_dir = "./outputs/" + final_name + "/" if state["output_dir"] == "" else state["output_dir"]

    # Generate Output Directory
    os.makedirs(output_dir, exist_ok=True)

    # Load IaC template
    path = state.get("input_file_path", "unknown_file")
    try:
        with open(path, "r", encoding="utf-8") as f:
            iac_code = f.read()
    except FileNotFoundError:
        print(f"Error: File not found at {path}")
        iac_code = ""
    except Exception as e:
        print(f"Error reading file: {e}")
        iac_code = ""

    # Initialize messages(short-term memory) with initial prompt
    messages = [
        SystemMessage(content=react_thinker_prompt_system),
        HumanMessage(content=react_thinker_prompt_human.format(
            file_path=state["input_file_path"],
            output_dir=output_dir,
            output_file_name=final_name,
            iac_template=iac_code
        ))
    ]

    return {
        "messages": messages,
        "output_file_name": final_name,
        "output_dir": output_dir,
        "iac_template": iac_code
    }


def llm_call(state: ReActGraphState, reason_llm) -> dict:
    """
    Reasoning LLM.
    Takes the messages from state, decides whether to call a tool or generate Answer.
    No prompt required as LLM can get all the context from messages.
    Make sure to populate messages with an initial SystemMessage and HumanMessage.
    """

    print("Calling Agent(Thinking)...")

    # Get memory
    messages = state["messages"]
    # Get next step from LLM
    response = reason_llm.invoke(messages)

    return {"messages": [response]}


def tool_call(state: ReActGraphState, tool_list: dict) -> dict:
    """
    Performs the tool call as requested by the reasoning LLM.
    """

    print("Calling Tools...")
    
    # Get last message(list of tools to be called)
    last_message = state["messages"][-1]
    # List to store all tool outputs
    tool_messages = []
    # Iterate over all tools
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        try:
            tool_func = tool_list[tool_name]
            print(f"Running tool: {tool_name} with args: {tool_args}")
            observation = tool_func.invoke(tool_args)
            tool_messages.append(
                ToolMessage(
                    content=str(observation), # The tool's output
                    tool_call_id=tool_call["id"] # The ID from the original call
                )
            )

        except Exception as e:
            print("Error occured while running tool")
            print(e)
            tool_messages.append(
                ToolMessage(
                    content=f"Error running tool: {e}",
                    tool_call_id=tool_call["id"]
                )
            )

    return {"messages": tool_messages}


def should_continue(state: ReActGraphState) -> Literal["tool_call", "write_report"]:
    """
    Conditional Edge Logic to decide whether to generate final answer or not.
    Environment -> Tool Call
    """

    if state["messages"][-1].tool_calls:
        return "tool_call"
    else:
        return "write_report"

def write_report(state: ReActGraphState, writer_llm) -> dict:
    """
    Writes the final report JSON from all the tool outputs.
    """

    writer_prompt_template = react_writer_prompt

    tool_data = []
    for message in state["messages"]:
        if isinstance(message, ToolMessage):
            tool_data.append(message.content)

    chain = writer_prompt_template | writer_llm
    ai_report = chain.invoke({"tool_data": "\n\n".join(tool_data)})
    issues = ai_report.issues

    summary = {
            "count": len(issues),
            "low": sum(1 for i in issues if i.severity == "Low"),
            "medium": sum(1 for i in issues if i.severity == "Medium"),
            "high": sum(1 for i in issues if i.severity == "High"),
    }

    final_report = SecurityReport(
        name=state["output_file_name"],
        summary=summary,
        timestamp=datetime.now(),
        file=state.get("input_file_path", "unknown_file"),
        issues=issues
    )

    return {
        "iac_issues": ai_report,
        "report": final_report
    }

def save_final_results(state: ReActGraphState):
    """
    Save the final report as a json file
    """

    print("Generated Report:\n")
    report = json.dumps(state["report"].model_dump(), indent=2, default=str)
    print(report)

    output_file_path = state["output_dir"] + state["output_file_name"] + ".json"
    with open(output_file_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nReport saved to: {output_file_path}")

    print(f"\nFINAL_REPORT_PATH: {output_file_path}")
