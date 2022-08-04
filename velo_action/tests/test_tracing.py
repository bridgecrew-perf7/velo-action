import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource  # type: ignore
from opentelemetry.sdk.trace import TracerProvider  # type: ignore
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter  # type: ignore

from velo_action.settings import GithubSettings
from velo_action.tracing_helpers import construct_github_action_trace


def gh_token():
    if token := os.environ.get("GITHUB_TOKEN"):
        return token
    try:
        result = subprocess.run(
            ["gh", "auth", "status", "-t"], capture_output=True, text=True, check=True
        )
        return re.search(r"Token: (.*)\n", result.stderr).group(1)
    except Exception:  # pylint: disable=broad-except
        return None


has_token = pytest.mark.skipif(not bool(gh_token()), reason="No Github token found")


class SpanList:
    def __init__(self):
        self.found_string_spans = []

    def write(self, span):
        span = json.loads(span)

        del span["resource"]["build.repository"]
        del span["resource"]["build.actor"]
        del span["context"]["trace_id"]
        del span["context"]["span_id"]
        del span["parent_id"]

        # Disregard dynamic start and end times
        utc_local_diff = datetime.now() - datetime.utcnow() + timedelta(seconds=1)
        if (
            datetime.now() - datetime.fromisoformat(span["end_time"][:-1])
            < utc_local_diff
        ):
            del span["end_time"]
        if (
            datetime.now() - datetime.fromisoformat(span["start_time"][:-1])
            < utc_local_diff
        ):
            del span["start_time"]

        self.found_string_spans.append(json.dumps(span))

    @staticmethod
    def flush():
        print("flushed the toilet")


def create_tracer_and_gh_settings(repo, actor, sha, run_id):
    tracing_attributes = {
        "build.repository": repo,
        "build.actor": actor,
    }
    resource = Resource(attributes={SERVICE_NAME: "velo-action", **tracing_attributes})
    trace.set_tracer_provider(TracerProvider(resource=resource))

    span_list = SpanList()
    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(ConsoleSpanExporter(out=span_list))
    )

    tracer = trace.get_tracer(__name__)

    gh_settings = GithubSettings(
        workspace="velo-action",
        sha=sha,
        ref_name="main",
        server_url="https://github.com",
        repository=repo,
        actor=actor,
        api_url="https://api.github.com",
        run_id=run_id,
        workflow="ci",
    )
    return tracer, gh_settings, span_list


def verify_results(tracer, span_list, results_file):
    """
    Compare the dynamically created spans with the expected results from a results_file.

    The main difficulty is that some properties are dynamic and cannot be compared. The trick is to simply delete these
    in both the stored results and in the spans created by the test before doing the comparison.
    """
    assert tracer.span_processor.force_flush()

    with (Path(__file__).parent / results_file).open("r") as file:
        required_spans = json.load(file)

    # If no start or end time exists while the spans are created they default to 'now'.
    # The solution is to delete all dynmically created 'now' timestamps from the spans.
    # The end time of the "build and deploy" span is always dynamic so we can delete all timestamps similar to that one.
    dynamic_end_time = [s for s in required_spans if s["name"] == "build and deploy"]
    dynamic_end_time = datetime.fromisoformat(dynamic_end_time[0]["end_time"][:-1])
    for span in required_spans:
        # Delete all dynamic attributes
        del span["resource"]["build.repository"]
        del span["resource"]["build.actor"]
        del span["context"]["trace_id"]
        del span["context"]["span_id"]
        del span["parent_id"]

        # Delete timestamps if they are dynamic
        end = datetime.fromisoformat(span["end_time"][:-1])
        if dynamic_end_time - end < timedelta(seconds=1):
            del span["end_time"]
        start = datetime.fromisoformat(span["start_time"][:-1])
        if dynamic_end_time - start < timedelta(seconds=1):
            del span["start_time"]

        # See if the span indeed exists
        try:
            span_list.found_string_spans.remove(json.dumps(span))
        except ValueError:
            pytest.fail(f"Span {span} not found")

    # All spans should have been found so this list should be empty now
    assert not span_list.found_string_spans


@has_token
def test_trace_creation_from_gh_response():
    """
    This test checks that the trace generation code outputs good traces. It is basically end to end testing hitting the
    GH API retrieving data on a workflow and then using the opentelemtry library to manually fill in traces.

    The hardcoded data has been generated by running using `make run` and copying it into a file. The only thing
    required to get it to work is to set an INPUT_TOKEN in env.dev-vars.

    You can find yours by running `gh auth status -t` if you have the GH cli installed.
    """
    tracer, gh_settings, span_list = create_tracer_and_gh_settings(
        "kolonialno/velo-action",
        "andersliland",
        "cbb6bfc4abc38abb8f50c60a567daac359c641cf",
        "2486719199",  # I think only this one matters?
    )

    construct_github_action_trace(
        tracer,
        gh_token(),
        "",
        github_settings=gh_settings,
    )
    verify_results(tracer, span_list, "action_trace_output_live_gh_api.json")


class MockResponse:
    def __init__(self):
        with (Path(__file__).parent / "gh_api_stored_response.json").open("r") as file:
            self.response = json.load(file)

    def json(self):
        return self.response

    def raise_for_status(self):
        pass


@patch("velo_action.github.requests.get", return_value=MockResponse())
def test_trace_creation_from_hardcoded_response(mocked_decode: MagicMock):
    """
    This test is very similar to the one in test_tracing_gh_api.py. The only difference is that this test uses a
    hardcoded gh api response from a workflow that is running instead of done.
    """
    tracer, gh_settings, span_list = create_tracer_and_gh_settings(
        "kolonialno/alma",
        "frenor",
        "a88bf7ccb2505624925a9e74175d2c01ec681591",
        "2795217427",
    )

    construct_github_action_trace(
        tracer,
        "notoken",  # This works because the request is mocked by 'patch'
        "",
        github_settings=gh_settings,
    )

    verify_results(tracer, span_list, "action_trace_output_hardcoded_gh_api.json")
    mocked_decode.assert_called_once()
