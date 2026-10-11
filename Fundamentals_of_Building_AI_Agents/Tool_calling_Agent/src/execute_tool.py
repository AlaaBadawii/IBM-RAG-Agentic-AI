"""Execute tool calls for the Tool Calling Agent."""

import json

from langchain_core.messages import ToolMessage

from tools import tools
from tools.fetch_transcript import TranscriptFetchError


def execute_tools(tool_calls) -> list[ToolMessage]:
    """
    Execute a list of tool calls and return their results as ToolMessage objects.
    """
    messages = []
    for tool_call in tool_calls:
        messages.append(execute_tool(tool_call))
    return messages


def execute_tool(tool_call) -> ToolMessage:
    """
    Execute a single tool call and return the result as a ToolMessage object.
    """
    tool_id = tool_call.get("id", None)
    if not tool_id:
        raise ValueError("Tool call is missing its ID.")

    tool_name = tool_call.get("name")
    if tool_name not in tools:
        return ToolMessage(
            content=f"Tool '{tool_name}' not found or tool ID is missing.",
            tool_call_id=tool_id,
        )

    tool_args = tool_call.get("args", {})
    if not isinstance(tool_args, dict):
        return ToolMessage(
            content="Invalid tool arguments: expected a dictionary.",
            tool_call_id=tool_id,
        )

    try:
        tool_result = tools[tool_name].invoke(tool_args)
        content = (
            tool_result
            if isinstance(tool_result, str)
            else json.dumps(tool_result, indent=2, ensure_ascii=False)
        )
        return ToolMessage(content=content, tool_call_id=tool_id)
    except TranscriptFetchError as e:
        return ToolMessage(
            content=f"Error fetching transcript: {e}", tool_call_id=tool_id
        )
    except (TypeError, ValueError, KeyError) as e:
        return ToolMessage(
            content=f"Can't perform this action. Error: {e}", tool_call_id=tool_id
        )
