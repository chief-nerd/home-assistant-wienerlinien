# wienerlinien

This integration was inspired originally by [home-assistant-wienerlinien](https://github.com/tofuSCHNITZEL/home-assistant-wienerlinien).

There are several differences here.

This updated integration is ONLY configurable via the UI.

All data is requested via a single API call for all stops, the update frequency for this is configurable with a default of 30 seconds.

The amount of departures is also configurable, up to a max of 10. Whether the stop itself has 10 departures available does not matter, the filtering is done after the data collection, and we always request all info available.

As with the integration that inspired this one, you should find the relevant stop ids (rbl numbers) from the following site resource: [Matthias Bendel](https://github.com/mabe-at) [https://till.mabe.at/rbl/](https://till.mabe.at/rbl/)

I have not submitted this integration to HACS, therefore you need to add the repo manually to HACS repos.

I'm still debating whether to submit to HACS or not.

## Setup

Initial setup is straightforward and hopefully easy to follow.

![image](./images/initial-config.png)

Each rbl number added creates a new device with 1-n line sensors, as shown in the following images.

![image](./images/config-success.png)

![image](./images/device-overview.png)

A given line monitor contains a list of departures, this departures list is updated based on the interval given in the config.

![image](./images/monitor-example.png)

The integration supports both options flow and reconfigure flow.

![image](./images/reconfigure-options.png)

The options flow supports modification of the departures list size, and the update interval.

![image](./images/options-flow.png)

The reconfigure flow supports modification of all cconfiguration settings, including adding/removing rbl numbers.

![image](./images/reconfigure-flow.png)

### Visualising the data

Based on the work done by [vinergha](https://github.com/vingerha) you can very easily create some nice [visualisations](https://github.com/vingerha/gtfs2/wiki/5.-Visualizing-the-data#local-stops-and-departures) on your dashboards.

#### Table

```yaml
type: custom:auto-entities
filter:
  include:
    - entity_id: "*_outbound_*"
    - entity_id: "*_inbound_*"
  exclude:
    - state: unavailable
card:
  type: custom:flex-table-card
  clickable: true
  max_rows: 50
  title: Wiener Linien
  strict: true
  columns:
    - name: Route
      data: departures
      modify: "'<ha-icon icon=' + x.line_icon + '></ha-icon>' + x.line_name"
    - name: Time
      data: departures
      modify: x.real_time
    - name: Stop
      data: departures
      modify: x.location
    - name: Headsign
      data: departures
      modify: x.towards
```
![image](./images/table.png)

#### Map
```yaml
type: custom:auto-entities
filter:
  include:
    - entity_id: "*_outbound_*"
    - entity_id: "*_inbound_*"
    - entity_id: person.foo
card:
  type: map
  clickable: true
  title: Stops
  dark_mode: false
  default_zoom: 15
  auto_fit: true
```
![image](./images/map.png)


## Resources and Thanks

- [Matthias Bendel](https://github.com/mabe-at)

- [tofuSCHNITZEL](https://github.com/tofuSCHNITZEL)

- [vinergha](https://github.com/vingerha)

- This platform is using the [Wienerlinien API](http://www.wienerlinien.at) API to get the information.
'Datenquelle: Stadt Wien – data.wien.gv.at'
Lizenz (CC BY 3.0 AT)