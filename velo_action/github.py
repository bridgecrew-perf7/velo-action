import os

import requests
from loguru import logger

from velo_action.settings import GithubSettings


def actions_output(key, value):
    """Output variables such that they can be used in GitHub Actions."""
    os.system(f'echo "::set-output name={key}::{value}"')
    logger.info(f"{key}: {value}")


def request_github_workflow_data(
    token: str, preceding_run_ids: str, github_settings: GithubSettings
):
    github_headers = {"authorization": f"Bearer {token}"}

    base_url = (
        f"{github_settings.api_url}/repos/{github_settings.repository}/actions/runs"
    )
    current_workflow_url = f"{base_url}/{github_settings.run_id}/jobs"

    req = requests.get(current_workflow_url, headers=github_headers)
    req.raise_for_status()
    total_action_dict = {github_settings.workflow: req.json()}

    if preceding_run_ids:
        for preceding_run_id in preceding_run_ids.split(","):
            workflow_run_url = f"{base_url}/{preceding_run_id}"

            req = requests.get(workflow_run_url, headers=github_headers)
            req.raise_for_status()
            preceding_wf_name = req.json()["name"]

            req = requests.get(f"{workflow_run_url}/jobs", headers=github_headers)
            req.raise_for_status()
            total_action_dict[preceding_wf_name] = req.json()

    for wf_jobs in total_action_dict.values():
        for job in wf_jobs["jobs"]:
            for step in job["steps"]:
                try:
                    if step["started_at"] > step["completed_at"]:
                        step["completed_at"] = step["started_at"]
                except TypeError:
                    logger.debug(f"{step['name']} has no completed_at")
    return total_action_dict


def request_commit_info(
    token: str, commit_sha: str, github_settings: GithubSettings
) -> dict:
    if not token:
        return {"commit": {"message": "Unknown"}}

    github_headers = {"authorization": f"Bearer {token}"}
    req = requests.get(
        f"{github_settings.api_url}/repos/{github_settings.repository}/commits/{commit_sha}",
        headers=github_headers,
    )
    req.raise_for_status()
    return req.json()
