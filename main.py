import os
import json
import sys
from typing import Any, Dict, Optional

import pandas as pd 
from dotenv import load_dotenv
from openai import OpenAI
from pandasql import sqldf


def load_excel(path: str) -> pd.DataFrame:
    return pd.read_excel(path)


def run_sql_query(sql: str, df: pd.DataFrame) -> pd.DataFrame:
    # Executes a SELECT query via pandasql on the 'data' table.
    return sqldf(sql, {"data": df})


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace(".", "_", regex=False)
        .str.replace("-", "_", regex=False)
    )
    return df


def infer_schema(df: pd.DataFrame, table_name: str = "data", sample_n: int = 3)->str:
    lines: list[str] = [f"TABLE: {table_name}"]
    for col in df.columns:
        dtype = str(df[col].dtype)
        samples = (
            df[col]
            .dropna()
            .astype(str)
            .apply(lambda x: x[:20])
            .head(sample_n)
            .tolist()
        )
        lines.append(f"- {col} ({dtype}) samples={samples}")
    return "\n".join(lines)


SYSTEM_PROMPT = """
You are an AI data analyst working on a single SQL table called `data`.
The user will ask questions about the data. Your job is to write a single
SQL SELECT query that answers the question.

Context:
- The data from an Excel file has been loaded into a single table named `data`.
- The schema with column names and example values is provided.

Rules:
- The query MUST start with SELECT.
- Use only the table name `data`.
- Use only columns that exist in the provided schema.
- NEVER use UPDATE, DELETE, INSERT, DROP, CREATE, ALTER, TRUNCATE or ';'.
- Prefer simple, readable SQL.
- You may use WHERE, GROUP BY, ORDER BY, LIMIT and basic aggregates
  (COUNT, AVG, SUM, MIN, MAX).

You must ALWAYS respond with exactly one JSON object and NOTHING else.

JSON format:
{
  "sql": "<SQL query here as a single-line string>",
  "comment": "<very short explanation of what this query does>"
}
"""

def build_user_prompt(question: str, schema: str) -> str:
    return f"""SCHEMA:
{schema}

QUESTION:
{question}

Return ONLY a JSON object with fields "sql" and "comment"."""


def create_openai_client() -> OpenAI:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set (e.g. in .env).")
    return OpenAI(api_key=api_key)


def plan_with_llm(client: OpenAI, question: str, schema: str, max_retries: int = 1) -> Dict[str, Any]:
    # Calls gpt-4o-mini, returns JSON with 'sql' and 'comment'.
    user_prompt = build_user_prompt(question, schema)

    for attempt in range(max_retries + 1):
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=300,
        )

        raw_text = response.choices[0].message.content

        try:
            plan = json.loads(raw_text)
        except json.JSONDecodeError:
            if attempt < max_retries:
                continue
            raise ValueError(f"Model did not return valid JSON after retry. Raw: {raw_text}")

        if not isinstance(plan, dict):
            raise ValueError(f"Model did not return a JSON object. Raw: {raw_text}")

        if "sql" not in plan:
            raise ValueError(f"Plan does not contain 'sql' field. Raw: {raw_text}")

        return plan

    raise RuntimeError("Unknown error in plan_with_llm.")


def validate_sql_plan(plan: Dict[str, Any]) -> Optional[str]:
    """
    Checks if SQL looks safe:
    - 'sql' field exists
    - starts with SELECT
    - does not contain banned keywords
    """
    sql = plan.get("sql")
    if not isinstance(sql, str) or not sql.strip():
        return "Missing or empty 'sql' field."

    sql_clean = sql.strip().rstrip(";")
    plan["sql"] = sql_clean
    sql_lower = sql_clean.lower()

    if not sql_lower.startswith("select"):
        return "SQL must be a SELECT query."

    banned = ["update", "delete", "insert", "drop", "create", "alter", "truncate"]
    if any(b in sql_lower for b in banned):
        return "SQL contains banned keywords."

    return None


def execute_sql_plan(plan: Dict[str, Any], df: pd.DataFrame) -> pd.DataFrame:
    sql = plan["sql"]
    return run_sql_query(sql, df)


def print_intro(schema: str, df: pd.DataFrame) -> None:
    print("=== Data loaded ===")
    print(schema)


def pretty_print_results(result: pd.DataFrame) -> None:
    print(result.to_string(index=False))


def main():
    if len (sys.argv) < 2:
        print("Usage: python main.py <path_to_excel>")
        sys.exit(1)

    excel_path = sys.argv[1]

    df = load_excel(excel_path)
    df = normalize_columns(df)
    schema = infer_schema(df, table_name="data")

    client = create_openai_client()

    print_intro(schema, df)

    while True:
        question = input("\nAsk a data question (or type 'exit'): ").strip()
        if question.lower() in {"exit", "quit"}:
            print("Bye.")
            break

        try:
            plan = plan_with_llm(client, question, schema)
        except Exception as e:
            print(f"[LLM error] {e}")
            continue

        err = validate_sql_plan(plan)
        if err:
            print(f"[Plan rejected] {err}")
            print("SQL from model:", plan.get("sql"))
            continue

        print("\n[Generated SQL]")
        print(plan["sql"])
        if "comment" in plan:
            print("[Comment]", plan["comment"])

        try:
            result = execute_sql_plan(plan, df)
        except Exception as e:
            print(f"[Execution error] {e}")
            continue

        print("\n=== Result ===")
        pretty_print_results(result)


if __name__ == "__main__":
    main()
