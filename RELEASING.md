# Releasing AnnexOps

This repo keeps releases lightweight and reproducible.

## Checklist

1. Ensure `main` is green in CI.
2. Update `CHANGELOG.md`:
   - Move items from `[Unreleased]` into a new version section.
3. Create an annotated tag and push it:

```bash
git checkout main
git pull
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

4. Create a GitHub Release for the tag (include changelog notes).

