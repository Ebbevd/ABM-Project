# Importing necessary libraries
import networkx as nx
from mesa import Model, Agent
from mesa.time import RandomActivation
from mesa.space import NetworkGrid
from mesa.datacollection import DataCollector
import rasterio as rs
import matplotlib.pyplot as plt
# Import the agent class(es) from agents.py
from agents import Households, Media, Government
# Import functions from functions.py
from functions import get_flood_map_data, calculate_basic_flood_damage, get_rain_dict
from functions import map_domain_gdf, floodplain_gdf


# Define the AdaptationModel class
class AdaptationModel(Model):
    """
    The main model running the simulation. It sets up the network of household agents,
    simulates their behavior, and collects data. The network type can be adjusted based on study requirements.
    """

    def __init__(self, 
                 seed = None,
                 number_of_households = 25, # number of household agents
                 # flood damage related: from Huizinga, de Moel --> damage factor
                 # in dollar and adjusted for inflation to 2020 value
                 max_damage_dol_per_sqm = 1216.65,
                 # Simplified argument for choosing flood map. Can currently be "harvey", "100yr", or "500yr".
                 flood_map_choice='harvey',
                 # ### network related parameters ###
                 # The social network structure that is used.
                 # Can currently be "erdos_renyi", "barabasi_albert", "watts_strogatz", or "no_network"
                 network = 'watts_strogatz',
                 # likeliness of edge being created between two nodes
                 probability_of_network_connection = 0.4,
                 # number of edges for BA network
                 number_of_edges = 3,
                 number_of_steps = 20,
                 tax_rate = 1000,
                 government_money = 3000000,
                 number_of_zones = 1,
                 base_water_level = 0, #the base of the water level
                 # number of nearest neighbours for WS social network
                 number_of_nearest_neighbours = 5,
                 media_coverage = 0,
                 adaptation_threshold = 0.3
                 ):
        
        super().__init__(seed = seed)
        
        # defining the variables and setting the values
        self.number_of_households = number_of_households  # Total number of household agents
        self.seed = seed #?
        self.government_money = government_money,
        self.tax_rate = tax_rate
        self.number_of_steps = number_of_steps
        self.current_policy = 'No policy'
        self.number_of_floods = 0
        self.water_level = {}
        self.number_of_zones = number_of_zones
        self.rain_values = {}
        self.heigh_locations = []
        self.base_water_level = base_water_level
        self.max_damage_dol_per_sqm = max_damage_dol_per_sqm
        self.media_coverage = media_coverage
        self.adaptation_threshold = adaptation_threshold
        # network
        self.network = network # Type of network to be created
        self.probability_of_network_connection = probability_of_network_connection
        self.number_of_edges = number_of_edges
        self.number_of_nearest_neighbours = number_of_nearest_neighbours


        # generating the graph according to the network used and the network parameters specified
        self.G = self.initialize_network()
        # create grid out of network graph
        self.grid = NetworkGrid(self.G)

        # Initialize maps
        self.initialize_maps(flood_map_choice)

        # set schedule for agents
        self.schedule = RandomActivation(self)  # Schedule for activating agents

        # create households through initiating a household on each node of the network graph
        for i, node in enumerate(self.G.nodes()):
            household = Households(unique_id=i, model=self, adaptation_threshold=self.adaptation_threshold)
            self.schedule.add(household)
            self.grid.place_agent(agent=household, node_id=node)
        
        media = Media(unique_id=i+1, model=self)
        self.schedule.add(media)

        government = Government(unique_id=i+2, model=self, money=government_money)
        self.schedule.add(government)

        # You might want to create other agents here, e.g. insurance agents.

        # Data collection setup to collect data
        model_metrics = {
                        "total_adapted_households": self.total_adapted_households,
                        "media_coverage": self.current_media_attention,
                        "number_of_floods": self.get_number_of_floods,
                        "current_policy": self.get_current_policy
                        }
        
        agent_metrics = {
                        "Type": "type",
                        "FloodDepthEstimated": "flood_depth_estimated",
                        "FloodDamageEstimated" : "flood_damage_estimated",
                        "FloodDepthActual": "flood_depth_actual",
                        "FloodDamageActual" : "flood_damage_actual",
                        "IsAdapted": "is_adapted",
                        "Money": "money",
                        "FriendsCount": lambda a: a.count_friends(radius=1),
                        "location": "location"
                        # ... other reporters ...
                        }
        #set up the data collector 
        self.datacollector = DataCollector(model_reporters=model_metrics,agent_reporters=agent_metrics)
            

    def initialize_network(self):
        """
        Initialize and return the social network graph based on the provided network type using pattern matching.
        """
        if self.network == 'erdos_renyi':
            return nx.erdos_renyi_graph(n=self.number_of_households,
                                        p=self.number_of_nearest_neighbours / self.number_of_households,
                                        seed=self.seed)
        elif self.network == 'barabasi_albert':
            return nx.barabasi_albert_graph(n=self.number_of_households,
                                            m=self.number_of_edges,
                                            seed=self.seed)
        elif self.network == 'watts_strogatz':
            return nx.watts_strogatz_graph(n=self.number_of_households,
                                        k=self.number_of_nearest_neighbours,
                                        p=self.probability_of_network_connection,
                                        seed=self.seed)
        elif self.network == 'no_network':
            G = nx.Graph()
            G.add_nodes_from(range(self.number_of_households))
            return G
        else:
            raise ValueError(f"Unknown network type: '{self.network}'. "
                            f"Currently implemented network types are: "
                            f"'erdos_renyi', 'barabasi_albert', 'watts_strogatz', and 'no_network'")


    def initialize_maps(self, flood_map_choice):
        """
        Initialize and set up the flood map related data based on the provided flood map choice.
        """
        # Define paths to flood maps
        flood_map_paths = {
            'harvey': r'../input_data/floodmaps/Harvey_depth_meters.tif',
            '100yr': r'../input_data/floodmaps/100yr_storm_depth_meters.tif',
            '500yr': r'../input_data/floodmaps/500yr_storm_depth_meters.tif',  # Example path for 500yr flood map
            'Netherlands': r'../input_data/floodmaps/Netherlands.tif' 
        }

        # Throw a ValueError if the flood map choice is not in the dictionary
        if flood_map_choice not in flood_map_paths.keys():
            raise ValueError(f"Unknown flood map choice: '{flood_map_choice}'. "
                             f"Currently implemented choices are: {list(flood_map_paths.keys())}")

        # Choose the appropriate flood map based on the input choice
        flood_map_path = flood_map_paths[flood_map_choice]

        # Loading and setting up the flood map
        self.flood_map = rs.open(flood_map_path)
        self.band_flood_img, self.bound_left, self.bound_right, self.bound_top, self.bound_bottom = get_flood_map_data(
            self.flood_map)
        
        self.rain_values = get_rain_dict(self.number_of_steps, self.number_of_zones, self.bound_left, self.bound_right, self.bound_bottom, self.bound_top)

    def total_adapted_households(self):
        """Return the total number of households that have adapted."""
        #BE CAREFUL THAT YOU MAY HAVE DIFFERENT AGENT TYPES SO YOU NEED TO FIRST CHECK IF THE AGENT IS ACTUALLY A HOUSEHOLD AGENT USING "ISINSTANCE"
        adapted_count = sum([1 for agent in self.schedule.agents if isinstance(agent, Households) and agent.is_adapted])
        return adapted_count
    
    def current_media_attention(self): #purely for data collection
        return self.media_coverage
    
    def get_number_of_floods(self):
        return self.number_of_floods
    
    def set_media_attention(self, val):
        self.media_coverage = val
    
    def set_current_policy(self, val):
        self.current_policy = val
    
    def get_current_policy(self):
        return self.current_policy
    
    def plot_model_domain_with_agents(self):
        fig, ax = plt.subplots()
        # Plot the model domain
        map_domain_gdf.plot(ax=ax, color='lightgrey')
        # Plot the floodplain
        floodplain_gdf.plot(ax=ax, color='lightblue', edgecolor='k', alpha=0.5)

        # Collect agent locations and statuses
        for agent in self.schedule.agents:
            color = 'blue' if agent.is_adapted else 'red'
            ax.scatter(agent.location.x, agent.location.y, color=color, s=10, label=color.capitalize() if not ax.collections else "")
            ax.annotate(str(agent.unique_id), (agent.location.x, agent.location.y), textcoords="offset points", xytext=(0,1), ha='center', fontsize=9)
        # Create legend with unique entries
        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ax.legend(by_label.values(), by_label.keys(), title="Red: not adapted, Blue: adapted")

        # Customize plot with titles and labels
        plt.title(f'Model Domain with Agents at Step {self.schedule.steps}')
        plt.xlabel('Longitude')
        plt.ylabel('Latitude')
        plt.show()
    
    def decide_if_flood(self, rain_value):
        if rain_value > 0.3:
            return True
        else:
            return False

    def step(self):
        """
        introducing a shock: 
        at time step 5, there will be a global flooding.
        This will result in actual flood depth. Here, we assume it is a random number
        between 0.5 and 1.2 of the estimated flood depth. In your model, you can replace this
        with a more sound procedure (e.g., you can devide the floop map into zones and 
        assume local flooding instead of global flooding). The actual flood depth can be 
        estimated differently

        Now the water level will get higher because of rainfall this can cause a flood. If there is a flood the agent will determine the depth based
        on the hight the agent is at. If the depth is really high the damage will get high and the agent will have a higher chance of adapting.
        
        The floods are devided into zones. The zones are now only on the x axis these still have to be expanded to the y axis 
        """
        rain_dict_keys = self.rain_values.keys()
        for i in rain_dict_keys:
            rain_value = self.rain_values[i] #this is a list
            rain_value = rain_value[self.schedule.steps]
            if self.decide_if_flood(float(rain_value)):
                self.number_of_floods += 1
                water_level = self.base_water_level + float(rain_value) #this should be based on the location of the agent
                self.water_level[i] = water_level
                
        for agent in self.schedule.agents:
            if agent.type == 'household':
                # Calculate the actual flood depth as a random number between 0.5 and 1.2 times the estimated flood depth
                for i in self.water_level:
                    if i[0] <= agent.location.x <= i[1]:
                        agent.flood_depth_actual = self.water_level[i] + agent.flood_depth_estimated #floodingdepth is random
                        # calculate the actual flood damage given the actual flood depth
                        agent.flood_damage_actual = calculate_basic_flood_damage(agent.flood_depth_actual)
                
        # Collect data and advance the model by one step
        self.datacollector.collect(self)
        self.schedule.step()
