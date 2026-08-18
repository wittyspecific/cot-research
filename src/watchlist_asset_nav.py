from __future__ import annotations

# Central navigation metadata only. Trading logic remains in pages/watchlist.py.
WATCHLIST_ASSET_PAGES = (
    {"asset_class": 'Currencies', "label": 'Währungen', "path": 'pages/watchlist_currencies.py'},
    {"asset_class": 'Cryptocurrencies', "label": 'Kryptowährungen', "path": 'pages/watchlist_cryptocurrencies.py'},
    {"asset_class": 'Indices', "label": 'Indizes', "path": 'pages/watchlist_indices.py'},
    {"asset_class": 'Rates', "label": 'US-Zinsen', "path": 'pages/watchlist_rates.py'},
    {"asset_class": 'Volatility', "label": 'Volatilität', "path": 'pages/watchlist_volatility.py'},
    {"asset_class": 'Energy', "label": 'Energie', "path": 'pages/watchlist_energy.py'},
    {"asset_class": 'Metals', "label": 'Metalle', "path": 'pages/watchlist_metals.py'},
    {"asset_class": 'Soft Commodities', "label": 'Soft-Rohstoffe', "path": 'pages/watchlist_soft_commodities.py'},
    {"asset_class": 'Grains', "label": 'Getreide', "path": 'pages/watchlist_grains.py'},
    {"asset_class": 'Livestock', "label": 'Vieh', "path": 'pages/watchlist_livestock.py'},
    {"asset_class": 'Forest Products', "label": 'Forstprodukte', "path": 'pages/watchlist_forest_products.py'},
)
