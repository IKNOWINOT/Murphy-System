"""
OpenWeatherMap Integration — Murphy System World Model Connector.

Uses OpenWeatherMap API v2.5 (free) and One Call API 3.0 (paid).
Required credentials: OPENWEATHERMAP_API_KEY
Setup: https://openweathermap.org/api
"""
from __future__ import annotations
import logging

from typing import Any, Dict, List, Optional, Union

from .base_connector import BaseIntegrationConnector


class OpenWeatherMapConnector(BaseIntegrationConnector):
    """OpenWeatherMap API connector."""

    INTEGRATION_NAME = "OpenWeatherMap"
    BASE_URL = "https://api.openweathermap.org"
    CREDENTIAL_KEYS = ["OPENWEATHERMAP_API_KEY"]
    REQUIRED_CREDENTIALS = ["OPENWEATHERMAP_API_KEY"]
    FREE_TIER = True
    SETUP_URL = "https://home.openweathermap.org/users/sign_up"
    DOCUMENTATION_URL = "https://openweathermap.org/api"

    def _api_key(self) -> str:
        return self._credentials.get("OPENWEATHERMAP_API_KEY", "")

    def _weather_params(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"appid": self._api_key(), "units": "metric"}
        if extra:
            params.update(extra)
        return params

    def _build_headers(self) -> Dict[str, str]:
        return {"Content-Type": "application/json"}

    # -- Current Weather --

    def get_current_weather(self, location: Union[str, Dict[str, float]]) -> Dict[str, Any]:
        """Get current weather for a city name or {lat, lon} dict."""
        if isinstance(location, str):
            params = self._weather_params({"q": location})
        else:
            params = self._weather_params({"lat": location["lat"], "lon": location["lon"]})
        return self._get("/data/2.5/weather", params=params)

    def get_current_weather_by_zip(self, zip_code: str, country: str = "us") -> Dict[str, Any]:
        return self._get("/data/2.5/weather",
                         params=self._weather_params({"zip": f"{zip_code},{country}"}))

    # -- Forecast --

    def get_forecast(self, location: Union[str, Dict[str, float]],
                     days: int = 5) -> Dict[str, Any]:
        """5-day / 3-hour forecast."""
        cnt = min(days * 8, 40)  # max 40 timestamps = 5 days
        if isinstance(location, str):
            params = self._weather_params({"q": location, "cnt": cnt})
        else:
            params = self._weather_params({"lat": location["lat"], "lon": location["lon"], "cnt": cnt})
        return self._get("/data/2.5/forecast", params=params)

    def get_hourly_forecast(self, lat: float, lon: float) -> Dict[str, Any]:
        """Hourly forecast via One Call API 3.0."""
        return self._get("/data/3.0/onecall",
                         params=self._weather_params({
                             "lat": lat, "lon": lon,
                             "exclude": "current,minutely,daily,alerts"}))

    # -- Historical --

    def get_historical_weather(self, lat: float, lon: float, dt: int) -> Dict[str, Any]:
        """Historical weather — dt is Unix timestamp."""
        return self._get("/data/3.0/onecall/timemachine",
                         params=self._weather_params({"lat": lat, "lon": lon, "dt": dt}))

    # -- Air Quality --

    def get_air_quality(self, lat: float, lon: float) -> Dict[str, Any]:
        return self._get("/data/2.5/air_pollution",
                         params=self._weather_params({"lat": lat, "lon": lon}))

    def get_air_quality_forecast(self, lat: float, lon: float) -> Dict[str, Any]:
        return self._get("/data/2.5/air_pollution/forecast",
                         params=self._weather_params({"lat": lat, "lon": lon}))

    # -- UV Index --

    def get_uv_index(self, lat: float, lon: float) -> Dict[str, Any]:
        return self._get("/data/2.5/uvi",
                         params=self._weather_params({"lat": lat, "lon": lon}))

    # -- Weather Alerts --

    def get_alerts(self, lat: float, lon: float) -> Dict[str, Any]:
        return self._get("/data/3.0/onecall",
                         params=self._weather_params({
                             "lat": lat, "lon": lon,
                             "exclude": "current,minutely,hourly,daily"}))

    # -- Geocoding --

    def geocode(self, city: str, country: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
        q = f"{city},{country}" if country else city
        return self._get("/geo/1.0/direct",
                         params={"q": q, "limit": limit, "appid": self._api_key()})

    def reverse_geocode(self, lat: float, lon: float, limit: int = 5) -> Dict[str, Any]:
        return self._get("/geo/1.0/reverse",
                         params={"lat": lat, "lon": lon, "limit": limit,
                                 "appid": self._api_key()})

    # -- Health --

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("health_check")
        result = self.get_current_weather("London")
        result["integration"] = self.INTEGRATION_NAME
        return result
