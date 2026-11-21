# Robo Treasure Hunt — Stealth & Detection Mathematics

## 1. Treasure Bearing & Directional Vector
The nearest artifact bearing is calculated dynamically from robot odometry $(x_r, y_r, \theta_r)$ and target artifact coordinate $(x_t, y_t)$:

$$\Delta x = x_t - x_r, \quad \Delta y = y_t - y_r$$
$$d = \sqrt{\Delta x^2 + \Delta y^2}$$
$$\theta_{\text{target}} = \operatorname{atan2}(\Delta y, \Delta x)$$
$$\phi = \operatorname{atan2}(\sin(\theta_{\text{target}} - \theta_r), \cos(\theta_{\text{target}} - \theta_r))$$

The relative angle $\phi \in [-\pi, \pi]$ is quantised into 8 directional arrows:

| Relative Angle $\phi$ | Compass Symbol | Interpretation |
|---|---|---|
| $|\phi| < \pi/8$ | `↑` | Direct Ahead |
| $\pi/8 \le \phi < 3\pi/8$ | `↖` | Forward Left |
| $3\pi/8 \le \phi < 5\pi/8$ | `←` | Direct Left |
| $5\pi/8 \le \phi < 7\pi/8$ | `↙` | Rear Left |
| $|\phi| \ge 7\pi/8$ | `↓` | Direct Behind |
| $-7\pi/8 < \phi \le -5\pi/8$ | `↘` | Rear Right |
| $-5\pi/8 < \phi \le -3\pi/8$ | `→` | Direct Right |
| $-3\pi/8 < \phi \le -\pi/8$ | `↗` | Forward Right |

Collection trigger: $d \le 0.65\text{ m}$.

---

## 2. Timed Security Zones
The museum world contains 3 discrete cylindrical security sectors defined in `config/security.yaml`:

```
Zone 1: North Gallery    (x = -1.5, y =  2.0, r = 1.0 m, t_suspicion = 3.0s, t_alarm = 6.0s)
Zone 2: Central Gallery  (x =  1.0, y =  0.0, r = 0.8 m, t_suspicion = 2.0s, t_alarm = 5.0s)
Zone 3: Lower Gallery    (x =  0.0, y = -3.5, r = 1.0 m, t_suspicion = 4.0s, t_alarm = 8.0s)
```

### State Equations
For robot position $(x_r, y_r)$ and zone center $(x_z, y_z)$ with radius $R$:

$$d_z = \sqrt{(x_r - x_z)^2 + (y_r - y_z)^2}$$

1. **Intrusion Ingress**: $d_z \le R$.
   - Zone timer starts: $t_{\text{entry}} = t_{\text{now}}$.
2. **Suspicion Condition**: $(t_{\text{now}} - t_{\text{entry}}) \ge t_{\text{suspicion}}$.
   - HUD triggers yellow warning banner and live countdown.
3. **Alarm Condition**: $(t_{\text{now}} - t_{\text{entry}}) \ge t_{\text{alarm}}$.
   - State machine triggers `GAME_FAILED`. Movement disabled.
4. **Egress Clearing**: $d_z > R$.
   - Timers immediately reset. State returns to `CLEAR`.
