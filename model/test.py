#create a function that takes past years weather events and grabs random data for each step
import pandas as pd
import numpy as np



def get_rain_list(steps):
    df = pd.read_csv('input_data/Delft_rain_data.csv', skiprows=27, on_bad_lines='skip', delimiter=",")
    df = df[:8784]
    df = df['Rain [mm/hr]']
    print(df)
    values = []
    for i in range(steps):
        value = df[np.random.randint(0, len(df))]
        values.append(value)
    
    return values

def decide_if_flood(rain_value):
    if rain_value > 0.3:
        return True
    else:
        return False


if __name__ == "__main__":
    values = get_rain_list(40)
    print(values)
    print(f"Max value of {max(values)}")
    for i in values:
        flood = decide_if_flood(float(i))
        print(flood)
    