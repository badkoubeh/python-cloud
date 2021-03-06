import sys
import warnings
from datetime import datetime, timedelta
import itertools
import pandas as pd
# import numpy as np
import matplotlib.pyplot as plt
from pyspark.sql.functions import pandas_udf, PandasUDFType
from statsmodels.tsa.arima_model import ARIMA
import statsmodels.api as sm
from statsmodels.tsa.api import ExponentialSmoothing, SimpleExpSmoothing, Holt
from statsmodels.tsa.seasonal import seasonal_decompose
from sklearn.metrics import mean_squared_error

# from statsmodels.tsa.arima.model import ARIMA

warnings.simplefilter(action='ignore', category=FutureWarning)


# evaluate an ARIMA model for a given order (p,d,q)
# refrence: https://machinelearningmastery.com/grid-search-arima-hyperparameters-with-python/
def evaluate_arima_model(X, arima_order):
    # prepare training dataset
    train_size = int(len(X) * 0.66)
    train, test = X[0:train_size], X[train_size:]
    history = [x for x in train]
    # make predictions
    predictions = list()
    for t in range(len(test)):
        model = ARIMA(history, order=arima_order)
        model_fit = model.fit(disp=0)
        yhat = model_fit.forecast()[0]
        predictions.append(yhat)
        history.append(test[t])
    # calculate out of sample error
    error = mean_squared_error(test, predictions)
    return error


# evaluate combinations of p, d and q values for an ARIMA model
def evaluate_models(dataset, p_values, d_values, q_values):
    dataset = dataset.astype('float32')
    best_score, best_cfg = float("inf"), None
    for p in p_values:
        for d in d_values:
            for q in q_values:
                order = (p, d, q)
                try:
                    mse = evaluate_arima_model(dataset, order)
                    if mse < best_score:
                        best_score, best_cfg = mse, order
                    print('ARIMA%s MSE=%.3f' % (order, mse))
                except:
                    continue
    print('Best ARIMA%s MSE=%.3f' % (best_cfg, best_score))


df = pd.read_parquet('sensor_data_ts')
df = df[['datetime', 'H2S', 'CO', 'LEL', 'O2']]

ts = df.set_index(pd.DatetimeIndex(df['datetime']), drop=True)

ts_train = ts['H2S'].loc[ts.index < datetime(2019, 7, 1)]

ts_train = ts_train.resample('30T').mean().ffill()

# remove outliers
# ts_train = ts_train[ts_train.between(ts_train.quantile(.05), ts_train.quantile(.95))]

x_train = ts_train.loc[ts_train.index < datetime(2019, 6, 1)]
x_val = ts_train.loc[ts_train.index >= datetime(2019, 6, 1)]


# evaluate parameters
p_values = [4, 6, 8, 10]
d_values = range(1, 3)
q_values = range(0, 3)
warnings.filterwarnings("ignore")
# evaluate_models(ts_col.values, p_values, d_values, q_values)

model_fit = ARIMA(x_train, order=(1, 1, 1)).fit()
# model_fit = Holt(ts_col, initialization_method="estimated").fit()
# model_fit = ExponentialSmoothing(ts_col, initialization_method="estimated").fit()

# print(model_fit.summary())
num_forecast_steps = x_val.count()
# forecast_res = model_fit.forecast(num_forecast_steps)
forecast_res, stderr, conf_int = model_fit.forecast(num_forecast_steps, alpha=0.05)
forecast_series = pd.Series(forecast_res, index=x_val.index)
lower_series = pd.Series(conf_int[:, 0], index=x_val.index)
upper_series = pd.Series(conf_int[:, 1], index=x_val.index)
output = pd.DataFrame({'O2': forecast_series})

plt.figure(figsize=(12, 5), dpi=100)
plt.plot(x_train, label='training')
plt.plot(x_val, label='actual')
plt.plot(forecast_series, label='forecast')
plt.fill_between(lower_series.index, lower_series, upper_series, color='k', alpha=.15)
plt.title('Forecast vs Actuals')
plt.legend(loc='upper left', fontsize=8)
# plt.show()

result = seasonal_decompose(x_train, model='additive', freq=365)
result.plot()
plt.show()
