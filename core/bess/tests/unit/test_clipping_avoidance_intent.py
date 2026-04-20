"""Behavioural tests for the CLIPPING_AVOIDANCE strategic intent.

The intent is introduced to label periods where the DP chooses to charge the
battery specifically because solar overproduction would otherwise be clipped by
the inverter's AC export cap. These tests verify:

1. The inverter-control mapping for the new intent is registered correctly
   (the hardware-visible contract).
2. When sustained DC overproduction meets a restrictive inverter cap, at least
   one resulting period carries the CLIPPING_AVOIDANCE label.
3. Without the cap, the same scenario uses a different label — so the relabel
   is gated on the feature being enabled.
"""

from core.bess.dp_battery_algorithm import optimize_battery_schedule
from core.bess.min_schedule import GrowattScheduleManager
from core.bess.settings import BatterySettings

battery_settings = BatterySettings()


def test_intent_to_mode_registers_clipping_avoidance():
    assert GrowattScheduleManager.INTENT_TO_MODE["CLIPPING_AVOIDANCE"] == "grid_first"


def test_intent_to_control_registers_clipping_avoidance():
    control = GrowattScheduleManager.INTENT_TO_CONTROL["CLIPPING_AVOIDANCE"]
    assert control == {
        "grid_charge": False,
        "charge_rate": 100,
        "discharge_rate": 0,
    }


def _sustained_clipping_scenario():
    horizon = 24
    buy_price = [0.5] * horizon
    sell_price = [0.3] * horizon
    home_consumption = [0.5] * horizon
    # 4 kWh per 15-min period = 16 kW — double an 8 kW inverter's export cap.
    solar_production = [0.0] * 8 + [4.0] * 8 + [0.0] * 8
    return {
        "buy_price": buy_price,
        "sell_price": sell_price,
        "home_consumption": home_consumption,
        "solar_production": solar_production,
        "initial_soe": battery_settings.reserved_capacity,
        "battery_settings": battery_settings,
    }


def test_sustained_clipping_produces_clipping_avoidance_intent():
    result = optimize_battery_schedule(
        **_sustained_clipping_scenario(),
        inverter_max_power_kw=8.0,
    )
    intents = {p.decision.strategic_intent for p in result.period_data}
    assert "CLIPPING_AVOIDANCE" in intents


def test_feature_disabled_never_produces_clipping_avoidance_intent():
    result = optimize_battery_schedule(
        **_sustained_clipping_scenario(),
        inverter_max_power_kw=0.0,
    )
    intents = {p.decision.strategic_intent for p in result.period_data}
    assert "CLIPPING_AVOIDANCE" not in intents
