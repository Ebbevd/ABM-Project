# Importing necessary libraries
import random
from mesa import Agent
from shapely.geometry import Point
from shapely import contains_xy
import numpy as np

# Import functions from functions.py
from functions import generate_random_location_within_map_domain, get_flood_depth, calculate_basic_flood_damage, prospect_theory_score, risk_score, move, get_low_locations, adapted_because_of_government_implementation, income_normal
from functions import floodplain_multipolygon


# Define the Households agent class
class Households(Agent): #money
    """
    An agent representing a household in the model.
    Each household has a flood depth attribute which is randomly assigned for demonstration purposes.
    In a real scenario, this would be based on actual geographical data or more complex logic.
    """

    def __init__(self, unique_id, model, adaptation_threshold, income_mean, insurance_price):
        super().__init__(unique_id, model)
        self.is_adapted = False  # Initial adaptation status set to False
        self.risk_behavior = risk_score() #this would be nice as a normal curve
        self.type = "household"
        self.adaptation_threshold = adaptation_threshold 
        self.moved = False
        self.insurance_price = insurance_price
        self.money_lost_because_of_flood_adaption = 0
        self.is_insured = False
        self.income_mean = income_mean
        self.money = income_normal(46000)
        self.current_adoptation = "None"
        self.step_adapted = 0
        self.adaptation_posibilites = ["None", "SandBags", "IntenseBarricading", "Move", "GovernmentBased"]
        self.adaptation_number = 0
        # getting flood map values
        # Get a random location on the map
        loc_x, loc_y = generate_random_location_within_map_domain()
        self.location = Point(loc_x, loc_y)
        self.income = income_normal(self.income_mean)

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
        self.flood_damage_estimated = calculate_basic_flood_damage(self, flood_depth=self.flood_depth_estimated)

        # Add an attribute for the actual flood depth. This is set to zero at the beginning of the simulation since there is not flood yet
        # and will update its value when there is a shock (i.e., actual flood). Shock happens at some point during the simulation
        self.flood_depth_actual = 0
        
        #calculate the actual flood damage given the actual flood depth. Flood damage is a factor between 0 and 1
        self.flood_damage_actual = calculate_basic_flood_damage(self, flood_depth=self.flood_depth_actual)
    
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

    def take_money(self):
        other_agent = random.sample(self.model.schedule.agents, 1)[0]
        if other_agent != self and other_agent.type == "household":
            chance_self = random.random()
            chance_i = random.random()
            current_agent_score = (self.money * chance_self)/3
            other_agent_score = (other_agent.money * chance_i)/3

            if current_agent_score > other_agent_score:
                self.money += other_agent_score
                if other_agent_score < other_agent.money:
                    other_agent.money -= other_agent_score
                else:
                    other_agent.money = 0
            elif other_agent_score > current_agent_score:
                other_agent.money += current_agent_score
                if self.money > other_agent_score:
                    self.money -= other_agent_score
        
    def decide_if_adapted(self, prospect_score):
        if self.model.schedule.steps % 10 == 0: #give an update every 10 steps
            f = open("logs/logs.txt", "a")
            f.write(f"[Step: {self.model.schedule.steps}] Agent: {self.unique_id} The scores are risk:{self.risk_behavior}, prospect_score: {prospect_score} and flood_damage est:{self.flood_damage_estimated} \n")
            f.close()
            
        if prospect_score > self.adaptation_threshold: #adaptation by prospect theory 
            return True
    
    def pay_taxes(self):
        for agent in self.model.schedule.agents:
            if agent.type == "government":
                tax_rate = agent.tax_rates
                personal_rate = [(income, tax) for income, tax in tax_rate.items() if income <= self.income]
                personal_rate = personal_rate[-1] #last item should be the tax rate that applies
                money_owed = personal_rate[1] * self.money #grab the tax and multply by money
                if self.money - money_owed != 0:
                    self.money -= money_owed
                    agent.money += money_owed
                else:
                    agent.money += self.money
                    self.money = 0 
    
    def pay_insurance_risk_based(self, insurance_agent):
        final_amount = self.risk_behavior * self.insurance_price
        if (self.money/2) >= final_amount: #assume agents do not want to pay insurance if that consts more than half their bank account
            self.money -= final_amount
            insurance_agent.money += final_amount
        else:
            self.is_insured = False

    def earn_money(self):
        self.money += self.income

    def decide_on_insurance(self):
        estimated_flood_damage = self.flood_damage_estimated
        neigbors = self.model.grid.get_neighbors(self.pos) #prospect theory aspect
        neigbors_insured = 0
        social_score = 0

        for i in neigbors:
            if i.is_insured:
                neigbors_insured += 1

        if neigbors_insured != 0:
            social_score = neigbors_insured/len(neigbors)

        if social_score > 0.5:
            return True
        elif estimated_flood_damage > 0.5: 
            return True
        return False

    def decide_adapting_mechanism(self, prospect_score):
        if prospect_score <= self.adaptation_threshold:
            self.current_adoptation = self.adaptation_posibilites[0]
            return self.adaptation_posibilites[0]
        elif self.adaptation_threshold <= prospect_score <= self.adaptation_threshold*1.2:
            self.current_adoptation = self.adaptation_posibilites[1]
            if self.money - 100 >= self.money:
                self.money -= 100
                return self.adaptation_posibilites[1]
        elif self.adaptation_threshold <= prospect_score <= self.adaptation_threshold*1.3:
            self.current_adoptation = self.adaptation_posibilites[2]
            if self.money - 1000 >= self.money:
                self.money -= 1000
                return self.adaptation_posibilites[2]
        else:
            self.current_adoptation = self.adaptation_posibilites[3]
            return self.adaptation_posibilites[3]

    def step(self):
        # Logic for adaptation based on estimated flood damage and a random chance.
        # These conditions are examples and should be refined for real-world applications.
        #here we can check how many neighbors are adapted, if there
        """
        Here the agent decides if they are adapted, if they are they move location. The model saves high locations and the actor will move to one of those locations creating clustering.
        If the flood dept still is very high they will be not adapted any more but there is a deley of 4 steps in before they are able to move again. 
        
        Now we can use the municipality to create better this process 
        """
    
        self.flood_depth_estimated = get_flood_depth(corresponding_map=self.model.flood_map, location=self.location, band=self.model.band_flood_img)
        if self.flood_depth_estimated < 0:
            self.flood_depth_estimated = 0
        
        # calculate the estimated flood damage given the estimated flood depth. Flood damage is a factor between 0 and 1
        self.flood_damage_estimated = calculate_basic_flood_damage(self, flood_depth=self.flood_depth_estimated)
        self.flood_damage_actual = calculate_basic_flood_damage(self, flood_depth=self.flood_depth_actual)

        self.pay_taxes() #first pay tax
        self.earn_money() #than earn money
        if self.model.schedule.steps %5 == 0 or self.model.schedule.steps == 0 and self.is_adapted == False: #decide if agent wants insurance do not get insurance if already adapted
            self.is_insured = self.decide_on_insurance() #decide if the agent wants an insurance
            if self.model.introduce_inequality:
                self.take_money() #inspired by simple economy agents can also take money from other agents
        if self.flood_depth_estimated < 0.025:
            self.model.heigh_locations.append(self.location)
        
        #Pay for insurance each step
        if self.is_insured:
            self.pay_insurance_risk_based(self.model.insurance_agent)
        
        friends_adapted = self.count_friends_adapted(radius=1)
        prospect_score = prospect_theory_score(friends_adapted=friends_adapted, risk_behavior=self.risk_behavior, number_of_households=self.model.number_of_households, media_coverage=self.model.media_coverage, flood_damage_estimated= self.flood_damage_estimated)
        #here we should say that if a household is close to a government implementation they are automatically adapted and nothing else realy matters past that point 
        if adapted_because_of_government_implementation(implementation_agents=self.model.implementation_agents, agent=self):
            self.is_adapted = True
            self.current_adoptation = "GovernmentBased"
        elif self.decide_if_adapted(prospect_score) and self.moved == False: #takes two more from self.
            adaptation_mechanism = self.decide_adapting_mechanism(prospect_score)
            self.is_adapted = True  # Agent adapts to flooding so it moves to a higher area  Maybe only move if that is tha last resort
            self.step_adapted = self.model.schedule.steps
            if adaptation_mechanism == "Move":
                if self.model.heigh_locations:
                    location = self.model.heigh_locations[random.randint(0, len(self.model.heigh_locations)-1)]
                    x = location.x
                    y= location.y 
                    x,y = move(x,y) #move to a new location that is higher and close to other high living neighborhoods
                    cost_of_moving = random.randint(1000,5000) 
                    if cost_of_moving <= self.money:
                        self.money -= cost_of_moving#if they move it will cost between 1000 and 5000
                        self.money_lost_because_of_flood_adaption += cost_of_moving
                        if self.is_insured:
                            self.model.insurance_agent.pay_agents(self, cost_of_moving)
                    else:
                        self.money = 0
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
        self.tax_rates = {
            0: 0,
            2000: 0.1,
            5000: 0.15,
            10000: 0.2,
            50000: 0.25
        }
        self.low_locations = get_low_locations(sample_size=100, corresponding_map=model.flood_map, band=model.band_flood_img, arrey_length=20)
    
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
        if 0.4 <= policy_number <= 0.5 and money_available > 1000000: #check how expencive dijks are
            policy = policies[1]
            self.model.set_current_policy(policy)
            self.money -= 1000000
        if policy_number >= 0.5 and money_available > 3000000: #this is rare but possible
            policy = policies[2]
            self.model.set_current_policy(policy)
            self.money -= 3000000
        return policy

    def spend_on_other_expences(self):
        expence = random.randint(17000, 20000) * self.model.number_of_households
        if self.money >= expence:
            self.money -= expence
        else:
            self.money = 0
    
    def generate_other_incomes(self):
        incomes = random.randint(150000, 400000) 
        self.money += incomes

    def step(self):
        agents = self.model.schedule.agents
        households = [ agent for agent in agents if agent.type == "household" ] #here there is one empty agent in the list
        adapted_households = self.list_adapted(households)
        #amount_adapted = len(adapted_households) #amount of households already adapted 
        self.spend_on_other_expences() #need to spend money on other things as well
        self.generate_other_incomes() #things like business taxes and among other things
        
        #If the flood damage is high and there are little households adaptd #check the policy every 5 steps and 
        if self.model.schedule.steps % 5 == 0:
            self.policy = self.decide_policy(households=households, adapted_households=adapted_households, money_available=self.money)
            # Implement the policy so add the implementation to the schedule
            if self.policy != "None" and self.amount_of_policies<=10:
                self.amount_of_policies += 1
                implementation = Government_policy_implementation(unique_id=self.unique_id+1 + self.amount_of_policies , model=self.model, position=self.low_locations[self.amount_of_policies], policy=self.policy)
                self.model.implementation_agents.append(implementation)
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
    def __init__(self, unique_id, model, money):
        super().__init__(unique_id, model)
        self.type = 'insurance'
        self.money = money
        self.bankrupt = False
        self.model.insurance_agent = self

    def pay_agents(self, agent, cost_of_moving):
        agent.money += cost_of_moving
        if self.money >= cost_of_moving:
            self.money -= cost_of_moving
        else:
            self.bankrupt = True

    def count_friends(self, radius): #has to be here because of the lamda function in the model can change this later
        pass

    def step(self):
        pass

