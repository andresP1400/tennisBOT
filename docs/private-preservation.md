# Preserve TennisBOT outside Codex

GitHub preserves committed source, provenance and aggregate reports. It deliberately excludes `models/saved/`, `data/raw/`, `reports/` and credentials. Publishing the cloud environment creates a separate environment version; it is not evidence of a copy on your Mac or independent storage. Later private forecasts and research artifacts can postdate that publication.

The previous `ceaf719` Git bundle and private archive were verified against all 370 tracked source files and all 20 existing personal model/pointer/report files. A fresh audit also verified SQLite integrity and 159 forecasts / 18 outcomes. Prior versions and losing forecasts remain intact. These workspace archives are recoverable local copies, not an off-machine backup.

For the continuation checkpoint, a new `TennisBOT-private-<commit>-<timestamp>.tar.gz` and matching `.tar.gz.sha256` are prepared under `/workspace`. The archive contains:

- The complete Git history bundle and all tracked source, including dependency constraints and license attribution.
- The real licensed raw data, every saved model version/pointer, all private research reports/artifacts and consistent SQLite snapshots taken using SQLite's backup API.
- `BACKUP-MANIFEST.json` with source commit, archive creation time, ledger counts and individual file SHA-256 hashes.

Credentials, dependency caches and build outputs are excluded. Archive/checksum files have mode 0600. This is a private, unencrypted archive: transfer and store it only using your private channel or encrypted storage. It must not be uploaded to the source repository.

## Exact preservation action

Copy **both** the `.tar.gz` archive and its `.tar.gz.sha256` file from `/workspace` to your Mac or independent private storage. The assistant's completion message supplies the exact filenames and file links. A workspace path/file link identifies the file; it does not prove that the interface supports download or that a transfer has occurred. No public file server, remote SSH endpoint or external storage transfer is provisioned by this task. If your interface cannot export workspace files, an authorized secure transfer channel is still required. Keep the published environment while arranging that transfer.

Place the files together in a dedicated folder on your Mac. Open Terminal, change to that folder, then verify:

```bash
shasum -a 256 -c TennisBOT-private-*.tar.gz.sha256
```

Every archive must report `OK`. Inspect contents without modifying your application:

```bash
tar -tzf TennisBOT-private-<commit>-<timestamp>.tar.gz
```

Replace that filename with the exact transferred archive. Confirm `BACKUP-MANIFEST.json`, `source-history.bundle`, `tennisBOT/models/saved/personal/`, and `tennisBOT/reports/personal/prediction-events.sqlite3` are present. Keep a second copy on your private backup disk/storage; Time Machine can protect the Mac copy. Do not delete the cloud copies until independent recovery is verified.

For recovery, extract into a **new empty directory**, never over an existing installation or ledger. The archive supplies a complete source tree plus the Git bundle for recovering commit history. Use [the Mac setup guide](mac-daily-use.md) for constrained dependencies and startup. Existing model bytes need those compatible versions; a fresh clone alone does not contain trained models. No automatic ledger merge is implemented. Retain existing local/cloud ledgers separately if both have accumulated forecasts.

## Publication and continued development

The publication confirmed in the October 16 continuation references `ceaf719` in environment configuration. New follow-up commits are pushed to the same PR; a subsequently saved draft can pin the newer source and startup notes. Saving that draft does not republish it. Review/save/publish the updated draft if you want the continuation included in the next environment snapshot. This still does not create an independent off-machine private backup or prove a future-task restore.
