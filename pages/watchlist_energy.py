from pathlib import Path
import runpy

import streamlit as st

# V3.14.3 · ASSET CLASS WATCHLIST WRAPPER
st.session_state["_watchlist_asset_scope_once"] = 'Energy'
runpy.run_path(
    str(Path(__file__).with_name("watchlist.py")),
    run_name="__main__",
)
