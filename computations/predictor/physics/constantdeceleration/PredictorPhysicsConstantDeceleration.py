from HelperConstantDeceleration import *
from computations.predictor.Phase import *
from utils.Logging import *


class PredictorPhysicsConstantDeceleration(object):
    FIXED_SLOPE = None

    @staticmethod
    def load_cache(database):
        slopes = []
        for session_id in database.get_session_ids():
            ball_cumsum_times = database.select_ball_lap_times(session_id)
            if len(ball_cumsum_times) >= Constants.MIN_NUMBER_OF_BALL_TIMES_BEFORE_PREDICTION:
                ball_cumsum_times = np.array(Helper.convert_to_seconds(ball_cumsum_times))
                ball_diff_times = Helper.compute_diff(ball_cumsum_times)
                ball_model = HelperConstantDeceleration.compute_model(ball_diff_times)
                slopes.append(ball_model.coef_[0, 0])
        print('slopes = {}'.format(slopes))
        mean_slopes = np.mean(slopes)
        print('mean slopes = {}'.format(mean_slopes))
        PredictorPhysicsConstantDeceleration.FIXED_SLOPE = mean_slopes

    @staticmethod
    def predict_most_probable_number(ball_cumsum_times, wheel_cumsum_times, debug=False):

        if len(wheel_cumsum_times) < Constants.MIN_NUMBER_OF_WHEEL_TIMES_BEFORE_PREDICTION:
            raise SessionNotReadyException()

        if len(ball_cumsum_times) < Constants.MIN_NUMBER_OF_BALL_TIMES_BEFORE_PREDICTION:
            raise SessionNotReadyException()

        # in seconds.
        ball_cumsum_times = np.array(Helper.convert_to_seconds(ball_cumsum_times))
        wheel_cumsum_times = np.array(Helper.convert_to_seconds(wheel_cumsum_times))

        most_probable_number = PredictorPhysicsConstantDeceleration.predict(ball_cumsum_times, wheel_cumsum_times,
                                                                            debug)
        return most_probable_number

    @staticmethod
    def predict(ball_cumsum_times, wheel_cumsum_times, debug):
        cutoff_speed = Constants.CUTOFF_SPEED
        """Think about merging all together and having the same time index."""
        last_wheel_lap_time_in_front_of_ref = Helper.get_last_time_wheel_is_in_front_of_ref(wheel_cumsum_times,
                                                                                            ball_cumsum_times[-1])
        last_time_ball_passes_in_front_of_ref = ball_cumsum_times[-1]
        log('Reference time of prediction = {} s'.format(last_time_ball_passes_in_front_of_ref), debug)
        ball_diff_times = Helper.compute_diff(ball_cumsum_times)
        wheel_diff_times = Helper.compute_diff(wheel_cumsum_times)

        fixed_slope = PredictorPhysicsConstantDeceleration.FIXED_SLOPE
        ball_loop_count = len(ball_diff_times)
        ball_model = HelperConstantDeceleration.compute_model(ball_diff_times, fixed_slope)
        number_of_revolutions_left_ball = HelperConstantDeceleration.estimate_revolution_count_left(ball_model,
                                                                                                    ball_loop_count,
                                                                                                    cutoff_speed)
        phase_at_cut_off = (number_of_revolutions_left_ball % 1) * len(Wheel.NUMBERS)

        estimated_time_left = HelperConstantDeceleration.estimate_time(ball_model, ball_loop_count,
                                                                       number_of_revolutions_left_ball)
        time_at_cutoff_ball = last_time_ball_passes_in_front_of_ref + estimated_time_left

        if time_at_cutoff_ball < last_time_ball_passes_in_front_of_ref + Constants.TIME_LEFT_FOR_PLACING_BETS_SECONDS:
            raise PositiveValueExpectedException()

        constant_wheel_speed = Helper.get_wheel_speed(wheel_diff_times[-1])
        initial_phase = Phase.find_phase_number_between_ball_and_wheel(last_time_ball_passes_in_front_of_ref,
                                                                       last_wheel_lap_time_in_front_of_ref,
                                                                       constant_wheel_speed,
                                                                       Constants.DEFAULT_WHEEL_WAY)

        shift_between_initial_time_and_cutoff = ((estimated_time_left / wheel_diff_times[-1]) % 1) * len(
            Wheel.NUMBERS)

        expected_bouncing_shift = (Constants.DEFAULT_SHIFT_PHASE * constant_wheel_speed)
        final_phase_to_add = phase_at_cut_off + shift_between_initial_time_and_cutoff + expected_bouncing_shift
        final_phase_to_add = int(np.round(final_phase_to_add))

        predicted_number = Wheel.get_number_with_phase(initial_phase, final_phase_to_add, Constants.DEFAULT_WHEEL_WAY)
        log("Number of pockets (computed from angle) = {}".format(shift_between_initial_time_and_cutoff), debug)
        log("expected_bouncing_shift = {}".format(expected_bouncing_shift), debug)
        log("predicted_number is = {}".format(predicted_number), debug)
        return predicted_number
