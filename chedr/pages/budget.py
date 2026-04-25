import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import json
from core.state import fin

dash.register_page(__name__, path="/budget", name="Budget")

# ---------------------------------------------------------- constants ---

CADENCE_OPTIONS = [
    {"label": "Weekly",     "value": "Weekly"},
    {"label": "Bi-weekly",  "value": "Bi-weekly"},
    {"label": "Monthly",    "value": "Monthly"},
    {"label": "Bi-Monthly", "value": "Bi-Monthly"},
    {"label": "Quarterly",  "value": "Quarterly"},
    {"label": "Bi-yearly",  "value": "Bi-yearly"},
    {"label": "Yearly",     "value": "Yearly"},
]

ACCOUNT_OPTIONS = [
    {"label": "Joint Acct",  "value": "Joint Acct"},
    {"label": "Acct 2", "value": "Acct 2"},
    {"label": "Acct 3",   "value": "Acct 3"},
]

NWS_OPTIONS = [
    {"label": "Need",    "value": "Need"},
    {"label": "Want",    "value": "Want"},
    {"label": "Saving",  "value": "Saving"},
]

CADENCE_MULTIPLIERS = {
    "Weekly":     52 / 12,
    "Bi-weekly":  26 / 12,
    "Monthly":    1,
    "Bi-Monthly": 2,
    "Quarterly":  1 / 3,
    "Bi-yearly":  1 / 6,
    "Yearly":     1 / 12,
}

# ------------------------------------------------------------ helpers ---

def compute_monthly(amount, cadence):
    """Compute the monthly equivalent of an amount given its cadence"""
    try:
        return round(float(amount) * CADENCE_MULTIPLIERS.get(cadence, 1), 2)
    except (TypeError, ValueError):
        return 0.0

def load_budget_records():
    """Load budget CSV as a list of dicts, adding computed Monthly column"""
    df = pd.read_csv(fin.budget_filename)
    df["Monthly"] = df.apply(
        lambda r: compute_monthly(r["Amount"], r["How often"]), axis=1
    )
    return df.to_dict("records")

def get_categories():
    return sorted(fin.total_df["Category"].dropna().unique().tolist())

def rolling_avg_by_category(window=6):
    """Returns a Series of category -> rolling average monthly spend"""
    df_exp = fin.calculate_total_expenses()
    if df_exp.empty:
        return pd.Series(dtype=float)
    months = list(df_exp.index)
    window_months = months[max(0, len(months) - window):]
    return df_exp.loc[window_months].fillna(0).mean()

def budget_by_category(records):
    """Aggregates budget records into category -> total monthly amount"""
    rows = []
    for r in records:
        rows.append({
            "Category": r.get("Category", ""),
            "Monthly":  compute_monthly(r.get("Amount", 0), r.get("How often", "Monthly"))
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.Series(dtype=float)
    return df.groupby("Category")["Monthly"].sum()

# ------------------------------------------------------------ layout ---

def layout(**kwargs):
    records    = load_budget_records()
    # if not hasattr(fin, "total_df") or fin.total_df.empty:
    #     categories = get_categories()

    return dbc.Container([

        # --- Header ---
        dbc.Row([
            dbc.Col(html.H4("Budget", className="mb-0")),
            dbc.Col([
                dbc.Button("← Back to Deep Dive", href="/deepdive",
                           color="secondary", outline=True, size="sm",
                           className="me-2"),
                dbc.Button("Save Budget", id="budget-save-btn",
                           color="primary", size="sm"),
            ], width="auto", className="ms-auto")
        ], align="center", className="mb-4"),

        # --- Main content: table left, chart right ---
        dbc.Row([

            # --- Left: budget table ---
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(
                        dbc.Row([
                            dbc.Col(html.Span("Recurring Items",
                                              style={"fontWeight": "500"})),
                            dbc.Col(
                                dbc.Button("+ Add Row", id="budget-add-row",
                                           color="secondary", outline=True,
                                           size="sm"),
                                width="auto"
                            )
                        ])
                    ),
                    dbc.CardBody([
                        html.Div(id="budget-table-container"),
                    ], style={"overflowY": "auto", "maxHeight": "72vh",
                              "padding": "0.5rem"})
                ])
            ], width=7),

            # --- Right: comparison chart ---
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(
                        dbc.Row([
                            dbc.Col(html.Span("Budget vs 6-month Average",
                                              style={"fontWeight": "500"})),
                            dbc.Col(
                                dcc.Slider(
                                    id="budget-avg-slider",
                                    min=3, max=12, step=3, value=6,
                                    marks={3:"3", 6:"6", 9:"9", 12:"12"},
                                    tooltip={"always_visible": False},
                                ),
                                width=6
                            )
                        ], align="center")
                    ),
                    dbc.CardBody(
                        dcc.Graph(id="budget-compare-chart",
                                  style={"height": "65vh"})
                    )
                ])
            ], width=5),

        ]),

        # --- Save confirmation toast ---
        dbc.Toast(
            "Budget saved successfully.",
            id="budget-save-toast",
            header="Saved",
            is_open=False,
            dismissable=True,
            duration=2500,
            color="success",
            style={"position": "fixed", "bottom": "1rem",
                   "right": "1rem", "zIndex": 9999}
        ),

        # --- Stores ---
        # Live working copy — edits go here, not to disk
        dcc.Store(id="budget-store", data=records),
        # Counter to track how many blank rows have been added
        dcc.Store(id="budget-row-counter", data=len(records)),

    ], fluid=True)


# ------------------------------------------------- table rendering ---

def render_row(r, idx, categories):
    """Renders a single budget row as a compact form row"""
    return dbc.Card(
        dbc.CardBody(
            dbc.Row([

                # Origin
                dbc.Col(
                    dbc.Input(
                        id={"type": "budget-origin", "index": idx},
                        value=r.get("Origin", ""),
                        placeholder="Name",
                        size="sm",
                        style={"fontSize": "0.8rem"}
                    ),
                    width=2
                ),

                # Amount
                dbc.Col(
                    dbc.Input(
                        id={"type": "budget-amount", "index": idx},
                        value=r.get("Amount", ""),
                        placeholder="Amount",
                        type="number",
                        min=0,
                        size="sm",
                        style={"fontSize": "0.8rem"}
                    ),
                    width=1
                ),

                # Cadence
                dbc.Col(
                    dcc.Dropdown(
                        id={"type": "budget-cadence", "index": idx},
                        options=CADENCE_OPTIONS,
                        value=r.get("How often", "Monthly"),
                        clearable=False,
                        style={"fontSize": "0.8rem"}
                    ),
                    width=2
                ),

                # Category
                dbc.Col(
                    dcc.Dropdown(
                        id={"type": "budget-category", "index": idx},
                        options=[{"label": c, "value": c} for c in categories],
                        value=r.get("Category", None),
                        clearable=False,
                        placeholder="Category",
                        style={"fontSize": "0.8rem"}
                    ),
                    width=2
                ),

                # Need/Want/Saving
                dbc.Col(
                    dcc.Dropdown(
                        id={"type": "budget-nws", "index": idx},
                        options=NWS_OPTIONS,
                        value=r.get("Need/Want/Saving", None),
                        clearable=False,
                        placeholder="N/W/S",
                        style={"fontSize": "0.8rem"}
                    ),
                    width=1
                ),

                # Account
                dbc.Col(
                    dcc.Dropdown(
                        id={"type": "budget-account", "index": idx},
                        options=ACCOUNT_OPTIONS,
                        value=r.get("Account", None),
                        clearable=False,
                        placeholder="Account",
                        style={"fontSize": "0.8rem"}
                    ),
                    width=1
                ),

                # Variable toggle
                dbc.Col(
                    dbc.Row([
                        dbc.Col(
                            html.P("Var.", className="text-muted mb-0",
                                   style={"fontSize": "0.7rem"}),
                            width="auto"
                        ),
                        dbc.Col(
                            dbc.Switch(
                                id={"type": "budget-variable", "index": idx},
                                value=r.get("Variable", "No") == "Yes",
                            ),
                            width="auto"
                        )
                    ], align="center", className="g-1"),
                    width=1
                ),

                # Monthly (auto-computed, read-only)
                dbc.Col(
                    html.P(
                        f"${compute_monthly(r.get('Amount', 0), r.get('How often', 'Monthly')):,.2f}/mo",
                        id={"type": "budget-monthly", "index": idx},
                        className="text-muted mb-0 mt-1",
                        style={"fontSize": "0.8rem", "textAlign": "right"}
                    ),
                    width=1
                ),

                # Delete button
                dbc.Col(
                    dbc.Button(
                        "×",
                        id={"type": "budget-delete", "index": idx},
                        color="danger",
                        outline=True,
                        size="sm",
                        style={"padding": "0 6px", "lineHeight": "1.4"}
                    ),
                    width="auto"
                ),

            ], className="g-1", align="center")
        ),
        className="mb-1",
        style={"border": "0.5px solid var(--bs-border-color)"}
    )


@callback(
    Output("budget-table-container", "children"),
    Input("budget-store",            "data"),
    prevent_initial_call=False
)
def render_table(records):
    categories = get_categories()
    if not records:
        return html.P("No budget items.", className="text-muted")
    return [render_row(r, i, categories) for i, r in enumerate(records)]


# ------------------------------------------------- store mutations ---

@callback(
    Output("budget-store",       "data",  allow_duplicate=True),
    Output("budget-row-counter", "data",  allow_duplicate=True),
    Input("budget-add-row",      "n_clicks"),
    State("budget-store",        "data"),
    State("budget-row-counter",  "data"),
    prevent_initial_call=True
)
def add_row(n_clicks, records, counter):
    """Appends a blank row to the budget store"""
    new_row = {
        "Origin":          "",
        "Amount":          0,
        "How often":       "Monthly",
        "Variable":        "No",
        "Need/Want/Saving":"Need",
        "Category":        None,
        "Account":         None,
        "Monthly":         0.0,
        "Comment":         "",
    }
    return records + [new_row], counter + 1


@callback(
    Output("budget-store", "data", allow_duplicate=True),
    Input({"type": "budget-delete",   "index": dash.ALL}, "n_clicks"),
    State("budget-store", "data"),
    prevent_initial_call=True
)
def delete_row(n_clicks_list, records):
    """Removes the row whose delete button was clicked"""
    triggered = dash.callback_context.triggered[0]
    if not any(n_clicks_list) or not triggered["value"]:
        return dash.no_update
    # Extract index from the triggered component id
    idx = json.loads(triggered["prop_id"].split(".")[0])["index"]
    return [r for i, r in enumerate(records) if i != idx]


@callback(
    Output("budget-store", "data", allow_duplicate=True),
    Input({"type": "budget-origin",   "index": dash.ALL}, "value"),
    Input({"type": "budget-amount",   "index": dash.ALL}, "value"),
    Input({"type": "budget-cadence",  "index": dash.ALL}, "value"),
    Input({"type": "budget-category", "index": dash.ALL}, "value"),
    Input({"type": "budget-nws",      "index": dash.ALL}, "value"),
    Input({"type": "budget-account",  "index": dash.ALL}, "value"),
    Input({"type": "budget-variable", "index": dash.ALL}, "value"),
    State("budget-store", "data"),
    prevent_initial_call=True
)
def sync_store(origins, amounts, cadences, categories,
               nws_list, accounts, variables, records):
    """
    Syncs all row field values back into the budget store.
    Fires on any field change — updates the store without touching disk.
    """
    if not records:
        return dash.no_update

    updated = []
    for i, r in enumerate(records):
        try:
            amount  = float(amounts[i]) if amounts[i] not in (None, "") else 0.0
            cadence = cadences[i] or "Monthly"
            updated.append({
                "Origin":           origins[i]   or r.get("Origin", ""),
                "Amount":           amount,
                "How often":        cadence,
                "Variable":         "Yes" if variables[i] else "No",
                "Need/Want/Saving": nws_list[i]  or r.get("Need/Want/Saving", ""),
                "Category":         categories[i] or r.get("Category", ""),
                "Account":          accounts[i]   or r.get("Account", ""),
                "Monthly":          compute_monthly(amount, cadence),
                "Comment":          r.get("Comment", ""),
            })
        except IndexError:
            updated.append(r)

    return updated


# -------------------------------------------- comparison chart ---

@callback(
    Output("budget-compare-chart", "figure"),
    Input("budget-store",          "data"),
    Input("budget-avg-slider",     "value"),
)
def update_compare_chart(records, window):
    """
    Live-updating chart: category monthly budget total vs rolling average.
    Reads from the store so it reflects unsaved edits in real time.
    """
    avg    = rolling_avg_by_category(window)
    budget = budget_by_category(records)

    all_cats = sorted(set(avg.index) | set(budget.index))
    avg_vals    = [avg.get(c, 0)    for c in all_cats]
    budget_vals = [budget.get(c, 0) for c in all_cats]

    # Color budget bars: red if over average, green if under
    bar_colors = [
        "#e74c3c" if avg_vals[i] > budget_vals[i] else "#2ecc71"
        for i in range(len(all_cats))
    ]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name="Budget",
        x=all_cats,
        y=budget_vals,
        marker_color="#95a5a6",
    ))

    fig.add_trace(go.Bar(
        name=f"{window}-month avg",
        x=all_cats,
        y=avg_vals,
        marker_color=bar_colors,
        opacity=0.7,
    ))

    fig.update_layout(
        barmode="group",
        xaxis_tickangle=-35,
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1),
        margin=dict(l=40, r=20, t=40, b=120),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(gridcolor="#ecf0f1", title="$/month"),
    )

    return fig


# ------------------------------------------------- save to disk ---

@callback(
    Output("budget-save-toast", "is_open"),
    Input("budget-save-btn",    "n_clicks"),
    State("budget-store",       "data"),
    prevent_initial_call=True
)
def save_budget(n_clicks, records):
    """Writes the current store state back to the budget CSV file"""
    df = pd.DataFrame(records)

    # Reorder to match original CSV column order
    cols = ["Origin", "Amount", "How often", "Variable",
            "Need/Want/Saving", "Category", "Account", "Monthly", "Comment"]
    df = df[[c for c in cols if c in df.columns]]

    df.to_csv(fin.budget_filename, index=False)

    # Also refresh the in-memory budget on the Chedr instance
    fin.read_budget()

    return True