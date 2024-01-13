# -*- coding: utf-8 -*-
"""
@author: thoridwagenblast

Functions that are used in the model_file.py and agent.py for the running of the Flood Adaptation Model.
Functions get called by the Model and Agent class.
"""
import random
import numpy as np
import math
from shapely import contains_xy
from shapely import prepare
import geopandas as gpd
from shapely.geometry import Point
import pandas as pd
from scipy.signal import argrelextrema

def set_initial_values(input_data, parameter, seed):
    """
    Function to set the values based on the distribution shown in the input data for each parameter.
    The input data contains which percentage of households has a certain initial value.
    
    Parameters
    ----------
    input_data: the dataframe containing the distribution of paramters
    parameter: parameter name that is to be set
    seed: agent's seed
    
    Returns
    -------
    parameter_set: the value that is set for a certain agent for the specified parameter 
    """
    parameter_set = 0
    parameter_data = input_data.loc[(input_data.parameter == parameter)] # get the distribution of values for the specified parameter
    parameter_data = parameter_data.reset_index()
    random.seed(seed)
    random_parameter = random.randint(0,100) 
    for i in range(len(parameter_data)):
        if i == 0:
            if random_parameter < parameter_data['value_for_input'][i]:
                parameter_set = parameter_data['value'][i]
                break
        else:
            if (random_parameter >= parameter_data['value_for_input'][i-1]) and (random_parameter <= parameter_data['value_for_input'][i]):
                parameter_set = parameter_data['value'][i]
                break
            else:
                continue
    return parameter_set


def get_flood_map_data(flood_map):
    """
    Getting the flood map characteristics.
    
    Parameters
    ----------
    flood_map: flood map in tif format

    Returns
    -------
    band, bound_l, bound_r, bound_t, bound_b: characteristics of the tif-file
    """
    band = flood_map.read(1)
    bound_l = flood_map.bounds.left
    bound_r = flood_map.bounds.right
    bound_t = flood_map.bounds.top
    bound_b = flood_map.bounds.bottom
    return band, bound_l, bound_r, bound_t, bound_b

shapefile_path = r'../input_data/model_domain/houston_model/houston_model.shp'
floodplain_path = r'../input_data/floodplain/floodplain_area.shp'

# Model area setup
map_domain_gdf = gpd.GeoDataFrame.from_file(shapefile_path)
map_domain_gdf = map_domain_gdf.to_crs(epsg=26915)
map_domain_geoseries = map_domain_gdf['geometry']
map_minx, map_miny, map_maxx, map_maxy = map_domain_geoseries.total_bounds
map_domain_polygon = map_domain_geoseries[0]  # The geoseries contains only one polygon
prepare(map_domain_polygon)

# Floodplain setup
floodplain_gdf = gpd.GeoDataFrame.from_file(floodplain_path)
floodplain_gdf = floodplain_gdf.to_crs(epsg=26915)
floodplain_geoseries = floodplain_gdf['geometry']
floodplain_multipolygon = floodplain_geoseries[0]  # The geoseries contains only one multipolygon
prepare(floodplain_multipolygon)

def generate_random_location_within_map_domain():
    """
    Generate random location coordinates within the map domain polygon.

    Returns
    -------
    x, y: lists of location coordinates, longitude and latitude
    """
    while True:
        # generate random location coordinates within square area of map domain
        x = random.uniform(map_minx, map_maxx)
        y = random.uniform(map_miny, map_maxy)
        # check if the point is within the polygon, if so, return the coordinates
        if contains_xy(map_domain_polygon, x, y):
            return x, y

def move(x, y):
     while True:
        # generate random location coordinates within square area of map domain
        x = x + random.randint(-1000, 1000)
        x = x + random.randint(-1000, 1000)
        # check if the point is within the polygon, if so, return the coordinates
        if contains_xy(map_domain_polygon, x, y):
            return x, y

def get_flood_depth(corresponding_map, location, band):
    """ 
    To get the flood depth of a specific location within the model domain.
    Households are placed randomly on the map, so the distribution does not follow reality.
    
    Parameters
    ----------
    corresponding_map: flood map used
    location: household location (a Shapely Point) on the map
    band: band from the flood map

    Returns
    -------
    depth: flood depth at the given location
    """
    row, col = corresponding_map.index(location.x, location.y)
    row = abs(row)
    depth = band[row -1, col -1]

    return depth

def get_low_locations(sample_size, corresponding_map, band, arrey_length):
    locations = {}
    low_locations = []
    
    for i in range(sample_size):
        x = random.uniform(map_minx, map_maxx)
        y = random.uniform(map_miny, map_maxy)
        location = Point(x,y)
        depth = get_flood_depth(corresponding_map, location, band)
        locations[depth] = location
    
    for i in range(arrey_length):
        min_key = min(locations.keys())
        low_location = locations[min_key]
        low_locations.append(low_location)
        locations.pop(min_key)
        
    return low_locations
    

def adapted_because_of_government_implementation(implementation_agents, agent):
    for i in implementation_agents:
        x = i.location.x
        y = i.location.y

        diff_x = abs(agent.location.x - x)
        diff_y = abs(agent.location.y - y)

        if i.policy == "Dikes":
            if diff_x < 8000 and diff_y < 8000:
                if agent not in agent.model.adapted_because_government:
                    agent.model.adapted_because_government.append(agent)
                return True
        elif i.policy == "Water locks": #water locks offer double the protection
             if diff_x < 16000 and diff_y < 16000:
                if agent not in agent.model.adapted_because_government:
                    agent.model.adapted_because_government.append(agent)
                return True

    return False

def get_position_flood(bound_l, bound_r, bound_t, bound_b, img, seed):
    """ 
    To generater the position on flood map for a household.
    Households are placed randomly on the map, so the distribution does not follow reality.
    
    Parameters
    ----------
    bound_l, bound_r, bound_t, bound_b, img: characteristics of the flood map data (.tif file)
    seed: seed to generate the location on the map

    Returns
    -------
    x, y: location on the map
    row, col: location within the tif-file
    """
    random.seed(seed)
    x = random.randint(round(bound_l, 0), round(bound_r, 0))
    y = random.randint(round(bound_b, 0), round(bound_t, 0))
    row, col = img.index(x, y)
    return x, y, row, col

def calculate_basic_flood_damage(self, flood_depth): 
    """
    To get flood damage based on flood depth of household
    from de Moer, Huizinga (2017) with logarithmic regression over it.
    If flood depth > 6m, damage = 1.
    
    Parameters
    ----------
    flood_depth : flood depth as given by location within model domain

    Returns
    -------
    flood_damage : damage factor between 0 and 1
    """
    
    if flood_depth >= 6:
        flood_damage = 1
    elif flood_depth < 0.025:
        flood_damage = 0
    else:
        # see flood_damage.xlsx for function generation
        flood_damage = 0.1746 * math.log(flood_depth) + 0.6483
    
    if self.current_adaptation != "None": #this is only the case if already adapted in the past
        flood_damage = flood_damage/(self.adaptation_posibilites.index(self.current_adaptation))
    return flood_damage

def prospect_theory_score(agent, probability_of_flood, friends_adapted, risk_behavior, number_of_households, media_coverage, flood_damage_estimated, cost_of_adapting):
    """
        Based on this article: https://onlinelibrary-wiley-com.tudelft.idm.oclc.org/doi/10.1111/risa.12740
        The score takes into account that low probability high risks situations are overweighted. 
        It also takes various social scores. 
    """
    
    friend_score = (len(friends_adapted)/(number_of_households-1))
    basian_weight = 0
    lambda_eq = np.random.normal(2.25, 1)
    theta = np.random.normal(0.88, 0.065) #found by harrison and rutstrom 
    delta = np.random.normal(0.69, 0.025)
    
    flood_damage_estimated_money = flood_damage_estimated*agent.money #convert the flood damage to be economical
    #print(f"{flood_damage_estimated_money} and {lambda_eq} and {theta}")
    
    if agent.is_insured:
        utility_1 = (-cost_of_adapting+agent.insurance_benefit_estimated) ** theta
        utility =  -lambda_eq * utility_1
        
        utility_no_action_1 = -flood_damage_estimated_money ** theta
        utility_no_action = -lambda_eq * utility_no_action_1
    else:
        utility = -lambda_eq * (-cost_of_adapting ** theta)
    
        utility_no_action_1 = -flood_damage_estimated_money ** theta
        utility_no_action = -lambda_eq * utility_no_action_1
        
    risk_perception = (friend_score + media_coverage + flood_damage_estimated + risk_behavior )/4 #this is a bit different from the theory but just in implementation
    
    basian_weight_top_1 = (10**((2*risk_perception)-1)*probability_of_flood)
    basian_weight_top_2 = basian_weight_top_1**delta
    basian_weight_bottom = basian_weight_top_2 + ((1-basian_weight_top_1)**delta)**(1/delta)
    basian_weight = basian_weight_top_2/basian_weight_bottom

    prospect_theory_score_action = basian_weight * utility
    prospect_theory_score_no_action = basian_weight * utility_no_action
    
    #print(f"prospect theory score no action: {prospect_theory_score_no_action}, and action: {prospect_theory_score_action}")
        
    return [prospect_theory_score_no_action, prospect_theory_score_action, risk_perception]

def risk_score():
    #creating a normal random distro between 0 and 1
    #the average was tested to be between 0.48 and 0.53
    dist = np.random.normal(0.5,0.5,1000) #
    dist_positive = dist[dist>=0]
    risk = dist_positive[dist_positive <= 1]
    
    risk_pick = risk[np.random.randint( 0, len(risk) ) ]

    #print(risk)
    #print(np.average(risk))
    return risk_pick

def income_normal(mean):
    income = np.random.normal(15000, 5000, 1000)
    income_pos = income[income>=0]
    
    return income_pos[np.random.randint(0, len(income_pos))]


def get_rain_list(steps):
    df = pd.read_csv(r'../input_data/Delft_rain_data.csv', skiprows=27, on_bad_lines='skip', delimiter=",")
    df = df[:8784]
    df = df['Rain [mm/hr]']
    values = []
    for i in range(steps):
        value = df[np.random.randint(0, len(df))]
        values.append(value)
    
    return values

def get_rain_dict(steps, number_of_zones, b_l, b_r, b_b, b_t): #devide the zones can do y later
    rain_dict = {}
    x = b_l + b_r
    #y = b_b + b_t
    x = x/number_of_zones
    #y = y/number_of_zones
    
    for i in range(number_of_zones):
        if i == 0:
            cord = []
            cord.append(0)
            cord.append(x*(i+1))
            x = x*(i+1)
        else:
            cord = []
            cord.append(x)
            cord.append(x*(i+1))
            x = x*(i+1)
            
        values = get_rain_list(steps)
        rain_dict[tuple(cord)] = values
    
    return rain_dict