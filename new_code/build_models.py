#!/usr/bin/env python3

from database import Database

from two_stops_model import Two_stops_model

class Build_models:
	## Builds models of rides between all pairs of stops

	def __init__(self):
		self.database_connection = Database()

	@staticmethod
	def time_to_sec(timed):
		return timed.time().hour * 3600 + timed.time().minute * 60 + timed.time().second  # + 3600

	@staticmethod
	def is_business_day(date):
		day_of_week = date.weekday()
		if 0 <= day_of_week < 5:
			return True
		return False

	def main(self):
		## Selects all trip_coordinates from the database and splits it into separated models

		stop_to_stop_data = self.database_connection.execute_fetchall(
			"""	SELECT schedule.id_trip,
					schedule.id_stop,
					schedule.lead_stop, 
					departure_time, 
					schedule.lead_stop_departure_time, 
					(schedule.lead_stop_shape_dist_traveled - schedule.shape_dist_traveled) 
						AS diff_shape_trav, 
					trip_coordinates.inserted, 
					(trip_coordinates.shape_dist_traveled - schedule.shape_dist_traveled) 
						AS shifted_shape_trav, 
					trip_coordinates.delay 
				FROM (
					SELECT id_trip, id_stop, shape_dist_traveled, departure_time, 
						LEAD(id_stop, 1) OVER (
							PARTITION BY id_trip ORDER BY shape_dist_traveled) lead_stop, 
						LEAD(shape_dist_traveled, 1) OVER (
							PARTITION BY id_trip ORDER BY shape_dist_traveled) lead_stop_shape_dist_traveled, 
						LEAD(departure_time, 1) OVER (
							PARTITION BY id_trip ORDER BY shape_dist_traveled) lead_stop_departure_time 
					FROM rides) AS schedule 
				JOIN trip_coordinates 
				ON trip_coordinates.id_trip = schedule.id_trip AND 
					schedule.lead_stop_shape_dist_traveled - schedule.shape_dist_traveled > 1500 AND 
					trip_coordinates.shape_dist_traveled BETWEEN schedule.shape_dist_traveled AND 
					schedule.lead_stop_shape_dist_traveled 
				ORDER BY id_stop, lead_stop, shifted_shape_trav"""
		)
		## This query selects all pairs of stops, the second leads the first,
		# by schedule and joins trip coordinates.
		# It order the result by id_stop and id_leading_stop

		# no data fetched
		if len(stop_to_stop_data) <= 0:
			# return TODO
			pass

		# For all stops pairs two models are created (business days and nonbusiness days)
		# dep stop id, arr stop id, distance between stops
		business_day_model = Two_stops_model(None, None, None)
		nonbusiness_day_model = Two_stops_model(None, None, None)


		for sts_row in stop_to_stop_data:

			# Because of ordered result all stop pairs coordinates are sorted in row by stops,
			# if new stop pair found a new model pair is created
			if nonbusiness_day_model.dep_id_stop == business_day_model.dep_id_stop == sts_row[1] and \
					nonbusiness_day_model.arr_id_stop == business_day_model.arr_id_stop == sts_row[2]:
				if Build_models.is_business_day(sts_row[6]):
					business_day_model.add_row(
						sts_row[7],  		# shape distance traveled from dep stop
						sts_row[3].seconds, # departure time
						Build_models.time_to_sec(sts_row[6]),  # day time
						sts_row[0],  		# id trip
						sts_row[4],  		# arr time
						sts_row[8])  		# delay
				else:
					nonbusiness_day_model.add_row(
						sts_row[7],
						sts_row[3].seconds,
						Build_models.time_to_sec(sts_row[6]),
						sts_row[0],
						sts_row[4],
						sts_row[8])

			else:
				business_day_model.create_model()
				business_day_model.save_model()
				business_day_model = Two_stops_model(
					sts_row[1],  # dep stop id
					sts_row[2],  # arr stop id
					sts_row[5]   # distance between stops
				)

				nonbusiness_day_model.save_model()
				nonbusiness_day_model.create_model()
				nonbusiness_day_model = Two_stops_model(
					sts_row[1],
					sts_row[2],
					sts_row[5]
				)
