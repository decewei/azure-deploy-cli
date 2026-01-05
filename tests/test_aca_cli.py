"""Tests for ACA CLI module."""

import argparse

import pytest

from azure_deploy_cli.aca.aca_cli import _label_weight_pair


class TestParseLabelWeightPair:
    """Tests for _parse_label_weight_pair function."""

    def test_valid_single_pair(self):
        """Test parsing a valid label=weight pair."""
        result = _label_weight_pair("prod=100")
        assert result == ("prod", 100)

    def test_valid_pair_with_whitespace(self):
        """Test that whitespace around label and weight is handled correctly."""
        result = _label_weight_pair(" prod = 100 ")
        assert result == ("prod", 100)

    def test_staging_zero_weight(self):
        """Test staging with zero weight."""
        result = _label_weight_pair("staging=0")
        assert result == ("staging", 0)

    def test_missing_equals_raises_error(self):
        """Test that missing equals sign raises ArgumentTypeError."""
        with pytest.raises(argparse.ArgumentTypeError, match="Invalid format.*Expected format"):
            _label_weight_pair("prod100")

    def test_empty_label_raises_error(self):
        """Test that empty label name raises ArgumentTypeError."""
        with pytest.raises(argparse.ArgumentTypeError, match="Label name cannot be empty"):
            _label_weight_pair("=100")

    def test_non_integer_weight_raises_error(self):
        """Test that non-integer weight raises ArgumentTypeError."""
        with pytest.raises(argparse.ArgumentTypeError, match="Weight must be an integer"):
            _label_weight_pair("prod=abc")

    def test_negative_weight_raises_error(self):
        """Test that negative weight raises ArgumentTypeError."""
        with pytest.raises(argparse.ArgumentTypeError, match="Weight must be between 0 and 100"):
            _label_weight_pair("prod=-10")

    def test_weight_over_100_raises_error(self):
        """Test that weight over 100 raises ArgumentTypeError."""
        with pytest.raises(argparse.ArgumentTypeError, match="Weight must be between 0 and 100"):
            _label_weight_pair("prod=150")

    def test_boundary_weight_zero_valid(self):
        """Test that weight of 0 is valid."""
        result = _label_weight_pair("staging=0")
        assert result == ("staging", 0)

    def test_boundary_weight_100_valid(self):
        """Test that weight of 100 is valid."""
        result = _label_weight_pair("prod=100")
        assert result == ("prod", 100)

    def test_label_with_hyphen(self):
        """Test that label names with hyphens work."""
        result = _label_weight_pair("pre-prod=50")
        assert result == ("pre-prod", 50)

    def test_float_weight_raises_error(self):
        """Test that float weight raises ArgumentTypeError."""
        with pytest.raises(argparse.ArgumentTypeError, match="Weight must be an integer"):
            _label_weight_pair("prod=50.5")
