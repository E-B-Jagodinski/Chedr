## ------------------------------
#
#          CHEDR
# 
# Finance tracking app
# By: Eric Jagodinski
#
## ------------------------------
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import os, sys, glob, json, datetime, json, logging
from pathlib import Path
import pandas as pd
import numpy as np


logger = logging.getLogger(__name__)
logging.basicConfig(filename='example.log', encoding='utf-8', level=logging.DEBUG)
# logging.basicConfig(level=logging.INFO)

FIGSIZE = (20,6)


CONFIG_DIRECTORY = "chedr/config"
ACTIVITIES_DIRECTORY = "activity"
EXTRA_COMMA_ACCTS = [6268]

class Chedr:

    def __init__(self, config_filename):
        self.config_filename = config_filename

    def setup(self):
        """
        Sets up the application configuration
        """
        # Read Configs
        self.read_configs()

        # Read the total overview csv if exists
        self.read_total_csv()

        # Read the budget csv
        self.read_budget()

        # Add statements to overall total
        # self.add_statements()

        if self.total_csv_exists and not self.total_df.empty:

            # Set the categories
            self.set_categories_by_key()

            # Categorize the unknown transactions
            self.get_uncategorized_transactions()

            # Store the total overview
            self.store_total_overview()

            # Set the datetime column
            self.set_datetime()

            # Parse earliest date (yr,m)
            idx = self.parse_first_date()
            return idx
        return None

    def read_configs(self):
        """
        Read the config files
        """
        # Read overall config file
        logging.info(f"Reading config: {self.config_filename}")
        with open(self.config_filename, 'r') as f:
            self.config = json.load(f)

        # Read the config values
        self.total_csv_filename = os.path.join(ACTIVITIES_DIRECTORY, self.config["total_csv_filename"]) 
        self.total_csv_meta_filename = os.path.join(ACTIVITIES_DIRECTORY, self.config["total_csv_meta_filename"])
        self.category_key_filename = os.path.join(CONFIG_DIRECTORY, self.config["category_key_filename"])
        self.budget_filename = os.path.join(CONFIG_DIRECTORY, self.config["budget_filename"])

        # Read the category key
        logging.info(f"Reading category keys: {self.category_key_filename}")
        with open(self.category_key_filename, 'r') as f:
            category_key = json.load(f)
        self.category_key = {k:v for k,v in category_key.items() if "__" not in k}

    def read_total_csv(self):
        self.total_csv_exists = os.path.exists(self.total_csv_filename)
        if self.total_csv_exists:
            self.total_df = pd.read_csv(self.total_csv_filename)
            # Store as DataFrame, not a list
            self.total_csv_meta = pd.read_csv(self.total_csv_meta_filename)
        else:
            # Always initialize as empty DataFrame so add_statements can rely on it
            self.total_csv_meta = pd.DataFrame({"statements": []})

    @staticmethod
    def monthly_cost(row: dict) -> float:
        often = row["How often"]
        amount = row["Amount"]
        monthly = None
        if often == "Monthly":
            monthly = amount
        elif often == "Yearly":
            monthly = amount / 12
        elif often == "Weekly":
            monthly = amount * 4
        elif often == "Bi-Yearly":
            monthly = amount / 6
        elif often == "Bi-Monthly":
            monthly = amount * 2
        elif often == "Bi-Weekly":
            monthly = amount * 2.166667
        else:
            raise ValueError(f"Unknown type: {often}")
        return round(monthly, 2)

    def read_budget(self):
        """Reads the budget csv"""

        # Read the budget csv
        self.budget_df = pd.read_csv(self.budget_filename)

        # Calculate the monthly amount
        self.budget_df["monthly_amount"] = self.budget_df.apply(lambda r: Chedr.monthly_cost(r), axis = 1)

    def read_statement(self, statement: str) -> tuple[pd.DataFrame, list[str]]:
        """Read a statement and prepare it to be added"""
        # Get account type and name
        acct_n = [k for k in self.config['accounts'] if k in statement]
        if acct_n == []:
            raise ValueError(f"Unknown account id statement {statement}")
        else:
            acct_n = acct_n[0]
        acct_type = self.config['accounts'][acct_n]
        logging.info(f"Adding statement for {acct_type}: {os.path.basename(statement)}")

        # Read the raw header first to get the true column count
        with open(statement, 'r') as f:
            header = f.readline().strip().split(',')
            data_sample = f.readline().strip().split(',')

        # If data rows have more columns than header, pandas will misread the index
        if len(data_sample) > len(header):
            df = pd.read_csv(statement, index_col=False, names=header + ['_extra'], skiprows=1)
            df = df.drop(columns=['_extra'], errors='ignore')
        else:
            df = pd.read_csv(statement, index_col=False)

        # Write new columns
        df['acct'] = acct_n
        df['acct_type'] = acct_type
        cols = list(df.columns)

        # Convert post date column name to be the same
        if ("Post Date" in cols) and ("Posting Date" not in cols):
            cols[cols.index("Post Date")] = "Posting Date"
            df.columns = cols

        # Parse date with format='mixed' to handle inconsistent formats across banks
        df['Date'] = pd.to_datetime(df['Posting Date'], format='mixed', dayfirst=False)
        cols = list(df.columns)

        # Add the Details column (debit/credit) if not included
        if "Details" not in df.columns:
            df["Details"] = np.where(df["Amount"] > 0, "CREDIT", "DEBIT")

        logging.debug(f"{acct_n}: {df.columns}")
        return (df, cols)
    
    def combine_columns(self, all_df: pd.DataFrame, total_cols: list[str]) -> pd.DataFrame:
        """Combines columns to ensure that there aren't errors"""
        # Prepare new statement dataframes to concat
        for n, df in enumerate(all_df):
            for column_name in total_cols:
                if column_name not in list(df.columns):
                    df[column_name] = None
            df = df[total_cols]
            all_df[n] = df
        return all_df
    
    def remove_ignored_statements_from_list(self, statements_list: list[str]) -> list[str]:
        return_list = []
        ignores = [self.config["total_csv_filename"], self.config["total_csv_meta_filename"]]
        for s in statements_list:
            if (not any([o in s for o in ignores]) and
                not Path(s).is_dir() and
                not "saving" in s.lower()):
                return_list.append(s)
        return return_list

    def add_statements(self, files: list[str]) -> list[str]:
        """Adds new statements to the total overview, returns list of new filenames"""
        
        if self.total_csv_exists:
            total_cols = list(self.total_df.columns)
            all_df     = [self.total_df]
            meta_list  = self.total_csv_meta["statements"].tolist()
        else:
            meta_list  = []
            total_cols = []
            all_df     = []

        # statements_directory_name = os.path.join(ACTIVITIES_DIRECTORY, '*')
        statements_list = files
        statements_list = self.remove_ignored_statements_from_list(statements_list)

        newly_added = []
        for statement in statements_list:
            basename = os.path.basename(statement)
            if basename not in meta_list:
                df, cols = self.read_statement(statement)

                if "set" not in cols:
                    df["set"] = False
                    cols.append("set")
                if "ignore" not in cols:
                    df["ignore"] = False
                    cols.append("ignore")

                all_df.append(df)
                [total_cols.append(c) for c in cols if c not in total_cols]
                meta_list.append(basename)
                newly_added.append(basename)

        if not newly_added:
            logging.info("Did not add any new statements")

        all_df = self.combine_columns(all_df, total_cols)
        self.total_df = pd.concat(
            all_df, axis=0, ignore_index=True
        ).drop_duplicates().reset_index(drop=True)
        self.total_csv_meta = pd.DataFrame({"statements": meta_list})

        return newly_added

    def get_new_statement_files(self) -> list[str]:
        """
        Returns a list of files in the imports directory that are not
        yet in the manifest. Does not read or process any files.
        """
        # Check if total csv exists
        self.total_csv_exists = os.path.exists(self.total_csv_filename)
        if self.total_csv_exists:
            self.total_df = pd.read_csv(self.total_csv_filename)
            self.total_csv_meta = pd.read_csv(self.total_csv_meta_filename)
        else:
            self.total_df       = pd.DataFrame()   # always exists after this point
            self.total_csv_meta = pd.DataFrame({"statements": []})

        statements_directory_name = os.path.join(ACTIVITIES_DIRECTORY, '*')
        statements_list = glob.glob(statements_directory_name)
        statements_list = self.remove_ignored_statements_from_list(statements_list)

        if self.total_csv_exists:
            meta_list = self.total_csv_meta["statements"].tolist()
        else:
            meta_list = []

        return [s for s in statements_list
                if os.path.basename(s) not in meta_list]

    def set_category(self, row: dict) -> dict:
        """If the Category is not set, match the description substring to a category"""
        for k, v in self.category_key.items():
            if (k.lower() in row["Description"].lower()) and (row["set"] == False):
                row["Category"] = v
                row["set"] = True
                if k.lower() == "ignore".lower():
                    row["ignore"] = True
        return row

    def set_categories_by_key(self):
        """Set the categories of the transactions"""
        self.total_df = self.total_df.apply(self.set_category, axis=1)
    
    def get_uncategorized_transactions(self) -> dict:
        """Returns rows that have no category set — called on startup"""
        df_nan = self.total_df.loc[
            self.total_df['Category'].apply(lambda x: not isinstance(x, str))
        ]
        return df_nan.to_dict('records')  # Dash stores data as dicts

    def resolve_category(
            self,
            description: str,
            category: str,
            key_substring:str=None,
            ignore:bool=False,
        ):
        """Resolves a single uncategorized transaction"""
        # Save the key
        if key_substring:
            self.category_key[key_substring.strip()] = category

        # Apply to all matching rows that aren't yet set
        mask = (
            (self.total_df["Description"] == description) &
            (self.total_df["set"] == False)
        )
        self.total_df.loc[mask, "Category"] = category
        self.total_df.loc[mask, "set"]      = True
        # Persist immediately
        self.store_total_overview()

    def store_total_overview(self):
        """Save the total overview and overview meta"""
        self.total_df.loc[self.total_df["Category"] == "IGNORE", "ignore"] = True
        self.total_df.to_csv(self.total_csv_filename, index=False)
        self.total_csv_meta.to_csv(self.total_csv_meta_filename, index=False)
        with open(self.category_key_filename, 'w') as json_file:
            json.dump(self.category_key, json_file, indent=4)

    def set_datetime(self):
        """Convert date to datetime"""
        logging.debug(self.total_df["Date"].head())
        self.total_df['Date'] = pd.to_datetime(self.total_df['Date'], format='mixed')

    def parse_first_date(self):
        """Parse the first date (yr,mo) of the spreadsheet"""
        df = self.total_df['Amount'].groupby([self.total_df["Date"].dt.year, self.total_df["Date"].dt.month, self.total_df['Category']]).sum().unstack()
        return df.first_valid_index()

    def saving_net_changes(self):
        """Plot the net savings account by month"""
        df = self.total_df.loc[self.total_df["ignore"]==False]
        df = df.loc[df['acct_type']=='savings']
        transactions = df['Amount'].groupby([df["Date"].dt.year, df["Date"].dt.month]).sum()
        y = transactions.to_list()
        x = transactions.index
        x2 = [datetime.datetime.strptime(f"{a}/{str(b).zfill(2)}", '%Y/%m') for (a,b) in x]

        fig = plt.figure(figsize=FIGSIZE)
        ax = fig.add_subplot(111)

        ax.plot(df['Date'],df['Balance'], 'k')
        ax.set_ylim([0, 50_000])
        ax2 = ax.twinx()
        colors = ['g' if e >= 0 else 'r' for e in y]
        ax2.bar(x2, y, width=10, alpha=0.5, color=colors, edgecolor='b', linestyle='dashed')
        ax2.hlines(0,df['Date'].iloc[-1],df['Date'].iloc[0], colors='b', linestyles="dashed")
        ax2.tick_params(axis='y', colors='b')
        ax2.yaxis.label.set_color('b')
        ax.set_title("Savings Acct")
        ax.set_ylabel("Savings Account Balance ($)")
        ax2.set_ylabel("Monthly Net Change ($)")
        plt.show()

    @staticmethod
    def colors(df):
        n_col = len(df.columns)
        return plt.cm.jet(np.linspace(0, 1, n_col))

    def calculate_total_expenses(self, since_date=None):
        df = self.total_df.loc[self.total_df["ignore"]==False].copy()
        df["Date"] = pd.to_datetime(df["Date"], format="mixed")  # always coerce
        df = df.loc[(df['acct_type']!='savings') & (df['Amount'] < 0) & (df['Category'] !='Payment')]
        if since_date:
            df = df.loc[df['Date'] >= since_date]
        df.loc[:, "Amount"] = df.loc[:, "Amount"].apply(lambda x: x*-1)
        df2 = df['Amount'].groupby([df["Date"].dt.year, df["Date"].dt.month, df['Category']]).sum().unstack()
        return df2

    def total_expenses(self, ax=None, plot=True, since=None):
        """Plot the total expenses each month by category"""

        df2 = self.calculate_total_expenses()

        if since:
            df2 = df2.loc[since:]        
        if plot:
            ax = df2.plot.bar(stacked=True, figsize=FIGSIZE, color=Chedr.colors(df2), linewidth=3)
            plt.show()
        if ax is not None:
            df2.plot.bar(stacked=True, figsize=FIGSIZE, ax=ax, color=Chedr.colors(df2))
        return df2

    def calculate_total_credit(self):
        df = self.total_df.loc[self.total_df["ignore"]==False].copy()
        df["Date"] = pd.to_datetime(df["Date"], format="mixed")  # always coerce
        df_checking = df[df["acct_type"].str.contains("checking", case=False)]
        df_pos = df_checking.loc[(df_checking['Amount'] >= 0) & (df_checking['Category'] != 'Payment')]
        df_pos2 = df_pos['Amount'].groupby([df_pos["Date"].dt.year, df_pos["Date"].dt.month, df_pos['Category']]).sum().unstack()
        return df_pos2

    def total_credit(self, ax=None, plot=True, since=None):
        """Plot the total account credit in Checking each month"""
        df_pos2 = self.calculate_total_credit()

        if since:
            df_pos2 = df_pos2.loc[since:]
        if plot:
            ax = df_pos2.plot.bar(stacked=True, figsize=FIGSIZE, color=Chedr.colors(df_pos2))
            plt.show()
            return True
        if ax is not None:
            df_pos2.plot.bar(stacked=True, figsize=FIGSIZE, ax=ax, color=Chedr.colors(df_pos2))
        return df_pos2

    def total_info(self, ax, plot=True, since=-12):
        
        width = 0.3
        # fig = Figure(figsize = (5, 5), 
        #          dpi = 100)
        # ax = fig.add_subplot(111)
        ax2 = ax.twinx()
        # plt.figure(figsize=FIGSIZE)
        df_exp = self.total_expenses(plot=False)
        df_cre = self.total_credit(plot=False)

        if since:
            df_exp = df_exp.loc[since:]
            df_cre = df_cre.loc[since:]

        df_exp.plot.bar(stacked=True,
                        figsize=FIGSIZE,
                        color=Chedr.colors(df_exp),
                        ax=ax2,
                        width=width,
                        align="edge"
        )
        df_cre.plot.bar(stacked=True,
                        figsize=FIGSIZE,
                        color=Chedr.colors(df_cre),
                        ax=ax,
                        width=width
        )
 
        ax2.legend(loc="lower left")
        if plot == True:
            plt.show()

    def calculate_budget_monthly(self):
        """Calculate the monthly budget"""
        cat_budget = self.budget_df["monthly_amount"].groupby(self.budget_df["Category"]).sum()
        cat_budget = cat_budget.to_frame()
        cat_budget.reset_index(inplace=True)
        return cat_budget

    def plot_budget_info(self, ax, plot=True, since=None):
        """Plot last month's expenses against the budget"""

        # Calculate the monthly budget
        cat_budget = self.calculate_budget_monthly()

        # Get last months expenses
        df_exp = self.calculate_total_expenses()
        i = df_exp.index.get_level_values(0)[-1]
        j = df_exp.index.get_level_values(1)[-2]
        df_exp = df_exp.loc[(i, j)]
        df_exp = df_exp.to_frame()
        df_exp.reset_index(inplace=True)
        df_exp.columns = ["Category", "monthly_amount"]

        # Merge the budget and expenses
        merged = pd.merge(cat_budget, df_exp, on="Category", how="outer")
        merged.fillna(0, inplace=True)
        merged.columns = ["Category", "Budgeted", "Spent"]

        # Plot the merged dataframe
        if plot:
            ax = merged.plot(x="Category", y=["Budgeted", "Spent"], kind="bar",
                             figsize=FIGSIZE, color=Chedr.colors(cat_budget))
            plt.show()
            return True
        if ax is not None:
            merged.plot(x="Category", y=["Budgeted", "Spent"], kind="bar", ax=ax,
                    figsize=FIGSIZE, color=Chedr.colors(cat_budget))
        return merged


if __name__ == "__main__":
    # FOR DEBUGGING
    fin = Chedr(os.path.join(CONFIG_DIRECTORY, "config.json"))
    _ = fin.setup()
    logger.info("Made it passed setup")
    fig = plt.figure(figsize = (5, 5), 
                dpi = 100)
    ax = fig.add_subplot(111)
    logger.info("Made figure")
    fin.total_credit(since=(2023, 10))
    fig.show()
