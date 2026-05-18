import json
import os
import sqlite3
from pathlib import Path

from openai import OpenAI


DEMO_DIR = Path(__file__).parent
ENV_PATH = DEMO_DIR / ".env"
DB_PATH = DEMO_DIR / "crm_demo.sqlite3"


def load_env_file():
    if not ENV_PATH.exists():
        return

    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_env_file()

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

client = OpenAI()


crm_save_tool = {
    "type": "function",
    "name": "save_crm_research",
    "description": "Save a minimal CRM research note for a company.",
    "parameters": {
        "type": "object",
        "properties": {
            "company_name": {
                "type": "string",
                "description": "Official or commonly used company name.",
            },
            "location": {
                "type": "string",
                "description": "Company headquarters or main public location.",
            },
            "essay": {
                "type": "string",
                "description": "A short CRM research note, maximum 500 words.",
            },
        },
        "required": ["company_name", "location", "essay"],
        "additionalProperties": False,
    },
    "strict": True,
}


def check_input_guardrail(company_name, context):
    response = client.responses.create(
        model=MODEL,
        reasoning={"effort": "low"},
        input=[
            {
                "role": "developer",
                "content": (
                    "You are an input guardrail. This tool is only for simple CRM company research. "
                    "Allowed: public company research for acquisition, investing, lending, sales, or account preparation. "
                    "Blocked: personal research, private contact discovery, doxxing, stalking, illegal requests, or requests unrelated to company research. "
                    "Blocked: any other use than research"
                    "Return exactly one word: ALLOWED or BLOCKED."
                ),
            },
            {
                "role": "user",
                "content": f"Company: {company_name}\nContext: {context}",
            },
        ],
    )
    return response.output_text.strip() == "ALLOWED"


def research_company(company_name, context):
    response = client.responses.create(
        model=MODEL,
        reasoning={"effort": "low"},
        tools=[{"type": "web_search"}],
        tool_choice="required",
        input=[
            {
                "role": "developer",
                "content": (
                    "You are a very simple CRM research agent. Use web search. "
                    "Find public, source-backed company information for the given context. "
                    "Do not include private personal information, contact details, personal addresses, private emails, or phone numbers. "
                    "Names and public roles of senior leaders are allowed only when directly relevant. "
                    "Do not create a risk score, psychological profile, or investment recommendation. "
                    "Return only valid JSON with this shape: "
                    "{"
                    '"company_name": "...", '
                    '"location": "...", '
                    '"facts": ['
                    '{"fact": "...", "source_title": "...", "source_url": "..."}'
                    "], "
                    '"essay": "..."'
                    "}. "
                    "Return exactly 5 facts. Keep the essay under 500 words."
                ),
            },
            {
                "role": "user",
                "content": f"Company: {company_name}\nResearch context: {context}",
            },
        ],
    )
    return json.loads(response.output_text)


def apply_output_guardrail(research):
    response = client.responses.create(
        model=MODEL,
        reasoning={"effort": "low"},
        input=[
            {
                "role": "developer",
                "content": (
                    "You are an output guardrail. Clean this CRM research JSON. "
                    "Remove doxxing, private contact details, personal addresses, private emails, phone numbers, and personal profiling. "
                    "Keep only public company-level facts and public role/name information when directly relevant. "
                    "Do not add a recommendation, rating, risk score, or subjective company profile. "
                    "Return only valid JSON in the same shape. Keep the essay under 500 words."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(research, ensure_ascii=False),
            },
        ],
    )
    return json.loads(response.output_text)


def approve_facts(facts):
    approved_facts = []

    print("\nPlease approve the facts that should be used in the CRM note.\n")

    for number, item in enumerate(facts, start=1):
        print(f"Fact {number}: {item['fact']}")
        print(f"Source: {item['source_title']} - {item['source_url']}")
        answer = input("Keep this fact? (y/n): ").strip().lower()
        print()

        if answer == "y":
            approved_facts.append(item)

    return approved_facts


def initialize_database():
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    cursor.execute(
        """
        create table if not exists crm_research (
            id integer primary key autoincrement,
            company_name text,
            location text,
            essay text,
            created_at datetime default current_timestamp
        )
        """
    )
    connection.commit()
    connection.close()


def save_crm_research(company_name, location, essay):
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    cursor.execute(
        "insert into crm_research (company_name, location, essay) values (?, ?, ?)",
        (company_name, location, essay),
    )
    connection.commit()
    row_id = cursor.lastrowid
    connection.close()

    return {
        "success": True,
        "database": str(DB_PATH),
        "row_id": row_id,
    }


def save_with_function_call(research, approved_facts):
    response = client.responses.create(
        model=MODEL,
        reasoning={"effort": "low"},
        tools=[crm_save_tool],
        tool_choice="required",
        input=[
            {
                "role": "developer",
                "content": (
                    "Use the save_crm_research function exactly once. "
                    "Write a maximum 500 word CRM note using only the approved facts. "
                    "After the function result is returned, summarize whether saving worked."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "company_name": research["company_name"],
                        "location": research["location"],
                        "approved_facts": approved_facts,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    )

    function_call = next(item for item in response.output if item.type == "function_call")
    arguments = json.loads(function_call.arguments)
    result = save_crm_research(**arguments)

    final_response = client.responses.create(
        model=MODEL,
        reasoning={"effort": "low"},
        tools=[crm_save_tool],
        previous_response_id=response.id,
        input=[
            {
                "type": "function_call_output",
                "call_id": function_call.call_id,
                "output": json.dumps(result),
            }
        ],
    )

    return final_response.output_text


def main():
    initialize_database()

    company_name = input("Company name: ")
    context = input("Why do you need this research? ")

    print("\nRunning input guardrail...")
    allowed = check_input_guardrail(company_name, context)

    if not allowed:
        print("Blocked: this demo is only for simple CRM company research.")
        return

    print("Researching with Responses API web search...")
    research = research_company(company_name, context)

    print("Applying output guardrail...")
    research = apply_output_guardrail(research)

    approved_facts = approve_facts(research["facts"])

    print("Calling custom save function through the Responses API...")
    report = save_with_function_call(research, approved_facts)

    print("\nOutput report")
    print("-------------")
    print(report)


if __name__ == "__main__":
    main()
