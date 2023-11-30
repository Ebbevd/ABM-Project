# Importing necessary libraries
import random
from mesa import Agent
from shapely.geometry import Point
from shapely import contains_xy
import numpy as np

# Import functions from functions.py
from functions import generate_random_location_within_map_domain, get_flood_depth, calculate_basic_flood_damage
from functions import floodplain_multipolygon

f = open("logs/logs.txt", "a")


# Define the Households agent class
class Households(Agent): #money
    """
    An agent representing a household in the model.
    Each household has a flood depth attribute which is randomly assigned for demonstration purposes.
    In a real scenario, this would be based on actual geographical data or more complex logic.
    """

    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.is_adapted = False  # Initial adaptation status set to False
        self.risk_behavior = random.random() #this would be nice as a normal curve
        self.type = "household"
        self.adaptation_number = 0
        # getting flood map values
        # Get a random location on the map
        loc_x, loc_y = generate_random_location_within_map_domain()
        self.location = Point(loc_x, loc_y)

        # Check whether the location is within floodplain
        self.in_floodplain = False
        if contains_xy(geom=floodplain_multipolygon, x=self.location.x, y=self.location.y):
            self.in_floodplain = True

        # Get the estimated flood depth at those coordinates. 
        # the estimated flood depth is calculated based on the flood map (i.e., past data) so this is not the actual flood depth
        # Flood depth can be negative if the location is at a high elevation
        self.flood_depth_estimated = get_flood_depth(corresponding_map=model.flood_map, location=self.location, band=model.band_flood_img)
        # handle negative values of flood depth
        if self.flood_depth_estimated < 0:
            self.flood_depth_estimated = 0
        
        # calculate the estimated flood damage given the estimated flood depth. Flood damage is a factor between 0 and 1
        self.flood_damage_estimated = calculate_basic_flood_damage(flood_depth=self.flood_depth_estimated)

        # Add an attribute for the actual flood depth. This is set to zero at the beginning of the simulation since there is not flood yet
        # and will update its value when there is a shock (i.e., actual flood). Shock happens at some point during the simulation
        self.flood_depth_actual = 0
        
        #calculate the actual flood damage given the actual flood depth. Flood damage is a factor between 0 and 1
        self.flood_damage_actual = calculate_basic_flood_damage(flood_depth=self.flood_depth_actual)
    
    # Function to count friends who can be influencial.
    def count_friends(self, radius):
        """Count the number of neighbors within a given radius (number of edges away). This is social relation and not spatial"""
        friends = self.model.grid.get_neighborhood(self.pos, include_center=False, radius=radius)
        return len(friends)
    
    def count_friends_adapted(self, radius):
        #here we can count how many of the friends are adapted.
        friends = self.model.grid.get_neighbors(self.pos)
        friends_adapted = []
        for i in friends:
            if i.is_adapted:
                friends_adapted.append(i)
        return friends

    def prospect_theory_score(self, friends_adapted, media):
        #score between 1 and 0
        #agent looks at the problem subjectively so if they have allready experianced a flood or if there is media interaction they will behave diffently
        #check if a neighbor has been flooded if so the agent is more 
        #percieved risk declines after a while
        friend_score = (len(friends_adapted)/self.model.number_of_households)/2
        media_score = 0

        if media.coverage == 1:
            media_score = 0.25
        else:
            media_score = 0.5
        
        return friend_score+media_score

    def decide_if_adapted(self, prospect_score):
        total_avarge = (self.risk_behavior + prospect_score + self.flood_damage_estimated)/3
        f.write(f"[Step {self.model.schedule.steps}] The scores are risk:{self.risk_behavior}, prospect_score: {prospect_score} and flood_damage est:{self.flood_damage_estimated} so the avarage is {total_avarge} (at 0.57 the agent will adapt)\n")
        if total_avarge > 0.57:
            return True
        else:
            return False


    def step(self):
        # Logic for adaptation based on estimated flood damage and a random chance.
        # These conditions are examples and should be refined for real-world applications.
        #here we can check how many neighbors are adapted, if there
        friends_adapted = self.count_friends_adapted(radius=1)
        media = [ ]
        for agent in self.model.schedule.agents:
            if agent.type =='media':
                media.append(agent)
        prospect_score = self.prospect_theory_score(friends_adapted=friends_adapted, media=media[0])

        if self.decide_if_adapted(prospect_score): #takes two more from self.
            self.is_adapted = True  # Agent adapts to flooding
        
# Define the Government agent class
class Government(Agent):
    """
    A government agent that currently doesn't perform any actions.
    - subsidies 
    - regulations
    - measurements 
    """
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.type = 'government'
    
    def list_adapted(self, agents):
        adapted = []
        for a in agents:
            if a.is_adapted:
                adapted.append(a)
        return adapted

    def step(self):
        agents = self.model.schedule.agents
        households = [ agent if agent.type == "household" else None for agent in agents ] #here there is one empty agent in the list
        households.remove(None) #remove the None that gets put for all other agent types 
        adapted_households = self.list_adapted(households)

        amount_adapted = len(adapted_households) #amount of households already adapted 
        pass

# More agent classes can be added here, e.g. for insurance agents.
class Media(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.type = "media"
        self.coverage_types = {
            0: "No coverage",
            1: "Small coverage",
            2: "Big coverage"
        }
        self.coverage = 1
    
    def count_friends(self, radius): #has to be here because of the lamda function in the model can change this later
        pass

    def avarge_flood_damage(self, agents):
        damage = 0
        for a in agents:
            damage += a.flood_damage_actual
        if damage != 0:
            return damage/self.model.number_of_households
        else:
            return 0

    def step(self):
        agents = self.model.schedule.agents
        households = [ agent if agent.type == "household" else None for agent in agents ] #here there is one empty agent in the list
        households.remove(None) #remove the None that gets put for all other agent types 
        avarge_damage = self.avarge_flood_damage(households)

        if avarge_damage < 0.2: #later we can base these numbers on sources. 
            self.coverage = 0
        elif avarge_damage < 0.5:
            self.coverage = 1
        else:
            self.coverage = 2
        
        f.write(f"ther avarage damage is {avarge_damage} and the coverage {self.coverage_types[self.coverage]}\n")



class Insurance(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)

    def step(self):
        pass

