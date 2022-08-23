import os
import time
import json
import jwt
from pathlib import Path
from pathlib import Path
from typing import List, Optional

from semantic_version import SimpleSpec, Version

from velo_action.settings import (
    APP_SPEC_FIELD_PROJECT,
    APP_SPEC_FILENAMES,
    VeloSettings,
)


def resolve_app_spec_filename(deploy_folder: Path) -> Path:
    for filename in APP_SPEC_FILENAMES:
        filepath = Path.joinpath(deploy_folder, filename)
        if filepath.is_file():
            return filepath
    raise FileNotFoundError(
        f"Did not find an app.yml or app.yaml file in '{deploy_folder}'"
    )


def read_file(file: Path):
    if not os.path.exists(file):
        raise FileNotFoundError(f"{file} does not exist")

    with open(file, "r", encoding="utf-8") as stream:
        return stream.read()


def read_velo_settings(deploy_folder: Path) -> VeloSettings:
    """Parse the AppSpec (app.yml)"""
    filepath = resolve_app_spec_filename(deploy_folder)

    try:
        project = read_field_from_app_spec(APP_SPEC_FIELD_PROJECT, filepath)
    except ValueError as error:
        raise SystemExit(
            "'project' field is required in the AppSpec (app.yml). "
            "See https://centro.prod.nube.tech/docs/default/component/velo/app-spec/ for instructions."
        ) from error

    return VeloSettings(project=project)


def read_field_from_app_spec(field: str, filename: Path) -> str:
    """Read the project field from the app.yml.

    Cannot assume the app.yml is rendered,
    hence we cannot read the files as YAML.
    """
    with open(filename, encoding="utf-8") as file:
        lines = file.readlines()
        for line in lines:
            if line.startswith(f"{field}:"):
                return line.split(":")[1].strip().strip('"').strip("'")
    raise ValueError(f"Could not find '{field}' in {filename}")


def find_matching_version(
    versions: List[str], version_to_match: SimpleSpec
) -> Optional[Version]:
    """
    Finds the highest matching version in a list of versions.
    using the python semantic_version package.
    """
    versions = [Version.coerce(v) for v in versions]
    matching_version = version_to_match.select(versions)
    return matching_version


def create_self_signed_jwt(jwt_content, url):

    gsa = json.loads(jwt_content)

    iat = time.time()
    exp = iat + 3600
    payload = {
        "email": gsa["client_email"],
        "iss": gsa["client_email"],
        "sub": gsa["client_email"],
        "aud": url,
        "iat": iat,
        "exp": exp,
    }
    additional_headers = {"kid": gsa["private_key_id"]}

    signed_jwt = jwt.encode(
        payload,
        gsa["private_key"],
        headers=additional_headers,
        algorithm="RS256",
    )

    return signed_jwt


def is_valid_gsa_json(gsa_token_json):
    try:
        json.loads(gsa_token_json)
    except ValueError as e:
        return False
    return True
