import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.signal import find_peaks

CSV = Path('sakshi_rr_intervals_20260611T074737_len128s.csv')
ART = Path(__file__).parent / 'artifacts'
ART.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(CSV)
cols = list(df.columns)
print('Columns in CSV:', cols)

# Use IR/Red if present, otherwise use rr_ms and weight as proxies
if 'IR' in df.columns and 'Red' in df.columns:
    a = df['IR'].astype(float)
    b = df['Red'].astype(float)
    a_name = 'IR'
    b_name = 'Red'
else:
    a = df['rr_ms'].astype(float)
    b = df['weight'].astype(float)
    a_name = 'rr_ms'
    b_name = 'weight'

# Create datetime index from mid_elapsed_ms if available
if 'mid_elapsed_ms' in df.columns:
    idx = pd.to_datetime(df['mid_elapsed_ms'], unit='ms')
else:
    idx = pd.RangeIndex(start=0, stop=len(df))

a.index = idx
b.index = idx

# Min-max normalization
a_min = (a - a.min()) / (a.max() - a.min() + 1e-12)
b_min = (b - b.min()) / (b.max() - b.min() + 1e-12)
plt.figure(figsize=(12,4))
plt.plot(a_min.index, a_min, label=f'{a_name} (min-max)')
plt.plot(b_min.index, b_min, label=f'{b_name} (min-max)')
plt.legend()
plt.title(f'{a_name} vs {b_name} (Min-Max Normalized)')
plt.savefig(ART / f'{a_name}_{b_name}_minmax.png')
plt.close()

# Z-score standardization
a_z = (a - a.mean()) / (a.std() + 1e-12)
b_z = (b - b.mean()) / (b.std() + 1e-12)
plt.figure(figsize=(12,4))
plt.plot(a_z.index, a_z, label=f'{a_name} (z-score)')
plt.plot(b_z.index, b_z, label=f'{b_name} (z-score)')
plt.legend()
plt.title(f'{a_name} vs {b_name} (Z-score Standardized)')
plt.savefig(ART / f'{a_name}_{b_name}_zscore.png')
plt.close()

# Peak detection on z-score series
try:
    vals_a = a_z.fillna(0).values
    vals_b = b_z.fillna(0).values
    peaks_a, prop_a = find_peaks(vals_a, height=0)
    peaks_b, prop_b = find_peaks(vals_b, height=0)

    # Save plot with peaks marked
    plt.figure(figsize=(12,4))
    plt.plot(a_z.index, a_z, label=f'{a_name} (z-score)')
    plt.plot(b_z.index, b_z, label=f'{b_name} (z-score)')
    if len(peaks_a) > 0:
        plt.scatter(a_z.index[peaks_a], a_z.values[peaks_a], c='C0', s=30, marker='x', label=f'{a_name} peaks')
    if len(peaks_b) > 0:
        plt.scatter(b_z.index[peaks_b], b_z.values[peaks_b], c='C1', s=30, marker='o', label=f'{b_name} peaks')
    plt.title(f'{a_name} vs {b_name} (Z-score) with Peaks)')
    plt.legend()
    plt.savefig(ART / f'{a_name}_{b_name}_zscore_peaks.png')
    plt.close()

    # Save peaks as CSV
    rows = []
    for i in peaks_a:
        rows.append({'timestamp': str(a_z.index[i]), 'series': a_name, 'value': float(a_z.values[i])})
    for i in peaks_b:
        rows.append({'timestamp': str(b_z.index[i]), 'series': b_name, 'value': float(b_z.values[i])})
    peaks_df = pd.DataFrame(rows).sort_values(['timestamp', 'series'])
    peaks_df.to_csv(ART / f'{a_name}_{b_name}_peaks.csv', index=False)
    print('Saved peaks CSV to', ART / f'{a_name}_{b_name}_peaks.csv')
except Exception as e:
    print('Peak detection failed:', e)

print('Saved superimposed plots to', ART)
