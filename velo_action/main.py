import os
import sys
from pathlib import Path
import yaml

from loguru import logger

from velo_action import gcp, github, tracing_helpers
from velo_action.octopus.client import OctopusClient
from velo_action.octopus.deployment import Deployment
from velo_action.octopus.release import Release
from velo_action.settings import Settings
from velo_action.version import generate_version

BASE_DIR = Path(__file__).resolve().parent.parent

VELO_DEPLOY_FOLDER_NAME = ".deploy"
VELO_PROJECT_NAME = "nube-velo-prod"


def action(input_args: Settings):  # pylint: disable=too-many-branches
    # TODO: These kind of logic verifiers (if this then that) should be separated into its own function to make it easily testable
    if input_args.deploy_to_environments:
        input_args.create_release = True

    log_format = "{time:YYYY-MM-DD HH:mm:ss} {message}"
    logger.add(sys.stdout, level=input_args.log_level, format=log_format)

    try:
        trace_id = tracing_helpers.start_trace(input_args.service_account_key)  # type: ignore
    except Exception as err:  # pylint: disable=broad-except
        trace_id = None
        logger.exception("Starting trace failed", exc_info=err)

    logger.info("Starting velo-action")
    os.chdir(input_args.workspace)

    if input_args.service_account_key:
        logger.info(f"Service account: {input_args.service_account_key[:15]}")

    logger.info(f"Deploy to environments: {input_args.deploy_to_environments}")

    if input_args.tenants:
        logger.info(f"Tenants: {input_args.tenants}")

    logger.info(f"Create release: {input_args.create_release}")

    if input_args.version is None:
        version = generate_version()
    else:
        version = input_args.version

    logger.info(f"Version: {version}")
    github.actions_output("version", version)

    if not input_args.create_release and not input_args.deploy_to_environments:
        logger.warning("Nothing to do. Exciting now.")
        return

    deploy_folder = Path.joinpath(Path(input_args.workspace), VELO_DEPLOY_FOLDER_NAME)

    if not deploy_folder.is_dir():
        raise Exception(
            f"Did not find a '{VELO_DEPLOY_FOLDER_NAME}' folder in '{input_args.workspace}'."
        )

    if not input_args.octopus_server_secret:
        raise ValueError("Octopus server secret not specified")
    if not input_args.octopus_api_key_secret:
        raise ValueError("Octopus api key secret not specified")
    if not input_args.velo_artifact_bucket_secret:
        raise ValueError("Artifact bucket secret not specified")
    if not input_args.service_account_key:
        logger.warning("GCP service account key not specified")

    gcloud = gcp.GCP(input_args.service_account_key)
    octopus_server = gcloud.lookup_data(
        input_args.octopus_server_secret, VELO_PROJECT_NAME
    )
    octopus_api_key = gcloud.lookup_data(
        input_args.octopus_api_key_secret, VELO_PROJECT_NAME
    )
    velo_artifact_bucket = gcloud.lookup_data(
        input_args.velo_artifact_bucket_secret, VELO_PROJECT_NAME
    )

    octo = OctopusClient(server=octopus_server, api_key=octopus_api_key)

    if input_args.create_release:
        ## Read the app.yml/app.yaml file form the deploy folder and parse the velo version
        ## To figure out what velo version we are deploying
        velo_config_path = None
        app_yml_path = Path.joinpath(deploy_folder, "app.yml")
        app_yaml_path = Path.joinpath(deploy_folder, "app.yaml")
        if app_yml_path.is_file():
            velo_config_path = app_yml_path
        elif app_yaml_path.is_file():
            velo_config_path = app_yaml_path
        else:
            raise Exception(
                f"Did not find an app.yml or app.yaml file in '{deploy_folder}'"
            )
        
        velo_version = None
        velo_project = None
        with open(velo_config_path, "r") as f:
            app_yml = f.read()
            velo_config = yaml.safe_load(app_yml)
            velo_version = velo_config.get('version', None)
            velo_project = velo_config.get('project', None)

        logger.info(
            f"Uploading artifacts to '{velo_artifact_bucket}/{velo_project}/{version}'"
        )

        gcloud.upload_from_directory(
            deploy_folder, velo_artifact_bucket, f"{velo_project}/{version}"
        )

        commit_id = os.getenv("GITHUB_SHA")
        branch_name = os.getenv("GITHUB_REF")
        assert (
            commit_id is not None
        ), "The environment variable GITHUB_SHA must be present."
        assert (
            len(commit_id) == 40
        ), "The environment variable GITHUB_SHA must contain the full git commit hash with 40 characters."
        assert (
            branch_name is not None
        ), "The environment variable GITHUB_REF must be present, and contain the git branch name."

        release_note_dict = {
            "commit_id": commit_id,
            "branch_name": branch_name,
            "commit_url": f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}/commit/{commit_id}",
        }
        logger.info(
            f"Creating a release for project '{velo_project}' with version '{version}'"
        )

        release = Release(client=octo)
        release.create(
            project_name=velo_project, version=version, notes=release_note_dict, velo_version=velo_version
        )

    if input_args.deploy_to_environments:
        deploy_vars = {}
        if trace_id:
            deploy_vars["GithubSpanID"] = trace_id

        tenants = input_args.tenants or [None]  # type: ignore

        for env in input_args.deploy_to_environments:
            for ten in tenants:
                log = f"Deploying project '{velo_project}' version '{version}' to '{env}' "
                if ten:
                    log += f"for tenant '{ten}'"
                logger.info(log)

                deploy = Deployment(
                    project_name=velo_project,
                    version=version,
                    client=octo,
                )

                deploy.create(
                    env_name=env,
                    tenant=ten,
                    wait_seconds=input_args.wait_for_success_seconds,
                    variables=deploy_vars,
                )
    logger.info("Done")


if __name__ == "__main__":
    try:
        s = Settings()
    except pydantic.ValidationError as err:
        logger.error(err)
        sys.exit(1)
    action(s)