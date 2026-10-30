# Phone list

The two lists the POS **Identify Phone** button searches. Updated automatically every Monday by
`.github/workflows/update.yml`.

| File | What it holds | Source |
|---|---|---|
| `tacdb.json` | IMEI model codes (first 8 digits of an IMEI) → phone | [MoazEb/tac-database](https://github.com/MoazEb/tac-database) (MIT) |
| `devices.json` | Android model numbers → phone | Google Play supported devices list |
| `last-checked.txt` | Date of the last weekly check | |

A list is only replaced when its download worked and still holds at least 80% of the phones it had
before, so a broken source never empties the list.

To update straight away: **Actions → Update phone list → Run workflow**.
