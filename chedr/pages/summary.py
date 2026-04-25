import dash
from dash import dcc, html, Input, Output, callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
from datetime import date

dash.register_page(__name__, path="/", name="Summary")

# Import the shared Chedr instance from app.py
from core.state import fin

# ------------------------------------------------------------------ layout ---

def layout():
    # Guard: no data yet on first run
    if not hasattr(fin, "total_df") or fin.total_df.empty:
        return dbc.Container([
            dbc.Row(dbc.Col(
                dbc.Card([
                    dbc.CardBody([
                        html.H5("No data yet", className="mb-2"),
                        html.P(
                            "No transaction data has been imported yet. "
                            "Head to the Import page to get started.",
                            className="text-muted mb-3",
                            style={"fontSize": "0.9rem"}
                        ),
                        dbc.Button("Go to Import →", href="/import",
                                   color="primary", size="sm")
                    ])
                ], className="mt-4")
            ), justify="center")
        ], fluid=True)

    # Get the last month present in the transaction data
    df_exp = fin.calculate_total_expenses()
    last_idx = df_exp.index[-1]  # (year, month) tuple
    last_month = date(last_idx[0], last_idx[1], 1)
    return dbc.Container([

        # --- Page header ---
        dbc.Row(dbc.Col(
            html.H4(
                f"Summary — {last_month.strftime('%B %Y')}",
                className="mb-3"
            )
        )),

        # --- Metric cards row ---
        dbc.Row([
            dbc.Col(metric_card("Total Spent",    id="m-spent"),   width=3),
            dbc.Col(metric_card("Budgeted",       id="m-budget"),  width=3),
            dbc.Col(metric_card("Remaining",      id="m-remaining"),width=3),
            dbc.Col(metric_card("Net Income",   id="m-net"),     width=3),
        ], className="mb-4"),

        # --- Budget vs Actual chart ---
        dbc.Row(dbc.Col(
            dbc.Card([
                dbc.CardHeader("Spending vs Budget by Category"),
                dbc.CardBody(dcc.Graph(id="budget-chart", style={"height": "420px"}))
            ])
        )),

        # --- Income vs Expenses chart ---
        dbc.Row(dbc.Col(
            dbc.Card([
                dbc.CardHeader(
                    dbc.Row([
                        dbc.Col(html.Span("Income vs Expenses",
                                        style={"fontWeight": "500"})),
                        dbc.Col([
                            html.Label(
                                "6 months",
                                id="income-slider-label",
                                className="text-muted me-2",
                                style={"fontSize": "0.8rem"}
                            ),
                            dcc.Slider(
                                id="income-months-slider",
                                min=3, max=24, step=1, value=6,
                                marks={3: "3", 6: "6", 12: "12",
                                    18: "18", 24: "24"},
                                tooltip={"always_visible": False},
                            ),
                        ], width=5),
                    ], align="center")
                ),
                dbc.CardBody(
                    dcc.Graph(id="income-expense-chart",
                            style={"height": "420px"})
                )
            ]), className="mt-4"
        )),

        # --- Hidden store: pre-computed data for this page ---
        dcc.Store(id="summary-data")

    ], fluid=True)


def metric_card(label, id):
    """Reusable summary metric card"""
    return dbc.Card([
        dbc.CardBody([
            html.P(label, className="text-muted mb-1", style={"fontSize": "0.8rem"}),
            html.H5("—", id=id, className="mb-0")
        ])
    ], className="text-center")


# --------------------------------------------------------------- callbacks ---

@callback(
    Output("summary-data", "data"),
    Input("url", "pathname")
)
def load_summary_data(pathname):
    if pathname != "/" or fin.total_df.empty:
        return {}

    df_exp        = fin.calculate_total_expenses()
    current_month = df_exp.index[-1]
    monthly       = df_exp.loc[current_month].fillna(0)

    budget = fin.calculate_budget_monthly()
    budget = budget.set_index("Category")["monthly_amount"]

    all_cats = sorted(set(monthly.index) | set(budget.index))
    # Remove Income from expense categories — it's handled separately
    all_cats = [c for c in all_cats if c != "Income"]
    spent    = monthly.reindex(all_cats, fill_value=0)
    budgeted = budget.reindex(all_cats,  fill_value=0)

    # --- Income: actual vs budgeted ---
    df_cre = fin.calculate_total_credit()
    if tuple(current_month) in df_cre.index:
        income_actual = float(df_cre.loc[current_month].fillna(0).sum())
    else:
        income_actual = 0.0
    income_budget = float(budget.get("Income", 0))

    return {
        "categories":     all_cats,
        "spent":          spent.tolist(),
        "budgeted":       budgeted.tolist(),
        "month_label":    f"{current_month[0]}-{str(current_month[1]).zfill(2)}",
        "income_actual":  income_actual,
        "income_budget":  income_budget,
        "income_total":   income_actual,
        "total_spent":    float(spent.sum()),
    }


@callback(
    Output("budget-chart",  "figure"),
    Output("m-spent",       "children"),
    Output("m-budget",      "children"),
    Output("m-remaining",   "children"),
    Output("m-net",         "children"),
    Input("summary-data",   "data")
)
def render_summary(data):
    empty_fig = go.Figure()
    empty_fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )

    if not data or not data.get("categories"):
        return empty_fig, "—", "—", "—", "—"

    cats     = data["categories"]
    spent    = data["spent"]
    budgeted = data["budgeted"]

    income_actual = data.get("income_actual", 0)
    income_budget = data.get("income_budget", 0)

    # Prepend Income as the first category
    all_cats     = ["Income"] + cats
    all_spent    = [income_actual] + spent
    all_budgeted = [income_budget] + budgeted

    # Income: green if actual >= budget, red if below (inverted vs expenses)
    # Expenses: red if over budget, green if under
    bar_colors = []
    for i, cat in enumerate(all_cats):
        s, b = all_spent[i], all_budgeted[i]
        if cat == "Income":
            bar_colors.append("#2ecc71" if s >= b else "#e74c3c")
        else:
            bar_colors.append("#e74c3c" if s > b else "#2ecc71")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Budgeted",
        x=all_cats, y=all_budgeted,
        marker_color="#95a5a6", opacity=0.6
    ))
    fig.add_trace(go.Bar(
        name="Actual",
        x=all_cats, y=all_spent,
        marker_color=bar_colors,
    ))
    fig.update_layout(
        barmode="group",
        xaxis_tickangle=-35,
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1),
        margin=dict(l=40, r=20, t=40, b=100),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(gridcolor="#ecf0f1", title="$")
    )

    total_spent    = data["total_spent"]
    total_budgeted = sum(budgeted)
    remaining      = total_budgeted - total_spent
    net            = income_actual - total_spent

    fmt = lambda v: f"${v:,.0f}"
    remaining_display = (
        f"-{fmt(abs(remaining))}" if remaining < 0 else fmt(remaining)
    )
    net_display = (
        f"-{fmt(abs(net))}" if net < 0 else f"+{fmt(net)}"
    )

    return (
        fig,
        fmt(total_spent),
        fmt(total_budgeted),
        remaining_display,
        net_display
    )

@callback(
    Output("income-expense-chart",  "figure"),
    Output("income-slider-label",   "children"),
    Input("income-months-slider",   "value"),
    Input("url",                    "pathname"),
)
def render_income_expense_chart(window, pathname):
    empty_fig = go.Figure()
    empty_fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    if pathname != "/" or fin.total_df.empty:
        return empty_fig, ""

    # --- Expenses: total per month ---
    df_exp = fin.calculate_total_expenses()
    exp_months = list(df_exp.index)[-window:]
    exp_totals = df_exp.loc[exp_months].fillna(0).sum(axis=1)

    # --- Income: stacked by category, same window ---
    df_cre = fin.calculate_total_credit()
    # Align to the same months as expenses
    common_months = [m for m in exp_months if m in df_cre.index]
    df_cre_window = df_cre.loc[common_months].fillna(0) if common_months else pd.DataFrame()

    # Month labels for x axis
    def fmt_month(ym):
        return f"{ym[1]:02d}/{str(ym[0])[2:]}"

    x_labels = [fmt_month(m) for m in exp_months]

    fig = go.Figure()

    # --- Stacked income bars by category ---
    if not df_cre_window.empty:
        # Build x aligned to exp_months, filling gaps with 0
        income_cats = df_cre_window.columns.tolist()
        cat_colors  = [
            "#2ecc71", "#27ae60", "#1abc9c", "#16a085",
            "#3498db", "#2980b9", "#9b59b6", "#8e44ad"
        ]
        for i, cat in enumerate(income_cats):
            y_vals = []
            for m in exp_months:
                if m in df_cre_window.index:
                    y_vals.append(df_cre_window.loc[m, cat])
                else:
                    y_vals.append(0)
            fig.add_trace(go.Bar(
                name=str(cat),
                x=x_labels,
                y=y_vals,
                marker_color=cat_colors[i % len(cat_colors)],
                offsetgroup="income",
                legendgroup="income",
            ))

    # --- Total expenses bar ---
    exp_y = []
    for m in exp_months:
        if m in exp_totals.index:
            exp_y.append(exp_totals[m])
        else:
            exp_y.append(0)

    fig.add_trace(go.Bar(
        name="Expenses",
        x=x_labels,
        y=exp_y,
        marker_color="#e74c3c",
        opacity=0.8,
        offsetgroup="expenses",
    ))

    fig.update_layout(
        barmode="group",
        xaxis_tickangle=-35,
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1),
        margin=dict(l=40, r=20, t=40, b=80),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(gridcolor="#ecf0f1", title="$"),
        bargroupgap=0.15,
    )

    label = f"{window} month{'s' if window != 1 else ''}"
    return fig, label