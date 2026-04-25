import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
from core.state import fin

dash.register_page(__name__, path="/import", name="Import")

# ---------------------------------------------------------- helpers ---

def get_all_categories() -> list[str]:
    """
    Merges categories from existing transactions and from the budget,
    so budget categories with no transactions yet are still available.
    """
    txn_cats    = set(fin.total_df["Category"].dropna().unique().tolist())
    budget_cats = set(fin.budget_df["Category"].dropna().unique().tolist())
    return sorted(txn_cats | budget_cats)


# ----------------------------------------------------------- layout ---

def layout(**kwargs):
    new_files   = fin.get_new_statement_files()
    has_new     = len(new_files) > 0

    # total_df doesn't exist on first run — skip pending check
    if fin.total_csv_exists:
        pending     = fin.get_uncategorized_transactions()
        has_pending = len(pending) > 0
    else:
        pending     = []
        has_pending = False

    return dbc.Container([

        # --- Page header ---
        dbc.Row(dbc.Col(html.H4("Import", className="mb-3"))),

        # --- Stepper ---
        dbc.Row(dbc.Col([

            # Step indicators
            dbc.Row([
                dbc.Col(step_indicator("1", "Scan",       "import-step-1"), width="auto"),
                dbc.Col(step_divider(),                                      width=True),
                dbc.Col(step_indicator("2", "Categorize", "import-step-2"), width="auto"),
                dbc.Col(step_divider(),                                      width=True),
                dbc.Col(step_indicator("3", "Done",       "import-step-3"), width="auto"),
            ], align="center", className="mb-4"),

            # Step panels — start on step 2 if there are pending transactions
            # but no new files, otherwise start on step 1
            html.Div(
                id="import-step-panel",
                children=panel_scan_ready(new_files, has_new)
            ),

        ])),

        # --- Stores ---
        dcc.Store(id="import-scan-results"),
        dcc.Store(
            id="import-pending",
            data=pending if has_pending else []
        ),
        dcc.Store(id="import-pending-idx", data=0),
        dcc.Store(
            id="import-step",
            # Jump to step 2 if there are already pending transactions
            data=2 if (has_pending and not has_new) else 1
        ),

    ], fluid=True)


# ------------------------------------------------- stepper widgets ---

def step_indicator(number, label, id):
    return html.Div([
        html.Div(
            number,
            id=id,
            style={
                "width": "32px", "height": "32px",
                "borderRadius": "50%",
                "display": "flex", "alignItems": "center",
                "justifyContent": "center",
                "fontWeight": "500", "fontSize": "0.85rem",
                "backgroundColor": "#dee2e6",
                "color": "#6c757d",
                "margin": "0 auto 4px",
                "transition": "all 0.2s"
            }
        ),
        html.P(label, style={"fontSize": "0.75rem", "color": "#6c757d",
                              "margin": 0, "textAlign": "center"})
    ])


def step_divider():
    return html.Hr(style={
        "borderTop": "2px solid #dee2e6",
        "margin": "0 0 20px 0"
    })


# ---------------------------------------------------- step panels ---

def panel_scan_ready(new_files, has_new):
    """
    Step 1 panel — shown on page load.
    Button is enabled if new files exist, greyed out if not.
    Lists any new files found so the user knows what will be imported.
    """
    if has_new:
        file_list = html.Div([
            html.P(
                f"{len(new_files)} new file{'s' if len(new_files) != 1 else ''} "
                f"ready to import:",
                className="mb-2",
                style={"fontSize": "0.85rem"}
            ),
            html.Ul([
                html.Li(f, style={"fontSize": "0.82rem", "color": "#6c757d"})
                for f in [__import__('os').path.basename(f) for f in new_files]
            ], className="mb-0")
        ])
        button_label = f"Import {len(new_files)} file{'s' if len(new_files) != 1 else ''}"
    else:
        file_list    = html.P(
            "No new files found in the imports directory.",
            className="text-muted mb-0",
            style={"fontSize": "0.85rem"}
        )
        button_label = "No new files"

    return dbc.Card(dbc.CardBody([
        html.H6("Scan", className="mb-3"),
        file_list,
        html.Hr(),
        dbc.Button(
            button_label,
            id="import-run-btn",
            color="primary",
            size="sm",
            disabled=not has_new,
            className="mt-2"
        ),
        # If there are already pending transactions, show a hint
        html.P(
            "There are uncategorized transactions from a previous import. "
            "Click 'Next →' below to continue categorizing, or import new "
            "files first.",
            className="text-warning mt-3 mb-0",
            style={"fontSize": "0.82rem",
                   "display": "block" if not has_new else "none"}
        ),
        # Show a 'Go to categorize' button if pending exist and no new files
        dbc.Button(
            "Continue categorizing →",
            id="import-skip-to-categorize",
            color="secondary",
            outline=True,
            size="sm",
            className="mt-2",
            style={"display": "block" if (not has_new) else "none"}
        ),
    ]), className="mt-3")


def panel_scanning():
    return dbc.Card(dbc.CardBody([
        dbc.Spinner(color="primary", size="sm"),
        html.Span(" Importing files...",
                  className="ms-2 text-muted",
                  style={"fontSize": "0.9rem"})
    ]), className="mt-3")


def panel_scan_summary(results):
    new_files = results.get("new_files",     [])
    n_txns    = results.get("n_transactions", 0)
    n_pending = results.get("n_pending",      0)

    if not new_files:
        status_content = html.P(
            "No new files were imported.",
            className="text-muted mb-0"
        )
    else:
        status_content = html.Div([
            html.P(
                f"{len(new_files)} file{'s' if len(new_files) != 1 else ''} imported, "
                f"{n_txns} transaction{'s' if n_txns != 1 else ''} added.",
                className="mb-2"
            ),
            html.Ul([
                html.Li(f, style={"fontSize": "0.85rem", "color": "#6c757d"})
                for f in new_files
            ], className="mb-0")
        ])

    next_label = (
        f"Categorize {n_pending} transaction{'s' if n_pending != 1 else ''} →"
        if n_pending > 0 else "View Summary →"
    )

    return dbc.Card(dbc.CardBody([
        html.H6("Import complete", className="mb-3"),
        status_content,
        html.Hr(),
        dbc.Button(
            next_label,
            id="import-scan-next",
            color="primary",
            size="sm",
            href="/" if n_pending == 0 else None,
            className="mt-2"
        )
    ]), className="mt-3")


def panel_categorize(pending, idx):
    """Shows one uncategorized transaction at a time"""
    total      = len(pending)
    row        = pending[idx]
    categories = get_all_categories()

    raw_desc   = row.get("Description", "")
    clean_desc = raw_desc.split("    ")[0].strip()

    return dbc.Card(dbc.CardBody([

        # Progress
        dbc.Row([
            dbc.Col(
                html.P(f"Transaction {idx + 1} of {total}",
                       className="text-muted mb-1",
                       style={"fontSize": "0.8rem"})
            ),
            dbc.Col(
                dbc.Progress(
                    value=int((idx / total) * 100),
                    style={"height": "6px"},
                    className="mt-2"
                )
            )
        ], className="mb-3"),

        # Transaction details
        dbc.Row([
            dbc.Col([
                html.P("Date", className="text-muted mb-0",
                       style={"fontSize": "0.75rem"}),
                html.P(str(row.get("Date", ""))[:10],
                       style={"fontWeight": "500"})
            ], width=3),
            dbc.Col([
                html.P("Amount", className="text-muted mb-0",
                       style={"fontSize": "0.75rem"}),
                html.P(f"${abs(float(row.get('Amount', 0))):,.2f}",
                       style={"fontWeight": "500"})
            ], width=3),
            dbc.Col([
                html.P("Account", className="text-muted mb-0",
                       style={"fontSize": "0.75rem"}),
                html.P(str(row.get("acct", "")),
                       style={"fontWeight": "500"})
            ], width=3),
        ], className="mb-3"),

        # Raw description (read-only)
        html.P("Raw description", className="text-muted mb-1",
               style={"fontSize": "0.75rem"}),
        dbc.Input(
            value=raw_desc,
            disabled=True,
            size="sm",
            className="mb-3",
            style={"fontSize": "0.82rem", "color": "#6c757d"}
        ),

        # Editable substring key
        html.P("Save as key (edit to shorten)",
               className="text-muted mb-1",
               style={"fontSize": "0.75rem"}),
        dbc.Input(
            id="import-key-input",
            value=clean_desc,
            size="sm",
            className="mb-3",
            style={"fontSize": "0.82rem"}
        ),

        # Category picker — includes budget categories
        html.P("Category", className="text-muted mb-1",
               style={"fontSize": "0.75rem"}),
        dcc.Dropdown(
            id="import-category-pick",
            options=[{"label": c, "value": c} for c in categories],
            placeholder="Select a category...",
            clearable=False,
            className="mb-3"
        ),

        # Action buttons
        dbc.Row([
            dbc.Col(
                dbc.Button("Confirm →", id="import-confirm",
                           color="primary", size="sm", disabled=True),
                width="auto"
            ),
            dbc.Col(
                dbc.Button("Skip", id="import-skip",
                           color="secondary", outline=True, size="sm"),
                width="auto"
            ),
        ], className="g-2"),

        html.P(id="import-cat-error",
               className="text-danger mt-2 mb-0",
               style={"fontSize": "0.8rem"})

    ]), className="mt-3")


def panel_done():
    return dbc.Card(dbc.CardBody([
        html.Div([
            html.Div(
                "✓",
                style={
                    "width": "48px", "height": "48px",
                    "borderRadius": "50%",
                    "backgroundColor": "#2ecc71",
                    "color": "white",
                    "display": "flex", "alignItems": "center",
                    "justifyContent": "center",
                    "fontSize": "1.4rem",
                    "margin": "0 auto 1rem"
                }
            ),
            html.H6("All done!", className="text-center mb-1"),
            html.P("All transactions are categorized.",
                   className="text-center text-muted mb-3",
                   style={"fontSize": "0.85rem"}),
            dbc.Row(
                dbc.Col(
                    dbc.Button("Go to Summary →", href="/",
                               color="primary", size="sm"),
                    width="auto", className="mx-auto"
                ), justify="center"
            )
        ])
    ]), className="mt-3")


# --------------------------------------------------------- callbacks ---

@callback(
    Output("import-scan-results", "data"),
    Output("import-pending",      "data",     allow_duplicate=True),
    Output("import-step",         "data",     allow_duplicate=True),
    Output("import-step-panel",   "children", allow_duplicate=True),
    Input("import-run-btn",       "n_clicks"),
    State("import-pending",       "data"),
    prevent_initial_call=True
)
def run_import(n_clicks, existing_pending):
    """
    Triggered by the Import button click.
    Runs ingestion, re-categorizes, then merges any newly uncategorized
    transactions with any that were already pending from before.
    """
    # Run ingestion — returns only the newly added filenames
    newly_added  = fin.add_statements()
    fin.set_categories_by_key()
    fin.set_datetime()
    fin.store_total_overview()

    n_txns = len(newly_added)

    # Collect all uncategorized rows after ingestion
    pending_df = fin.total_df.loc[
        fin.total_df["Category"].apply(lambda x: not isinstance(x, str))
    ]
    pending = pending_df[["Date", "Description", "Amount", "acct"]].copy()
    pending["Date"] = pending["Date"].astype(str)
    pending_records = pending.to_dict("records")
    n_pending = len(pending_records)

    results = {
        "new_files":      newly_added,
        "n_transactions": n_txns,
        "n_pending":      n_pending,
    }

    return (
        results,
        pending_records,
        1,
        panel_scan_summary(results)
    )


@callback(
    Output("import-step-panel",   "children", allow_duplicate=True),
    Output("import-step",         "data",     allow_duplicate=True),
    Input("import-scan-next",          "n_clicks"),
    State("import-pending",       "data"),
    State("import-pending-idx",   "data"),
    prevent_initial_call=True
)
def advance_to_categorize(n_clicks, pending, idx):
    if not pending:
        return panel_done(), 3
    return panel_categorize(pending, idx), 2


@callback(
    Output("import-step-panel",        "children", allow_duplicate=True),
    Output("import-step",              "data",     allow_duplicate=True),
    Input("import-skip-to-categorize", "n_clicks"),
    State("import-pending",            "data"),
    State("import-pending-idx",        "data"),
    prevent_initial_call=True
)
def skip_to_categorize(n_clicks, pending, idx):
    """
    Shown when there are pending transactions from a previous import
    but no new files — jumps straight to categorize step.
    """
    if not pending:
        return panel_done(), 3
    return panel_categorize(pending, idx), 2


@callback(
    Output("import-confirm", "disabled"),
    Input("import-category-pick", "value"),
)
def toggle_confirm_button(category):
    return category is None


@callback(
    Output("import-step-panel",   "children", allow_duplicate=True),
    Output("import-pending-idx",  "data",     allow_duplicate=True),
    Output("import-step",         "data",     allow_duplicate=True),
    Input("import-confirm",       "n_clicks"),
    Input("import-skip",          "n_clicks"),
    State("import-pending",       "data"),
    State("import-pending-idx",   "data"),
    State("import-category-pick", "value"),
    State("import-key-input",     "value"),
    prevent_initial_call=True
)
def handle_categorize(confirm_clicks, skip_clicks, pending, idx, category, key):
    triggered  = dash.callback_context.triggered[0]["prop_id"]
    is_confirm = "confirm" in triggered

    if is_confirm and category:
        fin.resolve_category(
            description=pending[idx]["Description"],
            category=category,
            key_substring=key
        )

    next_idx = idx + 1
    if next_idx >= len(pending):
        fin.store_total_overview()
        return panel_done(), next_idx, 3

    return panel_categorize(pending, next_idx), next_idx, 2


@callback(
    Output("import-step-1", "style"),
    Output("import-step-2", "style"),
    Output("import-step-3", "style"),
    Input("import-step",    "data"),
)
def update_step_indicators(step):
    active = {
        "width": "32px", "height": "32px", "borderRadius": "50%",
        "display": "flex", "alignItems": "center", "justifyContent": "center",
        "fontWeight": "500", "fontSize": "0.85rem",
        "backgroundColor": "#3498db", "color": "white",
        "margin": "0 auto 4px", "transition": "all 0.2s"
    }
    done     = {**active, "backgroundColor": "#2ecc71"}
    inactive = {
        "width": "32px", "height": "32px", "borderRadius": "50%",
        "display": "flex", "alignItems": "center", "justifyContent": "center",
        "fontWeight": "500", "fontSize": "0.85rem",
        "backgroundColor": "#dee2e6", "color": "#6c757d",
        "margin": "0 auto 4px", "transition": "all 0.2s"
    }
    styles = {
        1: [active, inactive, inactive],
        2: [done,   active,   inactive],
        3: [done,   done,     done    ],
    }
    return styles.get(step, styles[1])