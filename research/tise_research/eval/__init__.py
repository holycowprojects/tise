"""Evaluation: scoring rules, backtests, calibration.

Everything here is chronological. There is no shuffle, no `train_test_split`, and no
random seed that changes which rows land in which fold — folds are cut by time and only
by time. A random split on browsing data leaks the future into the past and produces
numbers that look excellent and mean nothing.
"""
