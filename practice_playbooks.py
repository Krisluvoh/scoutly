"""
practice_playbooks.py
-----------------------
Static reference data, one entry per consulting/advisory practice area,
that grounds the Company Research and Sales Recommendation agents in real,
practice-specific signals instead of one hardcoded vertical. This is what
makes Scoutly's prompting "industry-aware": a rep picks the practice
they're pitching (Technology & AI Advisory, Cybersecurity & Risk, etc.)
and the same five-agent pipeline is handed that practice's own research
signals, buying-trigger events, and engagement-model options — the same
grounding role sourcing_channels.py used to play for one vertical only.

Each playbook has three parts:
  - research_signals: what the Company Research Agent should actively look
    for in the fetched page text for this practice (still only reported
    if actually present — never invented because it's "worth looking for").
  - trigger_events: what counts as a time-sensitive buying signal for this
    practice, used by the Sales Recommendation Agent.
  - engagement_models: real, named engagement types and their typical
    approach/notes, so the Sales Recommendation Agent's engagement pick is
    grounded in this table rather than invented on the spot — same idea as
    sourcing_channels.py, generalized to consulting engagement shapes.

practice_area == "" (no playbook) is a legitimate choice, not an error —
it means the rep's offering doesn't fit one of these practices, and the
downstream agents simply omit the practice-specific extras.
"""

PRACTICE_PLAYBOOKS: dict[str, dict] = {
    "tech_ai_advisory": {
        "label": "Technology & AI Advisory",
        "research_signals": [
            "Mentions of AI/ML pilots, model deployments, or automation initiatives",
            "Data science, ML engineering, or AI-team hiring",
            "Presence or absence of a named Chief AI/Data/Digital Officer",
        ],
        "trigger_events": [
            "A newly announced AI or automation initiative with no named internal team",
            "A new Chief AI/Data/Digital Officer hire",
            "A competitor's public AI product launch",
        ],
        "engagement_models": [
            {
                "engagement_type": "AI Readiness Assessment",
                "example_approach": ["Data maturity audit", "Use-case prioritization workshop"],
                "notes": "Best fit when AI is discussed publicly but no internal roadmap is mentioned",
            },
            {
                "engagement_type": "Managed AI Delivery",
                "example_approach": ["Embedded delivery pod", "MLOps platform setup"],
                "notes": "Best fit once a pilot exists and needs to scale to production",
            },
            {
                "engagement_type": "AI Center of Excellence Setup",
                "example_approach": ["Governance framework", "Training & enablement program"],
                "notes": "Best fit for larger orgs standardizing AI practice across business units",
            },
        ],
    },
    "cloud_infrastructure": {
        "label": "Cloud & Infrastructure Modernization",
        "research_signals": [
            "Mentions of a current cloud vendor (AWS/Azure/GCP) or on-prem/legacy systems",
            "DevOps, SRE, or platform-engineering hiring",
            "Mentions of an outage, incident, or performance issue",
        ],
        "trigger_events": [
            "A publicly disclosed outage or incident",
            "A new CTO / VP of Infrastructure hire",
            "An acquisition likely to require system consolidation",
        ],
        "engagement_models": [
            {
                "engagement_type": "Cloud Migration Assessment",
                "example_approach": ["Workload discovery", "Migration wave planning"],
                "notes": "Best fit when legacy/on-prem systems are mentioned with no migration underway",
            },
            {
                "engagement_type": "Managed Cloud Operations",
                "example_approach": ["24/7 platform operations", "Cost optimization review"],
                "notes": "Best fit once workloads are already in the cloud but lack dedicated ops coverage",
            },
            {
                "engagement_type": "Modernization Sprint",
                "example_approach": ["Landing zone build", "CI/CD pipeline standup"],
                "notes": "Best fit after a disclosed incident or a stated infrastructure pain point",
            },
        ],
    },
    "cybersecurity_risk": {
        "label": "Cybersecurity & Risk",
        "research_signals": [
            "Mentions of a prior breach, incident, or vulnerability disclosure",
            "Compliance framework mentions (SOC 2, ISO 27001, HIPAA, GDPR)",
            "Presence or absence of a named CISO",
        ],
        "trigger_events": [
            "A disclosed breach or security incident",
            "A new compliance mandate affecting the company's industry",
            "CISO turnover or a newly created security leadership role",
        ],
        "engagement_models": [
            {
                "engagement_type": "Security Posture Assessment",
                "example_approach": ["Vulnerability assessment", "Gap analysis vs. a named framework"],
                "notes": "Best fit when no CISO or formal security program is mentioned",
            },
            {
                "engagement_type": "Managed Detection & Response",
                "example_approach": ["24/7 monitoring", "Incident response retainer"],
                "notes": "Best fit after a disclosed incident or breach",
            },
            {
                "engagement_type": "Compliance Readiness Program",
                "example_approach": ["Framework gap remediation", "Audit preparation"],
                "notes": "Best fit when a new regulatory or customer-driven compliance deadline is mentioned",
            },
        ],
    },
    "data_analytics": {
        "label": "Data & Analytics",
        "research_signals": [
            "Mentions of a data platform, data warehouse, or BI tooling",
            "Analytics or data-engineering hiring",
            "Mentions of data governance or data-quality challenges",
        ],
        "trigger_events": [
            "A new Chief Data Officer or VP of Analytics hire",
            "A stated data platform migration or consolidation effort",
            "A regulatory requirement around data handling or reporting",
        ],
        "engagement_models": [
            {
                "engagement_type": "Data Strategy & Governance Assessment",
                "example_approach": ["Data maturity audit", "Governance framework design"],
                "notes": "Best fit when data challenges are mentioned but no formal strategy is in place",
            },
            {
                "engagement_type": "Analytics Platform Build",
                "example_approach": ["Warehouse/lakehouse implementation", "Dashboard rollout"],
                "notes": "Best fit when a platform migration is already underway or announced",
            },
            {
                "engagement_type": "Managed Data Operations",
                "example_approach": ["Pipeline monitoring", "Ongoing data quality management"],
                "notes": "Best fit once a platform exists but lacks dedicated operational coverage",
            },
        ],
    },
    "digital_transformation": {
        "label": "Digital Transformation & Strategy",
        "research_signals": [
            "Press releases or statements about a digital transformation initiative",
            "Organizational restructuring or new digital/strategy leadership",
            "Mentions of legacy processes being replaced or modernized",
        ],
        "trigger_events": [
            "A newly announced transformation initiative",
            "A leadership change in a digital, strategy, or innovation role",
            "A stated multi-year modernization budget or program",
        ],
        "engagement_models": [
            {
                "engagement_type": "Transformation Roadmap",
                "example_approach": ["Current-state assessment", "Multi-year roadmap workshop"],
                "notes": "Best fit at the earliest stage, right after an initiative is announced",
            },
            {
                "engagement_type": "Program Management Office Setup",
                "example_approach": ["PMO design", "Governance cadence & reporting"],
                "notes": "Best fit once a roadmap exists and needs coordinated execution",
            },
            {
                "engagement_type": "Change Management Engagement",
                "example_approach": ["Stakeholder alignment", "Training & adoption program"],
                "notes": "Best fit when legacy process replacement is mentioned as a stated pain point",
            },
        ],
    },
    "supply_chain_ops": {
        "label": "Supply Chain & Operations",
        "research_signals": [
            "Mentions of logistics, inventory, or ERP systems",
            "Public statements about supply-chain disruption or challenges",
            "New COO or supply-chain leadership hires",
        ],
        "trigger_events": [
            "A publicly disclosed supply-chain disruption",
            "A new COO or Head of Supply Chain hire",
            "A stated ERP replacement or modernization effort",
        ],
        "engagement_models": [
            {
                "engagement_type": "Supply Chain Assessment",
                "example_approach": ["Network design review", "Risk/resilience audit"],
                "notes": "Best fit when disruption/challenges are mentioned with no remediation plan stated",
            },
            {
                "engagement_type": "ERP Modernization",
                "example_approach": ["System selection support", "Implementation planning"],
                "notes": "Best fit when a legacy ERP or manual process is mentioned",
            },
            {
                "engagement_type": "Managed Operations Support",
                "example_approach": ["Ongoing planning support", "Vendor performance management"],
                "notes": "Best fit once a network/system exists but lacks dedicated operational oversight",
            },
        ],
    },
    "retail_trend_sourcing": {
        "label": "Retail Trend Sourcing (Boutique/Resale)",
        "research_signals": [
            "Recent merchandising or buying-leadership changes",
            "Trend categories the retailer is expanding into",
            "Public statements about supply-chain or sourcing challenges",
        ],
        "trigger_events": [
            "A newly opened location or announced expansion",
            "A new Head Buyer or merchandising leadership hire",
            "A publicly discussed inventory glut or stockout",
        ],
        "engagement_models": [
            {
                "engagement_type": "Wholesale",
                "example_approach": ["Alibaba", "Faire", "SaleHoo"],
                "notes": "Higher margins, requires upfront buying — best for clothing, home goods, beauty",
            },
            {
                "engagement_type": "Liquidation",
                "example_approach": ["B-Stock", "QuickLotz", "Helpsy"],
                "notes": "Lower cost, variable quality — best for overstock, returns, trendy apparel",
            },
            {
                "engagement_type": "Dropshipping",
                "example_approach": ["AliExpress", "Spocket", "Syncee"],
                "notes": "No inventory needed — best for trend testing, low capital",
            },
            {
                "engagement_type": "Boutique/Vintage",
                "example_approach": ["Fleek", "Boutique by the Box"],
                "notes": "Higher resale value — best for trendy fashion, Y2K, curated items",
            },
            {
                "engagement_type": "Category-Specific",
                "example_approach": ["Torg"],
                "notes": "Niche but profitable — best for food & beverage trends",
            },
        ],
    },
}
