# State-Conditional Outcome Learning

## Problem

An experienced consequence is not necessarily a stationary property of an
action.

For a bounded body signal:

```text
same objective resource
+
different initial body state
→ different experienced signal delta
```

Example:

```text
energy = 0.92
resource objectively adds a large amount
signal saturates at 1.0
experienced delta ≈ +0.08
```

Later:

```text
energy = 0.10
same resource
experienced delta can be much larger
```

A context-free mean can therefore become systematically misleading.

## Minimal v0.3.2.1 representation

The psyche still has no access to objective Body Truth.

It conditions only on accessible interoception:

```text
energy_signal
hydration_signal
fatigue_signal
discomfort_signal
```

Each is coarsened:

```text
LOW
MID
HIGH
```

A learned action record contains:

```text
count
mean
contexts:
  <physiology-context>:
    count
    mean
    state_context
```

The global mean remains useful for transfer.

The contextual mean is preferred when the current context has direct evidence.

## Uncertainty

If an action has global experience but no sample in the current physiology
context:

```text
global prediction exists
context count = 0
uncertainty = 1
```

This makes "I know this action, but not what it does to me in this state" an
explicit computational distinction.

## Navigation correction

Route value is now an advantage rather than an absolute destination value.

For a target opportunity:

```text
factor(position) = 1 / (1 + learned route cost)

navigation advantage =
target benefit
× [factor(destination) - factor(current)]
```

This eliminates reward for leaving a reached goal merely to create a route
back to it.

## Multi-objective navigation

Target benefit is split into:

```text
regulatory benefit
progress benefit
```

Under physiological urgency:

```text
regulatory navigation ↑
progress navigation ↓
```

The model therefore does not require a special:

```text
if starving:
    go_home()
```

rule.
