# Cron jobs

Scheduled jobs for this profile live in `cron/jobs.json`. The template ships an
empty list (`{"jobs": []}`) so nothing runs until you add a job. Whether the
runtime will execute jobs at all is also gated by the top-level `cron_mode` key
in `config.yaml` (the template defaults it to `deny`).

## Schema

`jobs.json` is `{"jobs": [ <job>, ... ]}`. Each `<job>` object:

| Field         | Type    | Notes                                                        |
|---------------|---------|--------------------------------------------------------------|
| `id`          | string  | Stable unique id for the job.                                |
| `name`        | string  | Human-readable label.                                        |
| `prompt`      | string  | The instruction the agent runs (omit/empty when `no_agent`). |
| `skills`      | list    | Skill names made available for the run.                      |
| `script`      | string  | Optional script to execute instead of / alongside a prompt.  |
| `no_agent`    | bool    | If true, run `script` only — no agent turn.                  |
| `schedule`    | object  | `{ "kind": "cron"\|"interval", "expr": "...", "display": "..." }` |
| `repeat`      | bool    | Whether the job re-arms after running.                       |
| `enabled`     | bool    | If false, the job is kept but never scheduled.               |
| `state`       | string  | Runtime status (managed by the scheduler).                   |
| `created_at`  | string  | ISO-8601 timestamp (runtime-managed).                        |
| `next_run_at` | string  | ISO-8601 timestamp of the next fire (runtime-managed).       |

`schedule.expr` is a standard cron expression when `kind` is `cron`. Cron
expressions are evaluated against the profile's `timezone` (set in `config.yaml`;
blank means the host timezone).

## Example (do not ship enabled)

```json
{
  "jobs": [
    {
      "id": "daily-standup",
      "name": "Daily standup nudge",
      "prompt": "<<FILL-IN: what the agent should do on this schedule>>",
      "skills": [],
      "script": "",
      "no_agent": false,
      "schedule": { "kind": "cron", "expr": "0 9 * * 1-5", "display": "weekdays 9am" },
      "repeat": true,
      "enabled": false
    }
  ]
}
```
