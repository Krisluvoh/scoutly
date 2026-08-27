"""
sourcing_channels.py
----------------------
Static reference data on where a resale/curation business can source
trend and hard-to-find inventory. Fed to the Sales Recommendation Agent as
grounded context (same idea as web_research.lookup_public_filings feeding
real EDGAR data to the Company Research Agent) so its sourcing-channel
recommendation is grounded in real platform names and real margin/quality
tradeoffs instead of the model inventing them.

This is what ties the CAP 931-compliant account-research structure back to
the original Trendora's focus: trend/hard-to-find items and the resale
margin they can command.
"""

SOURCING_CHANNELS = [
    {
        "channel_type": "Wholesale",
        "example_platforms": ["Alibaba", "Faire", "SaleHoo"],
        "best_for": "Clothing, home goods, beauty",
        "notes": "Higher margins, requires upfront buying",
    },
    {
        "channel_type": "Liquidation",
        "example_platforms": ["B-Stock", "QuickLotz", "Helpsy"],
        "best_for": "Overstock, returns, trendy apparel",
        "notes": "Lower cost, variable quality",
    },
    {
        "channel_type": "Dropshipping",
        "example_platforms": ["AliExpress", "Spocket", "Syncee"],
        "best_for": "Trend testing, low capital",
        "notes": "No inventory needed",
    },
    {
        "channel_type": "Boutique/Vintage",
        "example_platforms": ["Fleek", "Boutique by the Box"],
        "best_for": "Trendy fashion, Y2K, curated items",
        "notes": "Higher resale value",
    },
    {
        "channel_type": "Category-Specific",
        "example_platforms": ["Torg"],
        "best_for": "Food & beverage trends",
        "notes": "Niche but profitable",
    },
]
