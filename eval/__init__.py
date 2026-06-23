"""Evaluation harness for the Verify agent's hallucination detection.

The Verify agent is the project's trust guarantee: it flags factual claims in a
draft that the profile/opportunity do not support. This package measures how well
it does that — precision, recall, F1, and a confusion matrix over a labeled set of
drafts with known planted (unsupported) claims and known grounded claims.
"""
