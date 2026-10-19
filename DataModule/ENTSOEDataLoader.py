"""
ENTSO-E Data Loader, storage and saving on Database
"""

import pandas as pd
import matplotlib.pyplot as plt
from entsoe import EntsoePandasClient
import geopandas as gpd
import copy
import numpy as np
from shapely.geometry import Point
from shapely import wkt
from datetime import datetime

class ENTSOEDataLoader:

    def __init__(self):
        pass

    def downloadENTSOEGenerationData(self, api_key, start_date, end_date, bidding_zones):

        aggregate_generation = []
        for i, bz in enumerate(bidding_zones):
            print("Processing Generation: " + bz + " - " + str(i + 1) + " out of " + str(
                len(bidding_zones.keys())) + "...")
            client = EntsoePandasClient(api_key=api_key)
            generation = client.query_generation(bidding_zones[bz]["code"], start=pd.Timestamp(start_date, tz="Europe/Brussels"), end=pd.Timestamp(end_date, tz="Europe/Brussels"))
            # Process columns
            new_columns = []
            for col in generation.columns:
                if isinstance(col, tuple):
                    new_columns.append(col)
                else:
                    if (col == "Date") | (col == "Bidding_zone") | (col == "Bidding_zone_code"):
                        new_columns.append((col, ""))
                    else:
                        new_columns.append((col, "Actual_aggregated"))
            generation.columns = pd.MultiIndex.from_tuples(new_columns)

            # Drop duplicated columns
            generation = generation.loc[:, ~generation.columns.duplicated()]
            # Merge the MultiIndex
            generation.columns = ["_".join([str(c) for c in col if c not in ("", None)]) for col in generation.columns]
            generation = generation.fillna(0)

            # Add zone codes to the data
            generation["zone"] = bz
            generation["short_code"] = bidding_zones[bz]["short_code"]
            generation["code"] = bidding_zones[bz]["code"]
            generation["map_code"] = bidding_zones[bz]["map_code"]

            # Append
            aggregate_generation.append(generation)

        aggregate_generation = pd.concat([df for df in aggregate_generation], axis=0)
        aggregate_generation = aggregate_generation.fillna(0)
        aggregate_generation = aggregate_generation.reset_index()
        aggregate_generation = aggregate_generation.rename(columns={"index": "Date"})

        # Merge with gpd geometry

        print("Merging with Multipolygon geometry...")

        url = "https://raw.githubusercontent.com/electricitymaps/electricitymaps-contrib/v1.238.0/web/geo/world.geojson"
        zones = gpd.read_file(url)
        aggregate_generation = pd.merge(left=aggregate_generation, right=zones[["zoneName", "geometry"]],left_on="map_code", right_on="zoneName", how="left")

        print("Number of bidding zones for generation: " + str(len(aggregate_generation["map_code"].unique())) + " (dict:" + str(len(bidding_zones.keys())) + ")")

        return aggregate_generation

    def downloadENTSOEPriceLoadData(self, api_key, start_date, end_date, bidding_zones):

        aggregate_load_data = []
        for i, bz in enumerate(bidding_zones):
            print("Processing Load, Load Forecast, DAM Prices: " + bz + " - " + str(i + 1) + " out of " + str(
                len(bidding_zones.keys())) + "...")
            client = EntsoePandasClient(api_key=api_key)

            # Launch query
            load = client.query_load(bidding_zones[bz]["code"], start=pd.Timestamp(start_date, tz="Europe/Brussels"),
                                     end=pd.Timestamp(end_date, tz="Europe/Brussels"))
            load_forecast = client.query_load_forecast(bidding_zones[bz]["code"], start=pd.Timestamp(start_date, tz="Europe/Brussels"), end=pd.Timestamp(end_date, tz="Europe/Brussels"))
            dam_prices = client.query_day_ahead_prices(bidding_zones[bz]["code"], start=pd.Timestamp(start_date, tz="Europe/Brussels"), end=pd.Timestamp(end_date, tz="Europe/Brussels"))
            # Concate to process everything together
            aggregate_data = pd.concat([load, load_forecast, dam_prices], axis=1)
            aggregate_data = aggregate_data.rename(columns={0: "DAM Price"})

            # Add other data on time zones
            aggregate_data["zone"] = bz
            aggregate_data["short_code"] = bidding_zones[bz]["short_code"]
            aggregate_data["code"] = bidding_zones[bz]["code"]
            aggregate_data["map_code"] = bidding_zones[bz]["map_code"]

            # Append
            aggregate_load_data.append(aggregate_data)
        aggregate_load_data = pd.concat([df for df in aggregate_load_data], axis=0).dropna()
        aggregate_load_data = aggregate_load_data.reset_index()
        aggregate_load_data = aggregate_load_data.rename(columns={"index": "Date"})

        print("Merging with Multipolygon geometry...")

        url = "https://raw.githubusercontent.com/electricitymaps/electricitymaps-contrib/v1.238.0/web/geo/world.geojson"
        zones = gpd.read_file(url)
        aggregate_load_data = pd.merge(left=aggregate_load_data, right=zones[["zoneName", "geometry"]],left_on="map_code", right_on="zoneName", how="left")

        print("Number of bidding zones for DAM Price, load, forecast: " + str(len(aggregate_load_data["map_code"].unique())) + " (dict:" + str(len(bidding_zones.keys())) + ")")

        return aggregate_load_data