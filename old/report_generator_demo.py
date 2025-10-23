# Import libraries
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, START, END

from typing import TypedDict, List, Literal
from pydantic import BaseModel, Field

import json
from dotenv import load_dotenv

# Load env variables(Google API KEY)
load_dotenv()

# Define the structured output schema for the LLM
class SecurityIssue(BaseModel):
    """
    Represents a security issue found in the IaC template.
    """
    issue_name: str = Field(..., description="A concise name for the security issue.")
    severity: Literal['Low', 'Medium', 'High'] = Field(..., description="The severity level, can be either Low, Medium or High.")
    possible_problems: List[str] = Field(..., description="A list of potential problems or risks that could result from this misconfiguration.")
    remedies: List[str] = Field(..., description="A list of actionable steps to fix the issue.")

class SecurityReport(BaseModel):
    """
    The final security report with all identified issues.
    """
    report_title: str = Field(..., description="A title for the security report.")
    summary: str = Field(..., description="A brief summary of the overall security posture.")
    issues: List[SecurityIssue] = Field(..., description="A list of all security issues found in the IaC template.")


# Define the state for LangGraph
class GraphState(TypedDict):
    """
    Represents the state of the graph.
    """
    iac_template: str
    report: SecurityReport

# Define the LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0, # Concise results only
).with_structured_output(SecurityReport) # Structured schema based output

# Define the prompt template for the LLM
prompt_template = PromptTemplate(
    template="""
    You are an expert in Infrastructure as Code (IaC) security analysis. Your task is to analyze the following IaC template for security misconfigurations and generate a detailed report.

    The report must be a JSON object that strictly follows the provided schema. For each identified issue, you must provide:
    1. A concise name for the issue.
    2. A severity level ('High', 'Medium', 'Low').
    3. A list of possible problems that could arise from the misconfiguration.
    4. A list of actionable remedies to fix the issue.

    If no misconfigurations are found, generate an empty list of issues.

    Here is the IaC template to analyze:
    ```
    {iac_template}
    ```
    """,
    input_variables=["iac_template"],
)

# Create the chain for the LLM node
llm_chain = prompt_template | llm

# Define the node function for the graph
def generate_report(state: GraphState) -> GraphState:
    """
    This node takes the IaC template and generates a security report using the LLM.
    """
    print("Analyzing IaC template and generating report...")
    iac_template = state["iac_template"]
    report = llm_chain.invoke({"iac_template": iac_template})
    print("Report generated.")
    return {"report": report}

# Build the LangGraph
workflow = StateGraph(GraphState)

# Add the single node to the graph
workflow.add_node("generate_report", generate_report)

# Set the entry and exit points for the graph
workflow.add_edge(START, "generate_report")
workflow.add_edge("generate_report", END)

# Compile the graph into a runnable application
app = workflow.compile()


secure_iac_template = """
resource "aws_s3_bucket" "my_bucket" {
  bucket = "my-secure-bucket-12345"
  acl    = "private"

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }
}
"""
# -----------------TESTING---------------------

misconfigured_iac_template = """
resource "aws_s3_bucket" "my_bucket" {
  bucket = "my-public-bucket-12345"

  acl    = "public-read"
}

resource "aws_security_group" "my_sg" {
  name = "allow_all_inbound"
  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}"""

# Run the workflow with the misconfigured template
print("\n--- Running analysis on misconfigured template ---")
initial_state = {"iac_template": misconfigured_iac_template}
final_state = app.invoke(initial_state)

# Print the structured report
print("\nGenerated Security Report:")
print(json.dumps(final_state["report"].model_dump(), indent=2))

# Trying on a secure IaC template to cross check

secure_iac_template = """
resource "aws_s3_bucket" "my_bucket" {
  bucket = "my-secure-bucket-12345"
  acl    = "private"

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }
}
"""

print("\n--- Running analysis on secure template ---")
initial_state_secure = {"iac_template": secure_iac_template}
final_state_secure = app.invoke(initial_state_secure)

print("\nGenerated Security Report:")
print(json.dumps(final_state_secure["report"].model_dump(), indent=2))

# Trying on a template generated by SadCloud

with open("main.tf", "r") as f:
    tf_string = f.read()

print("\n--- Running analysis on template ---")
initial_state = {"iac_template": tf_string}
final_state = app.invoke(initial_state)

print("\nGenerated Security Report:")
print(json.dumps(final_state["report"].model_dump(), indent=2))