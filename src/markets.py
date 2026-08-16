
CLASSIC_MARKETS = {
    "Currencies": [
        {"name": "Euro FX", "symbol": "EUR", "ticker": "6E=F", "aliases": ["EURO FX"], "exchange": "CHICAGO MERCANTILE EXCHANGE"},
        {"name": "British Pound", "symbol": "GBP", "ticker": "6B=F", "aliases": ["BRITISH POUND"], "exchange": "CHICAGO MERCANTILE EXCHANGE"},
        {"name": "Japanese Yen", "symbol": "JPY", "ticker": "6J=F", "aliases": ["JAPANESE YEN"], "exchange": "CHICAGO MERCANTILE EXCHANGE"},
        {"name": "Swiss Franc", "symbol": "CHF", "ticker": "6S=F", "aliases": ["SWISS FRANC"], "exchange": "CHICAGO MERCANTILE EXCHANGE"},
        {"name": "Canadian Dollar", "symbol": "CAD", "ticker": "6C=F", "aliases": ["CANADIAN DOLLAR"], "exchange": "CHICAGO MERCANTILE EXCHANGE"},
        {"name": "Australian Dollar", "symbol": "AUD", "ticker": "6A=F", "aliases": ["AUSTRALIAN DOLLAR"], "exchange": "CHICAGO MERCANTILE EXCHANGE"},
        {"name": "New Zealand Dollar", "symbol": "NZD", "ticker": "6N=F", "aliases": ["NEW ZEALAND DOLLAR", "NZ DOLLAR"], "exchange": "CHICAGO MERCANTILE EXCHANGE"},
        {"name": "Mexican Peso", "symbol": "MXN", "ticker": "6M=F", "aliases": ["MEXICAN PESO"], "exchange": "CHICAGO MERCANTILE EXCHANGE"},
        {"name": "U.S. Dollar Index", "symbol": "USD", "ticker": "DX-Y.NYB", "aliases": ["U.S. DOLLAR INDEX", "US DOLLAR INDEX", "USD INDEX"], "exchange": "ICE FUTURES U.S."},
        {"name": "Brazilian Real", "symbol": "BRL", "ticker": "6L=F", "aliases": ["BRAZILIAN REAL"], "exchange": "CHICAGO MERCANTILE EXCHANGE", "cftc_code": "102741"},
        {"name": "South African Rand", "symbol": "ZAR", "ticker": "6Z=F", "aliases": ["SO AFRICAN RAND", "SOUTH AFRICAN RAND"], "exchange": "CHICAGO MERCANTILE EXCHANGE", "cftc_code": "122741"},
    ],
    "Cryptocurrencies": [
        {"name": "Bitcoin", "symbol": "BTC", "ticker": "BTC=F", "aliases": ["BITCOIN"], "exchange": "CHICAGO MERCANTILE EXCHANGE"},
        {"name": "Ether", "symbol": "ETH", "ticker": "ETH=F", "aliases": ["ETHER CASH SETTLED", "ETHER"], "exchange": "CHICAGO MERCANTILE EXCHANGE"},
    ],
    "Energy": [
        {"name": "WTI Crude Oil", "symbol": "CL", "ticker": "CL=F", "aliases": ["CRUDE OIL, LIGHT SWEET", "LIGHT SWEET CRUDE OIL", "WTI CRUDE"], "exchange": "NEW YORK MERCANTILE EXCHANGE"},
        {"name": "Brent Crude Oil", "symbol": "BZ", "ticker": "BZ=F", "aliases": ["BRENT LAST DAY"], "exchange": "NEW YORK MERCANTILE EXCHANGE", "cftc_code": "06765T", "allow_excluded_terms": ["LAST DAY"]},
        {"name": "Natural Gas", "symbol": "NG", "ticker": "NG=F", "aliases": ["NATURAL GAS"], "exchange": "NEW YORK MERCANTILE EXCHANGE"},
        {"name": "RBOB Gasoline", "symbol": "RB", "ticker": "RB=F", "aliases": ["GASOLINE RBOB", "RBOB GASOLINE", "GASOLINE"], "exchange": "NEW YORK MERCANTILE EXCHANGE"},
        {"name": "Heating Oil / ULSD", "symbol": "HO", "ticker": "HO=F", "aliases": ["HEATING OIL", "ULTRA LOW SULFUR DIESEL", "NY HARBOR ULSD"], "exchange": "NEW YORK MERCANTILE EXCHANGE"},
    ],
    "Metals": [
        {"name": "Gold", "symbol": "GC", "ticker": "GC=F", "aliases": ["GOLD"], "exchange": "COMMODITY EXCHANGE"},
        {"name": "Silver", "symbol": "SI", "ticker": "SI=F", "aliases": ["SILVER"], "exchange": "COMMODITY EXCHANGE"},
        {"name": "Copper", "symbol": "HG", "ticker": "HG=F", "aliases": ["COPPER"], "exchange": "COMMODITY EXCHANGE"},
        {"name": "Platinum", "symbol": "PL", "ticker": "PL=F", "aliases": ["PLATINUM"], "exchange": "NEW YORK MERCANTILE EXCHANGE"},
        {"name": "Palladium", "symbol": "PA", "ticker": "PA=F", "aliases": ["PALLADIUM"], "exchange": "NEW YORK MERCANTILE EXCHANGE"},
    ],
    "Grains": [
        {"name": "Corn", "symbol": "ZC", "ticker": "ZC=F", "aliases": ["CORN"], "exchange": "CHICAGO BOARD OF TRADE"},
        {"name": "Wheat (SRW)", "symbol": "ZW", "ticker": "ZW=F", "aliases": ["WHEAT-SRW", "WHEAT SRW", "WHEAT"], "exchange": "CHICAGO BOARD OF TRADE"},
        {"name": "Wheat (HRW)", "symbol": "KE", "ticker": "KE=F", "aliases": ["WHEAT-HRW", "WHEAT HRW"], "exchange": "CHICAGO BOARD OF TRADE", "cftc_code": "001612"},
        {"name": "Wheat (HR Spring)", "symbol": "MWE", "ticker": "", "aliases": ["WHEAT-HRSPRING", "WHEAT HRSPRING"], "exchange": "MIAX FUTURES EXCHANGE", "cftc_code": "001626", "price_note": "Kein verlässlich aufgelöster Yahoo-Continuous-Preisfeed; COT-Auswertung bleibt verfügbar."},
        {"name": "Rough Rice", "symbol": "ZR", "ticker": "ZR=F", "aliases": ["ROUGH RICE"], "exchange": "CHICAGO BOARD OF TRADE", "cftc_code": "039601"},
        {"name": "Canola", "symbol": "RS", "ticker": "", "aliases": ["CANOLA"], "exchange": "ICE FUTURES U.S.", "cftc_code": "135731", "price_note": "Kein verlässlich aufgelöster Yahoo-Continuous-Preisfeed; COT-Auswertung bleibt verfügbar."},
        {"name": "Soybeans", "symbol": "ZS", "ticker": "ZS=F", "aliases": ["SOYBEANS"], "exchange": "CHICAGO BOARD OF TRADE"},
        {"name": "Soybean Meal", "symbol": "ZM", "ticker": "ZM=F", "aliases": ["SOYBEAN MEAL"], "exchange": "CHICAGO BOARD OF TRADE"},
        {"name": "Soybean Oil", "symbol": "ZL", "ticker": "ZL=F", "aliases": ["SOYBEAN OIL"], "exchange": "CHICAGO BOARD OF TRADE"},
    ],
    "Livestock": [
        {"name": "Live Cattle", "symbol": "LE", "ticker": "LE=F", "aliases": ["LIVE CATTLE"], "exchange": "CHICAGO MERCANTILE EXCHANGE"},
        {"name": "Feeder Cattle", "symbol": "GF", "ticker": "GF=F", "aliases": ["FEEDER CATTLE"], "exchange": "CHICAGO MERCANTILE EXCHANGE"},
        {"name": "Lean Hogs", "symbol": "HE", "ticker": "HE=F", "aliases": ["LEAN HOGS"], "exchange": "CHICAGO MERCANTILE EXCHANGE"},
    ],
    "Soft Commodities": [
        {"name": "Coffee C", "symbol": "KC", "ticker": "KC=F", "aliases": ["COFFEE C", "COFFEE"], "exchange": "ICE FUTURES U.S."},
        {"name": "Cocoa", "symbol": "CC", "ticker": "CC=F", "aliases": ["COCOA"], "exchange": "ICE FUTURES U.S."},
        {"name": "Sugar No. 11", "symbol": "SB", "ticker": "SB=F", "aliases": ["SUGAR NO. 11", "SUGAR #11", "SUGAR"], "exchange": "ICE FUTURES U.S."},
        {"name": "Cotton No. 2", "symbol": "CT", "ticker": "CT=F", "aliases": ["COTTON NO. 2", "COTTON"], "exchange": "ICE FUTURES U.S."},
        {"name": "Orange Juice", "symbol": "OJ", "ticker": "OJ=F", "aliases": ["FRZN CONCENTRATED ORANGE JUICE", "FROZEN CONCENTRATED ORANGE JUICE"], "exchange": "ICE FUTURES U.S.", "cftc_code": "040701"},
    ],
    "Forest Products": [
        {"name": "Lumber", "symbol": "LBR", "ticker": "LBR=F", "aliases": ["LUMBER"], "exchange": "CHICAGO MERCANTILE EXCHANGE", "cftc_code": "058644"},
    ],
    "Rates": [
        {"name": "U.S. Treasury 2Y Note", "symbol": "ZT", "ticker": "ZT=F", "aliases": ["UST 2Y NOTE"], "exchange": "CHICAGO BOARD OF TRADE", "cftc_code": "042601"},
        {"name": "U.S. Treasury 5Y Note", "symbol": "ZF", "ticker": "ZF=F", "aliases": ["UST 5Y NOTE"], "exchange": "CHICAGO BOARD OF TRADE", "cftc_code": "044601"},
        {"name": "U.S. Treasury 10Y Note", "symbol": "ZN", "ticker": "ZN=F", "aliases": ["UST 10Y NOTE"], "exchange": "CHICAGO BOARD OF TRADE", "cftc_code": "043602"},
        {"name": "U.S. Treasury Bond 30Y", "symbol": "ZB", "ticker": "ZB=F", "aliases": ["UST BOND"], "exchange": "CHICAGO BOARD OF TRADE", "cftc_code": "020601"},
        {"name": "Ultra U.S. Treasury Bond", "symbol": "UB", "ticker": "UB=F", "aliases": ["ULTRA UST BOND"], "exchange": "CHICAGO BOARD OF TRADE", "cftc_code": "020604"},
    ],
    "Volatility": [
        {"name": "VIX Futures", "symbol": "VIX", "ticker": "^VIX", "aliases": ["VIX FUTURES"], "exchange": "CBOE FUTURES EXCHANGE", "cftc_code": "1170E1", "price_note": "Preisproxy ist der CBOE VIX Spot Index (^VIX); COT-Daten beziehen sich auf VIX Futures."},
    ],
    "Indices": [
        {"name": "E-mini S&P 500", "symbol": "ES", "ticker": "ES=F", "aliases": ["E-MINI S&P 500", "E-MINI S&P"], "exchange": "CHICAGO MERCANTILE EXCHANGE"},
        {"name": "E-mini Nasdaq-100", "symbol": "NQ", "ticker": "NQ=F", "aliases": ["E-MINI NASDAQ-100", "NASDAQ-100"], "exchange": "CHICAGO MERCANTILE EXCHANGE"},
        {"name": "E-mini Dow", "symbol": "YM", "ticker": "YM=F", "aliases": ["E-MINI DOW", "DOW JONES"], "exchange": "CHICAGO BOARD OF TRADE"},
        {"name": "E-mini Russell 2000", "symbol": "RTY", "ticker": "RTY=F", "aliases": ["E-MINI RUSSELL 2000", "RUSSELL 2000"], "exchange": "CHICAGO MERCANTILE EXCHANGE"},
    ],
}

EXCLUDE_TERMS = (
    "MICRO", "BASIS", "SWAP", "BALMO", "LAST DAY", "PENULTIMATE",
    "CALENDAR SPREAD", "DIFFERENTIAL", "DAILY", "MONTHLY",
)
