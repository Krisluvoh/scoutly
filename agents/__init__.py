"""
The five Scoutly agents: Account Intake, Company Research, Competitor,
Sales Recommendation, and Report.

Each module in this package defines one agent's system prompt and wires it
to its output schema. Shared plumbing (prompt building, JSON parsing,
validation, retry) lives in base_agent.py; the individual agent files are
intentionally thin, since a prompt plus a schema is all that distinguishes
one agent from another.
"""
