# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.0.0] - 2022-08-23

- Require Google service account as JSON to authenticate with Auth Proxy

## [1.0.17] - 2022-05-11

- Improve workflow and release with comments in PRs.
- Add test verifying version generation when no inputs is provided.
- Do not init tracer when `service_account_key` is not provided. This use case is valid when using `velo-action` to only generate version.

## [1.0.13] - 2022-05-09

Update dependencies.

## [1.0.2] - 2022-04-26

Fix bug preventing the action to output the generated version if `service_account_key` input is not set.

## [1.0.1] - 2022-04-25

### Changed

Fix bug preventing deploys of existing releases in Octopus Deploy. If a release exist, do not recreate it, but do perform the deploys as specified in `deploy_to_environments`.

## [1.0.0] - 2022-04-20

### Added

Breaking changes:

- Input: `project` removed.

  Velo-action will now read the Octopus Project from the AppSpec `app.yml` file as described in the [Velo docs](https://centro.prod.nube.tech/docs/default/component/velo/app-spec/#project).

  Example:

  ```yml
  # .deploy/app.yml
  ...
  project: <project_name>
  vars:
    ...
  ```

- Reverted back to using [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

### Changed

- Reformat the releasenotes in Octopus Deploy to use readable HTML formating with links.
- Generate draft Github release of Velo-action on merge to main.

## [0.4.0] - 2022-02-01

### Added

- New input `wait_for_success_seconds` to specify that the action waits until Octopus Deploy is finished.
  Deprecates the input `wait_for_deployment`

### Changed

- Action input `octopus_cli_api_key_secret` is renamed to `octopus_api_key_secret`
- Action input `octopus_cli_server_secret` is renamed to `octopus_server_secret`
- Interact with Octopus Deploy using the API. The Octo CLI is no longer part of the container.

## [0.3.0] - 2021-12-22

### Removed

- Remove generation of semantic version numbers (SemVer). Default is now the shortened git
  hash (`git rev-parse --short HEAD`). Removes although the gitversion dependency. Please see
  [this example](https://github.com/kolonialno/velo/blob/c3d5ddff650fd97357b72ef178d93e5519eb5efa/.github/workflows/ci.yml#L71-L114)
  if you still want to auto-generate the SemVer.

  NOTE: The length of the version string is dynamic. It can be longer if it is not unique.

## [0.2.79] - 2021-12-17

### Changed

- Use `subprocess.run()` when calling the octo CLI

## [0.2.21] - 2021-09-23

## Changed

- Moved image to the new [public Artifact Registry](https://console.cloud.google.com/artifacts/docker/nube-artifacts-prod/europe/nube-container-images-public?project=nube-artifacts-prod) in Google Cloud Platform. Will deprecate the Dockerhub image when there have been no pull for a month. This change require no changes by the user.
- Use python slim image, reduce image size from 1.8GB to 1.14GB.

## [0.2.14] - 2021-08-10

### Added

- Add argument `wait_for_deployment`. This will cause the action to wait until Octopus Deploy finished the deployment. The action will fail if the deploy failes.
- Add argument `progress`. This will show progress of the deployment in Octopus Deploy. In other words a more verbose logs from Octopus Deploy

### Changed

- Refactored the argument parser

## [0.2.6] - 2021-06-30

### Added

- Initial release. Velo-action allows Github Action Workflows to generate a semantic versioning using [GitVersion](https://gitversion.net/), create an imutable relese using Velo and trigger a deploy of that relese in Octopus Deploy.
