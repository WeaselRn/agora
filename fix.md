runner.py — one unnecessary change introduced
The callback null-checks got over-engineered. You now have cb, cb1, cb2, cb3, cb4, cb5 — all just aliases for callback. This adds noise without any benefit. The original if callback: pattern was cleaner and identical in behaviour. Not a bug, just clutter worth cleaning up when you have a spare minute:
python# instead of:
cb = callback
if cb is not None:
    await cb("evaluation", asdict(result))

# just:
if callback:
    await callback("evaluation", asdict(result))
```