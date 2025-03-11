# CAMPS
Completely Automated Music Processing System

## Running CAMPS

Use the `camps_mt.py` file for now, `camps_legacy.py` is deprecated.

## What is CAMPS?
CAMPS is a script to automatically convert new songs to MP3, along with our desired bitrate in order to save on disk space. It will also automatically set any missing metadata, and then log to a Slack webhook when completed.

## Why does CAMPS exist?
Unfortunately, not all music gets added from the same source or as the right filetype or bitrate. This means we have to convert it to be used by our playout software.
