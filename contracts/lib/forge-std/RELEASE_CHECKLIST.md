# Release checklist

This checklist is meant to be used as a guide for the `forge-std` release process.

## Steps

- [ ] Update the version number in `package.json`
- [ ] Open and merge a PR with the version bump
- [ ] Tag the merged commit with the version number: `git tag v<X.Y.Z>`
- [ ] Push the tag to the repository: `git push --tags`
- [ ] Create a new GitHub release with the automatically generated changelog and the name set to `v<X.Y.Z>`
- [ ] Add `## Featured Changes` section to the top of the release notes
