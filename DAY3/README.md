# MLflow Iris Classification
### This notebook demonstrates the use of MLflow for tracking machine learning experiments, specifically for a RandomForestClassifier applied to the Iris dataset using scikit-learn.

## Colab Link: https://colab.research.google.com/drive/1OBRuV_tUfiS9lmI7jSgeANtDoVcmmjtt?authuser=1#scrollTo=MKsQqYEXPyHG

## Experiment Overview
The experiment performs the following actions:

### Data Preparation: Loads the Iris dataset and splits it into training and testing sets.
### Model Training: Trains a RandomForestClassifier with specified max_depth and n_estimators.
### MLflow Tracking: Configures MLflow to log experiment details:
### Sets a SQLite database (sqlite:///quiz.db) as the tracking URI.
### Defines an experiment named quiz-experiment.
### Logs hyperparameters max_depth and n_estimators.
### Logs evaluation metrics: accuracy_score and f1_score (macro average).
### Logs and registers the trained scikit-learn model under the name iris-rf-classifier.
### Sets a custom tag team with the value data science.
