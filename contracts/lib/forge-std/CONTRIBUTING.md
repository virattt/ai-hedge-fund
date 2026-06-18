## Contributing to Foundry

Thanks for your interest in improving Foundry!

There are multiple opportunities to contribute at any level. It doesn't matter if you are just getting started with Rust or are the most weathered expert, we can use your help.

This document will help you get started. **Do not let the document intimidate you**.
It should be considered as a guide to help you navigate the process.

The [dev Telegram][dev-tg] is available for any concerns you may have that are not covered in this guide.

### Code of Conduct

The Foundry project adheres to the [Rust Code of Conduct][rust-coc]. This code of conduct describes the _minimum_ behavior expected from all contributors.

Instances of violations of the Code of Conduct can be reported by contacting the team at [me@gakonst.com](mailto:me@gakonst.com).

### Ways to contribute

There are fundamentally four ways an individual can contribute:

1. **By opening an issue:** For example, if you believe that you have uncovered a bug
   in Foundry, creating a new issue in the issue tracker is the way to report it.
2. **By adding context:** Providing additional context to existing issues,
   such as screenshots and code snippets, which help resolve issues.
3. **By resolving issues:** Typically this is done in the form of either
   demonstrating that the issue reported is not a problem after all, or more often,
   by opening a pull request that fixes the underlying problem, in a concrete and
   reviewable manner.

**Anybody can participate in any stage of contribution**. We urge you to participate in the discussion
around bugs and participate in reviewing PRs.

### Contributions Related to Spelling and Grammar

At this time, we will not be accepting contributions that only fix spelling or grammatical errors in documentation, code or
elsewhere.

### Asking for help

If you have reviewed existing documentation and still have questions, or you are having problems, you can get help in the following ways:

-   **Asking in the support Telegram:** The [Foundry Support Telegram][support-tg] is a fast and easy way to ask questions.
-   **Opening a discussion:** This repository comes with a discussions board where you can also ask for help. Click the "Discussions" tab at the top.

As Foundry is still in heavy development, the documentation can be a bit scattered.
The [Foundry Book][foundry-book] is our current best-effort attempt at keeping up-to-date information.

### Submitting a bug report

When filing a new bug report in the issue tracker, you will be presented with a basic form to fill out.

If you believe that you have uncovered a bug, please fill out the form to the best of your ability. Do not worry if you cannot answer every detail; just fill in what you can. Contributors will ask follow-up questions if something is unclear.

The most important pieces of information we need in a bug report are:

-   The Foundry version you are on (and that it is up to date)
-   The platform you are on (Windows, macOS, an M1 Mac or Linux)
-   Code snippets if this is happening in relation to testing or building code
-   Concrete steps to reproduce the bug

In order to rule out the possibility of the bug being in your project, the code snippets should be as minimal
as possible. It is better if you can reproduce the bug with a small snippet as opposed to an entire project!

See [this guide][mcve] on how to create a minimal, complete, and verifiable example.

### Submitting a feature request

When adding a feature request in the issue tracker, you will be presented with a basic form to fill out.

Please include as detailed of an explanation as possible of the feature you would like, adding additional context if necessary.

If you have examples of other tools that have the feature you are requesting, please include them as well.

### Resolving an issue

Pull requests are the way concrete changes are made to the code, documentation, and dependencies of Foundry.

Even minor pull requests, such as those fixing wording, are greatly appreciated. Before making a large change, it is usually
a good idea to first open an issue describing the change to solicit feedback and guidance. This will increase
the likelihood of the PR getting merged.

Please make sure that the following commands pass if you have changed the code:

```sh
forge fmt --check
forge test -vvv
```

To make sure your changes are compatible with all compiler version targets, run the following commands:

```sh
forge build --skip test --use solc:0.6.2
forge build --skip test --use solc:0.6.12
forge build --skip test --use solc:0.7.0
forge build --skip test --use solc:0.7.6
forge build --skip test --use solc:0.8.0
```

The CI will also ensure that the code is formatted correctly and that the tests are passing across all compiler version targets.

#### Adding cheatcodes

Please follow the guide outlined in the [cheatcodes](https://github.com/foundry-rs/foundry/blob/master/docs/dev/cheatcodes.md#adding-a-new-cheatcode) documentation of Foundry.

When making modifications to the native cheatcodes or adding new ones, please make sure to run [`./scripts/vm.py`](./scripts/vm.py) to update the cheatcodes in the [`src/Vm.sol`](./src/Vm.sol) file.

By default the script will automatically generate the cheatcodes from the [`cheatcodes.json`](https://raw.githubusercontent.com/foundry-rs/foundry/master/crates/cheatcodes/assets/cheatcodes.json) file but alternatively you can provide a path to a JSON file containing the Vm interface, as generated by Foundry, with the `--from` flag.

```sh
./scripts/vm.py --from path/to/cheatcodes.json
```

It is possible that the resulting [`src/Vm.sol`](./src/Vm.sol) file will have some changes that are not directly related to your changes, this is not a problem.

#### Commits

It is a recommended best practice to keep your changes as logically grouped as possible within individual commits. There is no limit to the number of commits any single pull request may have, and many contributors find it easier to review changes that are split across multiple commits.

That said, if you have a number of commits that are "checkpoints" and don't represent a single logical change, please squash those together.

#### Opening the pull request

From within GitHub, opening a new pull request will present you with a template that should be filled out. Please try your best at filling out the details, but feel free to skip parts if you're not sure what to put.

#### Discuss and update

You will probably get feedback or requests for changes to your pull request.
This is a big part of the submission process, so don't be discouraged! Some contributors may sign off on the pull request right away, others may have more detailed comments or feedback.
This is a necessary part of the process in order to evaluate whether the changes are correct and necessary.

**Any community member can review a PR, so you might get conflicting feedback**.
Keep an eye out for comments from code owners to provide guidance on conflicting feedback.

#### Reviewing pull requests

**Any Foundry community member is welcome to review any pull request**.

All contributors who choose to review and provide feedback on pull requests have a responsibility to both the project and individual making the contribution. Reviews and feedback must be helpful, insightful, and geared towards improving the contribution as opposed to simply blocking it. If there are reasons why you feel the PR should not be merged, explain what those are. Do not expect to be able to block a PR from advancing simply because you say "no" without giving an explanation. Be open to having your mind changed. Be open to working _with_ the contributor to make the pull request better.

Reviews that are dismissive or disrespectful of the contributor or any other reviewers are strictly counter to the Code of Conduct.

When reviewing a pull request, the primary goals are for the codebase to improve and for the person submitting the request to succeed. **Even if a pull request is not merged, the submitter should come away from the experience feeling like their effort was appreciated**. Every PR from a new contributor is an opportunity to grow the community.

##### Review a bit at a time

Do not overwhelm new contributors.

It is tempting to micro-optimize and make everything about relative performance, perfect grammar, or exact style matches. Do not succumb to that temptation.

Focus first on the most significant aspects of the change:

1. Does this change make sense for Foundry?
2. Does this change make Foundry better, even if only incrementally?
3. Are there clear bugs or larger scale issues that need attending?
4. Are the commit messages readable and correct? If it contains a breaking change, is it clear enough?

Note that only **incremental** improvement is needed to land a PR. This means that the PR does not need to be perfect, only better than the status quo. Follow-up PRs may be opened to continue iterating.

When changes are necessary, _request_ them, do not _demand_ them, and **do not assume that the submitter already knows how to add a test or run a benchmark**.

Specific performance optimization techniques, coding styles and conventions change over time. The first impression you give to a new contributor never does.

Nits (requests for small changes that are not essential) are fine, but try to avoid stalling the pull request. Most nits can typically be fixed by the Foundry maintainers merging the pull request, but they can also be an opportunity for the contributor to learn a bit more about the project.

It is always good to clearly indicate nits when you comment, e.g.: `Nit: change foo() to bar(). But this is not blocking`.

If your comments were addressed but were not folded after new commits, or if they proved to be mistaken, please, [hide them][hiding-a-comment] with the appropriate reason to keep the conversation flow concise and relevant.

##### Be aware of the person behind the code

Be aware that _how_ you communicate requests and reviews in your feedback can have a significant impact on the success of the pull request. Yes, we may merge a particular change that makes Foundry better, but the individual might just not want to have anything to do with Foundry ever again. The goal is not just having good code.

##### Abandoned or stale pull requests

If a pull request appears to be abandoned or stalled, it is polite to first check with the contributor to see if they intend to continue the work before checking if they would mind if you took it over (especially if it just has nits left). When doing so, it is courteous to give the original contributor credit for the work they started, either by preserving their name and e-mail address in the commit log, or by using the `Author: ` or `Co-authored-by: ` metadata tag in the commits.

_Adapted from the [ethers-rs contributing guide](https://github.com/gakonst/ethers-rs/blob/master/CONTRIBUTING.md)_.

### Releasing

Releases are automatically done by the release workflow when a tag is pushed, however, these steps still need to be taken:

1. Ensure that the versions in the relevant `Cargo.toml` files are up-to-date.
2. Update documentation links
3. Perform a final audit for breaking changes.

[rust-coc]: https://github.com/rust-lang/rust/blob/master/CODE_OF_CONDUCT.md
[dev-tg]: https://t.me/foundry_rs
[foundry-book]: https://github.com/foundry-rs/foundry-book
[support-tg]: https://t.me/foundry_support
[mcve]: https://stackoverflow.com/help/mcve
[hiding-a-comment]: https://help.github.com/articles/managing-disruptive-comments/#hiding-a-comment
