import random
import numpy as np
import math
from shapely import contains_xy
from shapely import prepare
import rasterio as rs
import geopandas as gpd
import pandas as pd
from scipy.signal import argrelextrema


shapefile_path = 'input_data/model_domain/houston_model/houston_model.shp'
floodplain_path = 'input_data/floodmaps/Harvey_depth_meters.tif'

floodmap= rs.open(floodplain_path)
band = floodmap.read(1)
maxima = argrelextrema(band, np.greater)[0]
print(maxima)
#print(floodplain_geoseries)

#SOLUTION TO GET THE LOCAL MAXIMA FOR ALL HOUSEHOLDS:
#get the relative maxima of the map via the band and scipy functionality




