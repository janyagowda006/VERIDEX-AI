from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from app.core.config import settings


class ToolCallRequest(BaseModel):
    """
    Internal provider-agnostic representation of a tool call request.
    """
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ModelResponse(BaseModel):
    """
    Internal provider-agnostic representation of an LLM turn response.
    """
    has_tool_call: bool = False
    tool_call: Optional[ToolCallRequest] = None
    content: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BaseLLMProvider(ABC):
    """
    Abstract interface isolating provider-specific SDK request/response formats.
    The orchestrator depends ONLY on this interface and internal models (ModelResponse).
    """

    @abstractmethod
    def generate_turn(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        schema_text: str
    ) -> ModelResponse:
        """
        Executes a single model reasoning turn.
        Returns a provider-agnostic ModelResponse.
        """
        pass


class GeminiProvider(BaseLLMProvider):
    """
    Adapter implementation for Google Gemini API.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.LLM_API_KEY
        self.model_name = model or settings.LLM_MODEL or "gemini-2.5-flash"

    def generate_turn(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        schema_text: str
    ) -> ModelResponse:
        if not self.api_key or self.api_key == "your_llm_api_key_here":
            return ModelResponse(
                has_tool_call=False,
                error="Gemini API Key is not configured. Set LLM_API_KEY in backend/.env"
            )

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)

            # Convert tools to Gemini function declaration format
            gemini_tools = [
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name="sql_query",
                            description="Executes a safe read-only SQL SELECT query against the PostgreSQL business database.",
                            parameters=types.Schema(
                                type="OBJECT",
                                properties={
                                    "sql": types.Schema(type="STRING", description="The SQL SELECT query to execute."),
                                    "max_rows": types.Schema(type="INTEGER", description="Maximum rows to return (default 100).")
                                },
                                required=["sql"]
                            )
                        )
                    ]
                )
            ]

            # Build prompt contents
            full_prompt = f"Schema Context:\n{schema_text}\n\n"
            for m in messages:
                full_prompt += f"{m['role'].upper()}: {m['content']}\n"

            response = client.models.generate_content(
                model=self.model_name,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    tools=gemini_tools,
                    temperature=0.1
                )
            )

            # Check for function call
            if response.function_calls:
                call = response.function_calls[0]
                args_dict = dict(call.args) if hasattr(call, "args") else {}
                return ModelResponse(
                    has_tool_call=True,
                    tool_call=ToolCallRequest(
                        tool_name=call.name,
                        arguments=args_dict
                    )
                )

            return ModelResponse(
                has_tool_call=False,
                content=response.text or "No text content generated."
            )

        except Exception as e:
            return ModelResponse(
                has_tool_call=False,
                error=f"Gemini Provider Error: {str(e)}"
            )


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic mock provider for automated unit testing without network calls or API keys.
    """

    def __init__(self, custom_responses: Optional[List[ModelResponse]] = None):
        self.custom_responses = custom_responses or []
        self.call_count = 0

    def generate_turn(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        schema_text: str
    ) -> ModelResponse:
        self.call_count += 1

        if self.custom_responses:
            idx = min(self.call_count - 1, len(self.custom_responses) - 1)
            return self.custom_responses[idx]

        # Default deterministic mock sequence based on user question
        last_message = messages[-1]["content"] if messages else ""

        # Turn 1: Emit sql_query tool call
        if self.call_count == 1:
            if "revenue" in last_message.lower() and "region" in last_message.lower():
                sql = "SELECT c.region, SUM(oi.quantity * oi.unit_price) AS gross_revenue FROM orders o JOIN customers c ON o.customer_id = c.customer_id JOIN order_items oi ON o.order_id = oi.order_id WHERE o.order_status = 'Completed' GROUP BY c.region ORDER BY gross_revenue DESC"
            elif "top" in last_message.lower() and "product" in last_message.lower():
                sql = "SELECT p.product_name, SUM(oi.quantity * oi.unit_price) AS total_revenue FROM order_items oi JOIN products p ON oi.product_id = p.product_id GROUP BY p.product_name ORDER BY total_revenue DESC LIMIT 5"
            else:
                sql = "SELECT c.region, COUNT(o.order_id) AS total_orders FROM orders o JOIN customers c ON o.customer_id = c.customer_id GROUP BY c.region"

            return ModelResponse(
                has_tool_call=True,
                tool_call=ToolCallRequest(
                    tool_name="sql_query",
                    arguments={"sql": sql, "max_rows": 50}
                )
            )

        # Turn 2: Synthesize final answer from query results
        return ModelResponse(
            has_tool_call=False,
            content=f"Based on verified database evidence from the SQL tool execution, the query completed successfully."
        )


def get_llm_provider() -> BaseLLMProvider:
    """
    Factory function returning the configured LLM provider adapter.
    """
    if settings.LLM_PROVIDER == "mock":
        return MockLLMProvider()
    return GeminiProvider()
