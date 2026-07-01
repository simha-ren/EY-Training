# Taxis Dataset Analysis

## Overview
This project performs an exploratory data analysis (EDA) on the `taxis` dataset, available through the Seaborn library. The goal is to uncover patterns related to taxi trip behaviors, fare structures, and the influence of various factors like distance, payment methods, and passenger counts on trip costs. This analysis provides insights into pricing dynamics and travel patterns within the dataset.

## Dataset
The `taxis` dataset contains detailed records of taxi rides, including:
- `pickup` and `dropoff` times
- `passengers` count
- `distance` traveled
- `fare`, `tip`, `tolls`, and `total` cost
- `color` of the taxi (e.g., yellow, green)
- `payment` type (e.g., cash, credit card)
- `pickup_zone`, `dropoff_zone`, `pickup_borough`, `dropoff_borough`

## Analysis Steps
The analysis is structured into the following sections:

### 1. Load & Inspect
- Initial loading of the `taxis` dataset.
- Inspection of its shape, head, data types (`info()`), and summary statistics (`describe()`).

### 2. Clean & Prepare
- Identification and handling of missing values (rows with any missing data were dropped).
- Feature Engineering:
    - Calculation of `trip_duration` (in minutes) from `pickup` and `dropoff` times.
    - Calculation of `fare_per_km`.
- Dropping of original `pickup` and `dropoff` datetime columns after feature extraction.

### 3. Explore with Statistics
- Calculation of key percentiles for `fare` (25th, 50th, 75th).
- Group-by aggregations:
    - Average fare by `payment` type.
    - Total trips by `passengers` count.
- Pivot table to show average `fare` across `payment` types and `passengers` counts.
- Overall summary statistics including average/max/min fare per km, total trips, total passengers, and most common payment type.

### 4. Visualize
Various visualizations were created to explore the data:
- **Bar Chart**: Average Fare by Payment Type.
- **Histogram**: Distribution of `fare` values.
- **Scatter Plot**: `fare` vs. `distance`, with an annotation for the mean fare.
- **Multi-panel Subplots**: A dashboard providing a comprehensive overview:
    - Average Fare by Payment Type (Bar Chart)
    - Trip Distance Distribution (Histogram)
    - Fare vs Distance Scatter Plot
    - Average Fare Heatmap across Payment and Passengers

### 5. Key Insights
Based on the analysis, the following key insights were drawn:
1.  Trips paid by credit card generally have a higher average fare compared to other payment types.
2.  Distance is a strong determinant of fare charges, with a clear positive correlation.
3.  Payment type and passenger count introduce additional variations and complexities in pricing behavior, influencing the average fare.

## Technologies Used
- Python
- Pandas (for data manipulation and analysis)
- NumPy (for numerical operations)
- Matplotlib (for data visualization)
- Seaborn (for enhanced data visualization)

## How to Run
This analysis is provided as a Jupyter/Google Colab notebook. To run it:
1.  Open the `.ipynb` file in a Jupyter environment or Google Colab.
2.  Execute the cells sequentially to reproduce the analysis and visualizations.

Colab link: https://colab.research.google.com/drive/1_Ks4jRXga2glvnDL5nsRb3ARkJDjzB9T?authuser=1#scrollTo=OzJyoZcehHZz



## SENTIMENT ANALYSIS
Colab link: https://colab.research.google.com/drive/1Jc-Obzi2tP_kFmbGgPBjmkoscd4B8ivk?authuser=1#scrollTo=c9-vyiLi783T
