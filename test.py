import numpy as np
import matplotlib.pyplot as plt

# Sample categorical data
x_categories = ['A', 'B', 'C', 'D']
y_categories = ['X', 'Y', 'Z']

# Convert categorical data to numerical values
x_numerical = np.random.choice(len(x_categories), size=1000)
y_numerical = np.random.choice(len(y_categories), size=1000)

# Define the number of rows and columns
num_rows = len(y_categories)
num_cols = len(x_categories)

# Create the 2D histogram with specified number of rows and columns
plt.hist2d(x_numerical, y_numerical, bins=[np.arange(num_cols+1), np.arange(num_rows+1)])

# Set labels and title
plt.xticks(ticks=np.arange(num_cols) + 0.5, labels=x_categories)
plt.yticks(ticks=np.arange(num_rows) + 0.5, labels=y_categories)
plt.xlabel('X')
plt.ylabel('Y')
plt.title('2D Histogram with Categorical Data')

# Show the plot
plt.colorbar(label='Counts')
plt.show()
