import pandas as pd


# The data is already clean for the most part, because we are using validation data which has already been cleaned.
# We just need to drop the labels in this case.
# In most cases you will have more work done here.

df = pd.read_csv('/opt/ml/processing/input/raw_data.csv', header=None)
df = df.iloc[:10, 1:]
df.to_csv('/opt/ml/processing/output/clean_data.csv', header=False, index=False)
