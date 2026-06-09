"""GBNF grammar generation for grammar-constrained tool calling.

llama.cpp supports constrained decoding via GBNF grammars. By generating a
grammar from the registered tool schemas, a tiny local model *physically
cannot* emit a malformed tool call — the decoder only samples tokens that keep
the output inside the grammar. This removes the single biggest failure mode of
small models in agent loops: hallucinated or syntactically broken tool JSON.
"""

from typing import Any, Dict, List

# Standard JSON building blocks shared by every generated grammar.
_JSON_RULES = r"""
object ::= "{" ws ( string ws ":" ws value ( ws "," ws string ws ":" ws value )* )? ws "}"
array  ::= "[" ws ( value ( ws "," ws value )* )? ws "]"
value  ::= object | array | string | number | "true" | "false" | "null"
string ::= "\"" char* "\""
char   ::= [^"\\\x00-\x1f] | "\\" escape
escape ::= ["\\/bfnrt] | "u" hex hex hex hex
hex    ::= [0-9a-fA-F]
number ::= "-"? ("0" | [1-9] [0-9]*) ("." [0-9]+)? ([eE] [-+]? [0-9]+)?
ws     ::= [ \t\n]*
"""


def build_tool_call_grammar(tools: List[Dict[str, Any]]) -> str:
    """Build a GBNF grammar that only accepts a valid SIHA tool-call JSON object.

    The output is constrained to::

        {"tool": "<one of the registered tool names>", "arguments": { ... }}

    Arguments are constrained to valid JSON objects. Returns a GBNF grammar
    string suitable for ``llama_cpp.LlamaGrammar.from_string``.
    """
    names = []
    for t in tools:
        name = t.get("function", {}).get("name", "")
        if name:
            names.append(name)

    if not names:
        # Degenerate grammar: any JSON object.
        return f'root ::= object\n{_JSON_RULES}'

    toolname_alts = " | ".join(f'"\\"{n}\\""' for n in names)

    root = (
        'root ::= "{" ws "\\"tool\\"" ws ":" ws toolname ws "," ws '
        '"\\"arguments\\"" ws ":" ws object ws "}"\n'
        f"toolname ::= {toolname_alts}\n"
    )
    return root + _JSON_RULES
