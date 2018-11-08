# coding=utf-8
# Copyright 2018 The TF-Agents Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Test for tf_agents.utils.common."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import random

from absl.testing import parameterized
import numpy as np
import tensorflow as tf
import tensorflow_probability as tfp

from tf_agents.environments import time_step as ts
from tf_agents.specs import tensor_spec
from tf_agents.utils import common
from tensorflow.python.framework import test_util  # TF internal

nest = tf.contrib.framework.nest


class CreateCounterTest(tf.test.TestCase):

  @test_util.run_in_graph_and_eager_modes()
  def testDefaults(self):
    counter = common.create_counter('counter')
    self.evaluate(tf.global_variables_initializer())
    self.assertEqual(self.evaluate(counter), 0)

  @test_util.run_in_graph_and_eager_modes()
  def testInitialValue(self):
    counter = common.create_counter('counter', 1)
    self.evaluate(tf.global_variables_initializer())
    self.assertEqual(self.evaluate(counter), 1)

  @test_util.run_in_graph_and_eager_modes()
  def testIncrement(self):
    counter = common.create_counter('counter', 0)
    inc_counter = counter.assign_add(1)
    self.evaluate(tf.global_variables_initializer())
    self.assertEqual(self.evaluate(inc_counter), 1)

  @test_util.run_in_graph_and_eager_modes()
  def testMultipleCounters(self):
    counter1 = common.create_counter('counter', 1)
    counter2 = common.create_counter('counter', 2)
    self.evaluate(tf.global_variables_initializer())
    self.assertEqual(self.evaluate(counter1), 1)
    self.assertEqual(self.evaluate(counter2), 2)

  @test_util.run_in_graph_and_eager_modes()
  def testInitialValueWithShape(self):
    counter = common.create_counter('counter', 1, shape=(2,))
    self.evaluate(tf.global_variables_initializer())
    self.assertAllEqual(self.evaluate(counter), [1, 1])


class SoftVariablesUpdateTest(tf.test.TestCase, parameterized.TestCase):

  @parameterized.parameters(0.0, 0.5, 1.0)
  def testUpdateOnlyTargetVariables(self, tau):
    with tf.Graph().as_default() as g:
      inputs = tf.constant([[1, 2], [3, 4]], dtype=tf.float32)
      tf.contrib.layers.fully_connected(inputs, 2, scope='source')
      tf.contrib.layers.fully_connected(inputs, 2, scope='target')

      source_vars = tf.contrib.framework.get_model_variables('source')
      target_vars = tf.contrib.framework.get_model_variables('target')
      update_op = common.soft_variables_update(source_vars, target_vars, tau)
      with self.test_session(graph=g) as sess:
        tf.global_variables_initializer().run()
        v_s, v_t = sess.run([source_vars, target_vars])
        sess.run(update_op)
        new_v_s, new_v_t = sess.run([source_vars, target_vars])
        for i_v_s, i_v_t, n_v_s, n_v_t in zip(v_s, v_t, new_v_s, new_v_t):
          # Source variables don't change
          self.assertAllClose(n_v_s, i_v_s)
          # Target variables are updated
          self.assertAllClose(n_v_t, tau*i_v_s + (1-tau)*i_v_t)

  @parameterized.parameters(0.0, 0.5, 1.0)
  def testShuffleOrderVariables(self, tau):
    with tf.Graph().as_default() as g:
      inputs = tf.constant([[1, 2], [3, 4]], dtype=tf.float32)
      tf.contrib.layers.fully_connected(inputs, 2, scope='source')
      tf.contrib.layers.fully_connected(inputs, 2, scope='target')

      source_vars = tf.contrib.framework.get_model_variables('source')
      target_vars = tf.contrib.framework.get_model_variables('target')

      shuffled_source_vars = sorted(source_vars,
                                    key=lambda x: random.random())
      shuffled_target_vars = sorted(target_vars,
                                    key=lambda x: random.random())

      update_op = common.soft_variables_update(shuffled_source_vars,
                                               shuffled_target_vars,
                                               tau,
                                               sort_variables_by_name=True)
      with self.test_session(graph=g) as sess:
        tf.global_variables_initializer().run()
        v_s, v_t = sess.run([source_vars, target_vars])
        sess.run(update_op)
        new_v_s, new_v_t = sess.run([source_vars, target_vars])
        for i_v_s, i_v_t, n_v_s, n_v_t in zip(v_s, v_t, new_v_s, new_v_t):
          # Source variables don't change
          self.assertAllClose(n_v_s, i_v_s)
          # Target variables are updated
          self.assertAllClose(n_v_t, tau*i_v_s + (1-tau)*i_v_t)


class JoinScopeTest(tf.test.TestCase):

  def _test_scopes(self, parent_scope, child_scope, expected_joined_scope):
    joined_scope = common.join_scope(parent_scope, child_scope)
    self.assertEqual(joined_scope, expected_joined_scope)

  def testJoin(self):
    self._test_scopes('parent', 'child', 'parent/child')

  def testJoinEmptyChild(self):
    self._test_scopes('parent', '', 'parent')

  def testJoinEmptyParent(self):
    self._test_scopes('', 'child', 'child')

  def testJoinEmptyChildEmptyParent(self):
    self._test_scopes('', '', '')


class IndexWithActionsTest(tf.test.TestCase):

  def checkCorrect(self,
                   q_values,
                   actions,
                   expected_values,
                   multi_dim_actions=False):
    q_values = tf.constant(q_values, dtype=tf.float32)
    actions = tf.constant(actions, dtype=tf.int32)
    selected_q_values = common.index_with_actions(q_values, actions,
                                                  multi_dim_actions)
    selected_q_values_ = self.evaluate(selected_q_values)
    self.assertAllClose(selected_q_values_, expected_values)

  def testOneOuterDim(self):
    q_values = [[1., 2., 3.],
                [4., 5., 6.]]
    actions = [2, 1]
    expected_q_values = [3., 5.]
    self.checkCorrect(q_values, actions, expected_q_values)

  def testTwoOuterDims(self):
    q_values = [[[1., 2., 3.],
                 [4., 5., 6.]],
                [[7., 8., 9.],
                 [10., 11., 12.]]]
    actions = [[2, 1], [0, 2]]
    expected_q_values = [[3., 5.], [7., 12.]]
    self.checkCorrect(q_values, actions, expected_q_values)

  def testOneOuterDimTwoActionDims(self):
    q_values = [[[1., 2., 3.],
                 [4., 5., 6.]],
                [[7., 8., 9.],
                 [10., 11., 12.]]]
    actions = [[1, 2], [0, 1]]
    expected_q_values = [6., 8.]
    self.checkCorrect(
        q_values, actions, expected_q_values, multi_dim_actions=True)

  def testOneOuterDimThreeActionDims(self):
    q_values = [[[[1., 2., 3.],
                  [4., 5., 6.]],
                 [[7., 8., 9.],
                  [10., 11., 12.]]],
                [[[13., 14., 15.],
                  [16., 17., 18.]],
                 [[19., 20., 21.],
                  [22., 23., 24.]]]]
    actions = [[0, 1, 2], [1, 0, 1]]
    expected_q_values = [6., 20.]
    self.checkCorrect(
        q_values, actions, expected_q_values, multi_dim_actions=True)

  def testTwoOuterDimsUnknownShape(self):
    q_values = tf.placeholder(tf.float32, shape=[None, None, None])
    actions = tf.placeholder(tf.int32, shape=[None, None])
    values = common.index_with_actions(q_values, actions)
    with self.test_session() as sess:
      self.assertAllClose(
          [[51, 52]],
          sess.run(values,
                   feed_dict={q_values: [[[50, 51], [52, 53]]],
                              actions: [[1, 0]]}))


class PeriodicallyTest(tf.test.TestCase):
  """Tests function periodically."""

  @test_util.run_in_graph_and_eager_modes()
  def testPeriodically(self):
    """Tests that a function is called exactly every `period` steps."""
    target = tf.contrib.framework.global_variable(0, use_resource=True)
    period = 3

    periodic_update = common.periodically(
        body=lambda: tf.group(target.assign_add(1)), period=period)

    self.evaluate(tf.global_variables_initializer())
    desired_values = [0, 0, 0, 1, 1, 1, 2, 2, 2, 3]
    for desired_value in desired_values:
      result = self.evaluate(target)
      self.assertEqual(desired_value, result)
      self.evaluate(periodic_update)

  @test_util.run_in_graph_and_eager_modes()
  def testPeriodOne(self):
    """Tests that the function is called every time if period == 1."""
    target = tf.contrib.framework.global_variable(0, use_resource=True)

    periodic_update = common.periodically(
        lambda: tf.group(target.assign_add(1)), period=1)

    self.evaluate(tf.global_variables_initializer())
    for desired_value in range(0, 10):
      result = self.evaluate(target)
      self.assertEqual(desired_value, result)
      self.evaluate(periodic_update)

  @test_util.run_in_graph_and_eager_modes()
  def testPeriodNone(self):
    """Tests that the function is never called if period == None."""
    target = tf.contrib.framework.global_variable(0, use_resource=True)

    periodic_update = common.periodically(
        body=lambda: target.assign_add(1), period=None)

    self.evaluate(tf.global_variables_initializer())
    desired_value = 0
    for _ in range(1, 11):
      _, result = self.evaluate([periodic_update, target])
      self.assertEqual(desired_value, result)

  @test_util.run_in_graph_and_eager_modes()
  def testFunctionNotCallable(self):
    """Tests value error when argument fn is not a callable."""
    self.assertRaises(
        TypeError, common.periodically, body=1, period=2)

  @test_util.run_in_graph_and_eager_modes()
  def testPeriodVariable(self):
    """Tests that a function is called exactly every `period` steps."""
    target = tf.contrib.framework.global_variable(0, use_resource=True)
    period = tf.contrib.framework.global_variable(1, use_resource=True)

    periodic_update = common.periodically(
        body=lambda: tf.group(target.assign_add(1)), period=period)

    self.evaluate(tf.global_variables_initializer())
    # With period = 1
    desired_values = [0, 1, 2]
    for desired_value in desired_values:
      result = self.evaluate(target)
      self.assertEqual(desired_value, result)
      self.evaluate(periodic_update)

    self.evaluate(target.assign(0))
    self.evaluate(period.assign(3))
    # With period = 3
    desired_values = [0, 0, 0, 1, 1, 1, 2, 2, 2]
    for desired_value in desired_values:
      result = self.evaluate(target)
      self.assertEqual(desired_value, result)
      self.evaluate(periodic_update)

  @test_util.run_in_graph_and_eager_modes()
  def testMultiplePeriodically(self):
    """Tests that 2 periodically ops run independently."""
    target1 = tf.contrib.framework.global_variable(0, use_resource=True)
    periodic_update1 = common.periodically(
        body=lambda: tf.group(target1.assign_add(1)), period=1)

    target2 = tf.contrib.framework.global_variable(0, use_resource=True)
    periodic_update2 = common.periodically(
        body=lambda: tf.group(target2.assign_add(2)), period=2)

    self.evaluate(tf.global_variables_initializer())
    # With period = 1, increment = 1
    desired_values1 = [0, 1, 2, 3]
    # With period = 2, increment = 2
    desired_values2 = [0, 0, 2, 2]

    for i in range(len(desired_values1)):
      result1 = self.evaluate(target1)
      self.assertEqual(desired_values1[i], result1)
      result2 = self.evaluate(target2)
      self.assertEqual(desired_values2[i], result2)
      self.evaluate([periodic_update1, periodic_update2])


class ClipToSpecTest(tf.test.TestCase):

  def testClipToBounds(self):
    value = tf.constant([1, 2, 4, -3])
    spec = tensor_spec.BoundedTensorSpec((4,), tf.float32, [0, 0, 0, 0],
                                         [3, 3, 3, 3])
    expected_clipped_value = np.array([1, 2, 3, 0])
    clipped_value = common.clip_to_spec(value, spec)
    with self.test_session() as sess:
      clipped_value_ = sess.run(clipped_value)
      self.assertAllClose(expected_clipped_value, clipped_value_)


class ScaleToSpecTest(tf.test.TestCase):

  def testScaleToSpec(self):
    value = tf.constant([[1, -1], [0.5, -0.5], [1.0, 0.0]])
    spec = tensor_spec.BoundedTensorSpec(
        (3, 2),
        tf.float32,
        [[-5, -5], [-4, -4], [-2, -6]],
        [[5, 5], [4, 4], [2, 6]],
    )
    expected_scaled_value = np.array([[[5, -5], [2.0, -2.0], [2.0, 0.0]]])
    scaled_value = common.scale_to_spec(value, spec)
    with self.test_session() as sess:
      scaled_value_ = sess.run(scaled_value)
      self.assertAllClose(expected_scaled_value, scaled_value_)


class OrnsteinUhlenbeckSamplesTest(tf.test.TestCase):

  @test_util.run_in_graph_and_eager_modes()
  def testSamples(self):
    """Tests that samples follow Ornstein-Uhlenbeck process.

    This is done by checking that the successive differences
    `x_next - (1-theta) * x` have the expected mean and variance.
    """
    # Increasing the number of samples can help reduce the variance and make the
    # sample mean closer to the distribution mean.
    num_samples = 1000
    theta, sigma = 0.1, 0.2
    ou = common.ornstein_uhlenbeck_process(
        tf.zeros([10]), damping=theta, stddev=sigma)
    samples = np.ndarray([num_samples, 10])
    self.evaluate(tf.local_variables_initializer())
    for i in range(num_samples):
      samples[i] = self.evaluate(ou)

    diffs = np.ndarray([num_samples-1, 10])
    for i in range(num_samples - 1):
      diffs[i] = samples[i+1] - (1-theta) * samples[i]
    flat_diffs = diffs.reshape([-1])

    mean, variance = flat_diffs.mean(), flat_diffs.var()
    # To avoid flakiness, we can only expect the sample statistics to match
    # the population statistics to one or two decimal places.
    self.assertAlmostEqual(mean, 0.0, places=1)
    self.assertAlmostEqual(variance, sigma*sigma, places=2)

  @test_util.run_in_graph_and_eager_modes()
  def testMultipleSamples(self):
    """Tests that creates different samples.

    """
    theta, sigma = 0.1, 0.2
    ou1 = common.ornstein_uhlenbeck_process(
        tf.zeros([10]), damping=theta, stddev=sigma)
    ou2 = common.ornstein_uhlenbeck_process(
        tf.zeros([10]), damping=theta, stddev=sigma)

    samples = np.ndarray([100, 10, 2])
    self.evaluate(tf.local_variables_initializer())
    for i in range(100):
      samples[i, :, 0], samples[i, :, 1] = self.evaluate([ou1, ou2])

    diffs = samples[:, :, 0] - samples[:, :, 1]
    difference = np.absolute(diffs).mean()

    self.assertGreater(difference, 0.0)


class LogProbabilityTest(tf.test.TestCase):

  def testLogProbability(self):
    action_spec = tensor_spec.BoundedTensorSpec([2], tf.float32, -1, 1)
    distribution = tfp.distributions.Normal([0.0, 0.0], [1.0, 1.0])
    actions = tf.constant([0.0, 0.0])
    log_probs = common.log_probability(distribution, actions, action_spec)

    self.evaluate(tf.global_variables_initializer())
    log_probs_ = self.evaluate(log_probs)
    self.assertEqual(len(log_probs_.shape), 0)
    self.assertNear(log_probs_, 2 * -0.5 * np.log(2 * 3.14159), 0.001)

  def testNestedLogProbability(self):
    action_spec = [
        tensor_spec.BoundedTensorSpec([2], tf.float32, -1, 1),
        [tensor_spec.BoundedTensorSpec([1], tf.float32, -1, 1),
         tensor_spec.BoundedTensorSpec([1], tf.float32, -1, 1)]]
    distribution = [
        tfp.distributions.Normal([0.0, 0.0], [1.0, 1.0]),
        [
            tfp.distributions.Normal([0.5], [1.0]),
            tfp.distributions.Normal([-0.5], [1.0])
        ]
    ]
    actions = [tf.constant([0.0, 0.0]),
               [tf.constant([0.5]), tf.constant([-0.5])]]
    log_probs = common.log_probability(distribution, actions, action_spec)

    self.evaluate(tf.global_variables_initializer())
    log_probs_ = self.evaluate(log_probs)
    self.assertEqual(len(log_probs_.shape), 0)
    self.assertNear(log_probs_, 4 * -0.5 * np.log(2 * 3.14159), 0.001)

  def testBatchedNestedLogProbability(self):
    action_spec = [
        tensor_spec.BoundedTensorSpec([2], tf.float32, -1, 1),
        [tensor_spec.BoundedTensorSpec([1], tf.float32, -1, 1),
         tensor_spec.BoundedTensorSpec([1], tf.float32, -1, 1)]]
    distribution = [
        tfp.distributions.Normal([[0.0, 0.0], [0.0, 0.0]],
                                 [[1.0, 1.0], [2.0, 2.0]]),
        [
            tfp.distributions.Normal([[0.5], [0.5]], [[1.0], [2.0]]),
            tfp.distributions.Normal([[-0.5], [-0.5]], [[1.0], [2.0]])
        ]
    ]
    actions = [tf.constant([[0.0, 0.0], [0.0, 0.0]]),
               [tf.constant([[0.5], [0.5]]), tf.constant([[-0.5], [-0.5]])]]
    log_probs = common.log_probability(distribution, actions, action_spec)

    self.evaluate(tf.global_variables_initializer())
    log_probs_ = self.evaluate(log_probs)
    self.assertEqual(log_probs_.shape, (2,))
    self.assertAllClose(log_probs_,
                        [4 * -0.5 * np.log(2 * 3.14159),
                         4 * -0.5 * np.log(8 * 3.14159)], 0.001)


class EntropyTest(tf.test.TestCase):

  def testEntropy(self):
    action_spec = tensor_spec.BoundedTensorSpec([2], tf.float32, -1, 1)
    distribution = tfp.distributions.Normal([0.0, 0.0], [1.0, 2.0])
    entropies = common.entropy(distribution, action_spec)

    self.evaluate(tf.global_variables_initializer())
    entropies_ = self.evaluate(entropies)
    self.assertEqual(len(entropies_.shape), 0)
    self.assertNear(entropies_,
                    1.0 + 0.5 * np.log(2 * 3.14) + 0.5 * np.log(8 * 3.14159),
                    0.001)

  def testNestedEntropy(self):
    action_spec = [
        tensor_spec.BoundedTensorSpec([2], tf.float32, -1, 1),
        [tensor_spec.BoundedTensorSpec([1], tf.float32, -1, 1),
         tensor_spec.BoundedTensorSpec([1], tf.float32, -1, 1)]]
    distribution = [
        tfp.distributions.Normal([0.0, 0.0], [1.0, 2.0]),
        [
            tfp.distributions.Normal([0.5], [1.0]),
            tfp.distributions.Normal([-0.5], [2.0])
        ]
    ]
    entropies = common.entropy(distribution, action_spec)

    self.evaluate(tf.global_variables_initializer())
    entropies_ = self.evaluate(entropies)
    self.assertEqual(len(entropies_.shape), 0)
    self.assertNear(entropies_,
                    2.0 + np.log(2 * 3.14) + np.log(8 * 3.14159),
                    0.001)

  def testBatchedNestedEntropy(self):
    action_spec = [
        tensor_spec.BoundedTensorSpec([2], tf.float32, -1, 1),
        [tensor_spec.BoundedTensorSpec([1], tf.float32, -1, 1),
         tensor_spec.BoundedTensorSpec([1], tf.float32, -1, 1)]]
    distribution = [
        tfp.distributions.Normal([[0.0, 0.0], [0.0, 0.0]],
                                 [[1.0, 1.0], [2.0, 2.0]]),
        [
            tfp.distributions.Normal([[0.5], [0.5]], [[1.0], [2.0]]),
            tfp.distributions.Normal([[-0.5], [-0.5]], [[1.0], [2.0]])
        ]
    ]
    entropies = common.entropy(distribution, action_spec)

    self.evaluate(tf.global_variables_initializer())
    entropies_ = self.evaluate(entropies)
    self.assertEqual(entropies_.shape, (2,))
    self.assertAllClose(entropies_,
                        [4 * (0.5 + 0.5 * np.log(2 * 3.14159)),
                         4 * (0.5 + 0.5 * np.log(8 * 3.14159))], 0.001)


class DiscountedFutureSumTest(tf.test.TestCase):

  def testNumSteps(self):
    values = [[0, 1, 2, 3],
              [1, 2, 3, 4],
              [2, 3, 4, 5]]
    tensor = tf.constant(values, dtype=tf.float32)

    result_step1 = common.discounted_future_sum(tensor, 1.0, 1)
    result_step3 = common.discounted_future_sum(tensor, 1.0, 3)
    result_step20 = common.discounted_future_sum(tensor, 1.0, 20)

    expected_result_step1 = values
    expected_result_step3 = [
        [3, 6, 5, 3],
        [6, 9, 7, 4],
        [9, 12, 9, 5]]
    expected_result_step20 = [
        [6, 6, 5, 3],
        [10, 9, 7, 4],
        [14, 12, 9, 5]]

    self.assertAllClose(expected_result_step1, self.evaluate(result_step1))
    self.assertAllClose(expected_result_step3, self.evaluate(result_step3))
    self.assertAllClose(expected_result_step20, self.evaluate(result_step20))

  def testGamma(self):
    values = [[0, 1, 2, 3],
              [1, 2, 3, 4],
              [2, 3, 4, 5]]
    tensor = tf.constant(values, dtype=tf.float32)

    result_gamma0 = common.discounted_future_sum(tensor, 0.0, 3)
    result_gamma09 = common.discounted_future_sum(tensor, 0.9, 3)
    result_gamma1 = common.discounted_future_sum(tensor, 1.0, 3)
    result_gamma2 = common.discounted_future_sum(tensor, 2.0, 3)

    values = np.array(values)
    values_shift1 = np.pad(values[:, 1:], ((0, 0), (0, 1)), 'constant')
    values_shift2 = np.pad(values[:, 2:], ((0, 0), (0, 2)), 'constant')
    expected_result_gamma0 = values
    expected_result_gamma09 = (values + 0.9 * values_shift1 +
                               0.81 * values_shift2)
    expected_result_gamma1 = values + values_shift1 + values_shift2
    expected_result_gamma2 = values + 2 * values_shift1 + 4 * values_shift2

    self.assertAllClose(expected_result_gamma0, self.evaluate(result_gamma0))
    self.assertAllClose(expected_result_gamma09, self.evaluate(result_gamma09))
    self.assertAllClose(expected_result_gamma1, self.evaluate(result_gamma1))
    self.assertAllClose(expected_result_gamma2, self.evaluate(result_gamma2))

  def testMaskedReturns(self):
    rewards = tf.ones(shape=(3, 7), dtype=tf.float32)
    gamma = 0.9
    num_steps = 7
    episode_lengths = tf.constant([3, 7, 4])
    discounted_returns = common.discounted_future_sum_masked(
        rewards, gamma, num_steps, episode_lengths)

    # Episodes should end at indices 2, 6, and 3, respectively.
    # Values, counting back from the end of episode should be:
    #   [.9^0, (.9^1 + .9^0), (.9^2 + .9^1 + .9^0), ...]
    expected_returns = tf.constant([[2.71, 1.9, 1, 0, 0, 0, 0],
                                    [5.217, 4.686, 4.095, 3.439, 2.71, 1.9, 1],
                                    [3.439, 2.71, 1.9, 1, 0, 0, 0]],
                                   dtype=tf.float32)
    self.assertAllClose(self.evaluate(expected_returns),
                        self.evaluate(discounted_returns), atol=0.001)


class ShiftValuesTest(tf.test.TestCase):

  def testNumSteps(self):
    values = [[0, 1, 2, 3],
              [1, 2, 3, 4],
              [2, 3, 4, 5]]
    tensor = tf.constant(values, dtype=tf.float32)

    result_step0 = common.shift_values(tensor, 1.0, 0)
    result_step1 = common.shift_values(tensor, 1.0, 1)
    result_step3 = common.shift_values(tensor, 1.0, 3)
    result_step20 = common.shift_values(tensor, 1.0, 20)

    values = np.array(values)
    expected_result_step0 = values
    expected_result_step1 = np.pad(values[:, 1:], ((0, 0), (0, 1)), 'constant')
    expected_result_step3 = np.pad(values[:, 3:], ((0, 0), (0, 3)), 'constant')
    expected_result_step20 = np.zeros_like(values)

    self.assertAllClose(expected_result_step0, self.evaluate(result_step0))
    self.assertAllClose(expected_result_step1, self.evaluate(result_step1))
    self.assertAllClose(expected_result_step3, self.evaluate(result_step3))
    self.assertAllClose(expected_result_step20, self.evaluate(result_step20))

  def testGamma(self):
    values = [[0, 1, 2, 3],
              [1, 2, 3, 4],
              [2, 3, 4, 5]]
    tensor = tf.constant(values, dtype=tf.float32)

    result_gamma0 = common.shift_values(tensor, 0.0, 3)
    result_gamma09 = common.shift_values(tensor, 0.9, 3)
    result_gamma1 = common.shift_values(tensor, 1.0, 3)
    result_gamma2 = common.shift_values(tensor, 2.0, 3)

    values = np.array(values)
    values_shift3 = np.pad(values[:, 3:], ((0, 0), (0, 3)), 'constant')
    expected_result_gamma0 = np.zeros_like(values)
    expected_result_gamma09 = 0.9 ** 3 * values_shift3
    expected_result_gamma1 = values_shift3
    expected_result_gamma2 = 2 ** 3 * values_shift3

    self.assertAllClose(expected_result_gamma0, self.evaluate(result_gamma0))
    self.assertAllClose(expected_result_gamma09, self.evaluate(result_gamma09))
    self.assertAllClose(expected_result_gamma1, self.evaluate(result_gamma1))
    self.assertAllClose(expected_result_gamma2, self.evaluate(result_gamma2))

  def testFinalValues(self):
    values = [[0, 1, 2, 3],
              [1, 2, 3, 4],
              [2, 3, 4, 5]]
    tensor = tf.constant(values, dtype=tf.float32)
    final_values = tf.constant([11, 12, 13], dtype=tf.float32)

    result_gamma1 = common.shift_values(tensor, 1.0, 2, final_values)
    result_gamma09 = common.shift_values(tensor, 0.9, 2, final_values)
    result_step20 = common.shift_values(tensor, 0.9, 20, final_values)

    expected_result_gamma1 = [
        [2, 3, 11, 11],
        [3, 4, 12, 12],
        [4, 5, 13, 13]]
    expected_result_gamma09 = [
        [2 * 0.81, 3 * 0.81, 11 * 0.81, 11 * 0.9],
        [3 * 0.81, 4 * 0.81, 12 * 0.81, 12 * 0.9],
        [4 * 0.81, 5 * 0.81, 13 * 0.81, 13 * 0.9]]
    expected_result_step20 = [
        [11 * 0.9 ** 4, 11 * 0.9 ** 3, 11 * 0.9 ** 2, 11 * 0.9 ** 1],
        [12 * 0.9 ** 4, 12 * 0.9 ** 3, 12 * 0.9 ** 2, 12 * 0.9 ** 1],
        [13 * 0.9 ** 4, 13 * 0.9 ** 3, 13 * 0.9 ** 2, 13 * 0.9 ** 1]]

    self.assertAllClose(expected_result_gamma1, self.evaluate(result_gamma1))
    self.assertAllClose(expected_result_gamma09, self.evaluate(result_gamma09))
    self.assertAllClose(expected_result_step20, self.evaluate(result_step20))


class GetEpisodeMaskTest(tf.test.TestCase):

  def test(self):
    first = ts.StepType.FIRST
    mid = ts.StepType.MID
    last = ts.StepType.LAST
    step_types = [first, mid, mid, last, mid, mid, mid, last]
    discounts = [1.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 0.0]
    time_steps = ts.TimeStep(
        step_type=step_types, discount=discounts, reward=discounts,
        observation=discounts)
    episode_mask = common.get_episode_mask(time_steps)

    expected_mask = [1, 1, 1, 0, 1, 1, 1, 0]
    self.evaluate(tf.global_variables_initializer())
    self.assertAllEqual(expected_mask, self.evaluate(episode_mask))


class GetContiguousSubEpisodesTest(tf.test.TestCase):

  def testNumSteps(self):
    discounts = [
        [0.9, 0.9, 0.9, 0.9],  # No episode termination.
        [0.0, 0.9, 0.9, 0.9],  # Episode terminates on first step.
        [0.9, 0.9, 0.0, 0.9]]  # Episode terminates on third step.

    tensor = tf.constant(discounts, dtype=tf.float32)
    result = common.get_contiguous_sub_episodes(tensor)

    expected_result = [
        [1.0, 1.0, 1.0, 1.0],
        [1.0, 0.0, 0.0, 0.0],
        [1.0, 1.0, 1.0, 0.0]]

    self.assertAllClose(expected_result, self.evaluate(result))


class ConvertQLogitsToValuesTest(tf.test.TestCase):

  def testConvertQLogitsToValues(self):
    logits = tf.constant([[2., 4., 2.], [1., 1., 20.]])
    support = tf.constant([10., 20., 30.])
    values = common.convert_q_logits_to_values(logits, support)
    values_ = self.evaluate(values)
    self.assertAllClose(values_, [20.0, 30.0], 0.001)

  def testConvertQLogitsToValuesBatch(self):
    logits = tf.constant([[[1., 20., 1.], [1., 1., 20.]],
                          [[20., 1., 1.], [1., 20., 20.]]])
    support = tf.constant([10., 20., 30.])
    values = common.convert_q_logits_to_values(logits, support)
    values_ = self.evaluate(values)
    self.assertAllClose(values_, [[20.0, 30.0], [10., 25.]], 0.001)


class ComputeReturnsTest(tf.test.TestCase):

  def testComputeReturns(self):
    rewards = tf.constant(np.ones(9), dtype=tf.float32)
    discounts = tf.constant([1, 1, 1, 1, 0, 0.9, 0.9, 0.9, 0], dtype=tf.float32)
    returns = common.compute_returns(rewards, discounts)
    expected_returns = [5, 4, 3, 2, 1, 3.439, 2.71, 1.9, 1]

    self.evaluate(tf.global_variables_initializer())
    returns = self.evaluate(returns)
    self.assertAllClose(returns, expected_returns)

  def testComputeReturnsRandomized(self):
    rewards = tf.constant(np.random.random([20]), dtype=tf.float32)
    discounts = tf.constant(np.random.random([20]), dtype=tf.float32)
    returns = common.compute_returns(rewards, discounts)

    def _compute_returns_fn(rewards, discounts):
      """Python implementation of computing discounted returns."""
      returns = np.zeros(len(rewards))
      next_state_return = 0.0
      for t in range(len(returns) - 1, -1, -1):
        returns[t] = rewards[t] + discounts[t] * next_state_return
        next_state_return = returns[t]
      return returns.astype(np.float32)
    expected_returns = tf.py_func(_compute_returns_fn,
                                  [rewards, discounts],
                                  tf.float32)

    self.evaluate(tf.global_variables_initializer())
    returns = self.evaluate(returns)
    expected_returns = self.evaluate(expected_returns)
    self.assertAllClose(returns, expected_returns)


class ReplicateTensorTest(tf.test.TestCase, parameterized.TestCase):

  @parameterized.parameters('list', 'tf_constant', 'placeholder')
  def testReplicateTensor(self, outer_shape_type):
    value = np.array([[1., 2., 3.], [4., 5., 6.]])
    if outer_shape_type == 'placeholder':
      outer_shape = tf.placeholder(tf.int32, shape=[2])
    elif outer_shape_type == 'tf_constant':
      outer_shape = tf.constant([2, 1])
    else:
      outer_shape = [2, 1]
    expected_replicated_value = np.array([[value], [value]])

    tf_value = tf.constant(value)
    tf_replicated_value = common.replicate(tf_value, outer_shape)
    if isinstance(outer_shape, np.ndarray):
      # The shape should be fully defined in this case.
      self.assertEqual(tf.TensorShape(outer_shape + list(value.shape)),
                       tf_replicated_value.shape)

    with self.test_session() as sess:
      feed_dict = {}
      if outer_shape_type == 'placeholder':
        feed_dict = {outer_shape: np.array([2, 1])}
      replicated_value = sess.run(tf_replicated_value, feed_dict)
      self.assertAllEqual(expected_replicated_value, replicated_value)


if __name__ == '__main__':
  tf.test.main()
