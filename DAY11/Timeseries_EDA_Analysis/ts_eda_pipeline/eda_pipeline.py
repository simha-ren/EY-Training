import argparse
import os
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.stattools import adfuller, kpss
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.tsa.arima.model import ARIMA
from scipy.signal import find_peaks
from sklearn.metrics import mean_absolute_error, mean_squared_error

ARTIFACTS = Path(__file__).parent / 'artifacts'
ARTIFACTS.mkdir(parents=True, exist_ok=True)


def load_data(path):
    df = pd.read_csv(path)
    return df


def profile(df):
    print('Columns:', list(df.columns))
    print('Shape:', df.shape)
    print(df.describe())


def prepare_index(df):
    # Use mid_elapsed_ms (ms) as time index; convert to datetime anchored at 1970-01-01
    if 'mid_elapsed_ms' in df.columns:
        df = df.copy()
        df['datetime'] = pd.to_datetime(df['mid_elapsed_ms'], unit='ms')
        df = df.set_index('datetime')
        return df
    else:
        raise ValueError('mid_elapsed_ms not found')


def check_time_continuity(df):
    diffs = df.index.to_series().diff().dropna().dt.total_seconds() * 1000
    median_ms = diffs.median()
    gaps = diffs[diffs > 1.5 * median_ms]
    result = {
        'median_interval_ms': float(median_ms),
        'n_gaps': int(len(gaps)),
        'gaps_ms_sample': gaps.head().tolist()
    }
    return result


def handle_missing(df, method='interpolate'):
    missing_pct = df.isna().mean() * 100
    if method == 'ffill':
        df_filled = df.ffill()
    else:
        df_filled = df.interpolate(method='time').bfill().ffill()
    return df_filled, missing_pct


def resample_even(df):
    diffs = df.index.to_series().diff().dropna().dt.total_seconds() * 1000
    median_ms = int(round(diffs.median()))
    rule = f'{median_ms}ms'
    rs = df.resample(rule).mean()
    rs = rs.interpolate()
    return rs, median_ms


def estimate_period_from_fft(series, median_ms):
    y = series.values - np.nanmean(series.values)
    N = len(y)
    Fs = 1000.0 / median_ms
    freqs = np.fft.rfftfreq(N, d=1.0 / Fs)
    fft = np.abs(np.fft.rfft(y))
    if len(fft) < 3:
        return None
    idx = np.argmax(fft[1:]) + 1
    peak_freq = freqs[idx]
    if peak_freq <= 0:
        return None
    period_seconds = 1.0 / peak_freq
    period_samples = max(1, int(round(period_seconds * Fs)))
    return period_samples


def decompose_series(series, period):
    if period is None or period < 2:
        trend = series.rolling(window=max(3, int(len(series)*0.05)), center=True, min_periods=1).mean()
        resid = series - trend
        seasonal = series - trend - resid
        return trend, seasonal, resid
    stl = STL(series, period=period, robust=True)
    res = stl.fit()
    return res.trend, res.seasonal, res.resid


def detect_outliers(resid):
    z = (resid - np.nanmean(resid)) / (np.nanstd(resid) + 1e-12)
    outliers = np.where(np.abs(z) > 3)[0]
    return outliers, z


def stationarity_tests(series):
    adf_res = adfuller(series.dropna(), autolag='AIC')
    kpss_res = kpss(series.dropna(), regression='c', nlags='auto')
    return adf_res, kpss_res


def plot_series(df, column='rr_ms'):
    plt.figure(figsize=(12,4))
    plt.plot(df.index, df[column], label=column)
    plt.title('Time Series')
    plt.xlabel('time')
    plt.ylabel(column)
    plt.legend()
    out = ARTIFACTS / 'time_series.png'
    plt.savefig(out)
    plt.close()
    return out


def plot_acf_pacf(series):
    fig1 = plt.figure(figsize=(10,4))
    plot_acf(series.dropna(), ax=plt.gca(), lags=50)
    out1 = ARTIFACTS / 'acf.png'
    plt.savefig(out1)
    plt.close()

    fig2 = plt.figure(figsize=(10,4))
    plot_pacf(series.dropna(), ax=plt.gca(), lags=50, method='ywm')
    out2 = ARTIFACTS / 'pacf.png'
    plt.savefig(out2)
    plt.close()
    return out1, out2


def boxplots(df):
    if df.index.max() - df.index.min() < pd.Timedelta(days=1):
        # dataset too short for monthly/weekly; create boxplot by second-of-minute
        df['sec'] = df.index.second
        plt.figure(figsize=(10,4))
        sns.boxplot(x='sec', y='rr_ms', data=df.reset_index())
        out = ARTIFACTS / 'boxplot_sec.png'
        plt.savefig(out)
        plt.close()
        return [out]
    else:
        df['month'] = df.index.month
        df['weekday'] = df.index.day_name()
        outm = ARTIFACTS / 'boxplot_month.png'
        outw = ARTIFACTS / 'boxplot_weekday.png'
        plt.figure(figsize=(8,4))
        sns.boxplot(x='month', y='rr_ms', data=df.reset_index())
        plt.savefig(outm); plt.close()
        plt.figure(figsize=(8,4))
        sns.boxplot(x='weekday', y='rr_ms', data=df.reset_index())
        plt.savefig(outw); plt.close()
        return [outm, outw]


def compute_basic_stats(series):
    mean = float(np.nanmean(series))
    std = float(np.nanstd(series))
    mode = None
    try:
        mode = float(stats.mode(series.dropna(), nan_policy='omit').mode[0])
    except Exception:
        mode = None
    return mean, std, mode


def forecast_next_seconds(series, median_ms, seconds=30):
    # naive forecast: last-value carry forward with simple moving-average baseline
    Fs = 1000.0 / median_ms
    n_steps = int(round(seconds * Fs))
    last = series.dropna().iloc[-1]
    pred = np.repeat(last, n_steps)
    return pred


def forecast_arima(series, median_ms, seconds=30, max_p=2, max_q=2):
    Fs = 1000.0 / median_ms
    n_steps = int(round(seconds * Fs))
    series_clean = series.dropna()
    if n_steps < 1 or len(series_clean) < 10:
        return None, None, None
    n_train = max(5, len(series_clean) - n_steps)
    train = series_clean.iloc[:n_train]
    test = series_clean.iloc[n_train:n_train + n_steps]

    best_aic = np.inf
    best_order = None
    best_model = None
    for p in range(0, max_p + 1):
        for d in (0, 1):
            for q in range(0, max_q + 1):
                try:
                    model = ARIMA(train, order=(p, d, q)).fit()
                    if model.aic < best_aic:
                        best_aic = model.aic
                        best_order = (p, d, q)
                        best_model = model
                except Exception:
                    continue

    if best_model is None:
        return None, None, None

    try:
        fc = best_model.forecast(steps=n_steps)
    except Exception:
        fc = best_model.predict(start=len(train), end=len(train) + n_steps - 1)

    mae = float(mean_absolute_error(test, fc))
    rmse = float(np.sqrt(mean_squared_error(test, fc)))
    return fc.values, mae, rmse


def save_cot(step_name, hypothesis, reasoning, code_snippet, interpretation):
    p = ARTIFACTS / f'cot_{step_name}.txt'
    with open(p, 'w') as f:
        f.write('Hypothesis/Objective:\n')
        f.write(hypothesis + '\n\n')
        f.write('Reasoning & Approach:\n')
        f.write(reasoning + '\n\n')
        f.write('Python Code/Action:\n')
        f.write(code_snippet + '\n\n')
        f.write('Interpretation Guide:\n')
        f.write(interpretation + '\n')
    return p


def main(args):
    df = load_data(args.input)
    profile(df)
    df = prepare_index(df)
    continuity = check_time_continuity(df)
    print('Continuity:', continuity)
    df_filled, missing_pct = handle_missing(df)
    print('Missing % per column:\n', missing_pct)
    rs, median_ms = resample_even(df_filled)
    print('Median sampling interval (ms):', median_ms)

    # series
    if 'rr_ms' in rs.columns:
        series = rs['rr_ms']
    else:
        # fallback to weight
        series = rs.iloc[:, -1]

    mean, std, mode = compute_basic_stats(series)
    print('mean,std,mode:', mean, std, mode)

    ps = estimate_period_from_fft(series, median_ms)
    print('Estimated period (samples):', ps)

    trend, seasonal, resid = decompose_series(series, ps)
    out_trend = ARTIFACTS / 'trend.png'
    plt.figure(figsize=(12,4))
    plt.plot(series.index, series, label='series')
    plt.plot(series.index, trend, label='trend')
    plt.legend(); plt.savefig(out_trend); plt.close()

    out_season = ARTIFACTS / 'seasonal.png'
    plt.figure(figsize=(12,4))
    plt.plot(series.index, seasonal, label='seasonal')
    plt.legend(); plt.savefig(out_season); plt.close()

    out_resid = ARTIFACTS / 'resid.png'
    plt.figure(figsize=(12,4))
    plt.plot(series.index, resid, label='residual')
    plt.legend(); plt.savefig(out_resid); plt.close()

    out_acf, out_pacf = plot_acf_pacf(series)
    out_box = boxplots(rs)

    # Correlation matrix heatmap for numeric columns
    try:
        numeric = rs.select_dtypes(include=[np.number])
        corr = numeric.corr()
        plt.figure(figsize=(6,5))
        sns.heatmap(corr, annot=True, fmt='.2f', cmap='vlag', vmin=-1, vmax=1)
        out_corr = ARTIFACTS / 'correlation.png'
        plt.title('Correlation matrix')
        plt.savefig(out_corr)
        plt.close()
        # Rolling correlation between rr_ms and weight if present
        if 'rr_ms' in numeric.columns and 'weight' in numeric.columns:
            roll_corr = numeric['rr_ms'].rolling(window=max(3, int(len(numeric)*0.05))).corr(numeric['weight'])
            plt.figure(figsize=(10,3))
            plt.plot(roll_corr.index, roll_corr.values)
            plt.title('Rolling correlation rr_ms vs weight')
            plt.savefig(ARTIFACTS / 'rolling_corr_rr_weight.png')
            plt.close()
    except Exception:
        pass

    outliers, z = detect_outliers(resid)
    print('Outliers count:', len(outliers))

    adf_res, kpss_res = stationarity_tests(series)
    print('ADF p-value:', adf_res[1])
    print('KPSS p-value:', kpss_res[1])

    # Forecast
    # First attempt ARIMA forecast (walk-forward holdout on last N samples)
    arima_pred, mae, rmse = forecast_arima(series, median_ms, seconds=30)
    if arima_pred is not None:
        np.save(ARTIFACTS / 'forecast_arima_pred.npy', arima_pred)
        with open(ARTIFACTS / 'forecast_arima_metrics.txt', 'w') as f:
            f.write(f'MAE: {mae}\nRMSE: {rmse}\n')
        print('ARIMA forecast MAE,RMSE:', mae, rmse)
    else:
        pred = forecast_next_seconds(series, median_ms, seconds=30)
        np.save(ARTIFACTS / 'forecast_pred.npy', pred)

    # Superimpose IR and Red if present
    if 'IR' in rs.columns and 'Red' in rs.columns:
        ir_raw = rs['IR'].astype(float)
        red_raw = rs['Red'].astype(float)
        # Min-max normalization to [0,1]
        ir_min = (ir_raw - ir_raw.min()) / (ir_raw.max() - ir_raw.min() + 1e-12)
        red_min = (red_raw - red_raw.min()) / (red_raw.max() - red_raw.min() + 1e-12)
        plt.figure(figsize=(12,4))
        plt.plot(ir_min.index, ir_min, label='IR (min-max)')
        plt.plot(red_min.index, red_min, label='Red (min-max)')
        plt.title('IR vs Red (Min-Max Normalized)')
        plt.legend()
        plt.savefig(ARTIFACTS / 'ir_red_minmax.png')
        plt.close()

        # Z-score standardization
        ir_z = (ir_raw - ir_raw.mean()) / (ir_raw.std() + 1e-12)
        red_z = (red_raw - red_raw.mean()) / (red_raw.std() + 1e-12)
        plt.figure(figsize=(12,4))
        plt.plot(ir_z.index, ir_z, label='IR (z-score)')
        plt.plot(red_z.index, red_z, label='Red (z-score)')
        plt.title('IR vs Red (Z-score Standardized)')
        plt.legend()
        plt.savefig(ARTIFACTS / 'ir_red_zscore.png')
        plt.close()

        # Optional: mark peaks on the standardized plot for visualizing peak alignment
        try:
            peaks_ir, _ = find_peaks(ir_z.fillna(0).values, height=0)
            peaks_red, _ = find_peaks(red_z.fillna(0).values, height=0)
            plt.figure(figsize=(12,4))
            plt.plot(ir_z.index, ir_z, label='IR (z-score)')
            plt.plot(red_z.index, red_z, label='Red (z-score)')
            plt.scatter(ir_z.index[peaks_ir], ir_z.values[peaks_ir], c='C0', s=30, marker='x')
            plt.scatter(red_z.index[peaks_red], red_z.values[peaks_red], c='C1', s=30, marker='o')
            plt.title('IR vs Red (Z-score) with Peaks')
            plt.legend()
            plt.savefig(ARTIFACTS / 'ir_red_zscore_peaks.png')
            plt.close()
        except Exception:
            pass

    # Save cot note for step 1
    save_cot('profile', 'Profile dataset columns and size', 'Use pandas describe and head to inspect types and ranges', "df.head(); df.describe()", 'Review shapes and null counts')
    save_cot('time_continuity', 'Check for missing timestamps/gaps', f"Computed median interval {median_ms} ms and gaps: {continuity['n_gaps']}", "check_time_continuity(df)", 'Large gaps indicate dropped samples or sensor pauses')
    save_cot('missing_values', 'Identify and choose imputation', 'Use time-based interpolation then backfill/ffill for edge values', "df.interpolate(method='time'); df.bfill().ffill()", 'If seasonality exists prefer interpolation; if sudden shifts, consider LOCF')
    save_cot('decomposition', 'Decompose into trend/seasonal/residual', f"Estimated period={ps}", "STL or rolling mean", 'Trend shows long-term direction; residuals used for outlier detection')
    save_cot('stationarity', 'Run ADF and KPSS', 'ADF null: unit root present; KPSS null: stationarity', "adfuller(series); kpss(series)", 'Use differencing/log if non-stationary')
    save_cot('forecasting', 'Forecast next 30s using ARIMA with holdout', 'Select ARIMA by AIC on small grid and compute MAE/RMSE on holdout', "ARIMA(train, order=(p,d,q)).fit().forecast(steps)", 'MAE/RMSE indicate short-term predictive performance')

    print('Artifacts saved to', ARTIFACTS)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True)
    args = p.parse_args()
    main(args)
