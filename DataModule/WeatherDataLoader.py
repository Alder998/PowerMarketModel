"""
Loader for weather data from openMeteo (15-minutes data)
"""

import geopandas as gpd
import numpy as np
from shapely.geometry import Point
import pandas as pd

class WeatherDataLoader:

    def __init__(self, start_date, end_date, bidding_zones):
        self.start_date = start_date,
        self.end_date = end_date,
        self.bidding_zones = bidding_zones
        pass

    # Method to load geometry of bidding zones
    def getPointsFromGeometry (self, n_points):

        # Use the bidding zones dict to get a series of uniform points
        url = "https://raw.githubusercontent.com/electricitymaps/electricitymaps-contrib/v1.238.0/web/geo/world.geojson"
        entsoe_data_unique_zones = gpd.read_file(url)
        zones_gdf = gpd.GeoDataFrame(entsoe_data_unique_zones, geometry="geometry", crs="EPSG:4326")
        # Filter for the selected zones
        zones_gdf = zones_gdf[["zoneName", "geometry"]][zones_gdf["zoneName"].isin(pd.DataFrame(self.bidding_zones).T["map_code"])].reset_index(drop=True)

        def regular_grid_n_points(gdf, n_points=50):
            all_points = []

            for idx, row in gdf.iterrows():
                polygon = row.geometry
                zone = row["zoneName"]

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

            return pd.DataFrame(all_points, columns=["zoneName", "lat", "lon"])
        gdf = regular_grid_n_points(gdf=zones_gdf, n_points=n_points)

        return gdf