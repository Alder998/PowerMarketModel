"""
ENTSO-E Data Loader, storage and saving on Database
"""

import pandas as pd
from entsoe import EntsoePandasClient
import geopandas as gpd
import numpy as np
from shapely.geometry import Point
import json
from pathlib import Path
from DataModule import DataModule as dm

class ENTSOEDataLoader:

    def __init__(self, start_date, end_date, bidding_zones):
        self.API_Key = self.getConfig("api_key_ENTSOE")
        self.start_date = start_date
        self.end_date = end_date
        self.bidding_zones = bidding_zones
        pass

    def getConfig (self, key):

        PROJECT_ROOT = Path(__file__).resolve().parents[1]
        CONFIG_PATH = PROJECT_ROOT / "DataModule" / "credentials" / "credentials.json"

        if not CONFIG_PATH.is_file():
            raise FileNotFoundError("configuration file has not been found.")

        with CONFIG_PATH.open("r", encoding="utf-8") as file:
            config = json.load(file)

        api_key = config[key]
        return api_key

    def downloadENTSOEGenerationData(self):

        aggregate_generation = []
        for i, bz in enumerate(self.bidding_zones):
            print("ENTSO-E DATA LOADER - Processing Generation: " + bz + " - " + str(i + 1) + " out of " + str(
                len(self.bidding_zones.keys())) + "...")
            client = EntsoePandasClient(api_key=self.API_Key)
            generation = client.query_generation(self.bidding_zones[bz]["code"], start=pd.Timestamp(self.start_date, tz="Europe/Brussels"), end=pd.Timestamp(self.end_date, tz="Europe/Brussels"))
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
            generation["short_code"] = self.bidding_zones[bz]["short_code"]
            generation["code"] = self.bidding_zones[bz]["code"]
            generation["map_code"] = self.bidding_zones[bz]["map_code"]

            # Append
            aggregate_generation.append(generation)

        aggregate_generation = pd.concat([df for df in aggregate_generation], axis=0)
        aggregate_generation = aggregate_generation.fillna(0)
        aggregate_generation = aggregate_generation.reset_index()
        aggregate_generation = aggregate_generation.rename(columns={"index": "Date"})

        # Merge with gpd geometry
        url = "https://raw.githubusercontent.com/electricitymaps/electricitymaps-contrib/v1.238.0/web/geo/world.geojson"
        zones = gpd.read_file(url)
        aggregate_generation = pd.merge(left=aggregate_generation, right=zones[["zoneName", "geometry"]],left_on="map_code", right_on="zoneName", how="left")

        return aggregate_generation

    def downloadENTSOEPriceLoadData(self):

        aggregate_load_data = []
        for i, bz in enumerate(self.bidding_zones):
            print("ENTSO-E DATA LOADER - Processing Load, Load Forecast, DAM Prices: " + bz + " - " + str(i + 1) + " out of " + str(
                len(self.bidding_zones.keys())) + "...")
            client = EntsoePandasClient(api_key=self.API_Key)

            # Launch query
            load = client.query_load(self.bidding_zones[bz]["code"], start=pd.Timestamp(self.start_date, tz="Europe/Brussels"),
                                     end=pd.Timestamp(self.end_date, tz="Europe/Brussels"))
            load_forecast = client.query_load_forecast(self.bidding_zones[bz]["code"], start=pd.Timestamp(self.start_date, tz="Europe/Brussels"), end=pd.Timestamp(self.end_date, tz="Europe/Brussels"))
            dam_prices = client.query_day_ahead_prices(self.bidding_zones[bz]["code"], start=pd.Timestamp(self.start_date, tz="Europe/Brussels"), end=pd.Timestamp(self.end_date, tz="Europe/Brussels"))
            # Concate to process everything together
            aggregate_data = pd.concat([load, load_forecast, dam_prices], axis=1)
            aggregate_data = aggregate_data.rename(columns={0: "DAM Price"})

            # Add other data on time zones
            aggregate_data["zone"] = bz
            aggregate_data["short_code"] = self.bidding_zones[bz]["short_code"]
            aggregate_data["code"] = self.bidding_zones[bz]["code"]
            aggregate_data["map_code"] = self.bidding_zones[bz]["map_code"]

            # Append
            aggregate_load_data.append(aggregate_data)
        aggregate_load_data = pd.concat([df for df in aggregate_load_data], axis=0).dropna()
        aggregate_load_data = aggregate_load_data.reset_index()
        aggregate_load_data = aggregate_load_data.rename(columns={"index": "Date"})

        url = "https://raw.githubusercontent.com/electricitymaps/electricitymaps-contrib/v1.238.0/web/geo/world.geojson"
        zones = gpd.read_file(url)
        aggregate_load_data = pd.merge(left=aggregate_load_data, right=zones[["zoneName", "geometry"]],left_on="map_code", right_on="zoneName", how="left")

        return aggregate_load_data

    def downloadENTSOEData(self, save_path=None, n_points=1):

        gen_data = self.downloadENTSOEGenerationData()
        gen_data = gen_data.drop(columns=["zoneName"])
        load_data = self.downloadENTSOEPriceLoadData()
        load_data = load_data.drop(columns=["zoneName"])

        entsoe_aggregate_data = pd.merge(left=gen_data, right=load_data,
                                         on=["Date", "zone", "short_code", "code", "map_code", "geometry"], how="inner")

        aggregate_entsoe_zones_final = pd.concat([entsoe_aggregate_data[["Date", "zone", "short_code", "code", "map_code", "geometry"]], entsoe_aggregate_data.drop(columns=["Date", "zone", "short_code", "code", "map_code", "geometry"])],axis=1)

        aggregate_entsoe_zones_final["Date"] = pd.to_datetime(aggregate_entsoe_zones_final["Date"], utc=True)
        aggregate_entsoe_zones_final["Date"] = aggregate_entsoe_zones_final["Date"].dt.tz_localize(None)

        aggregate_entsoe_zones_final["year"] = aggregate_entsoe_zones_final["Date"].dt.year
        aggregate_entsoe_zones_final["month"] = aggregate_entsoe_zones_final["Date"].dt.month
        aggregate_entsoe_zones_final["day"] = aggregate_entsoe_zones_final["Date"].dt.day
        aggregate_entsoe_zones_final["hour"] = aggregate_entsoe_zones_final["Date"].dt.hour
        aggregate_entsoe_zones_final["minute"] = aggregate_entsoe_zones_final["Date"].dt.minute
        aggregate_entsoe_zones_final["day_of_week"] = aggregate_entsoe_zones_final["Date"].dt.dayofweek

        # From MultiPolygon to latitude-longitude
        entsoe_data_unique_zones = aggregate_entsoe_zones_final.drop_duplicates(subset=["geometry"])
        zones_gdf = gpd.GeoDataFrame(entsoe_data_unique_zones, geometry="geometry", crs="EPSG:4326")

        def regular_grid_n_points(gdf, n_points=50):
            all_points = []

            for idx, row in gdf.iterrows():
                polygon = row.geometry
                zone = row["zone"]

                # area bounding box
                minx, miny, maxx, maxy = polygon.bounds
                area_bbox = (maxx - minx) * (maxy - miny)

                # step per avere circa n punti
                step = np.sqrt(area_bbox / n_points)

                xs = np.arange(minx, maxx, step)
                ys = np.arange(miny, maxy, step)

                for x in xs:
                    for y in ys:
                        p = Point(x, y)
                        if polygon.contains(p):
                            all_points.append([zone, y, x])

            return pd.DataFrame(all_points, columns=["zone", "lat", "lon"])

        gdf = regular_grid_n_points(gdf=zones_gdf, n_points=n_points)
        entsoe_data_enriched = pd.merge(left=aggregate_entsoe_zones_final, right=gdf, on=["zone"], how="inner")

        if save_path is not None:
            entsoe_data_enriched.drop(columns=["geometry"]).to_csv(save_path)

        print("ENTSO-E DATA LOADER - Data Loaded correctly for the selected dates.")

        return aggregate_entsoe_zones_final

    # Method to store
    def downloadAndSaveENTSOEData (self, table_name, date_col):

        # Load
        pandas_dataframe = self.downloadENTSOEData()
        # Save or Update
        dm.DataModule(pandas_dataframe=pandas_dataframe).createOrUpdate(tableName=table_name, date_col=date_col)