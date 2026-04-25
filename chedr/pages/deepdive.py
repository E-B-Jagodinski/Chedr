import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
from datetime import date
from core.state import fin

dash.register_page(__name__, path="/deepdive", name="Deep Dive")

# ---------------------------------------------------------- helpers ---

def get_all_months():
    df_exp = fin.calculate_total_expenses()
    return list(df_exp.index)

def month_label(ym_tuple):
    return date(ym_tuple[0], ym_tuple[1], 1).strftime("%B %Y")

# ----------------------------------------------------------- layout ---

def layout():
    months = get_all_months()
    last_idx = len(months) - 1

    return dbc.Container([

        # --- Page header ---
        dbc.Row(dbc.Col(html.H4("Deep Dive", className="mb-3"))),

        # --- Controls row ---
        dbc.Row([

            # Month navigator
            dbc.Col([
                html.Label("Month", className="text-muted mb-1",
                           style={"fontSize": "0.8rem"}),
                dbc.InputGroup([
                    dbc.Button("←", id="month-prev", n_clicks=0,
                               color="secondary", outline=True, size="sm"),
                    dbc.Input(id="month-display", disabled=True,
                              value=month_label(months[last_idx]),
                              style={"textAlign": "center", "maxWidth": "140px"}),
                    dbc.Button("→", id="month-next", n_clicks=0,
                               color="secondary", outline=True, size="sm"),
                ], size="sm"),
            ], width="auto"),

            # Rolling average slider
            dbc.Col([
                html.Label(
                    "Rolling average window: 6 months",
                    id="slider-label",
                    className="text-muted mb-1",
                    style={"fontSize": "0.8rem"}
                ),
                dcc.Slider(
                    id="avg-slider",
                    min=3, max=12, step=3, value=6,
                    marks={3: "3", 6: "6", 9: "9", 12: "12"},
                    tooltip={"always_visible": False},
                    className="mt-1"
                ),
            ], width=4),

            # Average mode toggle
            dbc.Col([
                html.Label("Average calculated from", className="text-muted mb-1",
                           style={"fontSize": "0.8rem"}),
                dbc.ButtonGroup([
                    dbc.Button(
                        "Preceding selected",
                        id="avg-mode-preceding",
                        n_clicks=0,
                        color="primary",
                        outline=False,   # starts active
                        size="sm"
                    ),
                    dbc.Button(
                        "Latest in data",
                        id="avg-mode-latest",
                        n_clicks=0,
                        color="primary",
                        outline=True,    # starts inactive
                        size="sm"
                    ),
                ]),
            ], width="auto"),

            # Edit the budget
            dbc.Col(
                dbc.Button("Edit Budget →", href="/budget",
                        color="secondary", outline=True, size="sm",
                        className="mt-3"),
                width="auto"
            ),

        ], align="end", className="mb-4 g-3"),

        # --- Metric cards ---
        dbc.Row([
            dbc.Col(deepdive_metric_card("Total Spent",  "dd-m-spent"), width=3),
            dbc.Col(deepdive_metric_card("Avg Monthly",  "dd-m-avg"),   width=3),
            dbc.Col(deepdive_metric_card("Over Average", "dd-m-over"),  width=3),
            dbc.Col(deepdive_metric_card("vs Average",   "dd-m-delta"), width=3),
        ], className="mb-4"),

        # --- Chart ---
        dbc.Row(dbc.Col(
            dbc.Card([
                dbc.CardHeader(id="deepdive-card-header"),
                dbc.CardBody(
                    dcc.Graph(id="deepdive-chart", style={"height": "460px"})
                )
            ])
        )),

        # --- Stores ---
        dcc.Store(id="dd-month-index", data=last_idx),
        dcc.Store(id="dd-months-list", data=months),
        dcc.Store(id="avg-mode",       data="preceding"),  # "preceding" | "latest"

    ], fluid=True)


def deepdive_metric_card(label, id):
    return dbc.Card([
        dbc.CardBody([
            html.P(label, className="text-muted mb-1", style={"fontSize": "0.8rem"}),
            html.H5("—", id=id, className="mb-0")
        ])
    ], className="text-center")


# --------------------------------------------------------- callbacks ---

@callback(
    Output("dd-month-index", "data"),
    Input("month-prev", "n_clicks"),
    Input("month-next", "n_clicks"),
    State("dd-month-index", "data"),
    State("dd-months-list", "data"),
    prevent_initial_call=True
)
def navigate_month(prev_clicks, next_clicks, current_idx, months):
    triggered = dash.callback_context.triggered[0]["prop_id"]
    if "prev" in triggered:
        return max(0, current_idx - 1)
    else:
        return min(len(months) - 1, current_idx + 1)


@callback(
    Output("month-display", "value"),
    Input("dd-month-index", "data"),
    State("dd-months-list", "data"),
)
def update_month_display(idx, months):
    return month_label(tuple(months[idx]))


@callback(
    Output("slider-label", "children"),
    Input("avg-slider", "value")
)
def update_slider_label(window):
    return f"Rolling average window: {window} months"


@callback(
    Output("avg-mode",              "data"),
    Output("avg-mode-preceding",    "outline"),
    Output("avg-mode-latest",       "outline"),
    Input("avg-mode-preceding",     "n_clicks"),
    Input("avg-mode-latest",        "n_clicks"),
    prevent_initial_call=True
)
def toggle_avg_mode(n_preceding, n_latest):
    """
    Toggles between average modes, updating the store and
    the button styles (outline=False means active/filled).
    """
    triggered = dash.callback_context.triggered[0]["prop_id"]
    if "preceding" in triggered:
        return "preceding", False, True
    else:
        return "latest", True, False


@callback(
    Output("deepdive-chart",       "figure"),
    Output("deepdive-card-header", "children"),
    Output("dd-m-spent",           "children"),
    Output("dd-m-avg",             "children"),
    Output("dd-m-over",            "children"),
    Output("dd-m-delta",           "children"),
    Input("dd-month-index",        "data"),
    Input("avg-slider",            "value"),
    Input("avg-mode",              "data"),
    State("dd-months-list",        "data"),
)
def render_deepdive(idx, window, avg_mode, months):
    empty_fig = go.Figure()
    empty_fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )

    df_exp = fin.calculate_total_expenses()
    ym = tuple(months[idx])

    if ym not in df_exp.index:
        return empty_fig, "No data", "—", "—", "—", "—"

    monthly = df_exp.loc[ym].fillna(0)
    all_months = list(df_exp.index)
    pos = all_months.index(ym)

    # --- Compute rolling average based on mode ---
    if avg_mode == "preceding":
        # N months immediately before the selected month
        window_months = all_months[max(0, pos - window): pos]
    else:
        # N most recent months in the dataset, regardless of selection
        window_months = all_months[max(0, len(all_months) - window):]
        # Exclude the selected month itself if it's in the window
        window_months = [m for m in window_months if m != ym]

    if window_months:
        avg_series = df_exp.loc[window_months].fillna(0).mean()
    else:
        avg_series = pd.Series(0, index=df_exp.columns)

    # --- Align on full category universe ---
    all_cats = sorted(set(monthly.index) | set(avg_series.index))
    spent = monthly.reindex(all_cats, fill_value=0)
    avg   = avg_series.reindex(all_cats, fill_value=0)

    # Color spent bars: red if over average, green if under
    bar_colors = [
        "#e74c3c" if spent[c] > avg[c] else "#2ecc71"
        for c in all_cats
    ]

    # --- Budget ---
    budget = fin.calculate_budget_monthly().set_index("Category")["monthly_amount"]
    budgeted = budget.reindex(all_cats, fill_value=0)

    # Color spent bars: red if over budget, green if under
    bar_colors = [
        "#e74c3c" if spent[c] > budgeted[c] else "#2ecc71"
        for c in all_cats
    ]

    # --- Build triple bar figure ---
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name="Budget",
        x=all_cats,
        y=budgeted.values,
        marker_color="#3498db",
        opacity=0.7,
    ))

    fig.add_trace(go.Bar(
        name=f"{window}-month avg",
        x=all_cats,
        y=avg.values,
        marker_color="#95a5a6",
        opacity=0.7,
    ))

    fig.add_trace(go.Bar(
        name="Spent",
        x=all_cats,
        y=spent.values,
        marker_color=bar_colors,
        customdata=[[c, ym[0], ym[1]] for c in all_cats],
    ))

    fig.update_layout(
        barmode="group",
        xaxis_tickangle=-35,
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1),
        margin=dict(l=40, r=20, t=40, b=120),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(gridcolor="#ecf0f1", title="$"),
        clickmode="event+select"
    )

    # --- Metrics ---
    total_spent = spent.sum()
    total_avg   = avg.sum()
    n_over      = int((spent > avg).sum())
    delta       = total_spent - total_avg
    delta_str   = f"+${delta:,.0f}" if delta >= 0 else f"-${abs(delta):,.0f}"

    mode_label = "preceding months" if avg_mode == "preceding" else "latest data"
    header = f"{month_label(ym)} vs {window}-month average ({mode_label})"

    return (
        fig,
        header,
        f"${total_spent:,.0f}",
        f"${total_avg:,.0f}",
        str(n_over),
        delta_str
    )


@callback(
    Output("url", "href"),
    Input("deepdive-chart", "clickData"),
    State("dd-month-index", "data"),
    State("dd-months-list", "data"),
    prevent_initial_call=True
)
def click_through_to_transactions(clickData, idx, months):
    if not clickData:
        return dash.no_update
    point    = clickData["points"][0]
    category = point["x"]
    ym       = tuple(months[idx])
    return f"/transactions?category={category}&year={ym[0]}&month={ym[1]}"