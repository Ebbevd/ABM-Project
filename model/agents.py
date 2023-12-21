# Importing necessary libraries
import random
from mesa import Agent
from shapely.geometry import Point
from shapely import contains_xy
import numpy as np

# Import functions from functions.py
from functions import generate_random_location_within_map_domain, get_flood_depth, calculate_basic_flood_damage, prospect_theory_score, risk_score, move
from functions import floodplain_multipolygon


# Define the Households agent class
class Households(Agent): #money
    """
    An agent representing a household in the model.
    Each household has a flood depth attribute which is randomly assigned for demonstration purposes.
    In a real scenario, this would be based on actual geographical data or more complex logic.
    """

    def __init__(self, unique_id, model, adaptation_threshold):
        super().__init__(unique_id, model)
        self.is_adapted = False  # Initial adaptation status set to False
        self.risk_behavior = risk_score() #this would be nice as a normal curve
        self.type = "household"
        self.adaptation_threshold = adaptation_threshold 
        self.moved = False
        self.money = random.randint(1000,10000)
        self.step_adapted = 0
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

    def decide_if_adapted(self, prospect_score):
        if self.model.schedule.steps % 10 == 0: #give an update every 10 steps
            f = open("logs/logs.txt", "a")
            f.write(f"[Step: {self.model.schedule.steps}] Agent: {self.unique_id} The scores are risk:{self.risk_behavior}, prospect_score: {prospect_score} and flood_damage est:{self.flood_damage_estimated} \n")
            f.close()
            
        if prospect_score > self.adaptation_threshold: #adaptation by prospect theory 
            return True
    
    def pay_taxes(self):
        for agent in self.model.schedule.agents:
            if agent.type == "government" and self.money >= self.model.tax_rate:
                self.money -= self.model.tax_rate 
                agent.money += self.model.tax_rate
    
    def earn_money(self):
        self.money += random.randint(500, 3000)


    def step(self):
        # Logic for adaptation based on estimated flood damage and a random chance.
        # These conditions are examples and should be refined for real-world applications.
        #here we can check how many neighbors are adapted, if there
        """
        Here the agent decides if they are adapted, if they are they move location. The model saves high locations and the actor will move to one of those locations creating clustering.
        If the flood dept still is very high they will be not adapted any more but there is a deley of 4 steps in before they are able to move again. 
        
        Now we can use the municipality to create better this process 
        """
        self.pay_taxes() #first pay tax
        self.earn_money() #than earn money
        if self.flood_depth_estimated < 0.025:
            self.model.heigh_locations.append(self.location)
        
        friends_adapted = self.count_friends_adapted(radius=1)
        prospect_score = prospect_theory_score(friends_adapted=friends_adapted, risk_behavior=self.risk_behavior, number_of_households=self.model.number_of_households, media_coverage=self.model.media_coverage, flood_damage_estimated= self.flood_damage_estimated)

        if self.decide_if_adapted(prospect_score) and self.moved == False: #takes two more from self.
            self.is_adapted = True  # Agent adapts to flooding so it moves to a higher area  
            self.step_adapted = self.model.schedule.steps
            if self.model.heigh_locations:
                location = self.model.heigh_locations[random.randint(0, len(self.model.heigh_locations)-1)]
                x = location.x
                y= location.y 
                x,y = move(x,y)
                self.location = Point(x, y)
            else:
                x, y = generate_random_location_within_map_domain() #agent moves to a different spot where he is adapted, idealy this would be to a higher location but I don't know how to do this
                self.location = Point(x, y)
            self.moved = True
        elif self.flood_depth_estimated > 0.5 and self.model.schedule.steps - self.step_adapted > 4: #when the flood depth in theory can be higher than the actor is no longer adapted, value based on function calculate basic flood damage
            self.is_adapted = False
            self.moved = False #gotte reset this
        
# Define the Government agent class
class Government(Agent):
    """
    A government agent that currently doesn't perform any actions.
    - subsidies 
    - regulations
    - measurements 
    """
    def __init__(self, unique_id, model, money):
        super().__init__(unique_id, model)
        self.type = 'government'
        self.money = money
        self.policy = None
        self.amount_of_policies = 0
    
    def list_adapted(self, agents):
        adapted = []
        for a in agents:
            if a.is_adapted:
                adapted.append(a)
        return adapted
    
    def count_friends(self, radius): #has to be here because of the lamda function in the model can change this later
        pass

    def expected_damage(self, households):
        total = 0
        for agent in households:
            total += agent.flood_damage_estimated
        
        if total != 0:
            return total/len(households)
        else:
            return 0
    
    def actual_damage(self, households):
        total = 0
        for agent in households:
            total += agent.flood_damage_actual
        
        if total != 0:
            return total/len(households)
        else:
            return 0
    
    def decide_policy(self, households, adapted_households, money_available):
        policies = ['None', 'Dijks', 'Water locks']
        policy = 'None'
        ratio_adapted = len(adapted_households)/len(households)
        expected_damage = self.expected_damage(households=households)
        actual_damage = self.actual_damage(households=households)

        policy_number = (ratio_adapted + expected_damage + actual_damage)/3
        print(policy_number)

        if 0.3 <= policy_number <= 0.6 and money_available > 1000000: #check how expencive dijks are
            policy = policies[1]
            self.model.set_current_policy(policy)
            self.money -= 1000000
        if policy_number >= 0.6 and money_available > 5000000:
            policy = policies[2]
            self.model.set_current_policy(policy)
            self.money -= 5000000
        return policy

    def spend_on_other_expences(self):
        expence = random.randint(10000, 100000)
        if self.money >= expence:
            self.money -= expence
        else:
            self.money = 0
        

    def step(self):
        agents = self.model.schedule.agents
        households = [ agent for agent in agents if agent.type == "household" ] #here there is one empty agent in the list
        adapted_households = self.list_adapted(households)
        #amount_adapted = len(adapted_households) #amount of households already adapted 
        self.spend_on_other_expences() #need to spend money on other things as well
        
        #If the flood damage is high and there are little households adaptd #check the policy every 5 steps and 
        if self.model.schedule.steps % 5 == 0:
            self.policy = self.decide_policy(households=households, adapted_households=adapted_households, money_available=self.money)
            self.amount_of_policies += 1
            # Implement the policy so add the implementation to the schedule
            if self.policy != None:
                implementation = Government_policy_implementation(unique_id=self.unique_id + self.amount_of_policies , model=self.model, position=self.model.heigh_locations[0], policy=self.policy)
                self.model.schedule.add(implementation)

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
        households = [ agent for agent in agents if agent.type == "household" ] #here there is one empty agent in the list
        avarge_damage = self.avarge_flood_damage(households)

        if avarge_damage < 0.2: #later we can base these numbers on sources. 
            self.coverage = 0
            self.model.set_media_attention(0)
        elif avarge_damage < 0.5:
            self.coverage = 1
            self.model.set_media_attention(1)
        else:
            self.coverage = 2
            self.model.set_media_attention(2)
        if self.model.schedule.steps % 10 == 0: #give an update every 10 steps
            f = open("logs/logs.txt", "a")
            f.write(f"Step: {self.model.schedule.steps} Agent: Media ther avarage damage is {avarge_damage} and the coverage {self.coverage_types[self.coverage]}\n")
            f.close()
    
class Government_policy_implementation(Agent):
    def __init__(self, unique_id, model, position, policy):
        super().__init__(unique_id, model)
        self.location = position
        self.type = "implementation"
        self.policy = policy
    
    def count_friends(self, radius): #has to be here because of the lamda function in the model can change this later
        pass

    def step(self):
        pass


class Insurance(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)

    def step(self):
        pass

