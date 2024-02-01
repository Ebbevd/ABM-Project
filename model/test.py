import pandas as pd

dataFrame = pd.read_csv(r"C:\Users\vandi\OneDrive\Bureaublad\ABM\input_data\houston_rain_data.csv", on_bad_lines='skip', delimiter=",")

rainfall = dataFrame['rainfall']
amount_heiher_3 =  rainfall[rainfall > 3].count()
print(amount_heiher_3)
fraction = amount_heiher_3/len(rainfall)
print(fraction*100)

