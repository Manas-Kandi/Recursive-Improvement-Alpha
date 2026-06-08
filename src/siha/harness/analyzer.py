"""Post-run trace analysis using meta LLM"""

from typing import Dict, Any, List
from siha.llm.client import NvidiaClient
from siha.llm.registry import get_model_for_role
from siha.agent.session import Session
import json


class Analyzer:
    """Analyzes task execution traces to propose improvements"""
    
    def __init__(self):
        self.client = NvidiaClient(get_model_for_role("meta"))
    
    def analyze_task(self, task_id: int) -> Dict[str, Any]:
        """Analyze a completed task and propose mutations"""
        
        # Get full trace
        session = Session(task_id)
        trace = session.get_trace()
        
        # Build analysis prompt
        prompt = self._build_analysis_prompt(trace)
        
        # Get analysis from meta LLM
        response = self.client.chat([{"role": "user", "content": prompt}])
        
        # Parse structured critique
        critique = self._parse_critique(response.choices[0].message.content)
        
        return critique
    
    def _build_analysis_prompt(self, trace: Dict[str, Any]) -> str:
        """Build prompt for meta LLM analysis"""
        
        return f"""
Analyze this task execution trace and propose improvements:

Task:
- Prompt: {trace['task']['prompt']}
- Model: {trace['task']['model']}
- Status: {trace['task']['status']}
- Duration: {trace['task']['duration_ms']}ms

Steps ({len(trace['steps'])}):
{self._format_steps(trace['steps'])}

Tool Calls ({len(trace['tool_calls'])}):
{self._format_tool_calls(trace['tool_calls'])}

Provide a JSON response with:
- root_cause: what went wrong (or what could be better)
- what_went_well: what succeeded
- proposed_mutations: array of objects with:
  - kind: "prompt" | "tool" | "strategy"
  - target: which prompt/tool/strategy to modify
  - before: current value
  - after: proposed new value
  - rationale: why this change
  - expected_effect: what improvement to expect
"""
    
    def _format_steps(self, steps: List[Dict]) -> str:
        """Format steps for analysis"""
        formatted = []
        for step in steps:
            formatted.append(f"  Step {step['idx']} ({step['type']}): {step.get('content', {})}")
        return "\n".join(formatted)
    
    def _format_tool_calls(self, tool_calls: List[Dict]) -> str:
        """Format tool calls for analysis"""
        formatted = []
        for tc in tool_calls:
            formatted.append(f"  Tool {tc['tool_id']}: args={tc['args']}, success={tc['success']}")
        return "\n".join(formatted)
    
    def _parse_critique(self, content: str) -> Dict[str, Any]:
        """Parse structured critique from LLM response"""
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            json_str = content[start:end]
            return json.loads(json_str)
        except:
            return {
                "root_cause": "Parse error",
                "what_went_well": [],
                "proposed_mutations": []
            }
