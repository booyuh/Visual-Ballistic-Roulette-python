from __future__ import print_function

import time

from flask import Flask, Response
from flask_restful import Resource, Api, reqparse

from SessionManager import *
from computations.predictor import PredictorInterface
from computations.utils.Helper import *
from database.DatabaseAccessor import *


def current_time_millis():
    return int(round(time.time() * 1000))


class Parameters(object):
    #  Request
    TIME = "ts"
    TYPE = "type"

    #  Response
    SESSION_ID = "sessionid"
    OUTCOME = "outcome"
    TYPE_WHEEL = "wheel"
    TYPE_BALL = "ball"


app = Flask(__name__)
api = Api(app)

sm = SessionManager()
da = DatabaseAccessor()
sm.init(da)

pr = PredictorInterface.PredictorPhysicsConstantDeceleration()


def predict_most_probable_number(session_id):
    wheel_cumsum_times = da.select_wheel_lap_times(session_id)
    ball_cumsum_times = da.select_ball_lap_times(session_id)

    number_of_recorded_wheel_times = len(wheel_cumsum_times)
    if number_of_recorded_wheel_times < Constants.MIN_NUMBER_OF_WHEEL_TIMES_BEFORE_PREDICTION \
            or ball_cumsum_times.size() < Constants.MIN_NUMBER_OF_BALL_TIMES_BEFORE_PREDICTION:
        raise SessionNotReadyException()

    wheel_cumsum_times_seconds = Helper.convert_to_seconds(wheel_cumsum_times)
    ball_cumsum_times_seconds = Helper.convert_to_seconds(ball_cumsum_times)

    most_probable_number = pr.machineLearning().predict(ball_cumsum_times_seconds, wheel_cumsum_times_seconds)
    return most_probable_number


def enable_ajax(ret_value):
    resp = Response(ret_value)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET'
    resp.headers['Access-Control-Allow-Credentials'] = 'true'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Accept'
    resp.headers['Content-Type'] = 'application/json'
    return resp


class RequestRoulette(Resource):
    @staticmethod  # remove it if it does not work
    def get():
        try:
            parser = reqparse.RequestParser()
            parser.add_argument(Parameters.TIME, type=str)
            parser.add_argument(Parameters.TYPE, type=str)
            args = parser.parse_args()
            timestamp = args[Parameters.TIME]

            if timestamp is None:
                raise Exception('parameter time missing')
            object_type = args[Parameters.TYPE]
            if object_type is None:
                raise Exception('parameter type missing')

            session_id = sm.call_manager(query_time=current_time_millis())

            if object_type == Constants.Type.BALL:
                da.insert_ball_lap_times(session_id, timestamp)
            elif object_type == Constants.Type.WHEEL:
                da.insert_wheel_lap_times(session_id, timestamp)
            else:
                raise Exception('parameter type is invalid')

        except Exception as e:
            return {'error': str(e)}


class ResponseRoulette(Resource):
    @staticmethod  # remove it if it does not work
    def get():
        ret_value = ''
        try:
            parser = reqparse.RequestParser()
            parser.add_argument(Parameters.SESSION_ID, type=str)
            parser.add_argument('outcome', type=str)
            args = parser.parse_args()
            session_id = args[Parameters.SESSION_ID]
            if session_id is None:
                da.get_last_session_id()
                print('No session specified. Selecting the last known session id = ' + session_id)
            if session_id is None or session_id == '':
                print('Problem occurred. SessionId should not be empty.')
                raise Exception()
            outcome = args['outcome']
            if outcome is not None and outcome != '':
                da.insert_outcome(session_id, outcome)
                print('New outcome inserted. Session id = ' + session_id + ', outcome = ' + outcome)

            # Predict outcome workflow.
            predicted_number = predict_most_probable_number(session_id)
            ret_value = {'predicted_number': predicted_number}
            print('Prediction=' + str(predicted_number) + ', sessionId=' + session_id)
        except Exception as e:
            print(str(e))

        resp = enable_ajax(ret_value)
        return resp


api.add_resource(RequestRoulette, '/Request', methods=['GET'])
api.add_resource(ResponseRoulette, '/Response', methods=['GET'])

if __name__ == '__main__':
    app.run(debug=True)