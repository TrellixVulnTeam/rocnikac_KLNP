from collections import namedtuple, Set

import numpy as np
import alphashape
from skimage.metrics import mean_squared_error
from sklearn.linear_model import Ridge
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures

class Norm_data:

	def __init__(self, shapes, coor_times, day_times, ids_trip):
		assert len(shapes) == len(day_times) == len(coor_times) == len(ids_trip)
		self.data = np.array([shapes, coor_times, day_times, ids_trip])

	def get_shapes(self):
		return self.data[0]

	def get_coor_times(self):
		return self.data[1]

	def get_day_times(self):
		return self.data[2]

	def get_ids_trip(self):
		return self.data[3]

	def __len__(self):
		return self.data.shape[1]

	def __iter__(self):
		row = namedtuple('Row', 'shape coor_time day_time id_trip')
		for i in range(self.data.shape[1]):
			yield row(shape=self.get_shapes()[i],
					  coor_time=self.get_coor_times()[i],
					  day_time=self.get_day_times()[i],
					  id_trip=self.get_ids_trip()[i])

	def remove_items_by_id_trip(self, ids_trip: Set):
		indecies = []
		for i in range(len(self.data)):
			if self.get_ids_trip()[i] in ids_trip:
				indecies.append(i)

		transp = self.data.transpose()
		np.delete(transp, indecies)
		self.data = transp.transpose()
		assert len(self.data) == 4


class Super_model:
	def predict(self, norm_shape_dist_trv, update_time, departure_time, arrival_time):
		pass

	def predict_standard(self, norm_shape_dist_trv, update_time):
		pass

	def get_name(self):
		pass


# model returns normal delay as a trip at departure stop has no delay

class Two_stops_model:

	class Linear_model(Super_model):

		# distance between the stops, time between the stops
		def __init__(self, distance):
			self.distance = distance

		# distance traveled from departure stop, all in seconds
		def predict(self, norm_shape_dist_trv, update_time, departure_time, arrival_time):
			time_diff = arrival_time - departure_time
			norm_update_time = update_time - arrival_time

			ratio = norm_shape_dist_trv / self.distance
			estimated_time_progress = time_diff * ratio
			return norm_update_time - estimated_time_progress

		def predict_standard(self, norm_shape_dist_trv, update_time):
			print("should not occurs")
			pass


		def get_name(self):
			return "Linear"


	class Polynomial_model(Super_model):

		def __init__(self, distance, norm_data: Norm_data):
			self.norm_data = norm_data
			self.distance = distance
			self.min_day_time = min(self.norm_data.get_day_times())
			self.max_day_time = max(self.norm_data.get_day_times())
			self._train_model()

		def _train_model(self):
			input_data = np.array([self.norm_data.get_shapes(), self.norm_data.get_day_times()]).transpose()
			input_data = np.pad(input_data, ((0, 0), (0, 1)), constant_values=1)

			output_data = np.array(self.norm_data.get_coor_times())

			X_train, X_test, y_train, y_test = train_test_split(input_data, output_data, test_size=0.33, random_state=42)

			best_degree = 3
			best_error = float('inf')  # maxint

			for degree in [3, 4, 5, 6, 7, 8, 9, 10]:
				model = make_pipeline(PolynomialFeatures(degree), Ridge())
				model.fit(X_train, y_train)
				pred = model.predict(X_test)
				error = mean_squared_error(y_test, pred)
				if error < best_error:
					best_degree = degree
					best_error = error
				# print("Deg:", degree, "Err", error)

			self.model = make_pipeline(PolynomialFeatures(best_degree), Ridge())
			self.model.fit(input_data, output_data)
			pred = self.model.predict(input_data)
			self.rmse = mean_squared_error(output_data, pred)

			del self.norm_data  # deletes norm data structure because it is no more needed

		def predict(self, norm_shape_dist_trv, update_time, departure_time, arrival_time):
			if self.max_day_time < update_time:  # if in estimator area
				update_time = self.max_day_time

			if self.min_day_time > update_time:
				update_time = self.min_day_time

			time_diff = arrival_time - departure_time
			norm_update_time = update_time - departure_time

			input_data = np.pad(np.array([norm_shape_dist_trv, update_time]).T, ((0, 0), (0, 1)), constant_values=1)
			prediction = self.model.predict(input_data)  # estimation of coor time
			arrival_data = np.pad(np.array([self.distance, arrival_time]).T, ((0, 0), (0, 1)), constant_values=1)
			model_delay = self.model.predict(arrival_data) - time_diff  # no of seconds difference between scheduled arrival and model estimation
			return model_delay + norm_update_time - prediction

		def predict_standard(self, norm_shape_dist_trv, update_time):
			input_data = np.pad(np.array([norm_shape_dist_trv, update_time]).T, ((0, 0), (0, 1)), constant_values=1)
			return self.model.predict(input_data)

		def get_rmse(self):
			return self.rmse

		def get_name(self):
			return "Poly"

	class Concave_hull_model(Super_model):

		def __init__(self, distance, norm_data):
			self.norm_data = norm_data
			self.distance = distance
			self.min_day_time = min(self.norm_data.get_day_times())
			self.max_day_time = max(self.norm_data.get_day_times())
			self._train_model()

		def _train_model(self):
			last_data_before_arrival = {}
			for row in self.norm_data:
				if 30 < self.distance - row.shape < 200:
					if row.id_trip not in last_data_before_arrival:
						last_data_before_arrival[row.id_trip] = [row.coor_time, row.day_time]
					elif last_data_before_arrival[row.id_trip][0] < row.coor_time:
						last_data_before_arrival[row.id_trip] = [row.coor_time, row.day_time]

			if len(last_data_before_arrival) < (self.max_day_time - self.min_day_time) / 3600 * 0.7:
				print(len(last_data_before_arrival), (self.max_day_time - self.min_day_time) / 3600 * 1)
				raise RuntimeError("not enough data for hull")

			# for k, v in last_data_before_arrival.items():
			#
			# 	print([v[0], v[1], k])

			last_data_before_arrival = [[v[0], v[1], k] for k, v in last_data_before_arrival.items()]

			input_data = np.array([last_data_before_arrival]).transpose()[1]  # takes day times from data array
			input_data = np.pad(input_data, ((0, 0), (0, 1)), constant_values=1)

			output_data = np.array([last_data_before_arrival]).transpose()[0]

			# last_data_before_arrival = last_data_before_arrival[0]  # for some reason np.array consume array in one element array only

			X_train, X_test, y_train, y_test = train_test_split(input_data, output_data, test_size=0.33, random_state=42)

			best_degree = 1
			best_error = float('inf')  # maxint

			for degree in [1, 3, 4, 5, 6, 7, 8, 9, 10]:
				model = make_pipeline(PolynomialFeatures(degree), Ridge())
				model.fit(X_train, y_train)
				pred = model.predict(X_test)
				error = mean_squared_error(y_test, pred)
				if error < best_error:
					best_degree = degree
					best_error = error
			# print("Deg:", degree, "Err", error)

			# TODO unself
			self.model_arrivals = make_pipeline(PolynomialFeatures(best_degree), Ridge())
			self.model_arrivals.fit(input_data, output_data)

			last_data_before_arrival.sort(key=lambda x: x[1], reverse=False)  # sort by date time

			self.points_of_concave_hull = []
			all_usable_trips = set()
			current_index_start = 0
			current_index_stop = 0

			for hour in range(int((self.max_day_time - self.min_day_time) / 3600 + 3600)):  # for each hour
				for i in range(len(last_data_before_arrival[current_index_start:])):
					if last_data_before_arrival[current_index_start + i][1] > self.min_day_time + hour * 3600 + 3600:
						current_index_stop = current_index_start + i
						break

				trips_of_this_hour = last_data_before_arrival[
									 current_index_start: current_index_stop]  # .sort(key=lambda x: x[0], reverse=True)
				current_index_start = current_index_stop
				estimated_arrival = float(self.model_arrivals.predict([[self.min_day_time + 3600 * hour + 3600 / 2, 1]])[0])

				for i in range(len(trips_of_this_hour)):
					trips_of_this_hour[i].append(abs(estimated_arrival - trips_of_this_hour[i][0]))

				trips_of_this_hour.sort(key=lambda x: x[3], reverse=False)

				if len(trips_of_this_hour) < 3:
					all_usable_trips.update(x[2] for x in trips_of_this_hour)
				else:
					all_usable_trips.update(x[2] for x in trips_of_this_hour[:int(len(trips_of_this_hour) * 0.7) + 1])

			for hour in range(int((self.max_day_time - self.min_day_time) / 3600 + 3600)):  # for each hour
				all_points_of_this_hour = []
				for row in self.norm_data:
					if row.id_trip in all_usable_trips and self.min_day_time + hour * 3600 < row.day_time < self.min_day_time + hour * 3600 + 3600:
						all_points_of_this_hour.append([row.coor_time, row.shape])
				if len(all_points_of_this_hour) != 0:
					self.points_of_concave_hull.extend([self.min_day_time + hour * 3600 + 3600/30, x[0], x[1]] for x in list(alphashape.alphashape(all_points_of_this_hour).exterior.coords))






		def has_enough_data(self):
			pass

		# now for arrivals curve, remake for regular model
		def predict_standard(self, norm_shape_dist_trv, update_time):
			pass

		def predict_nonstandard(self, day_times):
			input_data = np.array([day_times, np.full(len(day_times), 1)]).transpose()
			return self.model_arrivals.predict(input_data)

		def predict(self, norm_shape_dist_trv, update_time, departure_time, arrival_time):
			pass

		def get_name(self):
			return "Hull"



	# norm_data is dict of shapes, coor_times ands day_times, ids_trip
	def __init__(self, dep_id_stop: str, arr_id_stop: str, distance: int, max_travel_time: int, shapes, coor_times, day_times, ids_trip):
		self.dep_id_stop = dep_id_stop
		self.arr_id_stop = arr_id_stop
		self.distance = distance
		self.norm_data = Norm_data(shapes, coor_times, day_times, ids_trip)
		self.max_travel_time = max_travel_time
		self._create_model()

	def _reduce_errors(self):

		remove_alpha = 2
		trips_to_remove = set()
		for row in self.norm_data:
			if row.shape > self.distance - 200:  # 200 m to arrival stop
				if row.coor_time > self.max_travel_time * remove_alpha:
					trips_to_remove.add(row.id_trip)

		self.norm_data.remove_items_by_id_trip(trips_to_remove)


	def _create_model(self):
		# linear -> < 2000 m, pocet dat alespon 10 na kilometr a 4 spoje denne
		self._reduce_errors()
		poly_model = Two_stops_model.Polynomial_model(self.distance, self.norm_data)
		rmse_aplha = 0.2
		print("rmse:", poly_model.get_rmse(), "dist * alpha:", self.distance * rmse_aplha)

		if self.distance < 1500 or len(self.norm_data) < self.distance * 0.0001 * 9 * 4:  # 9 samples per km, 4 times a day:
			self.model = Two_stops_model.Linear_model(self.distance)
			print("less than 2 km or not enough data")
		else:  # creates poly model and if rmse is not acceptable it creates hull model
			poly_model = Two_stops_model.Polynomial_model(self.distance, self.norm_data)

			if poly_model.get_rmse() < self.distance * rmse_aplha:
				self.model = poly_model
			else:
				try:
					self.model = Two_stops_model.Concave_hull_model(self.distance, self.norm_data)
				except RuntimeError as e:
					print(self.dep_id_stop, self.arr_id_stop)
					raise e

	def get_model(self) -> Super_model:
		return self.model