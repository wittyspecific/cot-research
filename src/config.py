
"""
Feste Produktionsparameter der COT-Markanalyse.

Diese Werte bilden die eingefrorene Standardmethodik. Änderungen sollen nicht
über die normale Benutzeroberfläche erfolgen. Für Forschung/Sensitivität kann
die App explizit in einen Sensitivitätsmodus versetzt werden.
"""

# Stufe 1 · COT-Index
COT_INDEX_WEEKS = 26
INDEX_UPPER = 80
INDEX_LOWER = 20

# Stufe 2 · Netto-Validierung / reales Commercial-Extrem
NET_VALIDATION_WEEKS = 156
NET_UPPER_PERCENTILE = 80
NET_LOWER_PERCENTILE = 20
COMMERCIAL_RANGE_WEEKS = 26

# Stufe 5 · Non-Commercial-Divergenz
NC_DIVERGENCE_WEEKS = 4
NC_CONFIRMING_WEEKS = 3
NC_MIN_PRICE_MOVE_PCT = 1.00
NC_MIN_NET_CHANGE_GROSS_PCT = 1.00
NC_MIN_ACTIVE_LEG_GROSS_PCT = 0.50
NC_MIN_ACTIVE_BUILD_SHARE = 0.55

# Historische COT-Auswertung
FORWARD_HORIZONS_WEEKS = (4, 8)

# Saisonalität
SEASONAL_PRIMARY_HORIZON_DAYS = 10
SEASONAL_OUTLIER_IQR_FACTOR = 2.75
SEASONAL_HISTORY_WINDOWS = (5, 10, 15, 20, 30)
SEASONAL_FORWARD_HORIZONS_DAYS = (10, 20, 40, 60)

# Hedger Release-Kontext
RELEASE_ACTIVE_WEEKS = 6

# Research / neue spekulative Divergenzmethodik
# Diese Parameter sind bewusst getrennt von den eingefrorenen Legacy-Produktionsparametern.
NC_DIV_PRICE_WINDOW_W = 4
NC_DIV_FLOW_WINDOW_W = 4
NC_DIV_PATH_WINDOW_W = 8
NC_DIV_STANDARDIZE_HIST_W = 156
NC_DIV_Z_THRESHOLD = 1.0
NC_DIV_USE_OI_NORM = True
