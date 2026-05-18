# Minimal CRM Agent Demo

This is a very small Python demo for the OpenAI Responses API.

It shows a simplified CRM research workflow:

1. Ask the user for a company name and research context.
2. Check whether the request fits this narrow CRM research use case.
3. Search the web for public company information.
4. Clean the output with a simple output guardrail.
5. Ask the user to approve or reject each fact in the terminal.
6. Save the approved research note to a local SQLite database.

This is intentionally minimal and not production-ready.

## Run It

Install the OpenAI Python SDK:

```bash
pip install openai
```

Add your API key to `.env`:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

Run the script:

```bash
python3 crm_agent.py
```

The SQLite database is created automatically in this folder as `crm_demo.sqlite3`.

## Functions

`load_env_file()`

Loads `OPENAI_API_KEY` from the local `.env` file.

`check_input_guardrail(company_name, context)`

Checks whether the user request fits the CRM company research use case.

`research_company(company_name, context)`

Uses the Responses API with web search to collect five public company facts.

`apply_output_guardrail(research)`

Removes unwanted personal details, contact data, profiling, and recommendations.

`approve_facts(facts)`

Shows each fact and source in the terminal and asks the user to approve it.

`initialize_database()`

Creates the local SQLite database and table if they do not exist yet.

`save_crm_research(company_name, location, essay)`

Stores the final CRM research note in SQLite.

`save_with_function_call(research, approved_facts)`

Lets the model call the custom save function and then reports whether saving worked.

`main()`

Runs the full demo workflow from user input to final report.
