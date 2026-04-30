"""Tool-discovery namespace.

agent-core's runtime introspects ``sme_tools.example.tools`` to register
the SME's callables with the LLM. The actual implementations live in
``skills.sanmar.sanmar_tools`` — this package only re-exports them.

Do not add new logic here. Add tools to ``skills.sanmar.sanmar_tools``
and re-export from ``sme_tools.example.tools``.
"""
