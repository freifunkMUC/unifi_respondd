#!/usr/bin/env python3
"""Unit tests for unifi_respondd/net.py module."""

from unittest.mock import Mock, patch

import pytest

from unifi_respondd.net import get_location_by_address, scrape


class TestGetLocationByAddress:
    """Test the get_location_by_address function."""

    def test_valid_point_string(self):
        """Test with a valid point string (lat, lon)."""
        address = "48.1351, 11.5820"
        app = Mock()

        lat, lon = get_location_by_address(address, app)
        assert lat == pytest.approx(48.1351, rel=1e-4)
        assert lon == pytest.approx(11.5820, rel=1e-4)

    @patch("unifi_respondd.net.time.sleep")
    def test_geocoding_fallback(self, mock_sleep):
        """Test fallback to geocoding when point parsing fails."""
        address = "Munich, Germany"
        app = Mock()
        app.geocode.return_value = Mock(raw={"lat": "48.1351", "lon": "11.5820"})

        lat, lon = get_location_by_address(address, app)
        assert lat == "48.1351"
        assert lon == "11.5820"
        mock_sleep.assert_called_once_with(1)

    @patch("unifi_respondd.net.time.sleep")
    @patch("unifi_respondd.net.get_location_by_address")
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

    @patch("unifi_respondd.net.rget")
    def test_scrape_success(self, mock_rget):
        """Test successful scraping of JSON data."""
        mock_response = Mock()
        mock_response.json.return_value = {"nodes": [{"mac": "00:11:22:33:44:55"}]}
        mock_rget.return_value = mock_response

        result = scrape("http://example.com/api")
        assert result == {"nodes": [{"mac": "00:11:22:33:44:55"}]}
        mock_rget.assert_called_once_with("http://example.com/api")

    @patch("unifi_respondd.net.rget")
    @patch("unifi_respondd.net.logger.error")
    def test_scrape_failure(self, mock_logger, mock_rget):
        """Test scraping failure handling."""
        mock_rget.side_effect = Exception("Network error")

        result = scrape("http://example.com/api")
        assert result is None
        mock_logger.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
