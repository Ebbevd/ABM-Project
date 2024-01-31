import pandas as pd

dataFrame = pd.read_csv(r"C:\Users\vandi\OneDrive\Bureaublad\ABM\input_data\houston_rain_data.csv", on_bad_lines='skip', delimiter=",")

print(dataFrame)