import numpy as np


dist = np.random.normal(0.5,0.5,1000) #
dist_positive = dist[dist>=0]
risk = dist_positive[dist_positive <= 1]
risk_pick = risk[np.random.randint( 0, len(risk) ) ]
print(risk_pick)
    #print(np.average(risk))