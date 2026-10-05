"""The coordinated vehicle must not drift away after a route ends."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from openipc_cinewhoop_demo.simple_indoor_autonomy import (
    SimpleIndoorAutonomy, CRUISE, TURN,
)


@pytest.mark.parametrize('state', [CRUISE, TURN])
@pytest.mark.parametrize('bearing,target', [(None, (1., 0.)), (0., (.05, 0.))])
def test_missing_or_reached_coordinated_target_holds(state, bearing, target):
    params = dict(scan_timeout_s=1., require_target=True, target_arrival_m=.12)
    node = SimpleNamespace(
        _state=state, _position=(0., 0.), _target=target,
        _scan_age_s=lambda: 0., _battery_reason=lambda: None,
        _bearing_to_target=lambda: bearing,
        get_parameter=lambda name: SimpleNamespace(value=params[name]),
        _publish=Mock())
    SimpleIndoorAutonomy._tick(node)
    node._publish.assert_called_once_with(0.)


class _Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return _Stamp(self.t)


class _Stamp:
    def __init__(self, t):
        self.t = t

    def __sub__(self, other):
        return SimpleNamespace(nanoseconds=int((self.t - other.t) * 1e9))


def _service_node(clock):
    params = dict(service_timeout_s=3.)
    return SimpleNamespace(
        _pending=None, _pending_since=None,
        get_clock=lambda: clock, get_logger=lambda: Mock(),
        get_parameter=lambda name: SimpleNamespace(value=params[name]))


def test_an_unanswered_service_call_is_asked_again():
    # One lost request over XRCE-DDS used to leave prearm pending for good.
    clock = _Clock()
    node = _service_node(clock)
    lost = Mock()
    lost.done.return_value = False
    client = Mock(srv_name='/ap/v1/prearm_check')
    client.service_is_ready.return_value = True
    client.call_async.side_effect = [lost, Mock()]

    SimpleIndoorAutonomy._call(node, client, 'request', Mock())
    clock.t = 2.9
    SimpleIndoorAutonomy._call(node, client, 'request', Mock())
    assert client.call_async.call_count == 1
    clock.t = 3.1
    SimpleIndoorAutonomy._call(node, client, 'request', Mock())
    assert client.call_async.call_count == 2
    client.remove_pending_request.assert_called_once_with(lost)
    assert node._pending is not lost


def test_an_answered_call_frees_the_next_one_at_once():
    clock = _Clock()
    node = _service_node(clock)
    answered = Mock()
    answered.done.return_value = True
    client = Mock(srv_name='/ap/v1/prearm_check')
    client.service_is_ready.return_value = True
    client.call_async.side_effect = [answered, Mock()]
    SimpleIndoorAutonomy._call(node, client, 'request', Mock())
    clock.t = 0.2
    SimpleIndoorAutonomy._call(node, client, 'request', Mock())
    assert client.call_async.call_count == 2
    client.remove_pending_request.assert_not_called()
