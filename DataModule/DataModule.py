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

    def __init__(self):
        self.user = self.getConfig("db_user")
        self.port = self.getConfig("db_port")
        self.password = self.getConfig("db_password")
        self.name = self.getConfig("db_name")
        self.engine = self.create_engine()
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
    def createTable (self, pandas_dataframe, tableName, date_col):

        # Uniform dates
        pandas_dataframe[date_col] = pd.to_datetime(pandas_dataframe[date_col], utc=True).dt.tz_localize(None)

        # Create Table on SQL (postgres)
        pandas_dataframe.to_sql(name=tableName, con=self.engine, if_exists="replace", index=False)

        # Backup on OneDrive
        path = self.getConfig(key="path_OneDrive")
        # Save new table
        pandas_dataframe.to_csv(path + "\\" + tableName + ".csv", index=False)
        # Log
        rows_ex, start_date_ex, end_date_ex = len(pandas_dataframe.index), datetime.strftime(pandas_dataframe[date_col].min(), "%d/%m/%Y"), datetime.strftime(pandas_dataframe[date_col].max(), "%d/%m/%Y")

        print("DATA MODULE - BACKUP - File created. Rows: " + str(rows_ex) + ", first date: " + start_date_ex + ", last date: " + end_date_ex + ".")

    # Method to read data from table
    def loadDataFromTable (self, tableName):

        query = 'SELECT * FROM public."' + tableName + '"'
        dataframe = pd.read_sql(query, self.engine)

        return dataframe

    # Method to update Table
    def updateTable (self, pandas_dataframe, tableName, date_col):

        # Main update: the "append" method should work, and this is standard.
        # But in this case it does not work, because for every update new columns could be added (if a generation
        # source is new, or something actually changes), and new columns for SQL means errors in making the INSERT, even
        # though is standard and proven.
        # Therefore, the flow will be "load in pandas" - "update in pandas" - "save back on SQL"
        # It would be really much slower for dataset creation, not as much slower for adding a new day (96 observations)

        # Therefore, read existing
        existing_dataframe = self.loadDataFromTable(tableName=tableName)
        # Drop columns if necessary
        if "level_0" in existing_dataframe.columns:
            existing_dataframe = existing_dataframe.drop(columns=["level_0"])
        if "index" in existing_dataframe.columns:
            existing_dataframe = existing_dataframe.drop(columns=["index"])
        # Update through a concat on axis=0
        new_dataframe = pd.concat([existing_dataframe, pandas_dataframe], axis=0)
        # Uniform Dates into datetime format, and remove zones
        new_dataframe[date_col] = pd.to_datetime(new_dataframe[date_col], utc=True).dt.tz_localize(None)
        # Re-work dataframe (drop duplicates, fill the new columns with 0)
        new_dataframe = new_dataframe.drop_duplicates(keep="last").reset_index()
        new_dataframe = new_dataframe.fillna(0)
        # Save back on SQL (with create table, unfortunately)
        self.createTable(pandas_dataframe=new_dataframe, tableName=tableName, date_col=date_col)

        # Backup
        path = self.getConfig(key="path_OneDrive")
        # Read
        existing = pd.read_csv(path + "\\" + tableName + ".csv")
        # Update with a concat
        new_data = pd.concat([existing, pandas_dataframe], axis=0)
        # Drop Duplicates
        new_data = new_data.drop_duplicates().reset_index(drop=True)
        # Save again
        new_data.to_csv(path + "\\" + tableName + ".csv", index=False)

    # Method to create or update Table
    def createOrUpdate (self, tableName, date_col, pandas_dataframe):

        path = self.getConfig(key="path_OneDrive")
        if os.path.exists(path + "\\" + tableName + ".csv"):
            self.updateTable(tableName=tableName, date_col=date_col, pandas_dataframe=pandas_dataframe)
        else:
            self.createTable(tableName=tableName, date_col=date_col, pandas_dataframe=pandas_dataframe)

