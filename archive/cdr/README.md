# The CDR bulk-file archive (#46)

**Proposal in the pull request for #46, for Eleonora to review. Not a decision record, and not an input declaration.**

The FFIEC CDR rebuilds every quarter's "Call Reports -- Single Period" bulk file from its current content, so the
first-filed figures of a past quarter cannot be recovered (`docs/research/slr-headroom-due-diligence.md`). Eleonora
accepted starting an archive (ruling on PR #44, Q2). This archive gives quarters filed from now on a first print. It does
not replace reading 2 (latest-filed figures, labelled).

## What is kept, and where

- `scripts/archive_cdr.py` downloads the latest two quarter-ends listed on the bulk page and records, for each distinct
  SHA-256, an entry in `manifest.json`: quarter-end, URL, file name, SHA-256, size, `first_retrieved_utc` and
  `last_checked_utc`. An unchanged file moves only `last_checked_utc`; a new SHA-256 is a new entry.
- `.github/workflows/cdr-archive.yml` runs it on weekdays. It never pushes to `main`: it commits the manifest to the
  branch `cdr-archive` and uploads each new zip (`<quarter-end>-<sha256>.zip`, 6 to 8 MB) to the release `cdr-archive`
  as an asset, which does not expire. The manifest on `main` is the state at the time of the last merge; the branch
  `cdr-archive` is the live one.
- The zips are not tracked in git.

## Availability

A day's archived file is **available from its `first_retrieved_utc`, never earlier.** The portal records no posting time,
and the "Last Date/Time Submission Updated On" column of a file says when the latest submission was made, not when it was
public. Between two retrievals the archive says nothing: a figure first filed and amended inside the gap is seen only in
its amended form. The daily cadence bounds that gap at one weekday (three days over a weekend). A quarter's first retrieval
after its quarter-end is the first print only if no filer had amended by then; the archive cannot show that either way.

This is not a declaration yet. A declaration (`declarations/`) comes when an input reads from the archive.
