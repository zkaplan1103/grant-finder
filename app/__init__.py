"""Grant Navigator — a multi-agent funding-match system for nonprofits.

Package layout:
    app.models        Pydantic contract: Profile, Opportunity, Match, Draft, VerifyResult
    app.agents        Match / Drafter / Verify agents over an injectable LLM client
    app.orchestrator  The bounded Drafter<->Verify loop (PRD section 7)
    app.mapper        Deterministic ICP -> grants.gov params (PRD section 4)
    app.discovery     grants.gov Search2 client + curated YAML sources (PRD section 9)
    app.db            SQLite persistence (stdlib sqlite3)
    app.web           FastAPI + Jinja UI
"""
