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

    def downloadENTSOEData(self, api_key, start_date, end_date, bidding_zones, save_path=None, n_points=2):

        gen_data = self.downloadENTSOEGenerationData(api_key=api_key, start_date=start_date, end_date=end_date,bidding_zones=bidding_zones)
        gen_data = gen_data.drop(columns=["zoneName"])
        load_data = self.downloadENTSOEPriceLoadData(api_key=api_key, start_date=start_date, end_date=end_date, bidding_zones=bidding_zones)
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

        print("AGGREGATE DATA - Number of bidding zones: " + str(len(aggregate_entsoe_zones_final["map_code"].unique())) + " (dict:" + str(len(bidding_zones.keys())) + ")")

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

        print("AGGREGATE DATA - Number of bidding zones: " + str(
            len(entsoe_data_enriched["map_code"].unique())) + " (dict:" + str(len(bidding_zones.keys())) + ")")

        if save_path is not None:
            entsoe_data_enriched.drop(columns=["geometry"]).to_csv(save_path)

        return aggregate_entsoe_zones_final