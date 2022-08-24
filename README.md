<h1 align="center">
  🚲 <br>
  Velo-action
</h1>

<p align="center">
  A GitHub Action to create releases and trigger deployments
</p>

This GitHub actions is part of the Velo deploy system at Oda.

This repo is public since GitHub actions does not yet
[support actions in private repos](https://github.com/github/roadmap/issues/74).

## Local execution

[The Makefile](../Makefile) covers the most common commands you need. For testing,
you should check out the [example-deploy-project](https://github.com/kolonialno/example-deploy-project/) to have a working deployable application.

 1. Setup dependencies and virtual env: `make install`
 2. All configuration os done via [development variables](../env.dev-vars). It
    should be easy to integrate this env-file into your IDE as well

Now you can execute velo-action using `make run`.

In order to use the containerized build, use `make run_docker`.

## Testing

This can be used to test a pre-release or a PR draft.

1. Create a PR.
2. You may need to update the `action.yml`. The docker image should have the corresponding tag as if you run `make version`. Update `action.yml` with this.
3. Head over to your repository where you want to test `velo-action` in the workflow. Copy the latest commit hash and add it to `<commit>`.

    ```yaml
   - name: Use Velo-action
    uses: kolonialno/velo-action@<commit>
    with:
      service_account_key: ${{ secrets.VELO_ACTION_GSA_KEY_PROD_PUBLIC }}
      ...
    ```

## Create a release

A new draft [Github release of Velo-action](https://github.com/kolonialno/velo-action/releases) is created on every merge to main.

Manually convert the release from a draft to a release to [release it](https://github.com/kolonialno/velo-action/releases).

1. Determine the version of the current release by running `make verison`.
   Bump version if necessary according [SevVer](https://semver.org/) by adding this to the commit message (the PR commits are squashed)

   - `+semver: major`
   - `+semver: minor`

In short:

Given a version number MAJOR.MINOR.PATCH, increment the:

MAJOR version when you make incompatible API changes
MINOR version when you add functionality in a backwards compatible manner
PATCH version when you make backwards compatible bug fixes

Additional labels for pre-release and build metadata are available as extensions to the MAJOR.MINOR.PATCH format.

1. Update the `changelog.md` with the changes for this release and the upcoming verison.

*IMPORTANT!* A new release will trigger Dependabot. Dependabot will create a PR in all repos that use velo-action.  
