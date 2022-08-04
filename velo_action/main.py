import os
import sys
from pathlib import Path

import pydantic
from loguru import logger

from velo_action import gcp, github
from velo_action.octopus.client import OctopusClient
from velo_action.octopus.deployment import Deployment
from velo_action.octopus.release import Release
from velo_action.settings import (
    VELO_TRACE_ID_NAME,
    ActionInputs,
    ActionOutputs,
    GithubSettings,
    resolve_workspace,
)
from velo_action.tracing_helpers import (
    construct_github_action_trace,
    init_tracer,
    print_trace_link,
    stringify_span,
)
from velo_action.utils import read_velo_settings

BASE_DIR = Path(__file__).resolve().parent.parent

VELO_DEPLOY_FOLDER_NAME = ".deploy"
LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} {message}"


def action(  # pylint: disable=too-many-branches,too-many-locals,too-many-statements
    args: ActionInputs,
    github_settings: GithubSettings,
) -> ActionOutputs:
    """Velo-action has two seperate usages: to create and deplot a release, or just generate verison.

    When just generating version it will be run without any inputs.
    Meaning no 'service_account_key'.
    This should not produce an error when initialising the tracing.
    """
    init_trace = False

    local_debug_mode = pydantic.parse_obj_as(
        bool, os.getenv("LOCAL_DEBUG_MODE", "False")
    )
    if args.service_account_key or local_debug_mode:
        # Do not init tracer when action is running without a
        # service_account_key.
        # This is supported behavior when only generating the verison.
        try:
            tracer = init_tracer(args, github_settings)
            span = construct_github_action_trace(
                tracer,
                args.token,
                args.preceding_run_ids,
                github_settings=github_settings,
            )
            trace_id = stringify_span(span)
            init_trace = True
        except Exception as error:  # pylint: disable=broad-except
            trace_id = None
            logger.warning(f"Starting trace failed: {error}", exc_info=error)

    if args.create_release or args.deploy_to_environments:
        deploy_folder = Path.joinpath(Path(args.workspace), VELO_DEPLOY_FOLDER_NAME)  # type: ignore
        if not deploy_folder.is_dir():
            sys.exit(
                f"Did not find a '{VELO_DEPLOY_FOLDER_NAME}' folder in '{args.workspace}'."
            )

        os.chdir(args.workspace)  # type: ignore

        gcloud = gcp.GCP(
            project=args.velo_project, service_account_key=args.service_account_key
        )
        octopus_server = gcloud.lookup_data(
            args.octopus_server_secret, args.velo_project
        )
        octopus_api_key = gcloud.lookup_data(
            args.octopus_api_key_secret, args.velo_project
        )
        velo_artifact_bucket = gcloud.lookup_data(
            args.velo_artifact_bucket_secret, args.velo_project
        )
        octo = OctopusClient(server=octopus_server, api_key=octopus_api_key)

    if args.create_release:
        release = Release(client=octo)

        velo_settings = read_velo_settings(deploy_folder)

        release_exists = release.exists(
            project_name=velo_settings.project, version=args.version, client=octo
        )

        if release_exists:
            logger.info(
                f"Release '{args.version}' already exists at "
                f"'{release.client.baseurl}/app#/Spaces-1/projects/"
                f"{velo_settings.project}/deployments/releases/{args.version}'. "
                "If you want to recreate this release, please delete it first in Octopus Deploy."
                "Project -> Releases -> <Select Release> -> : menu in top right corner -> Delete. "
            )
        else:
            files = gcloud.upload_from_directory(
                path=deploy_folder,
                dest_bucket_name=velo_artifact_bucket,
                dest_blob_name=f"{velo_settings.project}/{args.version}",
            )

            logger.info(
                f"Uploaded {len(files)} release files to "
                "'https://console.cloud.google.com/storage/browser/"
                f"{velo_artifact_bucket}/{velo_settings.project}/{args.version}'"
            )

            logger.info(
                f"Creating a release in Octopus Deploy for project '{velo_settings.project}' with version '{args.version}'"
            )
            release.create(
                project_name=velo_settings.project,
                project_version=args.version,
                github_settings=github_settings,
            )
            logger.info(
                f"See {release.client.baseurl}/app#/Spaces-1/projects/{velo_settings.project}/deployments/releases/{args.version}"
            )

    if args.deploy_to_environments:
        logger.info(f"Deploy to environments: {args.deploy_to_environments}")
        deploy_vars = {}
        if trace_id:
            deploy_vars[VELO_TRACE_ID_NAME] = trace_id

        tenants = args.tenants or [None]  # type: ignore

        for env in args.deploy_to_environments:
            for ten in tenants:
                log = f"Deploying project '{velo_settings.project}' version '{args.version}' to '{env}' "
                if ten:
                    log += f"for tenant '{ten}'"
                logger.info(log)

                deploy = Deployment(
                    project_name=velo_settings.project,
                    version=args.version,
                    client=octo,
                )

                deploy.create(
                    env_name=env,
                    tenant=ten,
                    wait_seconds=args.wait_for_success_seconds,
                    variables=deploy_vars,
                )

    if init_trace and (args.deploy_to_environments or args.create_release):
        print_trace_link(span)

    output = ActionOutputs(version=args.version)
    # Set outputs in environment to be used by other
    # steps in the Github Action Workflows
    logger.info("Github actions outputs:")
    github.actions_output("version", args.version)

    return output


if __name__ == "__main__":
    try:
        gh = GithubSettings()
        s = ActionInputs()

        s.workspace = resolve_workspace(s, gh)

    except pydantic.ValidationError as err:
        # Logger is not instantiated yet
        print(err)
        sys.exit(1)

    logger.add(sys.stdout, level=s.log_level, format=LOG_FORMAT)
    action(s, gh)
