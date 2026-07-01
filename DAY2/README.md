# Machine Learning Evaluation Frameworks Notebook

This notebook demonstrates various machine learning concepts, focusing on dataset preparation, model training, and evaluation, particularly for classification tasks using the Breast Cancer dataset and a regression task using the Diabetes dataset.

## Colab link: https://colab.research.google.com/drive/18-s-SrsaT9tfuFptcd3AvzJYZnP6FXT1?authuser=1

## Table of Contents
1.  [Setup](#setup)
2.  [Dataset Preparation](#dataset-preparation)
    *   [Breast Cancer Dataset (Classification)](#breast-cancer-dataset-classification)
    *   [Diabetes Dataset (Regression)](#diabetes-dataset-regression)
3.  [Data Exploration](#data-exploration)
4.  [Model Training and Evaluation (Classification)](#model-training-and-evaluation-classification)
    *   [Confusion Matrix Analysis](#confusion-matrix-analysis)

## Setup
This section installs necessary Python libraries and imports them for use throughout the notebook. It also sets up plotting styles and a random seed for reproducibility.

```python
!pip install matplotlib pandas scikit-learn seaborn
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
warnings.filterwarnings('ignore')
# ... (other imports from sklearn.datasets, sklearn.model_selection, etc.)
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette('husl')
np.random.seed(42)
```

## Dataset Preparation

### Breast Cancer Dataset (Classification)
The Breast Cancer dataset is loaded, split into training and testing sets, and features are scaled using `StandardScaler`. This dataset is used for binary classification (malignant vs. benign).

```python
cancer = load_breast_cancer()
X_clf, y_clf = cancer.data, cancer.target
X_train_c, X_test_c, y_train_c, y_test_c = train_test_split(X_clf, y_clf, test_size=0.2, random_state=42)

scaler = StandardScaler()
X_train_c = scaler.fit_transform(X_train_c)
X_test_c = scaler.transform(X_test_c)
```

### Diabetes Dataset (Regression)
The Diabetes dataset is loaded, split, and scaled similarly. This dataset is prepared for regression tasks.

```python
diabetes = load_diabetes()
X_reg, y_reg = diabetes.data, diabetes.target
X_train_r, X_test_r, y_train_r, y_test_r = train_test_split(X_reg, y_reg, test_size=0.2, random_state=42)

# ... (scaling for regression data)
```

## Data Exploration
Basic data exploration includes printing the first few feature names, calculating the class imbalance ratio, and visualizing the class distribution for the Breast Cancer dataset.

```python
print("Feature names:", cancer.feature_names[:5])
imbalance_ratio = (y_clf == 0).sum() / (y_clf == 1).sum()
print("Imbalance ratio:", imbalance_ratio)
# ... (plot class distribution)
```

## Model Training and Evaluation (Classification)
Three classification models—Logistic Regression, Random Forest, and Gradient Boosting—are trained on the scaled Breast Cancer dataset. Their performance is evaluated using accuracy and confusion matrices.

```python
models = {
    'Logistic Regression': LogisticRegression(max_iter=1000),
    'Random Forest': RandomForestClassifier(n_estimators=100, random_state=42),
    'Gradient Boosting': GradientBoostingClassifier(n_estimators=100, random_state=42)
}

results = {}

for name, model in models.items():
    model.fit(X_train_c, y_train_c)
    y_pred = model.predict(X_test_c)
    accuracy = accuracy_score(y_test_c, y_pred)
    cm = confusion_matrix(y_test_c, y_pred)
    results[name] = {'model': model, 'y_pred': y_pred, 'accuracy': accuracy, 'cm': cm}
    print(f"{name} - Accuracy: {accuracy:.4f}")

# Visualize confusion matrices side by side
# ...
```

### Confusion Matrix Analysis

Specifically for Logistic Regression, the confusion matrix values (True Positives, True Negatives, False Positives, False Negatives) are extracted and displayed. The manual calculation of accuracy is also compared against the `accuracy_score` from `scikit-learn` to ensure consistency.

```python
log_reg_cm = results['Logistic Regression']['cm']
TN_lr = log_reg_cm[0][0]
FP_lr = log_reg_cm[0][1]
FN_lr = log_reg_cm[1][0]
TP_lr = log_reg_cm[1][1]

print("Logistic Regression - True Positives (TP):", TP_lr)
print("Logistic Regression - True Negatives (TN):", TN_lr)
print("Logistic Regression - False Positives (FP):", FP_lr)
print("Logistic Regression - False Negatives (FN):", FN_lr)

manual_accuracy_lr = (TP_lr + TN_lr) / (TP_lr + TN_lr + FP_lr + FN_lr)
sklearn_accuracy_lr = results['Logistic Regression']['accuracy']

print(f"Logistic Regression - Manual Accuracy: {manual_accuracy_lr:.4f}")
print(f"Logistic Regression - Scikit-learn Accuracy: {sklearn_accuracy_lr:.4f}")
```
