"""
Class to manage the boring CRUD Data (for serious stuff: Database)
"""

import pandas as pd
from sqlalchemy import create_engine, text
from pathlib import Path
from datetime import datetime
import json
import os

class DataModule:

    def __init__(self, pandas_dataframe):
        self.user = self.getConfig("db_user")
        self.port = self.getConfig("db_port")
        self.password = self.getConfig("db_password")
        self.name = self.getConfig("db_name")
        self.engine = self.create_engine()
        self.pandas_dataframe = pandas_dataframe
        pass

    # Get Config Method
    def getConfig (self, key):

        PROJECT_ROOT = Path(__file__).resolve().parents[1]
        CONFIG_PATH = PROJECT_ROOT / "DataModule" / "credentials" / "credentials.json"

        if not CONFIG_PATH.is_file():
            raise FileNotFoundError("configuration file has not been found.")

        with CONFIG_PATH.open("r", encoding="utf-8") as file:
            config = json.load(file)

        api_key = config[key]
        return api_key

    # Method to create engine fot the whole class
    def create_engine (self):
        engine = create_engine("postgresql://" + self.user + ":" + self.password + "@localhost:" + self.port + "/" + self.name)
        return engine

    # Method to execute query
    def executeQueryOnDatabase (self, query):

        with self.engine.begin() as conn:
            conn.execute(text(query))

    # Method to create Table
    def createTable (self, tableName, date_col):

        # Create Table on SQL (postgres)
        self.pandas_dataframe.to_sql(name=tableName, con=self.engine, if_exists="append")

        # Backup on OneDrive
        path = self.getConfig(key="db_path")
        # Save new table
        self.pandas_dataframe.to_csv(path + "\\" + tableName + ".csv", index=False)
        # Log
        rows_ex, start_date_ex, end_date_ex = len(self.pandas_dataframe.index), self.pandas_dataframe[date_col].min(), self.pandas_dataframe[date_col].max()
        print("DATA MODULE - BACKUP - File created. Rows: " + str(rows_ex) + ", first date: " + datetime.strftime(start_date_ex, "%Y-%m-%d") + ", last date: "+ datetime.strftime(end_date_ex, "%Y-%m-%d"))

    # Method to update Table
    def updateTable (self, tableName, date_col):

        # Main update (working because if_exists="append")
        self.pandas_dataframe.to_sql(name=tableName, con=self.engine, if_exists="append")

        # Backup
        path = self.getConfig(key="db_path")
        # Read
        existing = pd.read_csv(path + "\\" + tableName + ".csv")
        rows_ex, start_date_ex, end_date_ex = len(existing.index), existing[date_col].min(), existing[date_col].max()
        # Update with a concat
        new_data = pd.concat([existing, self.pandas_dataframe], axis=0)
        # Drop Duplicates
        new_data = new_data.drop_duplicates().reset_index(drop=True)
        rows_n, start_date_n, end_date_n = len(new_data.index), new_data[date_col].min(), new_data[date_col].max()
        # Save again
        new_data.to_csv(path + "\\" + tableName + ".csv", index=False)
        # Log
        print("DATA MODULE - BACKUP - Rows before updating: " + str(rows_ex) + ", first date: " + datetime.strftime(start_date_ex, "%Y-%m-%d") + ", last date: "+ datetime.strftime(end_date_ex, "%Y-%m-%d"))
        print("DATA MODULE - BACKUP - Rows after updating: " + str(rows_n) + ", first date: " +  datetime.strftime(start_date_n, "%Y-%m-%d") + ", last date: "+ datetime.strftime(end_date_n, "%Y-%m-%d"))

    # Method to create or update Table
    def createOrUpdate (self, tableName, date_col):

        path = self.getConfig(key="db_path")
        if os.path.exists(path + "\\" + tableName + ".csv"):
            self.updateTable(tableName=tableName, date_col=date_col)
        else:
            self.createTable(tableName=tableName, date_col=date_col)

