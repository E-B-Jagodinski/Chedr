import dash
from dash import dcc, html, Input, Output, State, callback, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import date
from flask import request
from core.state import fin

dash.register_page(__name__, path="/transactions", name="Transactions")

# ---------------------------------------------------------- helpers ---

def get_all_months():
    df = fin.calculate_total_expenses()
    return list(df.index)

def month_label(ym):
    return date(ym[0], ym[1], 1).strftime("%B %Y")

def get_accounts():
    return sorted(fin.total_df["acct"].dropna().unique().tolist())

def get_categories():
    return sorted(fin.total_df["Category"].dropna().unique().tolist())

def get_transactions_df():
    """Returns the display-ready transaction dataframe, most recent first"""
    df = fin.total_df.copy()

    # Filter first, while all columns are still available
    df = df.loc[
        (df["acct_type"] != "savings") &
        (df["Amount"] < 0) &
        (df["Category"] != "Payment")
    ]

    # Then select only display columns
    cols = ["Date", "Description", "Amount", "Category", "acct", "ignore"]
    df = df[cols].copy()

    df["Amount"] = df["Amount"].abs().round(2)
    df["Date"]   = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    df = df.sort_values("Date", ascending=False).reset_index(drop=True)
    df["ignore"] = df["ignore"].fillna(False)

    return df

# ----------------------------------------------------------- layout ---

def layout(category="", year="", month="", **kwargs):
    # kwargs catches any other query params Dash might pass
    
    # Resolve pre-populated month index
    months   = get_all_months()
    last_idx = len(months) - 1
    if year and month:
        try:
            pre_ym  = (int(year), int(month))
            pre_idx = months.index(pre_ym)
        except (ValueError, IndexError):
            pre_idx = last_idx
    else:
        pre_idx = last_idx

    accounts   = get_accounts()
    categories = get_categories()

    return dbc.Container([

        # --- Page header ---
        dbc.Row(dbc.Col(html.H4("Transactions", className="mb-3"))),

        # --- Filter row ---
        dbc.Row([

            # Month navigator
            dbc.Col([
                html.Label("Month", className="text-muted mb-1",
                           style={"fontSize": "0.8rem"}),
                dbc.InputGroup([
                    dbc.Button("←", id="txn-month-prev", n_clicks=0,
                               color="secondary", outline=True, size="sm"),
                    dbc.Input(id="txn-month-display", disabled=True,
                              value=month_label(months[pre_idx]),
                              style={"textAlign": "center", "maxWidth": "140px"}),
                    dbc.Button("→", id="txn-month-next", n_clicks=0,
                               color="secondary", outline=True, size="sm"),
                ], size="sm"),
            ], width="auto"),

            # Account filter
            dbc.Col([
                html.Label("Account", className="text-muted mb-1",
                           style={"fontSize": "0.8rem"}),
                dcc.Dropdown(
                    id="txn-account-filter",
                    options=[{"label": a, "value": a} for a in accounts],
                    placeholder="All accounts",
                    clearable=True,
                    style={"minWidth": "160px"}
                ),
            ], width="auto"),

            # Category filter
            dbc.Col([
                html.Label("Category", className="text-muted mb-1",
                           style={"fontSize": "0.8rem"}),
                dcc.Dropdown(
                    id="txn-category-filter",
                    options=[{"label": c, "value": c} for c in categories],
                    value=category or None,
                    placeholder="All categories",
                    clearable=True,
                    style={"minWidth": "160px"}
                ),
            ], width="auto"),

            # Description search
            dbc.Col([
                html.Label("Search", className="text-muted mb-1",
                           style={"fontSize": "0.8rem"}),
                dbc.Input(
                    id="txn-search",
                    placeholder="Search description...",
                    debounce=True,
                    size="sm",
                    style={"minWidth": "180px"}
                ),
            ], width="auto"),

            # Show ignored toggle
            dbc.Col([
                html.Label("Show ignored", className="text-muted mb-1",
                           style={"fontSize": "0.8rem"}),
                dbc.Switch(id="txn-show-ignored", value=False),
            ], width="auto"),

            # Clear filters button
            dbc.Col([
                dbc.Button("Clear filters", id="txn-clear-filters",
                           color="secondary", outline=True, size="sm",
                           className="mt-3")
            ], width="auto"),

            # Bulk Recategorize
            dbc.Col(
                dbc.Button("Bulk Recategorize", id="bulk-recat-open",
                        color="warning", outline=True, size="sm",
                        className="mt-3"),
                width="auto"
            ),

        ], align="end", className="mb-3 g-3"),

        # --- Summary strip ---
        dbc.Row([
            dbc.Col(html.P(id="txn-summary-strip",
                           className="text-muted",
                           style={"fontSize": "0.85rem"})),
        ], className="mb-2"),

        # --- Transaction table ---
        dbc.Row(dbc.Col(
            dash_table.DataTable(
                id="txn-table",
                columns=[
                    {"name": "Date",        "id": "Date",        "type": "text"},
                    {"name": "Description", "id": "Description", "type": "text"},
                    {"name": "Amount",      "id": "Amount",      "type": "numeric",
                     "format": dash_table.FormatTemplate.money(2)},
                    {"name": "Category",    "id": "Category",    "type": "text",
                     "presentation": "dropdown"},
                    {"name": "Account",     "id": "acct",        "type": "text"},
                    {"name": "Ignore",      "id": "ignore",      "type": "any",
                     "presentation": "dropdown"},
                ],
                dropdown={
                    "Category": {
                        "options": [{"label": c, "value": c} for c in categories],
                        "clearable": False,
                    },
                    "ignore": {
                        "options": [
                            {"label": "Yes", "value": True},
                            {"label": "No",  "value": False},
                        ],
                        "clearable": False,
                    }
                },
                editable=True,
                sort_action="native",
                sort_by=[{"column_id": "Date", "direction": "desc"}],
                page_action="native",
                page_size=25,
                style_table={"overflowX": "auto"},
                style_header={
                    "fontWeight": "500",
                    "fontSize": "0.82rem",
                    "borderBottom": "1px solid #dee2e6",
                    "backgroundColor": "transparent",
                },
                style_cell={
                    "fontSize": "0.83rem",
                    "padding": "8px 12px",
                    "border": "none",
                    "borderBottom": "0.5px solid #f0f0f0",
                    "backgroundColor": "transparent",
                    "textOverflow": "ellipsis",
                    "maxWidth": "260px",
                },
                style_data_conditional=[
                    # Highlight over-budget rows
                    {
                        "if": {"filter_query": "{ignore} eq 'True'"},
                        "color": "#adb5bd",
                        "fontStyle": "italic",
                    },
                ],
            )
        )),

        # --- Re-categorization save confirmation toast ---
        dbc.Toast(
            "Transaction updated and saved.",
            id="txn-save-toast",
            header="Saved",
            is_open=False,
            dismissable=True,
            duration=2500,
            color="success",
            style={"position": "fixed", "bottom": "1rem",
                   "right": "1rem", "zIndex": 9999}
        ),

        # --- Stores ---
        dcc.Store(id="txn-month-index", data=pre_idx),
        dcc.Store(id="txn-months-list", data=months),
        dcc.Store(id="txn-raw-data"),      # full filtered dataframe as records
        dcc.Store(id="txn-prev-data"),     # snapshot to diff against on edit

        # --- Bulk recategorize modal ---
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Bulk Recategorize")),
            dbc.ModalBody([
                html.P(
                    "Reassign all transactions whose description contains the "
                    "substring below to a new category. This will also update "
                    "the category key so future imports are categorized correctly.",
                    className="text-muted mb-3",
                    style={"fontSize": "0.85rem"}
                ),

                html.Label("Substring to match", className="text-muted mb-1",
                        style={"fontSize": "0.8rem"}),
                dbc.Input(
                    id="bulk-recat-substring",
                    placeholder="e.g. WHOLE FOODS",
                    size="sm",
                    className="mb-3"
                ),

                html.Label("New category", className="text-muted mb-1",
                        style={"fontSize": "0.8rem"}),
                dcc.Dropdown(
                    id="bulk-recat-category",
                    options=[{"label": c, "value": c} for c in get_categories()],
                    placeholder="Select a category...",
                    clearable=False,
                    className="mb-3"
                ),

                html.P(id="bulk-recat-preview", className="text-muted mb-0",
                    style={"fontSize": "0.82rem"})
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="bulk-recat-cancel",
                        color="secondary", outline=True, size="sm",
                        className="me-2"),
                dbc.Button("Apply", id="bulk-recat-apply",
                        color="primary", size="sm", disabled=True),
            ])
        ], id="bulk-recat-modal", is_open=False),

    ], fluid=True)


# --------------------------------------------------------- callbacks ---

@callback(
    Output("txn-month-index", "data"),
    Input("txn-month-prev",   "n_clicks"),
    Input("txn-month-next",   "n_clicks"),
    State("txn-month-index",  "data"),
    State("txn-months-list",  "data"),
    prevent_initial_call=True
)
def navigate_month(prev_clicks, next_clicks, current_idx, months):
    triggered = dash.callback_context.triggered[0]["prop_id"]
    if "prev" in triggered:
        return max(0, current_idx - 1)
    return min(len(months) - 1, current_idx + 1)


@callback(
    Output("txn-month-display", "value"),
    Input("txn-month-index",    "data"),
    State("txn-months-list",    "data"),
)
def update_month_display(idx, months):
    return month_label(tuple(months[idx]))


@callback(
    Output("txn-account-filter",  "value"),
    Output("txn-category-filter", "value"),
    Output("txn-search",          "value"),
    Input("txn-clear-filters",    "n_clicks"),
    prevent_initial_call=True
)
def clear_filters(_):
    return None, None, ""


@callback(
    Output("txn-table",         "data"),
    Output("txn-summary-strip", "children"),
    Output("txn-prev-data",     "data"),
    Input("txn-month-index",    "data"),
    Input("txn-account-filter", "value"),
    Input("txn-category-filter","value"),
    Input("txn-search",         "value"),
    Input("txn-show-ignored",   "value"),
    State("txn-months-list",    "data"),
)
def load_table(idx, account, category, search, show_ignored, months):
    ym  = tuple(months[idx])
    df  = get_transactions_df()

    # --- Apply filters ---
    df = df.loc[
        (pd.to_datetime(df["Date"]).dt.year  == ym[0]) &
        (pd.to_datetime(df["Date"]).dt.month == ym[1])
    ]
    if account:
        df = df.loc[df["acct"] == account]
    if category:
        df = df.loc[df["Category"] == category]
    if search:
        df = df.loc[df["Description"].str.contains(search, case=False, na=False)]
    if not show_ignored:
        df = df.loc[df["ignore"] == False]

    records = df.to_dict("records")

    # Summary strip
    total = df["Amount"].sum()
    n     = len(df)
    strip = f"{n} transaction{'s' if n != 1 else ''} — ${total:,.2f} total"

    return records, strip, records


@callback(
    Output("txn-save-toast", "is_open"),
    Input("txn-table",       "data"),
    State("txn-prev-data",   "data"),
    State("txn-months-list", "data"),
    State("txn-month-index", "data"),
    prevent_initial_call=True
)
def save_edits(current_data, prev_data, months, idx):
    """
    Diffs the current table data against the previous snapshot.
    Writes any changed Category or ignore values back to total_df
    and persists to parquet.
    """
    if not prev_data or not current_data:
        return False

    changed = False
    prev_map = {r["Description"]: r for r in prev_data}
    
    # Coerce Date column to datetime before using .dt accessor
    date_col = pd.to_datetime(fin.total_df["Date"], format="mixed")

    for row in current_data:
        desc = row["Description"]
        if desc not in prev_map:
            continue
        prev_row = prev_map[desc]

        category_changed = row["Category"] != prev_row["Category"]
        ignore_changed   = row["ignore"]   != prev_row["ignore"]

        if category_changed or ignore_changed:
            # Match on description + date to avoid updating unrelated rows
            mask = (
                (fin.total_df["Description"] == desc) &
                (date_col.dt.strftime("%Y-%m-%d") == row["Date"])
            )
            if category_changed:
                fin.total_df.loc[mask, "Category"] = row["Category"]
                fin.total_df.loc[mask, "set"]      = True
            if ignore_changed:
                fin.total_df.loc[mask, "ignore"] = row["ignore"]
            changed = True

    if changed:
        fin.store_total_overview()

    return changed

@callback(
    Output("bulk-recat-modal", "is_open"),
    Input("bulk-recat-open",   "n_clicks"),
    Input("bulk-recat-cancel", "n_clicks"),
    Input("bulk-recat-apply",  "n_clicks"),
    State("bulk-recat-modal",  "is_open"),
    prevent_initial_call=True
)
def toggle_bulk_recat_modal(open_clicks, cancel_clicks, apply_clicks, is_open):
    triggered = dash.callback_context.triggered[0]["prop_id"]
    if "open" in triggered:
        return True
    return False


@callback(
    Output("bulk-recat-preview", "children"),
    Output("bulk-recat-apply",   "disabled"),
    Input("bulk-recat-substring","value"),
    Input("bulk-recat-category", "value"),
    prevent_initial_call=True
)
def preview_bulk_recat(substring, category):
    """
    Shows a live count of how many transactions will be affected
    before the user commits.
    """
    if not substring or not category:
        return "", True

    mask = fin.total_df["Description"].str.contains(
        substring, case=False, na=False
    )
    n = mask.sum()

    if n == 0:
        return (
            f"No transactions found matching '{substring}'.",
            True   # keep Apply disabled
        )

    current_cats = fin.total_df.loc[mask, "Category"].value_counts()
    breakdown = ", ".join(
        f"{cat} ({count})" for cat, count in current_cats.items()
    )
    return (
        f"{n} transaction{'s' if n != 1 else ''} will be reassigned "
        f"to '{category}'. Currently: {breakdown}.",
        False  # enable Apply
    )


@callback(
    Output("bulk-recat-modal",   "is_open",  allow_duplicate=True),
    Output("txn-save-toast",     "is_open",  allow_duplicate=True),
    Output("txn-table",          "data",     allow_duplicate=True),
    Input("bulk-recat-apply",    "n_clicks"),
    State("bulk-recat-substring","value"),
    State("bulk-recat-category", "value"),
    State("txn-month-index",     "data"),
    State("txn-months-list",     "data"),
    State("txn-account-filter",  "value"),
    State("txn-category-filter", "value"),
    State("txn-search",          "value"),
    State("txn-show-ignored",    "value"),
    prevent_initial_call=True
)
def apply_bulk_recat(n_clicks, substring, category, idx, months,
                     account, cat_filter, search, show_ignored):
    """
    Applies the bulk recategorization to total_df, updates the
    category key, persists, and refreshes the visible table.
    """
    if not substring or not category:
        return False, False, dash.no_update

    # Update total_df
    mask = fin.total_df["Description"].str.contains(
        substring, case=False, na=False
    )
    fin.total_df.loc[mask, "Category"] = category
    fin.total_df.loc[mask, "set"]      = True

    # Update the category key so future imports use this mapping
    fin.category_key[substring.upper()] = category

    # Persist both
    fin.store_total_overview()

    # Re-run the table load logic to reflect changes
    ym  = tuple(months[idx])
    df  = get_transactions_df()
    df  = df.loc[
        (pd.to_datetime(df["Date"]).dt.year  == ym[0]) &
        (pd.to_datetime(df["Date"]).dt.month == ym[1])
    ]
    if account:
        df = df.loc[df["acct"] == account]
    if cat_filter:
        df = df.loc[df["Category"] == cat_filter]
    if search:
        df = df.loc[df["Description"].str.contains(search, case=False, na=False)]
    if not show_ignored:
        df = df.loc[df["ignore"] == False]

    return False, True, df.to_dict("records")