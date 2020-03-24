import datetime

import prometheus_client
import requests


class AquantaCollector(object):

    API_BASE = "https://apiv2.aquanta.io"
    PORTAL_BASE = "https://portal.aquanta.io/portal"

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self._prefix = "aquanta_"

    def make_metric(self, _is_counter, _name, _documentation, _value,
                    **_labels):
        if _is_counter:
            cls = prometheus_client.core.CounterMetricFamily
        else:
            cls = prometheus_client.core.GaugeMetricFamily
        label_names = list(_labels.keys())
        metric = cls(
            self._prefix + _name, _documentation or "No Documentation",
            labels=label_names)
        metric.add_metric([str(_labels[k]) for k in label_names], _value)
        return metric

    def get(self, *args, **kwargs):
        response = self.session.get(*args, **kwargs)
        if response.status_code == 401:
            response = self.session.post(
                self.PORTAL_BASE + "/login", json=dict(
                    username=self.username, password=self.password,
                    remember=True))
            if not response.ok:
                response.raise_for_status()
            response = self.session.get(*args, **kwargs)
        response.raise_for_status()
        return response

    def api_get(self, path, *args, **kwargs):
        return self.get(self.API_BASE + path, *args, **kwargs)

    def portal_get(self, path, *args, **kwargs):
        return self.get(self.PORTAL_BASE + path, *args, **kwargs)

    def fetch_last_metric(self, _is_counter, _name, _documentation, _dsn,
                          **labels):
        # Publishing of their metrics seems to be delayed by an hour. We'll
        # fetch the last six hours, and report the most recent one.
        now = datetime.datetime.utcnow().replace(microsecond=0)
        a_while_ago = now - datetime.timedelta(hours=6)
        datapoints = self.api_get(
            "/v2/datapoints?dsn=" + _dsn + "&name=" + _name +
            "&timestamp__gt=" + a_while_ago.isoformat() + "Z").json()
        most_recent = sorted(datapoints, key=lambda p: p["timestamp"])[-1]
        value = float(most_recent["value"])
        return self.make_metric(
            _is_counter, _name, _documentation, value, **labels)

    def collect(self):
        metrics = []
        devices = self.api_get("/v2/devices").json()
        for device in devices:
            dsn = device["dsn"]
            device_id = device["id"]
            labels = dict(dsn=dsn, device_id=device_id)

            status = self.api_get("/v2/deviceStatuses?dsn=" + dsn).json()[0]
            connectivity = self.api_get(
                "/v2/devices/" + dsn + "/connectivity").json()
            status["connectivity"] = connectivity["status"]
            info = self.api_get("/v2/devices/" + dsn + "/infocenter").json()
            status["mode"] = info["currentMode"]["type"]
            status.update(labels)
            metrics.append(self.make_metric(
                False, "status", None, 1, **status))

            metrics.append(self.fetch_last_metric(
                False, "Activity", None, dsn, **labels))
            metrics.append(self.fetch_last_metric(
                False, "Delta_E_Aux", None, dsn, **labels))

            self.session.put(
                self.PORTAL_BASE + "/set/selected_location?locationId=" +
                str(device_id)).raise_for_status()
            p = self.portal_get("/get").json()
            metrics.append(self.make_metric(
                False, "away", None, float(p["awayRunning"]), **labels))
            metrics.append(self.make_metric(
                False, "boost", None, float(p["boostRunning"]), **labels))
            metrics.append(self.make_metric(
                False, "hot_water_available", None,
                float(p["hw_avail_fraction"]), **labels))
            metrics.append(self.make_metric(
                False, "temperature", None,
                float(p["tempValue"]), **labels))

            p = self.portal_get("/get/settings").json()
            metrics.append(self.make_metric(
                False, "set_point", None, float(p["setPoint"]), **labels))
            metrics.append(self.make_metric(
                False, "set_point_min", None,
                float(p["setPointMin"]), **labels))
            metrics.append(self.make_metric(
                False, "set_point_max", None,
                float(p["setPointMax"]), **labels))
            config = dict(
                aquanta_intelligence=p["aquantaIntel"],
                aquanta_system=p["aquantaSystem"],
                height=p["height"],
                make=p["make"],
                model=p["model"],
                timer=p["timerEnabled"],
                tou=p["touEnabled"])
            config.update(labels)
            metrics.append(self.make_metric(
                False, "config", None, 1, **config))

        return metrics
