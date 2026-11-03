"""
Loader for weather data from openMeteo (15-minutes data)
"""

import geopandas as gpd
import numpy as np
from shapely.geometry import Point
import pandas as pd
import requests

class WeatherDataLoader:

    def __init__(self, start_date, end_date, bidding_zones):
        self.start_date = start_date
        self.end_date = end_date
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

    # Method to load single weather from latitude and logitude
    def loadWeather (self, latitude, longitude):

        url = f"https://archive-api.open-meteo.com/v1/archive?latitude={latitude}&longitude={longitude}&start_date={self.start_date}&end_date={self.end_date}&hourly=temperature_2m,precipitation,relative_humidity_2m,windspeed_10m,cloudcover,pressure_msl&timezone=Europe/Rome"

        response = requests.get(url)
        data = response.json()

        weatherDB = []
        for i, date in enumerate(data["hourly"]["time"]):
            temperature = data["hourly"]["temperature_2m"][i]
            precipitation = data["hourly"]["precipitation"][i]
            humidity = data["hourly"]["relative_humidity_2m"][i]
            wind = data["hourly"]["windspeed_10m"][i]
            cloudCover = data["hourly"]["cloudcover"][i]
            pressure = data["hourly"]["pressure_msl"][i]

            # Handle the data from JSON to DataFrame
            singleDatabase = pd.concat([pd.DataFrame(pd.Series(date)).set_axis(['date'], axis=1),
                                        pd.DataFrame(pd.Series(latitude)).set_axis(['latitude'], axis=1),
                                        pd.DataFrame(pd.Series(longitude)).set_axis(['longitude'], axis=1),
                                        pd.DataFrame(pd.Series(temperature)).set_axis(['temperature'], axis=1),
                                        pd.DataFrame(pd.Series(precipitation)).set_axis(['precipitation'], axis=1),
                                        pd.DataFrame(pd.Series(humidity)).set_axis(['humidity_mean'], axis=1),
                                        pd.DataFrame(pd.Series(wind)).set_axis(['windSpeed'], axis=1),
                                        pd.DataFrame(pd.Series(cloudCover)).set_axis(['cloudCover'], axis=1),
                                        pd.DataFrame(pd.Series(pressure)).set_axis(['pressure_msl'], axis=1)],
                                       axis=1)
            weatherDB.append(singleDatabase)
        weatherDB = pd.concat([df for df in weatherDB], axis=0).reset_index(drop=True)
        return weatherDB

    # Method to load data from OpenMeteo
    def loadWeatherForBiddingZone (self, n_points):

        # Get coordinates
        coords = self.getPointsFromGeometry(n_points=n_points)
        # Iterate for single bidding zone
        weather_data = []
        for i, bz in enumerate(self.bidding_zones):
            print("WEATHER DATA LOADER - Processing: " + bz + " - " + str(i + 1) + " out of " + str(len(self.bidding_zones.keys())) + "...")
            coords_for_zone = coords[coords["zoneName"] == self.bidding_zones[bz]["map_code"]].reset_index(drop=True)
            # Now load the data
            weather_for_bz = []
            for ci in coords_for_zone.index:
                wfcoords = self.loadWeather(latitude=coords_for_zone.iloc[ci]["lat"], longitude=coords_for_zone.iloc[ci]["lon"])
                weather_for_bz.append(wfcoords)
            weather_for_bz = pd.concat([df for df in weather_for_bz], axis=0).reset_index(drop=True)
            weather_for_bz = weather_for_bz.groupby("date").mean()
            weather_for_bz = weather_for_bz.drop(columns=["latitude", "longitude"])
            weather_for_bz["map_code"] = self.bidding_zones[bz]["map_code"]
            weather_for_bz = pd.concat([weather_for_bz["map_code"], weather_for_bz.drop(columns=["map_code"])], axis=1)
            weather_data.append(weather_for_bz)
        weather_data = pd.concat([df for df in weather_data], axis=0)

        return weather_data



