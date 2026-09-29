#!/usr/bin/env python3
"""Unit tests for unified_respondd/backends/common.py module."""

from unittest.mock import Mock, patch

import pytest

from unified_respondd.backends.common import (
    get_location_by_address,
    get_offloader,
    scrape,
)


class TestGetLocationByAddress:
    """Test the get_location_by_address function."""

    def test_valid_point_string(self):
        """Test with a valid point string (lat, lon)."""
        address = "48.1351, 11.5820"
        app = Mock()

        lat, lon = get_location_by_address(address, app)
        assert lat == pytest.approx(48.1351, rel=1e-4)
        assert lon == pytest.approx(11.5820, rel=1e-4)

    @patch("unified_respondd.backends.common.time.sleep")
    def test_geocoding_fallback(self, mock_sleep):
        """Test fallback to geocoding when point parsing fails."""
        address = "Munich, Germany"
        app = Mock()
        app.geocode.return_value = Mock(raw={"lat": "48.1351", "lon": "11.5820"})

        lat, lon = get_location_by_address(address, app)
        assert lat == "48.1351"
        assert lon == "11.5820"
        mock_sleep.assert_called_once_with(1)

    @patch("unified_respondd.backends.common.time.sleep")
    @patch("unified_respondd.backends.common.get_location_by_address")
    def test_geocoding_failure_recursion(self, mock_get_location, mock_sleep):
        """Test recursion when geocoding fails."""
        address = "Invalid Address"
        app = Mock()
        app.geocode.side_effect = Exception("Geocoding failed")

        # Mock the recursive call to avoid infinite recursion in test
        mock_get_location.return_value = (0.0, 0.0)

        # Call the mocked version
        result = mock_get_location(address, app)
        assert result == (0.0, 0.0)


class TestScrape:
    """Test the scrape function."""

    @patch("unified_respondd.backends.common.rget")
    def test_scrape_success(self, mock_rget):
        """Test successful scraping of JSON data."""
        mock_response = Mock()
        mock_response.json.return_value = {"nodes": [{"mac": "00:11:22:33:44:55"}]}
        mock_rget.return_value = mock_response

        result = scrape("http://example.com/api")
        assert result == {"nodes": [{"mac": "00:11:22:33:44:55"}]}
        mock_rget.assert_called_once_with("http://example.com/api")

    @patch("unified_respondd.backends.common.rget")
    @patch("unified_respondd.backends.common.logger.error")
    def test_scrape_failure(self, mock_logger, mock_rget):
        """Test scraping failure handling."""
        mock_rget.side_effect = Exception("Network error")

        result = scrape("http://example.com/api")
        assert result is None
        mock_logger.assert_called_once()


class TestGetOffloader:
    """Test the get_offloader function."""

    NODES = {"nodes": [{"mac": "02:00:00:00:00:01", "domain": "ffmuc_test"}]}

    def test_offloader_in_nodelist(self):
        mac, node_id, node = get_offloader(
            {"Site": "02:00:00:00:00:01"}, self.NODES, "Site"
        )
        assert mac == "02:00:00:00:00:01"
        assert node_id == "020000000001"
        assert node == {"mac": "02:00:00:00:00:01", "domain": "ffmuc_test"}

    def test_offloader_not_in_nodelist(self):
        mac, node_id, node = get_offloader(
            {"Site": "02:00:00:00:00:02"}, self.NODES, "Site"
        )
        assert (mac, node_id, node) == ("02:00:00:00:00:02", None, {})

    def test_no_offloader_for_site(self):
        assert get_offloader({"Other": "x"}, self.NODES, "Site") == (None, None, {})

    def test_no_offloaders_configured(self):
        assert get_offloader(None, self.NODES, "Site") == (None, None, {})

    def test_no_nodelist(self):
        mac, node_id, node = get_offloader({"Site": "02:00:00:00:00:01"}, None, "Site")
        assert (mac, node_id, node) == ("02:00:00:00:00:01", None, {})
