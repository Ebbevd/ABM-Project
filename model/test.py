import numpy as np

def prospect_theory_scores(agent, probability_of_flood, friends_adapted, risk_behavior, number_of_households, media_coverage, flood_damage_estimated, cost_of_adapting):
    """
        Based on this article: https://onlinelibrary-wiley-com.tudelft.idm.oclc.org/doi/10.1111/risa.12740
        The score takes into account that low probability high risks situations are overweighted. 
        It also takes various social scores. 
    """
    
    friend_score = friends_adapted/number_of_households
    basian_weight = 0
    lambda_eq = np.random.normal(2.25, 1)
    theta = np.random.normal(0.88, 0.065) #found by harrison and rutstrom 
    delta = np.random.normal(0.69, 0.025)
    
    flood_damage_estimated_money = flood_damage_estimated*agent.money #convert the flood damage to be economical
    #print(f"{flood_damage_estimated_money} and {lambda_eq} and {theta}")
    
    if agent.is_insured:
        utility_1 = -cost_of_adapting+agent.insurance_benefit_estimated ** theta
        utility =  -lambda_eq * utility_1
        
        utility_no_action_1 = -flood_damage_estimated_money ** theta
        utility_no_action = -lambda_eq * utility_no_action_1
    else:
        utility = -lambda_eq * (-cost_of_adapting ** theta)
    
        utility_no_action_1 = -flood_damage_estimated_money ** theta
        utility_no_action = -lambda_eq * utility_no_action_1
        
    risk_perception = (friend_score + media_coverage + flood_damage_estimated + risk_behavior )/4

    basian_weight_top_1 = (10**((2*risk_perception)-1)*probability_of_flood)
    basian_weight_top_2 = basian_weight_top_1**delta
    basian_weight_bottom = basian_weight_top_2 + ((1-basian_weight_top_1)**delta)**(1/delta)
    basian_weight = basian_weight_top_2/basian_weight_bottom

    prospect_theory_score_action = basian_weight * utility
    prospect_theory_score_no_action = basian_weight * utility_no_action
    
    #print(f"prospect theory score no action: {prospect_theory_score_no_action}, and action: {prospect_theory_score_action}")
    scores = {
        "action": prospect_theory_score_action,
        "noAction": prospect_theory_score_no_action,
        "riskPerception": risk_perception
    }
    return scores

class Agent:
    def __init__(self, money, is_insured, insurance_benifit_estimated):
        self.money = money
        self.is_insured = is_insured
        self.insurance_benefit_estimated = insurance_benifit_estimated
        

if __name__ == "__main__":
    agent = Agent(10000, True, 1000)
    probability_of_flood = 0.1 #dmnml
    friends_adapted = 10 #dmnl
    risk_behavior = 0.5 #dmnl
    number_of_households = 50 #dmnl
    media_coverage = 0.5 #dmnl
    flood_damage_estimated = 0.8 #dmnl
    cost_of_adapting = 2000 #euro
    
    scores = prospect_theory_scores(agent=agent,
                                    probability_of_flood=probability_of_flood, 
                                    friends_adapted=friends_adapted, 
                                    risk_behavior=risk_behavior, 
                                    number_of_households=number_of_households, 
                                    media_coverage=media_coverage, 
                                    flood_damage_estimated=flood_damage_estimated,
                                    cost_of_adapting=cost_of_adapting)
    
    action = scores["action"]
    no_action = scores["noAction"]
    risk_perception = scores["riskPerception"]
    
    print(scores)
    
    if action >= no_action:
        print(f"agent taking action because the action score was {action} and the no action score was {no_action}")
    else:
        print(f"agent taking no action because the action score was {action} and the no action score was {no_action}")