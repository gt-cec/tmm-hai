from sklearn.neural_network import MLPRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import numpy as np

# load the dataset
data = np.loadtxt('./dataset.txt', delimiter=',')

# parameters
num_class = 250
 
# balance the pairs
pot = data[data[:, 0] == 1, :]
pot_pot = pot[pot[:,9] == 1, :]
pot_soup = pot[pot[:,10] == 1, :]
pot_station = pot[pot[:,11] == 1, :]
pot_onion = pot[pot[:,12] == 1, :]
pot_tomato = pot[pot[:,13] == 1, :]
pot_pot = pot_pot[np.random.choice(pot_pot.shape[0], num_class, replace=False), :]
pot_soup = pot_soup[np.random.choice(pot_soup.shape[0], num_class, replace=False), :]
pot_station = pot_station[np.random.choice(pot_station.shape[0], num_class, replace=False), :]
pot_onion = pot_onion[np.random.choice(pot_onion.shape[0], num_class, replace=False), :]
pot_tomato = pot_tomato[np.random.choice(pot_tomato.shape[0], num_class, replace=False), :]

print("pot", pot_pot.shape, pot_soup.shape, pot_station.shape, pot_onion.shape, pot_tomato.shape)

soup = data[data[:, 1] == 1, :]
soup_pot = soup[soup[:,9] == 1, :]
soup_soup = soup[soup[:,10] == 1, :]
soup_station = soup[soup[:,11] == 1, :]
soup_onion = soup[soup[:,12] == 1, :]
soup_tomato = soup[soup[:,13] == 1, :]
soup_pot = soup_pot[np.random.choice(soup_pot.shape[0], num_class, replace=False), :]
soup_soup = soup_soup[np.random.choice(soup_soup.shape[0], num_class, replace=False), :]
soup_station = soup_station[np.random.choice(soup_station.shape[0], num_class, replace=False), :]
soup_onion = soup_onion[np.random.choice(soup_onion.shape[0], num_class, replace=False), :]
soup_tomato = soup_tomato[np.random.choice(soup_tomato.shape[0], num_class, replace=False), :]

print("soup", soup_soup.shape, soup_station.shape, soup_onion.shape, soup_tomato.shape)

station = data[data[:, 2] == 1, :]
station_pot = station[station[:,9] == 1, :]
station_soup = station[station[:,10] == 1, :]
station_station = station[station[:,11] == 1, :]
station_onion = station[station[:,12] == 1, :]
station_tomato = station[station[:,13] == 1, :]
station_pot = station_pot[np.random.choice(station_pot.shape[0], num_class, replace=False), :]
station_soup = station_soup[np.random.choice(station_soup.shape[0], num_class, replace=False), :]
station_station = station_station[np.random.choice(station_station.shape[0], num_class, replace=False), :]
station_onion = station_onion[np.random.choice(station_onion.shape[0], num_class, replace=False), :]
station_tomato = station_tomato[np.random.choice(station_tomato.shape[0], num_class, replace=False), :]

print("station", station_station.shape, station_onion.shape, station_tomato.shape)

onion = data[data[:, 3] == 1, :]
onion_pot = onion[onion[:,9] == 1, :]
onion_soup = onion[onion[:,10] == 1, :]
onion_station = onion[onion[:,11] == 1, :]
onion_onion = onion[onion[:,12] == 1, :]
onion_tomato = onion[onion[:,13] == 1, :]
onion_pot = onion_pot[np.random.choice(onion_pot.shape[0], num_class, replace=False), :]
onion_soup = onion_soup[np.random.choice(onion_soup.shape[0], num_class, replace=False), :]
onion_station = onion_station[np.random.choice(onion_station.shape[0], num_class, replace=False), :]
onion_onion = onion_onion[np.random.choice(onion_onion.shape[0], num_class, replace=False), :]
onion_tomato = onion_tomato[np.random.choice(onion_tomato.shape[0], num_class, replace=False), :]
print("onion", onion_onion.shape, onion_tomato.shape)

tomato = data[data[:, 4] == 1, :]
tomato_pot = tomato[tomato[:,9] == 1, :]
tomato_soup = tomato[tomato[:,10] == 1, :]
tomato_station = tomato[tomato[:,11] == 1, :]
tomato_onion = tomato[tomato[:,12] == 1, :]
tomato_tomato = tomato[tomato[:,13] == 1, :]
tomato_pot = tomato_tomato[np.random.choice(tomato_pot.shape[0], num_class, replace=False), :]
tomato_soup = tomato_soup[np.random.choice(tomato_soup.shape[0], num_class, replace=False), :]
tomato_station = tomato_station[np.random.choice(tomato_station.shape[0], num_class, replace=False), :]
tomato_onion = tomato_onion[np.random.choice(tomato_onion.shape[0], num_class, replace=False), :]
tomato_tomato = tomato_tomato[np.random.choice(tomato_tomato.shape[0], num_class, replace=False), :]
print("tomato", tomato_tomato.shape)

data = np.concatenate((pot_pot, pot_soup, pot_station, pot_onion, pot_tomato,
                       soup_pot, soup_soup, soup_station, soup_onion, soup_tomato,
                       station_pot, station_soup, station_station, station_onion, station_tomato,
                       onion_pot, onion_soup, onion_station, onion_onion, onion_tomato,
                       tomato_pot, tomato_soup, tomato_station, tomato_onion, tomato_tomato), axis=0)

print(data.shape)
  
# encoding: pot soup station onion tomato isCooking isReady isIdle numIngredients
#            0    1    2      3     4  
#            9    10   11     12    13

# split the data into train, test
X = data[:,:-1]
y = data[:,-1]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42) 

# create an MLP
regressor = MLPRegressor(hidden_layer_sizes = (512, 512, 512, 512, 512), max_iter = 10, random_state = 42, verbose = 2)
print("starting fit")
regressor.fit(X_train, y_train)
print("fit!")
y_pred = regressor.predict(X_test)
print("predicted!")
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
print(rmse)