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
    Adapter implementation for Google Gemini API using official google-genai SDK (0.8.0+).
    Isolates Gemini-specific request/response models from the orchestrator.
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
        # Check API key configuration explicitly
        if not self.api_key or self.api_key.strip() == "" or self.api_key == "your_llm_api_key_here":
            return ModelResponse(
                has_tool_call=False,
                error="Gemini API Key is not configured. Set LLM_API_KEY in backend/.env"
            )

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)

            # Convert tool definitions to official Gemini FunctionDeclarations
            declarations = []
            for tool_def in tools:
                t_name = tool_def.get("name", "sql_query")
                t_desc = tool_def.get("description", "")
                declarations.append(
                    types.FunctionDeclaration(
                        name=t_name,
                        description=t_desc
                    )
                )

            gemini_tools = [types.Tool(function_declarations=declarations)] if declarations else None

            # Build native SDK conversation turns
            sdk_contents = []
            for m in messages:
                role = m.get("role", "user")
                text_content = m.get("content", "")
                sdk_role = "model" if role == "model" else "user"
                sdk_contents.append(
                    types.Content(
                        role=sdk_role,
                        parts=[types.Part.from_text(text=text_content)]
                    )
                )

            system_instruction = f"Schema Context:\n{schema_text}\n" if schema_text else None

            config = types.GenerateContentConfig(
                tools=gemini_tools,
                temperature=0.1,
                system_instruction=system_instruction
            )

            response = client.models.generate_content(
                model=self.model_name,
                contents=sdk_contents if sdk_contents else "Investigate business question",
                config=config
            )

            # Parse function call requested by model
            if hasattr(response, "function_calls") and response.function_calls:
                call = response.function_calls[0]
                args_dict = dict(call.args) if hasattr(call, "args") and call.args else {}
                return ModelResponse(
                    has_tool_call=True,
                    tool_call=ToolCallRequest(
                        tool_name=call.name,
                        arguments=args_dict
                    )
                )

            text_output = response.text if hasattr(response, "text") and response.text else "No text content generated."

            return ModelResponse(
                has_tool_call=False,
                content=text_output
            )

        except Exception as e:
            # Sanitize exception message to ensure no secrets are exposed
            err_msg = str(e).replace(self.api_key, "[REDACTED_API_KEY]") if self.api_key else str(e)
            return ModelResponse(
                has_tool_call=False,
                error=f"Gemini Provider Error: {err_msg}"
            )


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic mock provider for automated unit testing without network calls or API keys.
    Supports tool execution simulation for all tools in ToolRegistry.
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

        # Extract initial user question and full message text
        first_user_message = messages[0]["content"] if messages else ""
        last_message = messages[-1]["content"] if messages else ""
        all_text = " ".join(m.get("content", "") for m in messages).lower()

        # Multi-tool sequence detection: "Revenue fell last month. Why, and did the campaign help?"
        if ("why" in first_user_message.lower() or "declin" in first_user_message.lower()) and ("campaign" in first_user_message.lower() or "did" in first_user_message.lower()):
            if self.call_count == 1:
                return ModelResponse(
                    has_tool_call=True,
                    tool_call=ToolCallRequest(
                        tool_name="driver_decomposition",
                        arguments={
                            "metric": "revenue",
                            "period_a": {"start_date": "2025-01-01", "end_date": "2025-03-31"},
                            "period_b": {"start_date": "2025-04-01", "end_date": "2025-06-30"},
                            "dimensions": ["region", "category"]
                        }
                    )
                )
            elif self.call_count == 2:
                return ModelResponse(
                    has_tool_call=True,
                    tool_call=ToolCallRequest(
                        tool_name="campaign_impact",
                        arguments={
                            "campaign_id": "CMP-2025-Q3-SOUTH",
                            "min_sample_size": 15
                        }
                    )
                )
            else:
                return ModelResponse(
                    has_tool_call=False,
                    content="Driver decomposition indicates that revenue in South region declined. Campaign impact analysis shows Difference-in-Differences lift of 1929.41."
                )

        # Single-tool selection in Turn 1
        if self.call_count == 1:
            lower_msg = first_user_message.lower()
            if any(w in lower_msg for w in ("declin", "driver", "decompose", "variance", "why did revenue")):
                return ModelResponse(
                    has_tool_call=True,
                    tool_call=ToolCallRequest(
                        tool_name="driver_decomposition",
                        arguments={
                            "metric": "revenue",
                            "period_a": {"start_date": "2025-01-01", "end_date": "2025-03-31"},
                            "period_b": {"start_date": "2025-04-01", "end_date": "2025-06-30"},
                            "dimensions": ["region", "category"]
                        }
                    )
                )
            elif any(w in lower_msg for w in ("campaign", "impact", "lift")):
                return ModelResponse(
                    has_tool_call=True,
                    tool_call=ToolCallRequest(
                        tool_name="campaign_impact",
                        arguments={
                            "campaign_id": "CMP-2025-Q3-SOUTH",
                            "min_sample_size": 15
                        }
                    )
                )
            elif any(w in lower_msg for w in ("verify", "claim", "statement")):
                return ModelResponse(
                    has_tool_call=True,
                    tool_call=ToolCallRequest(
                        tool_name="claim_verification",
                        arguments={
                            "llm_text": "Q3 revenue in South region was 125000 across 31 customers.",
                            "tolerance": 0.05
                        }
                    )
                )
            else:
                if "revenue" in lower_msg and "region" in lower_msg:
                    sql = "SELECT c.region, SUM(oi.quantity * oi.unit_price) AS gross_revenue FROM orders o JOIN customers c ON o.customer_id = c.customer_id JOIN order_items oi ON o.order_id = oi.order_id WHERE o.order_status = 'Completed' GROUP BY c.region ORDER BY gross_revenue DESC"
                elif "top" in lower_msg and "product" in lower_msg:
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

        # Turn 2 / final answer
        return ModelResponse(
            has_tool_call=False,
            content="Based on verified database evidence from tool execution, the query completed successfully."
        )


def get_llm_provider() -> BaseLLMProvider:
    """
    Factory function returning the configured LLM provider adapter.
    """
    if settings.LLM_PROVIDER == "mock":
        return MockLLMProvider()
    return GeminiProvider()
