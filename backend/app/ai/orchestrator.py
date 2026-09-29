import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.schemas.ai import AskResponse, ToolCallRecord
from app.schemas.sql_tool import SQLQueryRequest
from app.services.schema_introspection import get_database_schema
from app.tools.sql_tool import execute_read_only_sql
from app.ai.prompts import SYSTEM_PROMPT_V1, format_schema_for_prompt
from app.ai.provider import BaseLLMProvider


def run_investigation_loop(
    question: str,
    db: Session,
    provider: BaseLLMProvider,
    max_turns: int = 3
) -> AskResponse:
    """
    Custom bounded decision intelligence orchestration loop.
    Connects LLM reasoning to the existing safe read-only SQL tool.
    """
    bounded_turns = min(max(max_turns, 1), 5)
    schema_context = get_database_schema(db)
    schema_text = format_schema_for_prompt(schema_context)

    tool_definitions = [{
        "name": "sql_query",
        "description": "Executes a safe read-only SQL SELECT query against the business database.",
        "parameters": {
            "sql": "string (SQL SELECT statement)",
            "max_rows": "integer (optional, default 100)"
        }
    }]

    messages: List[Dict[str, Any]] = [
        {"role": "user", "content": question}
    ]

    tool_call_records: List[ToolCallRecord] = []

    for turn in range(1, bounded_turns + 1):
        response = provider.generate_turn(
            messages=messages,
            tools=tool_definitions,
            schema_text=schema_text
        )

        if response.error:
            return AskResponse(
                success=False,
                question=question,
                answer="",
                tool_calls=tool_call_records,
                error=response.error
            )

        if response.has_tool_call and response.tool_call:
            tool_req = response.tool_call

            if tool_req.tool_name != "sql_query":
                err_msg = f"Unsupported tool requested by model: '{tool_req.tool_name}'"
                return AskResponse(
                    success=False,
                    question=question,
                    answer="",
                    tool_calls=tool_call_records,
                    error=err_msg
                )

            # Extract arguments and execute via existing safe SQL tool boundary
            raw_args = tool_req.arguments
            sql_str = raw_args.get("sql", "")
            max_r = raw_args.get("max_rows", 100)

            sql_req = SQLQueryRequest(sql=sql_str, max_rows=max_r)
            sql_result = execute_read_only_sql(db, sql_req)

            record = ToolCallRecord(
                turn=turn,
                tool_name="sql_query",
                arguments=raw_args,
                result=sql_result
            )
            tool_call_records.append(record)

            # Append tool result to messages history for model's next turn
            tool_res_text = json.dumps({
                "success": sql_result.success,
                "row_count": sql_result.row_count,
                "columns": sql_result.columns,
                "data": sql_result.data,
                "error_type": sql_result.error_type,
                "error_message": sql_result.error_message
            }, default=str)

            messages.append({"role": "model", "content": f"Requested tool 'sql_query' with SQL: {sql_str}"})
            messages.append({"role": "tool_result", "content": f"Tool Result for turn {turn}: {tool_res_text}"})

        elif response.content:
            # Model synthesized final answer
            return AskResponse(
                success=True,
                question=question,
                answer=response.content,
                tool_calls=tool_call_records,
                metadata={
                    "total_turns": turn,
                    "max_turns": bounded_turns,
                    "total_tool_calls": len(tool_call_records)
                }
            )

    # Max turns reached without explicit content finish
    final_summary = f"Investigation reached the maximum allowed turn boundary ({bounded_turns} turns)."
    if tool_call_records:
        last_rec = tool_call_records[-1]
        if last_rec.result.success:
            final_summary += f" Executed {len(tool_call_records)} tool query(ies). Last query returned {last_rec.result.row_count} records."
        else:
            final_summary += f" Last tool call failed: {last_rec.result.error_message}"

    return AskResponse(
        success=True,
        question=question,
        answer=final_summary,
        tool_calls=tool_call_records,
        metadata={
            "total_turns": bounded_turns,
            "max_turns": bounded_turns,
            "total_tool_calls": len(tool_call_records),
            "boundary_reached": True
        }
    )
