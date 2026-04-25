import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
from core.state import fin
import os

# --- Init Dash ---
app = dash.Dash(
    __name__,
    use_pages=True,               # enables pages/ directory routing
    external_stylesheets=[dbc.themes.FLATLY],
    suppress_callback_exceptions=True
)

# --- Navbar ---
navbar = dbc.NavbarSimple(
    children=[
        dbc.NavItem(dbc.NavLink("Summary",      href="/",            active="exact")),
        dbc.NavItem(dbc.NavLink("Deep Dive",    href="/deepdive",    active="exact")),
        dbc.NavItem(dbc.NavLink("Transactions", href="/transactions", active="exact")),
        dbc.NavItem(dbc.NavLink("Import",       href="/import",      active="exact")),
        dbc.NavItem(dbc.NavLink("Budget", href="/budget", active="exact")),
    ],
    brand="Chedr",
    brand_href="/",
    color="primary",
    dark=True,
    className="mb-4"
)

# --- Root layout ---
app.layout = dbc.Container([
    dcc.Location(id="url"),
    navbar,
    dash.page_container   # renders the active page here
], fluid=True)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)