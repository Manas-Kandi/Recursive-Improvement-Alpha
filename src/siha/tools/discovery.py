"""Tool auto-discovery sub-agent"""

from typing import Dict, Any, Optional
from siha.llm.client import NvidiaClient
from siha.llm.registry import get_model_for_role
from siha.db import get_session
from siha.models import Tool, ToolKind, ToolStatus, Mutation, MutationKind, MutationStatus
from siha.sandbox.local import LocalSandbox
import json


class DiscoveryAgent:
    """Auto-discovers and validates new tools"""
    
    def __init__(self):
        self.client = NvidiaClient(get_model_for_role("discovery"))
        self.sandbox = LocalSandbox()
    
    def discover_tool(self, gap_description: str) -> Optional[Tool]:
        """Discover a new tool based on a capability gap"""
        
        # Step 1: Search for relevant libraries/APIs
        search_result = self._search_for_solution(gap_description)
        
        # Step 2: Browse documentation
        docs = self._browse_documentation(search_result)
        
        # Step 3: Synthesize tool implementation
        tool_spec = self._synthesize_tool(gap_description, docs)
        
        # Step 4: Validate the tool
        if self._validate_tool(tool_spec):
            # Step 5: Persist the tool
            tool = self._persist_tool(tool_spec)
            # Step 6: Log mutation
            self._log_mutation(tool)
            return tool
        
        return None
    
    def _search_for_solution(self, gap: str) -> str:
        """Search for libraries/APIs that can solve the gap"""
        from siha.tools.builtin import WebSearchTool
        
        search_tool = WebSearchTool()
        result = search_tool.run(query=f"python library for {gap}")
        return result.output if result.success else ""
    
    def _browse_documentation(self, search_result: str) -> str:
        """Browse documentation for the found solution"""
        from siha.tools.builtin import BrowseWebTool
        
        # Extract URL from search result (simplified)
        # In production, parse search results properly
        browse_tool = BrowseWebTool()
        # Placeholder - would extract actual URL
        return search_result
    
    def _synthesize_tool(self, gap: str, docs: str) -> Dict[str, Any]:
        """Use meta LLM to synthesize tool implementation"""
        
        prompt = f"""
Based on the following need and documentation, create a Python tool:

Need: {gap}
Documentation: {docs}

Generate a JSON response with:
- name: tool name (snake_case)
- description: what the tool does
- parameters: JSON Schema for parameters
- code: Python implementation that defines a top-level function with the exact
  signature `def run(**kwargs):` which performs the work and returns a
  JSON-serializable result (string, number, list, or dict)
- source_url: where the library documentation came from

The code MUST:
1. Import any libraries it needs inside the file
2. Define `def run(**kwargs):` as the single entry point
3. Handle errors gracefully and return a serializable value
"""
        
        response = self.client.chat([{"role": "user", "content": prompt}])
        
        try:
            content = response.choices[0].message.content
            # Extract JSON from response
            start = content.find("{")
            end = content.rfind("}") + 1
            json_str = content[start:end]
            return json.loads(json_str)
        except:
            return {}
    
    def _validate_tool(self, tool_spec: Dict[str, Any]) -> bool:
        """Validate that the tool works in the sandbox"""
        
        if not tool_spec or "code" not in tool_spec:
            return False
        
        code = tool_spec["code"]
        
        # Validate by importing the code and confirming a callable `run` exists.
        test_script = (
            code
            + "\n\n"
            + "if callable(globals().get('run')):\n"
            + "    print('VALIDATION_OK')\n"
            + "else:\n"
            + "    print('VALIDATION_ERROR: no run() function defined')\n"
        )
        
        result = self.sandbox.run("python3 test.py", files={"test.py": test_script})
        
        return "VALIDATION_OK" in result.stdout
    
    def _persist_tool(self, tool_spec: Dict[str, Any]) -> Tool:
        """Persist the discovered tool to the database"""
        
        with get_session() as session:
            tool = Tool(
                name=tool_spec["name"],
                version="1.0.0",
                description=tool_spec["description"],
                json_schema=tool_spec.get("parameters", {}),
                implementation_kind=ToolKind.python_code,
                code=tool_spec["code"],
                source_url=tool_spec.get("source_url"),
                status=ToolStatus.active
            )
            session.add(tool)
            session.commit()
            session.refresh(tool)
            return tool
    
    def _log_mutation(self, tool: Tool):
        """Log the tool discovery as a mutation"""
        
        with get_session() as session:
            mutation = Mutation(
                kind=MutationKind.tool,
                target_id=tool.id,
                before={},
                after={
                    "name": tool.name,
                    "description": tool.description,
                    "code": tool.code
                },
                rationale=f"Auto-discovered tool: {tool.name}",
                status=MutationStatus.active
            )
            session.add(mutation)
            session.commit()
