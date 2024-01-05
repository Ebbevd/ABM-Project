import random
import numpy as np
import math
from shapely import contains_xy
from shapely import prepare
import rasterio as rs
import geopandas as gpd
import pandas as pd
from scipy.signal import argrelextrema
import seaborn as sns
import matplotlib.pyplot as plt

income = np.random.normal(15000, 5000, 1000)
income_pos = income[income>=0]
