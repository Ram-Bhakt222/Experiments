# Experiments

Flatten folders for Qdrant ingestion.

## Flattening files
Use the helper script to copy or move every file from a directory tree into a single folder. The script can also emit a JSONL manifest that records the original and flattened paths so you can keep metadata for Qdrant.

```bash
python scripts/flatten_for_qdrant.py /path/to/source /path/to/output \
  --mode copy \
  --manifest /path/to/output/manifest.jsonl
```

- `--mode copy` (default) leaves the source tree intact; switch to `move` if you want to relocate the files.
- Filenames are flattened using `__` between path segments (e.g., `docs/api/readme.md` becomes `docs__api__readme.md`). If duplicates occur, numeric suffixes are added.
- The manifest is optional but useful when you need to relate flattened files back to their origin during ingestion.
