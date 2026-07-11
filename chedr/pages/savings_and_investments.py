import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
from datetime import date
from core.state import fin

dash.register_page(__name__, path="/savings-investments", name="Savings & Investments")

# ---------------------------------------------------------- constants ---

ACCOUNT_COLORS = [
    "#3498db", "#2ecc71", "#e67e22", "#9b59b6",
    "#1abc9c", "#e74c3c", "#f1c40f", "#34495e",
]

WINDOW_MARKS = {3: "3", 6: "6", 12: "12", 24: "24", 36: "36"}

NEW_ACCOUNT_VALUE = "__new__"

# ---------------------------------------------------------- helpers ---

def account_dropdown_options():
    """Existing tracked accounts, plus an option to add a new one. Used in the Add Entry modal."""
    return [{"label": a, "value": a} for a in fin.get_savings_accounts()] + \
           [{"label": "+ Add new account", "value": NEW_ACCOUNT_VALUE}]


def account_filter_options():
    """Plain list of tracked accounts (no add-new entry). Used for the chart's display filter."""
    return [{"label": a, "value": a} for a in fin.get_savings_accounts()]


# ----------------------------------------------------------- layout ---

def layout(**kwargs):
    return dbc.Container([

        # --- Header ---
        dbc.Row([
            dbc.Col(html.H4("Savings & Investments", className="mb-0")),
            dbc.Col(
                dbc.Button("+ Add Entry", id="si-add-entry-btn",
                           color="primary", size="sm"),
                width="auto", className="ms-auto"
            ),
        ], align="center", className="mb-4"),

        # --- Chart card ---
        dbc.Row(dbc.Col(
            dbc.Card([
                dbc.CardHeader(
                    dbc.Row([
                        dbc.Col(html.Span("Balances Over Time",
                                          style={"fontWeight": "500"}), width=3),
                        dbc.Col(
                            dcc.Dropdown(
                                id="si-account-filter",
                                options=account_filter_options(),
                                value=fin.get_savings_accounts(),
                                multi=True,
                                placeholder="All accounts",
                                style={"fontSize": "0.85rem"},
                            ),
                            width=5
                        ),
                        dbc.Col(
                            dcc.Slider(
                                id="si-months-slider",
                                min=3, max=36, step=None,
                                marks=WINDOW_MARKS,
                                value=12,
                                included=False,
                            ),
                            width=4
                        )
                    ], align="center", className="g-2")
                ),
                dbc.CardBody(
                    dcc.Graph(id="si-balance-chart", style={"height": "500px"})
                )
            ])
        )),

        # --- Save confirmation toast ---
        dbc.Toast(
            "Entry saved.",
            id="si-save-toast",
            header="Saved",
            is_open=False,
            dismissable=True,
            duration=2500,
            color="success",
            style={"position": "fixed", "bottom": "1rem",
                   "right": "1rem", "zIndex": 9999}
        ),

        # --- Add entry modal ---
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Add Balance Entry")),
            dbc.ModalBody([

                html.Label("Account", className="text-muted mb-1",
                           style={"fontSize": "0.8rem"}),
                dcc.Dropdown(
                    id="si-account-select",
                    options=account_dropdown_options(),
                    placeholder="Select an account...",
                    clearable=False,
                    className="mb-2",
                ),
                dbc.Input(
                    id="si-new-account-name",
                    placeholder="New account name",
                    size="sm",
                    className="mb-3",
                    style={"display": "none"},
                ),

                html.Label("Date", className="text-muted mb-1",
                           style={"fontSize": "0.8rem"}),
                html.Div(
                    dcc.DatePickerSingle(
                        id="si-date-picker",
                        date=date.today(),
                        display_format="YYYY-MM-DD",
                    ),
                    className="mb-3"
                ),

                html.Label("Balance", className="text-muted mb-1",
                           style={"fontSize": "0.8rem"}),
                dbc.Input(
                    id="si-balance-input",
                    placeholder="Balance",
                    type="number",
                    className="mb-2",
                ),

                html.P(id="si-form-error", className="text-danger mb-0",
                       style={"fontSize": "0.8rem"}),

            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="si-modal-cancel",
                           color="secondary", outline=True, size="sm",
                           className="me-2"),
                dbc.Button("Save", id="si-modal-save",
                           color="primary", size="sm", disabled=True),
            ])
        ], id="si-modal", is_open=False),

        # --- Store: bump to trigger a chart / account-list refresh ---
        dcc.Store(id="si-refresh", data=0),

    ], fluid=True)


# --------------------------------------------------------- callbacks ---

@callback(
    Output("si-modal",            "is_open"),
    Output("si-account-select",   "options"),
    Output("si-account-select",   "value"),
    Output("si-new-account-name", "value"),
    Output("si-new-account-name", "style", allow_duplicate=True),
    Output("si-date-picker",      "date"),
    Output("si-balance-input",    "value"),
    Output("si-form-error",       "children"),
    Input("si-add-entry-btn",     "n_clicks"),
    Input("si-modal-cancel",      "n_clicks"),
    Input("si-modal-save",        "n_clicks"),
    prevent_initial_call=True
)
def toggle_modal(open_clicks, cancel_clicks, save_clicks):
    """
    Opens the modal fresh (with an up-to-date account list) on 'Add Entry',
    and closes + resets the form on cancel or after a successful save.
    """
    triggered = dash.callback_context.triggered[0]["prop_id"]
    is_open = "add-entry-btn" in triggered
    return (
        is_open,
        account_dropdown_options(),
        None,
        "",
        {"display": "none"},
        date.today(),
        None,
        "",
    )


@callback(
    Output("si-new-account-name", "style", allow_duplicate=True),
    Input("si-account-select",    "value"),
    prevent_initial_call=True
)
def toggle_new_account_input(selected):
    """Reveals the free-text account name field when '+ Add new account' is picked."""
    if selected == NEW_ACCOUNT_VALUE:
        return {"display": "block"}
    return {"display": "none"}


@callback(
    Output("si-modal-save",      "disabled"),
    Input("si-account-select",   "value"),
    Input("si-new-account-name", "value"),
    Input("si-date-picker",      "date"),
    Input("si-balance-input",    "value"),
)
def toggle_save_button(account, new_account, entry_date, balance):
    """Enables Save once an account, date, and balance are all present."""
    has_account = bool(account) and (
        account != NEW_ACCOUNT_VALUE or bool((new_account or "").strip())
    )
    has_balance = balance is not None and balance != ""
    return not (has_account and bool(entry_date) and has_balance)


@callback(
    Output("si-save-toast",      "is_open"),
    Output("si-refresh",         "data"),
    Output("si-form-error",      "children", allow_duplicate=True),
    Input("si-modal-save",       "n_clicks"),
    State("si-account-select",   "value"),
    State("si-new-account-name", "value"),
    State("si-date-picker",      "date"),
    State("si-balance-input",    "value"),
    State("si-refresh",          "data"),
    prevent_initial_call=True
)
def save_entry(n_clicks, account, new_account, entry_date, balance, refresh_count):
    """Persists the new balance entry to the savings/investments json."""
    account_name = (new_account or "").strip() if account == NEW_ACCOUNT_VALUE else account

    if not account_name:
        return False, dash.no_update, "Please select or enter an account name."

    try:
        balance_val = float(balance)
    except (TypeError, ValueError):
        return False, dash.no_update, "Please enter a valid balance."

    fin.add_savings_entry(
        account=account_name,
        entry_date=str(entry_date)[:10],
        balance=balance_val,
    )

    return True, refresh_count + 1, ""


@callback(
    Output("si-account-filter", "options"),
    Output("si-account-filter", "value"),
    Input("si-refresh",         "data"),
    State("si-account-filter",  "value"),
    prevent_initial_call=True
)
def refresh_account_filter(refresh_count, current_value):
    """
    Keeps the display filter in sync with the account list after a save.
    Preserves the user's existing selections/deselections and auto-selects
    any brand-new account rather than resetting everything back to 'all'.
    """
    accounts = fin.get_savings_accounts()
    options = [{"label": a, "value": a} for a in accounts]

    current_value = current_value or []
    new_accounts = [a for a in accounts if a not in current_value]
    value = [v for v in (current_value + new_accounts) if v in accounts]

    return options, value


@callback(
    Output("si-balance-chart", "figure"),
    Input("si-months-slider",  "value"),
    Input("si-account-filter", "value"),
    Input("si-refresh",        "data"),
)
def render_chart(window, selected_accounts, refresh_count):
    """Renders the balance line chart, limited to the selected accounts and window."""
    empty_fig = go.Figure()
    empty_fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )

    df = fin.get_savings_dataframe()
    if df.empty:
        return empty_fig

    if not selected_accounts:
        return empty_fig

    df = df.loc[df["Account"].isin(selected_accounts)]

    cutoff = df["Date"].max() - pd.DateOffset(months=window)
    df = df.loc[df["Date"] >= cutoff]

    fig = go.Figure()
    accounts = sorted(df["Account"].unique())
    for i, account in enumerate(accounts):
        sub = df.loc[df["Account"] == account].sort_values("Date")
        fig.add_trace(go.Scatter(
            x=sub["Date"],
            y=sub["Balance"],
            mode="lines+markers",
            name=account,
            line=dict(color=ACCOUNT_COLORS[i % len(ACCOUNT_COLORS)], width=2),
            marker=dict(size=5),
        ))

    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1),
        margin=dict(l=40, r=20, t=40, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(gridcolor="#ecf0f1", title="Balance ($)"),
        xaxis=dict(title=""),
        hovermode="x unified",
    )
    return fig
