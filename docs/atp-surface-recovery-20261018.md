# ATP surface recovery — October 18, 2026

The advanced continuation branch is `codex/preserve-verified-tennisbot`.
The previously unpushed history-refresh commit `6524789f979888c85a3b19a0acef661f6e71d42a`
was pushed successfully and independently confirmed with `git ls-remote`.
No authentication change or force push was necessary.

## Reviewed tournament facts

The official public draw sheets explicitly identify the current tournaments,
cities, dates and **Hard** courts:

- Almaty: https://www.protennislive.com/posting/2026/9410/mds.pdf
- Brussels: https://www.protennislive.com/posting/2026/7485/mds.pdf

The organizers' current-season calendars corroborate identity and the
October 17–25 event windows, including qualifying; the draw headers give
October 19–25 for the main draw:
https://almatyopen.kz/en and https://europeanopen.be/about/.

Only minimal reviewed facts and response hashes are stored in the source
provenance file `docs/data-sources/atp-surfaces-20261018.json`. Full evidence
PDFs remain in private reports and private backups. Public availability is
not treated as a general license to redistribute draws, harvest results,
or reuse a database. No bulk collector or access-restriction bypass was added.

ESPN IDs are explicitly mapped independently of official tournament IDs.
These ATP reviews require exact normalized name, season, city and event-date
agreement. Missing cities, wrong identities, dates outside the event, and
future seasons fail closed. A bounded 512-entry positive/negative memory
cache uses checked-in reviewed facts without per-match network requests.
New evidence requires a reviewed source revision and process restart.

## Current live verification

At approximately 21:18 UTC:

| Tour | Genuine forecasts | Unsupported fixtures | Verified surfaces |
| --- | ---: | ---: | --- |
| ATP | 17 | 19 | 24 of 36 fixtures |
| WTA | 22 | 6 | All 28 fixtures |

The ATP forecasts comprise 11 Almaty and six Brussels matches. Seven other
surface-verified ATP fixtures lack sufficient or unambiguous historical
player coverage. Twelve fixtures labeled Grand Prix Auvergne-Rhône-Alpes
remain surface-unverified. Counts changed from the earlier 28-fixture feed;
no extra fixtures or outcomes were manufactured.

The accessible old Open Parc material concerns May 2024 and cannot verify
an October 2026 tournament. ATP overview/calendar requests returned HTTP
403, candidate organizer domains were unavailable, and no accessible
current authoritative Lyon surface evidence was established. IDs `110-2026`
and `452-2026` must not inherit the surface of an older event. To enable
these fixtures, obtain an official current draw/factsheet or an authorized
calendar confirming name, city, event dates and surface; then review its
provider identity explicitly and add date/venue mismatch tests. No purchase
is needed for the already recovered Almaty and Brussels coverage.

Chromium checked both dashboard tour selections against API forecast IDs,
model versions, winners and surface provenance. Probabilities normalize to
one. All six worker phases succeed; the 300-second unattended prediction
and settlement cycle is healthy. No frontend rebuild or redesign occurred.

## Preservation and checks

All 12 saved model/pointer files remain byte-identical to the verified
pre-change archive. Calibration, training, historical evaluation and feature
state were not modified. All 29 previous prediction rows and three outcomes
remain intact; 17 genuine future ATP forecast snapshots were appended,
bringing the ledger to 46 forecasts and three outcomes. No historical
forecasts were backdated.

251 backend tests pass, including 13 additional ATP surface cases. Ruff,
Black and strict mypy (143 source files) pass. Existing frontend source and
production build are unchanged; both tour selections were checked live.

Private archive creation uses
`/workspace/tennisbot-backups/create_private_backup.py`, verifies every file
hash and takes consistent SQLite backup-API snapshots. The newest surface
checkpoint is identified by
`/workspace/tennisbot-backups/surface-backup-result.json` and its SHA256
sidecar. Keep earlier archives. Workspace backups still need secure export
to independent private storage for protection against workspace loss.

Daily limitations remain partial/embargoed historical features, unknown
players, unverified future tournament identities, and external fixture-feed
availability. Existing warning and missing-data safeguards remain active.
There is no claim of complete ATP coverage or improved model accuracy.
