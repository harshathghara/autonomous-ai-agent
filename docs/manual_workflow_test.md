# Manual multi-step workflow test (Week 4)

Run these in order after `pytest -v` passes. Use `-v` to see each tool call and `-y` to auto-approve send/calendar actions.

## 1. Save a preference

```powershell
python run_agent.py -v "Remember that I prefer all meetings at 10 am"
```

Expected: `memory_save` with `preferred_meeting_time`.

## 2. Research + email (4+ steps)

```powershell
python run_agent.py -v -y "Search for the top 3 Python conferences in 2026 and email me a short summary"
```

Expected tools: `web_search` → `email_send` (may also call `memory_read`).

## 3. Schedule using memory

```powershell
python run_agent.py -v -y "Schedule a meeting tomorrow named daily standup"
```

Expected: `memory_read` or prompt includes `preferred_meeting_time`; `calendar_write` at **10:00**.

## 4. Confirmation decline (error recovery)

```powershell
python run_agent.py -v "Email me a test message saying hello"
```

When prompted `Proceed? [y/N]:`, press **Enter** (decline).

Expected: agent explains the email was **not** sent; no crash.

## 5. Full workflow (plan example)

```powershell
python run_agent.py -v -y "Find 2 Python conferences in 2026, email me a summary, and block one hour on my calendar tomorrow for reviewing them"
```

Expected tools (order may vary): `web_search`, `email_send`, `calendar_write`.

## 6. Delete a memory

```powershell
python run_agent.py -v "Delete my preferred meeting time memory"
```

Expected: `memory_read` then `memory_delete`.
